"""Telegram commands for the free local AI-lite assistant."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot.ai import AiLiteService


ai_lite_service = AiLiteService()


def _question_from_args(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Extract AI question from command arguments."""
    return " ".join(context.args).strip()


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Answer a question with the local free AI-lite assistant."""
    if not update.message:
        return

    question = _question_from_args(context)
    await update.message.reply_text(ai_lite_service.answer(question), parse_mode="HTML")


async def ai_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show AI-lite help."""
    if not update.message:
        return

    await update.message.reply_text(ai_lite_service.help_text(), parse_mode="HTML")
