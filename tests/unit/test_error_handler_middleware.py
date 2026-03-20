"""
Unit тесты для ErrorHandlerMiddleware (Task 6.3.1)
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


@pytest.fixture
def mock_data(mock_bot):
    """Создает мок данных для обработчика"""
    return {"bot": mock_bot}


@pytest.fixture
def mock_message():
    """Создает мок сообщения"""
    message = MagicMock(spec=types.Message)
    message.chat = MagicMock()
    message.chat.id = 12345
    message.from_user = MagicMock()
    message.from_user.id = 67890
    message.from_user.username = "testuser"
    message.text = "/test"
    return message


class TestErrorHandlerMiddleware:
    """Тесты ErrorHandlerMiddleware"""

    async def test_error_handler_calls_notify_user(self, middleware, mock_bot, mock_data, mock_message):
        """Тест: middleware отправляет уведомление пользователю при ошибке"""
        
        async def failing_callback(event, data):
            raise ValueError("Test error")
        
        # Перехватываем send_message
        with patch.object(mock_bot, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_data["bot"] = mock_bot
            
            result = await middleware(failing_callback, mock_message, mock_data)
            
            assert result is None
            mock_send.assert_called()

    async def test_error_handler_notifies_admins(self, middleware, mock_bot, mock_data, mock_message):
        """Тест: middleware уведомляет администраторов о критических ошибках"""
        
        async def failing_callback(event, data):
            raise RuntimeError("Critical error")
        
        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999
            
            with patch.object(mock_bot, 'send_message', new_callable=AsyncMock) as mock_send:
                mock_data["bot"] = mock_bot
                
                await middleware(failing_callback, mock_message, mock_data)
                
                # Проверяем, что уведомление администратору было отправлено
                assert mock_send.call_count >= 1

    async def test_error_handler_logs_exception(self, middleware, mock_bot, mock_data, mock_message):
        """Тест: middleware логирует полный стектрейс ошибки"""
        
        async def failing_callback(event, data):
            raise KeyError("Missing key")
        
        with patch('bot.middleware.error_handler.logger') as mock_logger:
            with patch.object(mock_bot, 'send_message', new_callable=AsyncMock):
                mock_data["bot"] = mock_bot
                
                await middleware(failing_callback, mock_message, mock_data)
                
                mock_logger.exception.assert_called_once()

    async def test_error_handler_handles_callback_query(self, middleware, mock_bot, mock_data):
        """Тест: middleware обрабатывает CallbackQuery"""
        
        callback_query = MagicMock(spec=types.CallbackQuery)
        callback_query.message = MagicMock()
        callback_query.message.chat = MagicMock()
        callback_query.message.chat.id = 12345
        callback_query.from_user = MagicMock()
        callback_query.from_user.id = 67890
        callback_query.data = "test_callback"
        
        async def failing_callback(event, data):
            raise ValueError("Test error")
        
        with patch.object(mock_bot, 'send_message', new_callable=AsyncMock):
            mock_data["bot"] = mock_bot
            
            result = await middleware(failing_callback, callback_query, mock_data)
            
            assert result is None

    async def test_error_handler_no_chat_id(self, middleware, mock_bot, mock_data):
        """Тест: middleware обрабатывает событие без chat_id"""
        
        # Объект без chat.id
        event = MagicMock(spec=TelegramObject)
        event.chat = None
        
        async def failing_callback(event, data):
            raise ValueError("Test error")
        
        with patch.object(mock_bot, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_data["bot"] = mock_bot
            
            result = await middleware(failing_callback, event, mock_data)
            
            assert result is None
            # send_message не должен быть вызван без chat_id
            mock_send.assert_not_called()

    async def test_error_handler_bot_not_in_data(self, middleware, mock_data, mock_message):
        """Тест: middleware обрабатывает случай, когда бота нет в данных"""
        
        async def failing_callback(event, data):
            raise ValueError("Test error")
        
        # Удаляем bot из данных
        data_without_bot = {k: v for k, v in mock_data.items() if k != "bot"}
        
        with patch('bot.middleware.error_handler.logger') as mock_logger:
            result = await middleware(failing_callback, mock_message, data_without_bot)
            
            assert result is None
            mock_logger.warning.assert_called()

    async def test_error_handler_truncates_traceback(self, middleware, mock_bot, mock_data, mock_message):
        """Тест: middleware обрезает длинный стектрейс для Telegram"""
        
        async def failing_callback(event, data):
            # Создаем длинное исключение
            raise ValueError("x" * 5000)
        
        with patch.object(mock_bot, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_data["bot"] = mock_bot
            
            await middleware(failing_callback, mock_message, mock_data)
            
            # Проверяем, что сообщение было отправлено
            assert mock_send.called
            # Получаем отправленное сообщение
            call_args = mock_send.call_args
            text = call_args[1]['text'] if call_args else ""
            
            # Текст должен быть обрезан (меньше 4000 символов)
            assert len(text) <= 4000

    async def test_error_handler_user_not_found(self, middleware, mock_bot, mock_data, mock_message):
        """Тест: middleware обрабатывает случай, когда пользователь не найден"""
        
        async def failing_callback(event, data):
            raise ValueError("User not found")
        
        # Меняем chat_id на несуществующий
        mock_message.chat.id = 999999
        
        with patch.object(mock_bot, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_data["bot"] = mock_bot
            
            result = await middleware(failing_callback, mock_message, mock_data)
            
            assert result is None
            # Должен быть вызван send_message
            assert mock_send.called

    async def test_error_handler_admin_notification_format(self, middleware, mock_bot, mock_data, mock_message):
        """Тест: формат уведомления администратору содержит все необходимые поля"""
        
        async def failing_callback(event, data):
            raise RuntimeError("Test critical error")
        
        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999
            
            with patch.object(mock_bot, 'send_message', new_callable=AsyncMock) as mock_send:
                mock_data["bot"] = mock_bot
                
                await middleware(failing_callback, mock_message, mock_data)
                
                # Проверяем формат сообщения
                call_args = mock_send.call_args
                text = call_args[1]['text'] if call_args else ""
                
                # Проверяем наличие ключевых полей
                assert "КРИТИЧЕСКАЯ ОШИБКА" in text
                assert "RuntimeError" in text
                assert "Test critical error" in text
                assert "testuser" in text or "67890" in text
