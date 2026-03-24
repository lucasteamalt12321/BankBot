"""
Централизованный обработчик ошибок для python-telegram-bot 20.x.

Регистрируется через Application.add_error_handler().
Логирует ошибки, уведомляет пользователя и администратора.
"""

import traceback
import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.config import settings

logger = structlog.get_logger()


class ErrorHandlerMiddleware:
    """
    Обработчик ошибок для PTB Application.

    Использование:
        setup_error_handler(application)
    """

    async def __call__(
        self,
        update: object,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """
        Обрабатывает необработанные исключения из handlers.

        Args:
            update: Telegram Update (может быть None)
            context: Контекст с информацией об ошибке
        """
        error = context.error
        logger.exception("Unhandled exception in handler", exc_info=error)

        # Уведомляем пользователя
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ Произошла ошибка при обработке запроса.\n"
                    "Мы уже уведомлены и работаем над исправлением.\n"
                    "Пожалуйста, попробуйте позже."
                )
            except Exception:
                pass

        # Уведомляем администратора
        if settings.ADMIN_TELEGRAM_ID:
            await self._notify_admin(update, context, error)

    async def _notify_admin(
        self,
        update: object,
        context: ContextTypes.DEFAULT_TYPE,
        error: Exception,
    ) -> None:
        """Отправляет администратору сообщение об ошибке."""
        error_type = type(error).__name__
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        if len(tb) > 3500:
            tb = tb[:3500] + "\n... (обрезано)"

        user_info = "неизвестен"
        message_text = "—"
        if isinstance(update, Update):
            if update.effective_user:
                u = update.effective_user
                user_info = f"@{u.username or 'no_username'} ({u.id})"
            if update.effective_message:
                message_text = (update.effective_message.text or "")[:200]

        text = (
            f"⚠️ <b>ОШИБКА БОТА</b>\n\n"
            f"<b>Тип:</b> <code>{error_type}</code>\n"
            f"<b>Пользователь:</b> {user_info}\n"
            f"<b>Сообщение:</b> <code>{message_text}</code>\n\n"
            f"<pre>{tb}</pre>"
        )

        try:
            await context.bot.send_message(
                chat_id=settings.ADMIN_TELEGRAM_ID,
                text=text,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Failed to notify admin", error=str(e))


# Синглтон для регистрации
_handler = ErrorHandlerMiddleware()


def setup_error_handler(application) -> None:
    """
    Регистрирует обработчик ошибок в PTB Application.

    Args:
        application: PTB Application instance
    """
    application.add_error_handler(_handler)
    logger.info("Error handler registered")
