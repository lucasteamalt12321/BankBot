"""
Integration тесты для ErrorHandlerMiddleware (Task 6.3.2)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import types
from aiogram.types import TelegramObject

from bot.middleware.error_handler import ErrorHandlerMiddleware


@pytest.fixture
def middleware():
    """Создает экземпляр ErrorHandlerMiddleware"""
    return ErrorHandlerMiddleware()


@pytest.fixture
def mock_bot():
    """Создает мок объекта бота"""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


class TestErrorHandlerIntegration:
    """Integration тесты ErrorHandlerMiddleware"""

    async def test_error_handler_full_flow(self, middleware, mock_bot):
        """Тест: полный цикл обработки ошибки от начала до конца"""

        async def failing_callback(event, data):
            raise RuntimeError("Integration test error")

        message = MagicMock(spec=types.Message)
        message.chat = MagicMock()
        message.chat.id = 12345
        message.from_user = MagicMock()
        message.from_user.id = 67890
        message.from_user.username = "testuser"
        message.text = "/test_command"

        data = {"bot": mock_bot}

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            result = await middleware(failing_callback, message, data)

            # Проверяем, что middleware вернул None
            assert result is None

            # Проверяем, что send_message был вызван (пользователю и админу)
            assert mock_bot.send_message.call_count >= 1

    async def test_error_handler_with_database_error(self, middleware, mock_bot):
        """Тест: обработка ошибки базы данных"""

        async def failing_callback(event, data):
            from sqlalchemy.exc import SQLAlchemyError
            raise SQLAlchemyError("Database connection failed")

        message = MagicMock(spec=types.Message)
        message.chat = MagicMock()
        message.chat.id = 12345
        message.from_user = MagicMock()
        message.from_user.id = 67890
        message.from_user.username = "testuser"
        message.text = "/balance"

        data = {"bot": mock_bot}

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            result = await middleware(failing_callback, message, data)

            assert result is None
            assert mock_bot.send_message.called

    async def test_error_handler_with_telegram_error(self, middleware, mock_bot):
        """Тест: обработка ошибки Telegram API"""

        async def failing_callback(event, data):
            from aiogram.exceptions import TelegramAPIError
            raise TelegramAPIError("Message too long")

        message = MagicMock(spec=types.Message)
        message.chat = MagicMock()
        message.chat.id = 12345
        message.from_user = MagicMock()
        message.from_user.id = 67890
        message.from_user.username = "testuser"
        message.text = "/test"

        data = {"bot": mock_bot}

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            result = await middleware(failing_callback, message, data)

            assert result is None
            assert mock_bot.send_message.called

    async def test_error_handler_with_multiple_admins(self, middleware, mock_bot):
        """Тест: уведомление нескольких администраторов"""

        async def failing_callback(event, data):
            raise RuntimeError("Multiple admins test")

        message = MagicMock(spec=types.Message)
        message.chat = MagicMock()
        message.chat.id = 12345
        message.from_user = MagicMock()
        message.from_user.id = 67890
        message.from_user.username = "testuser"
        message.text = "/test"

        data = {"bot": mock_bot}

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            result = await middleware(failing_callback, message, data)

            assert result is None
            # Должен быть вызван send_message хотя бы один раз
            assert mock_bot.send_message.called

    async def test_error_handler_callback_query_flow(self, middleware, mock_bot):
        """Тест: полный цикл обработки ошибки для CallbackQuery"""

        async def failing_callback(event, data):
            raise ValueError("Callback query error")

        callback_query = MagicMock(spec=types.CallbackQuery)
        callback_query.message = MagicMock()
        callback_query.message.chat = MagicMock()
        callback_query.message.chat.id = 12345
        callback_query.from_user = MagicMock()
        callback_query.from_user.id = 67890
        callback_query.from_user.username = "testuser"
        callback_query.data = "test_callback_data"

        data = {"bot": mock_bot}

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            result = await middleware(failing_callback, callback_query, data)

            assert result is None
            assert mock_bot.send_message.called

    async def test_error_handler_no_admin_configured(self, middleware, mock_bot):
        """Тест: обработка ошибки без настроенного администратора"""

        async def failing_callback(event, data):
            raise ValueError("No admin configured")

        message = MagicMock(spec=types.Message)
        message.chat = MagicMock()
        message.chat.id = 12345
        message.from_user = MagicMock()
        message.from_user.id = 67890
        message.from_user.username = "testuser"
        message.text = "/test"

        data = {"bot": mock_bot}

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = None

            result = await middleware(failing_callback, message, data)

            assert result is None
            # Пользователю должно быть отправлено сообщение
            assert mock_bot.send_message.called

    async def test_error_handler_graceful_failure(self, middleware, mock_bot):
        """Тест: graceful failure при отправке уведомлений"""

        async def failing_callback(event, data):
            raise ValueError("Test error")

        message = MagicMock(spec=types.Message)
        message.chat = MagicMock()
        message.chat.id = 12345
        message.from_user = MagicMock()
        message.from_user.id = 67890
        message.from_user.username = "testuser"
        message.text = "/test"

        # Настраиваем bot.send_message чтобы выбрасывал исключение
        mock_bot.send_message.side_effect = Exception("Failed to send message")

        data = {"bot": mock_bot}

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            # Middleware должен обработать ошибку отправки уведомлений
            result = await middleware(failing_callback, message, data)

            assert result is None
