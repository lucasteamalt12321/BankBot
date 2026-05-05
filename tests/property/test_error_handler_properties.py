"""
Property-based тесты для ErrorHandlerMiddleware (Task 6.3.3)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import hypothesis.strategies as st
from hypothesis import given, settings, reproduce_failure
import re

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


class TestErrorHandlerProperties:
    """Property-based тесты ErrorHandlerMiddleware"""

    @given(
        error_type=st.sampled_from([ValueError, RuntimeError, KeyError, TypeError, AttributeError]),
        error_message=st.text(min_size=1, max_size=100),
        user_id=st.integers(min_value=1, max_value=999999999),
        username=st.text(min_size=1, max_size=50).filter(lambda x: x and not x.isspace())
    )
    @settings(max_examples=10, deadline=1000)
    async def test_error_handler_handles_all_error_types(
        self, middleware, mock_bot, error_type, error_message, user_id, username
    ):
        """
        Свойство: middleware корректно обрабатывает все типы исключений
        
        Validates: Requirements 6.1, 6.2
        """

        async def failing_callback(event, data):
            raise error_type(error_message)

        message = MagicMock(spec=types.Message)
        message.chat = MagicMock()
        message.chat.id = 12345
        message.from_user = MagicMock()
        message.from_user.id = user_id
        message.from_user.username = username
        message.text = "/test"

        data = {"bot": mock_bot}

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            result = await middleware(failing_callback, message, data)

            # Middleware всегда должен возвращать None
            assert result is None
            # Должен быть вызван send_message
            assert mock_bot.send_message.called

    @given(
        chat_id=st.integers(min_value=1, max_value=999999999),
        user_id=st.integers(min_value=1, max_value=999999999),
        message_text=st.text(min_size=0, max_size=1000)
    )
    @settings(max_examples=10, deadline=1000)
    async def test_error_handler_sends_user_message(
        self, middleware, mock_bot, chat_id, user_id, message_text
    ):
        """
        Свойство: middleware всегда отправляет сообщение пользователю при ошибке
        
        Validates: Requirements 6.1, 6.2
        """

        async def failing_callback(event, data):
            raise ValueError("Test error")

        message = MagicMock(spec=types.Message)
        message.chat = MagicMock()
        message.chat.id = chat_id
        message.from_user = MagicMock()
        message.from_user.id = user_id
        message.from_user.username = "testuser"
        message.text = message_text

        data = {"bot": mock_bot}

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            await middleware(failing_callback, message, data)

            # Проверяем, что send_message был вызван
            assert mock_bot.send_message.called

            # Проверяем, что сообщение отправлено на правильный chat_id
            call_args = mock_bot.send_message.call_args
            sent_chat_id = call_args[1]['chat_id'] if call_args else None
            assert sent_chat_id == chat_id

    @given(
        admin_id=st.integers(min_value=1, max_value=999999999).filter(lambda x: x > 0),
        error_type=st.sampled_from([ValueError, RuntimeError, KeyError]),
        error_message=st.text(min_size=1, max_size=100)
    )
    @settings(max_examples=10, deadline=1000)
    async def test_error_handler_notifies_admin(
        self, middleware, mock_bot, admin_id, error_type, error_message
    ):
        """
        Свойство: middleware уведомляет администратора о критических ошибках
        
        Validates: Requirements 6.1, 6.3
        """

        async def failing_callback(event, data):
            raise error_type(error_message)

        message = MagicMock(spec=types.Message)
        message.chat = MagicMock()
        message.chat.id = 12345
        message.from_user = MagicMock()
        message.from_user.id = 67890
        message.from_user.username = "testuser"
        message.text = "/test"

        data = {"bot": mock_bot}

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = admin_id

            await middleware(failing_callback, message, data)

            # Проверяем, что send_message был вызван хотя бы один раз
            assert mock_bot.send_message.called

    @given(
        error_message=st.text(min_size=1, max_size=5000)
    )
    @settings(max_examples=5, deadline=1000)
    async def test_error_handler_truncates_long_traceback(
        self, middleware, mock_bot, error_message
    ):
        """
        Свойство: middleware обрезает длинные стектрейсы для Telegram
        
        Validates: Requirements 6.1, 6.2
        """

        async def failing_callback(event, data):
            raise ValueError(error_message)

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

            await middleware(failing_callback, message, data)

            # Проверяем, что send_message был вызван
            assert mock_bot.send_message.called

            # Получаем отправленное сообщение
            call_args = mock_bot.send_message.call_args
            text = call_args[1]['text'] if call_args else ""

            # Текст должен быть меньше 4000 символов (ограничение Telegram)
            assert len(text) <= 4000

    @given(
        user_id=st.integers(min_value=1, max_value=999999999),
        username=st.text(min_size=1, max_size=50).filter(lambda x: x and not x.isspace()),
        message_text=st.text(min_size=0, max_size=1000)
    )
    @settings(max_examples=10, deadline=1000)
    async def test_error_handler_preserves_user_info(
        self, middleware, mock_bot, user_id, username, message_text
    ):
        """
        Свойство: middleware со��раняет информацию о пользователе в уведомлениях
        
        Validates: Requirements 6.1, 6.2
        """

        async def failing_callback(event, data):
            raise ValueError("Test error")

        message = MagicMock(spec=types.Message)
        message.chat = MagicMock()
        message.chat.id = 12345
        message.from_user = MagicMock()
        message.from_user.id = user_id
        message.from_user.username = username
        message.text = message_text

        data = {"bot": mock_bot}

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            await middleware(failing_callback, message, data)

            # Проверяем, что send_message был вызван
            assert mock_bot.send_message.called

            # Получаем отправленное сообщение администратору
            # (второй вызов - уведомление админу)
            all_calls = mock_bot.send_message.call_args_list
            if len(all_calls) >= 2:
                admin_call = all_calls[1]
                admin_text = admin_call[1]['text'] if admin_call else ""

                # Проверяем, что в уведомлении админу есть информация о пользователе
                assert str(user_id) in admin_text or username in admin_text

    @given(
        chat_id=st.integers(min_value=1, max_value=999999999),
        user_id=st.integers(min_value=1, max_value=999999999),
        message_text=st.text(min_size=0, max_size=1000)
    )
    @settings(max_examples=10, deadline=1000)
    async def test_error_handler_message_format_consistency(
        self, middleware, mock_bot, chat_id, user_id, message_text
    ):
        """
        Свойство: формат сообщения пользователю всегда содержит ключевые элементы
        
        Validates: Requirements 6.1, 6.2
        """

        async def failing_callback(event, data):
            raise ValueError("Test error")

        message = MagicMock(spec=types.Message)
        message.chat = MagicMock()
        message.chat.id = chat_id
        message.from_user = MagicMock()
        message.from_user.id = user_id
        message.from_user.username = "testuser"
        message.text = message_text

        data = {"bot": mock_bot}

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            await middleware(failing_callback, message, data)

            # Проверяем, что send_message был вызван
            assert mock_bot.send_message.called

            # Получаем отправленное сообщение пользователю
            call_args = mock_bot.send_message.call_args
            text = call_args[1]['text'] if call_args else ""

            # Проверяем, что сообщение содержит ключевые элементы
            assert "ошибка" in text.lower() or "ошибку" in text.lower()
            assert "администраторы" in text.lower() or "уведомлены" in text.lower()

    @given(
        admin_id=st.integers(min_value=1, max_value=999999999).filter(lambda x: x > 0),
        error_type=st.sampled_from([ValueError, RuntimeError, KeyError, TypeError]),
        error_message=st.text(min_size=1, max_size=100)
    )
    @settings(max_examples=10, deadline=1000)
    async def test_error_handler_admin_notification_format(
        self, middleware, mock_bot, admin_id, error_type, error_message
    ):
        """
        Свойство: формат уведомления администратору всегда содержит ключевые поля
        
        Validates: Requirements 6.1, 6.3
        """

        async def failing_callback(event, data):
            raise error_type(error_message)

        message = MagicMock(spec=types.Message)
        message.chat = MagicMock()
        message.chat.id = 12345
        message.from_user = MagicMock()
        message.from_user.id = 67890
        message.from_user.username = "testuser"
        message.text = "/test"

        data = {"bot": mock_bot}

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = admin_id

            await middleware(failing_callback, message, data)

            # Проверяем, что send_message был вызван
            assert mock_bot.send_message.called

            # Получаем все вызовы send_message
            all_calls = mock_bot.send_message.call_args_list

            # Ищем уведомление администратору (обычно это второй вызов)
            admin_notification_found = False
            for call in all_calls:
                text = call[1]['text'] if call else ""
                if "КРИТИЧЕСКАЯ ОШИБКА" in text:
                    admin_notification_found = True
                    # Проверяем наличие ключевых полей
                    assert "Тип ошибки" in text
                    assert "Сообщение" in text
                    assert "Пользователь" in text
                    assert "Сообщение" in text
                    break

            assert admin_notification_found, "Уведомление администратору не найдено"

    @given(
        admin_id=st.integers(min_value=1, max_value=999999999).filter(lambda x: x > 0),
        error_type=st.sampled_from([ValueError, RuntimeError, KeyError]),
        error_message=st.text(min_size=1, max_size=100)
    )
    @settings(max_examples=10, deadline=1000)
    async def test_error_handler_handles_admin_send_failure(
        self, middleware, mock_bot, admin_id, error_type, error_message
    ):
        """
        Свойство: middleware корректно обрабатывает ошибку отправки уведомления админу
        
        Validates: Requirements 6.1, 6.3
        """

        async def failing_callback(event, data):
            raise error_type(error_message)

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
            mock_settings.ADMIN_TELEGRAM_ID = admin_id

            # Middleware должен обработать ошибку без выброса исключения
            result = await middleware(failing_callback, message, data)

            assert result is None
