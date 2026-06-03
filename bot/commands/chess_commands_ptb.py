"""Chess Module commands for python-telegram-bot."""

from __future__ import annotations

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot.chess.lichess_api import LichessApiError, LichessUser, fetch_lichess_user
from database.database import ChessAccount, SessionLocal

logger = logging.getLogger(__name__)


def _format_link_success(user: LichessUser) -> str:
    """Return a user-facing success message for linked Lichess account."""

    title_prefix = f"{user.title} " if user.title else ""
    online_text = "онлайн" if user.online else "оффлайн/неизвестно"
    return (
        "♟ **Lichess аккаунт привязан!**\n\n"
        f"Аккаунт: **{title_prefix}{user.username}**\n"
        f"Статус: {online_text}\n\n"
        "Теперь можно будет использовать шахматные команды BankBot."
    )


async def chess_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle `/chess link <username>` and link Telegram user to Lichess."""

    if not update.message or not update.effective_user:
        return

    if len(context.args) < 2 or context.args[0].lower() != "link":
        await update.message.reply_text(
            "♟ Использование: `/chess link <ник>`\n\n"
            "Пример: `/chess link DrNykterstein`",
            parse_mode="Markdown",
        )
        return

    lichess_username = context.args[1].strip()
    if not lichess_username:
        await update.message.reply_text("❌ Укажите ник Lichess: `/chess link <ник>`", parse_mode="Markdown")
        return

    status_message = await update.message.reply_text(
        f"🔍 Проверяю Lichess аккаунт **{lichess_username}**...",
        parse_mode="Markdown",
    )

    try:
        lichess_user = await fetch_lichess_user(lichess_username)
    except LichessApiError:
        logger.exception("Lichess lookup failed for /chess link")
        await status_message.edit_text(
            "❌ Сейчас не удалось проверить Lichess аккаунт. Попробуйте позже."
        )
        return

    if lichess_user is None:
        await status_message.edit_text(
            f"❌ Lichess аккаунт **{lichess_username}** не найден. Проверьте ник.",
            parse_mode="Markdown",
        )
        return

    telegram_id = update.effective_user.id
    try:
        with SessionLocal() as session:
            existing_by_username = (
                session.query(ChessAccount)
                .filter(ChessAccount.lichess_username == lichess_user.username)
                .first()
            )
            if existing_by_username and existing_by_username.user_id != telegram_id:
                await status_message.edit_text(
                    "❌ Этот Lichess аккаунт уже привязан к другому пользователю."
                )
                return

            account = session.query(ChessAccount).filter(ChessAccount.user_id == telegram_id).first()
            if account is None:
                account = ChessAccount(user_id=telegram_id, lichess_username=lichess_user.username)
                session.add(account)
            else:
                account.lichess_username = lichess_user.username
                account.linked_at = datetime.utcnow()
            session.commit()
    except Exception:
        logger.exception("Failed to save chess account link")
        await status_message.edit_text("❌ Ошибка сохранения привязки. Попробуйте позже.")
        return

    await status_message.edit_text(_format_link_success(lichess_user), parse_mode="Markdown")


def get_chess_handlers() -> list[CommandHandler]:
    """Return PTB handlers for Chess Module commands."""

    return [CommandHandler("chess", chess_link_command)]
