"""Telegram commands for the free local AI-lite assistant."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import ContextTypes

from bot.ai import AiLiteService
from bot.commands.core_commands import get_default_user_mode


logger = logging.getLogger(__name__)
ai_lite_service = AiLiteService()

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
) -> None:
    """Send AI replies with HF-friendly retries and explicit Telegram timeouts."""
    if not update.message:
        return

    for attempt in range(1, max_retries + 1):
        try:
            await update.message.reply_text(
                text,
                parse_mode=parse_mode,
                **AI_REPLY_TIMEOUTS,
            )
            return
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
                return
            await asyncio.sleep(2)


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Answer a question with the local free AI-lite assistant."""
    if not update.message:
        return

    question = _question_from_args(context)
    if not question:
        await _reply_text_with_retry(update, ai_lite_service.help_text(), parse_mode="HTML")
        return

    mode = get_default_user_mode(update.effective_user.id if update.effective_user else None)
    await _reply_text_with_retry(update, ai_lite_service.answer(question, mode=mode))


async def ai_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show AI-lite help."""
    if not update.message:
        return

    await _reply_text_with_retry(update, ai_lite_service.help_text(), parse_mode="HTML")
