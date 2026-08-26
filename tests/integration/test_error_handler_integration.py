"""
Integration тесты для ErrorHandlerMiddleware (PTB-based, Task 6.3.2)

Текущая реализация (bot/middleware/error_handler.py):
- ErrorHandlerMiddleware.__call__(update, context) — обработчик ошибок PTB,
  ошибка передаётся через context.error.
- Уведомляет пользователя через update.effective_message.reply_text.
- Уведомляет администратора через context.bot.send_message, если настроен
  settings.ADMIN_TELEGRAM_ID.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Update
from telegram.error import TelegramError

from sqlalchemy.exc import SQLAlchemyError

from bot.middleware.error_handler import ErrorHandlerMiddleware


def make_update_context(error, admin_id=999999, with_message=True):
    """Строит mock update/context в стиле python-telegram-bot."""
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=67890, username="testuser", full_name="Test User")
    update.effective_chat = MagicMock(id=12345, type="private")
    update.to_dict = MagicMock(return_value={"update_id": 1})

    if with_message:
        update.effective_message = MagicMock()
        update.effective_message.text = "/test_command"
        update.effective_message.reply_text = AsyncMock()
    else:
        update.effective_message = None
        update.effective_callback_query = MagicMock()

    context = MagicMock()
    context.error = error
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return update, context


@pytest.fixture
def middleware():
    """Создает экземпляр ErrorHandlerMiddleware"""
    return ErrorHandlerMiddleware()


class TestErrorHandlerIntegration:
    """Integration тесты ErrorHandlerMiddleware"""

    async def test_error_handler_full_flow(self, middleware):
        """Тест: полный цикл обработки ошибки от начала до конца"""

        update, context = make_update_context(RuntimeError("Integration test error"))

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            result = await middleware(update, context)

            # Middleware возвращает None
            assert result is None

            # Пользователю отправлено сообщение об ошибке
            update.effective_message.reply_text.assert_called_once()
            # Администратору отправлено уведомление
            context.bot.send_message.assert_called_once()

    async def test_error_handler_with_database_error(self, middleware):
        """Тест: обработка ошибки базы данных"""

        update, context = make_update_context(
            SQLAlchemyError("Database connection failed")
        )

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            result = await middleware(update, context)

            assert result is None
            update.effective_message.reply_text.assert_called_once()
            context.bot.send_message.assert_called_once()

    async def test_error_handler_with_telegram_error(self, middleware):
        """Тест: обработка ошибки Telegram API"""

        update, context = make_update_context(TelegramError("Message too long"))

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            result = await middleware(update, context)

            assert result is None
            update.effective_message.reply_text.assert_called_once()
            context.bot.send_message.assert_called_once()

    async def test_error_handler_with_multiple_admins(self, middleware):
        """Тест: уведомление администратора (поддержка нескольких не реализована,
        проверяем, что уведомление отправляется настроенному админу)"""

        update, context = make_update_context(RuntimeError("Multiple admins test"))

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            result = await middleware(update, context)

            assert result is None
            context.bot.send_message.assert_called_once()

    async def test_error_handler_callback_query_flow(self, middleware):
        """Тест: полный цикл обработки ошибки для CallbackQuery"""

        update, context = make_update_context(
            ValueError("Callback query error"), with_message=False
        )

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            result = await middleware(update, context)

            assert result is None
            # У пользователя нет effective_message (callback query) — уведомляем только админа
            context.bot.send_message.assert_called_once()

    async def test_error_handler_no_admin_configured(self, middleware):
        """Тест: обработка ошибки без настроенного администратора"""

        update, context = make_update_context(ValueError("No admin configured"))

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = None

            result = await middleware(update, context)

            assert result is None
            # Пользователю должно быть отправлено сообщение
            update.effective_message.reply_text.assert_called_once()
            # Администратору НЕ отправляется (не настроен)
            context.bot.send_message.assert_not_called()

    async def test_error_handler_graceful_failure(self, middleware):
        """Тест: graceful failure при отправке уведомлений"""

        update, context = make_update_context(ValueError("Test error"))
        # Настраиваем bot.send_message чтобы выбрасывал исключение
        context.bot.send_message.side_effect = Exception("Failed to send message")

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            # Middleware должен обработать ошибку отправки уведомлений
            result = await middleware(update, context)

            assert result is None
            # Пользователю сообщение всё равно ушло
            update.effective_message.reply_text.assert_called_once()
            # Попытка уведомить админа была предпринята
            context.bot.send_message.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
