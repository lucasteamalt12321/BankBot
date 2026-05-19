"""Telegram commands for the free local AI-lite assistant."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from telegram import Message, Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import ContextTypes

from bot.ai import AiLiteService
from bot.ai.knowledge_updater import update_ai_knowledge_cache
from bot.response_modes import get_default_user_mode
from bot.commands.feedback_commands import _append_feedback, _append_feedback_db


logger = logging.getLogger(__name__)
ai_lite_service = AiLiteService()
AI_RESPONSE_PREFIX = "🤖"
AI_FEEDBACK_POSITIVE = "+"
AI_FEEDBACK_NEGATIVE = "-"
MAX_TRACKED_AI_RESPONSES = 200

_ai_response_registry: dict[tuple[int, int], dict[str, Any]] = {}
_pending_ai_improvements: dict[tuple[int, int], dict[str, Any]] = {}

AI_REPLY_TIMEOUTS = {
    "connect_timeout": 30,
    "read_timeout": 60,
    "write_timeout": 60,
    "pool_timeout": 30,
}


def _question_from_args(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Extract AI question from command arguments."""
    return " ".join(context.args).strip()


async def _reply_text_with_retry(
    update: Update,
    text: str,
    *,
    parse_mode: str | None = None,
    max_retries: int = 2,
) -> Message | None:
    """Send AI replies with HF-friendly retries and explicit Telegram timeouts."""
    if not update.message:
        return None

    for attempt in range(1, max_retries + 1):
        try:
            return await update.message.reply_text(
                text,
                parse_mode=parse_mode,
                **AI_REPLY_TIMEOUTS,
            )
        except (TimedOut, NetworkError) as exc:
            logger.warning(
                "AI reply failed due to transient Telegram network error",
                extra={
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "error_type": type(exc).__name__,
                    "error_msg": str(exc),
                },
            )
            if attempt >= max_retries:
                return None
            await asyncio.sleep(2)

    return None


def _register_ai_response(
    *,
    chat_id: int,
    message_id: int,
    question: str,
    answer: str,
    mode: str,
) -> None:
    """Track AI responses so users can rate them by replying + or -."""
    _ai_response_registry[(chat_id, message_id)] = {
        "question": question,
        "answer": answer,
        "mode": mode,
    }
    while len(_ai_response_registry) > MAX_TRACKED_AI_RESPONSES:
        oldest_key = next(iter(_ai_response_registry))
        _ai_response_registry.pop(oldest_key, None)


def _get_ai_response_context(reply_to_message: Message | None) -> dict[str, Any] | None:
    """Return stored or heuristic context for a replied-to AI message."""
    if not reply_to_message or not reply_to_message.chat:
        return None

    stored = _ai_response_registry.get((reply_to_message.chat.id, reply_to_message.message_id))
    if stored:
        return stored

    # Fallback after container restart: old AI replies are not in memory, but the
    # user may still reply to a visible bot message. Recognize our AI-like text.
    text = reply_to_message.text or ""
    if text.startswith(AI_RESPONSE_PREFIX) and (
        "AI" in text or "канон" in text or "BankBot" in text or "Справочник" in text
    ):
        return {"question": "unknown_after_restart", "answer": text, "mode": "unknown"}

    return None


