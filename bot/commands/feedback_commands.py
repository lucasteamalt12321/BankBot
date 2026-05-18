"""User feedback commands for suggestions and complaints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import structlog
from telegram import Update
from telegram.ext import ContextTypes


FEEDBACK_FILE = Path("data/feedback.jsonl")
MAX_FEEDBACK_PREVIEW_LENGTH = 800
logger = structlog.get_logger()


FEEDBACK_HELP_TEXT = """💬 <b>Предложения и жалобы</b>

/feedback &lt;текст&gt; — отправить предложение или жалобу
/suggest &lt;текст&gt; — алиас для предложения
/complaint &lt;текст&gt; — алиас для жалобы

Для администратора:
/feedback_list [количество] — показать последние обращения

Пример:
/feedback Добавьте команду для просмотра топа игроков"""


def _feedback_text_from_args(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Return feedback text from command arguments."""
    return " ".join(context.args).strip()


def _is_admin(user_id: int | None, admin_telegram_id: int) -> bool:
    """Check whether the current user may read feedback entries."""
    return bool(user_id and user_id == admin_telegram_id)


def _append_feedback(entry: dict) -> None:
    """Append a feedback entry to JSONL storage."""
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with FEEDBACK_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_feedback_entries(limit: int) -> list[dict]:
    """Read last feedback entries from JSONL storage."""
    if not FEEDBACK_FILE.exists():
        return []

    entries = []
    with FEEDBACK_FILE.open("r", encoding="utf-8") as file:
        lines = file.readlines()[-limit:]

    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save user suggestion or complaint for later review."""
    if not update.message or not update.effective_user or not update.effective_chat:
        return

    feedback_text = _feedback_text_from_args(context)
    if not feedback_text:
        await update.message.reply_text(FEEDBACK_HELP_TEXT, parse_mode="HTML")
        return

    user = update.effective_user
    chat = update.effective_chat
    entry = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "type": "feedback",
        "text": feedback_text,
        "telegram_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "chat_id": chat.id,
        "chat_type": chat.type,
    }
    _append_feedback(entry)
    logger.info(
        "Feedback saved",
        feedback_text=feedback_text,
        telegram_id=user.id,
        username=user.username,
        chat_id=chat.id,
        chat_type=chat.type,
        storage_path=str(FEEDBACK_FILE),
    )

    await update.message.reply_text(
        "✅ Спасибо! Предложение/жалоба сохранены и будут прочитаны разработчиком."
    )


async def feedback_list_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_telegram_id: int,
) -> None:
    """Show recent feedback entries to the bot admin."""
    if not update.message or not update.effective_user:
        return

    if not _is_admin(update.effective_user.id, admin_telegram_id):
        await update.message.reply_text("❌ Эта команда доступна только администратору.")
        return

    limit = 5
    if context.args and context.args[0].isdigit():
        limit = max(1, min(int(context.args[0]), 20))

    entries = _read_feedback_entries(limit)
    if not entries:
        await update.message.reply_text("📭 Предложений и жалоб пока нет.")
        return

    lines = [f"📬 Последние обращения ({len(entries)}):"]
    for entry in entries:
        username = entry.get("username") or entry.get("first_name") or "без username"
        text = entry.get("text", "")
        if len(text) > MAX_FEEDBACK_PREVIEW_LENGTH:
            text = text[:MAX_FEEDBACK_PREVIEW_LENGTH] + "…"
        lines.append(
            "\n"
            f"• {entry.get('created_at', 'unknown time')}\n"
            f"  От: @{username} / ID {entry.get('telegram_id')}\n"
            f"  Чат: {entry.get('chat_id')} ({entry.get('chat_type')})\n"
            f"  Текст: {text}"
        )

    await update.message.reply_text("\n".join(lines))