def _build_ai_feedback_entry(
    update: Update,
    feedback_type: str,
    text: str,
    context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a feedback entry compatible with feedback storage."""
    user = update.effective_user
    chat = update.effective_chat
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "type": feedback_type,
        "text": text,
        "telegram_id": user.id if user else None,
        "username": user.username if user else None,
        "first_name": user.first_name if user else None,
        "chat_id": chat.id if chat else None,
        "chat_type": chat.type if chat else None,
        "ai_question": context.get("question") if context else None,
        "ai_answer": context.get("answer") if context else None,
        "ai_mode": context.get("mode") if context else None,
    }


def _save_ai_feedback(entry: dict[str, Any]) -> None:
    """Persist AI feedback to DB when possible and always mirror to JSONL."""
    try:
        _append_feedback_db(entry)
    except Exception as exc:
        logger.warning("Failed to save AI feedback to DB", extra={"error": str(exc)})
    _append_feedback(entry)


async def handle_ai_feedback_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle + / - replies to AI answers and collect improvement text after -."""
    if not update.message or not update.effective_user or not update.effective_chat:
        return False

    message_text = (update.message.text or "").strip()
    pending_key = (update.effective_chat.id, update.effective_user.id)
    pending_context = _pending_ai_improvements.get(pending_key)
    if pending_context and message_text and not message_text.startswith("/"):
        _pending_ai_improvements.pop(pending_key, None)
        entry = _build_ai_feedback_entry(
            update,
            "ai_feedback_improvement",
            message_text,
            pending_context,
        )
        _save_ai_feedback(entry)
        await _reply_text_with_retry(update, "✅ Спасибо! Улучшение ответа ИИ сохранено.")
        return True

    if message_text not in {AI_FEEDBACK_POSITIVE, AI_FEEDBACK_NEGATIVE}:
        return False

    ai_context = _get_ai_response_context(update.message.reply_to_message)
    if not ai_context:
        return False

    if message_text == AI_FEEDBACK_POSITIVE:
        entry = _build_ai_feedback_entry(update, "ai_feedback_positive", "+", ai_context)
        _save_ai_feedback(entry)
        await _reply_text_with_retry(update, "✅ Спасибо за оценку ответа ИИ!")
        return True

    entry = _build_ai_feedback_entry(update, "ai_feedback_negative", "-", ai_context)
    _save_ai_feedback(entry)
    _pending_ai_improvements[pending_key] = ai_context
    await _reply_text_with_retry(
        update,
        "Что улучшить в ответе ИИ? Напишите следующим сообщением — я сохраню это для доработки.",
    )
    return True


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Answer a question with the local free AI-lite assistant."""
    if not update.message:
        return

    question = _question_from_args(context)
    if not question:
        await _reply_text_with_retry(update, ai_lite_service.help_text(), parse_mode="HTML")
        return

    mode = get_default_user_mode(update.effective_user.id if update.effective_user else None)
    answer = ai_lite_service.answer(question, mode=mode)
    sent_message = await _reply_text_with_retry(update, answer)
    if sent_message and update.effective_chat:
        _register_ai_response(
            chat_id=update.effective_chat.id,
            message_id=sent_message.message_id,
            question=question,
            answer=answer,
            mode=mode,
        )


async def ai_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show AI-lite help."""
    if not update.message:
        return

    await _reply_text_with_retry(update, ai_lite_service.help_text(), parse_mode="HTML")


async def ai_update_knowledge_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
) -> None:
    """Admin command: refresh AI-lite knowledge from public canon sources."""

    if not update.message or not update.effective_user:
        return

    if not admin_system.is_admin(update.effective_user.id):
        await _reply_text_with_retry(update, "🔒 Эта команда доступна только администратору.")
        return

    await _reply_text_with_retry(
        update,
        "⏳ Обновляю данные ИИ из канала, Google Doc канона и источников уровня Высокий/Средний...",
    )
    result = await update_ai_knowledge_cache()
    loaded_count = ai_lite_service.reload_dynamic_knowledge()

    failed_part = ""
    if result.failed_urls:
        failed_part = "\n⚠️ Не удалось загрузить: " + str(len(result.failed_urls))

    await _reply_text_with_retry(
        update,
        "✅ База знаний ИИ обновлена.\n"
        f"• Новых runtime-записей: {result.entries_count}\n"
        f"• Загружено в AI-lite: {loaded_count}\n"
        f"• Успешных источников: {len(result.fetched_urls)}\n"
        f"• Кэш: {result.cache_path}"
        f"{failed_part}\n\n"
        "Теперь /ai будет учитывать свежий кэш вместе с встроенным каноном.",
    )
