"""
Property-based тесты для ErrorHandlerMiddleware (Task 6.3.3)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import hypothesis.strategies as st
from hypothesis import given, settings, HealthCheck

from telegram import Update

from bot.middleware.error_handler import ErrorHandlerMiddleware


@pytest.fixture
def middleware():
    """Создает экземпляр ErrorHandlerMiddleware"""
    return ErrorHandlerMiddleware()


@pytest.fixture
def mock_context():
    """Мок PTB ContextTypes.DEFAULT_TYPE."""
    context = MagicMock()
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return context


@pytest.fixture
def mock_update():
    """Мок PTB Update (isinstance-совместимый)."""
    update = MagicMock(spec=Update)
    update.effective_message = MagicMock()
    update.effective_message.text = "/test"
    update.effective_message.reply_text = AsyncMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 67890
    update.effective_user.username = "testuser"
    return update


SUPPRESS = [HealthCheck.function_scoped_fixture]


class TestErrorHandlerProperties:
    """Property-based тесты ErrorHandlerMiddleware"""

    @given(
        error_type=st.sampled_from([ValueError, RuntimeError, KeyError, TypeError, AttributeError]),
        error_message=st.text(min_size=1, max_size=100),
        admin_id=st.integers(min_value=1, max_value=999999999),
    )
    @settings(max_examples=10, deadline=1000, suppress_health_check=SUPPRESS)
    async def test_error_handler_handles_all_error_types(
        self, middleware, mock_update, mock_context, error_type, error_message, admin_id
    ):
        """
        Свойство: middleware корректно обрабатывает все типы исключений

        Validates: Requirements 6.1, 6.2
        """
        mock_context.error = error_type(error_message)

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = admin_id

            result = await middleware(mock_update, mock_context)

            # Middleware всегда должен возвращать None
            assert result is None
            # Пользователь уведомлён
            mock_update.effective_message.reply_text.assert_awaited()
            # Админ уведомлён
            mock_context.bot.send_message.assert_awaited()

    @given(
        message_text=st.text(min_size=0, max_size=1000),
        admin_id=st.integers(min_value=1, max_value=999999999),
    )
    @settings(max_examples=10, deadline=1000, suppress_health_check=SUPPRESS)
    async def test_error_handler_sends_user_message(
        self, middleware, mock_update, mock_context, message_text, admin_id
    ):
        """
        Свойство: middleware всегда отправляет сообщение пользователю при ошибке

        Validates: Requirements 6.1, 6.2
        """
        mock_update.effective_message.text = message_text
        mock_context.error = ValueError("Test error")

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = admin_id

            await middleware(mock_update, mock_context)

            # Проверяем, что сообщение пользователю было отправлено
            mock_update.effective_message.reply_text.assert_awaited()

    @given(
        admin_id=st.integers(min_value=1, max_value=999999999).filter(lambda x: x > 0),
        error_type=st.sampled_from([ValueError, RuntimeError, KeyError]),
        error_message=st.text(min_size=1, max_size=100)
    )
    @settings(max_examples=10, deadline=1000, suppress_health_check=SUPPRESS)
    async def test_error_handler_notifies_admin(
        self, middleware, mock_update, mock_context, admin_id, error_type, error_message
    ):
        """
        Свойство: middleware уведомляет администратора о критических ошибках

        Validates: Requirements 6.1, 6.3
        """
        mock_context.error = error_type(error_message)

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = admin_id

            await middleware(mock_update, mock_context)

            # Проверяем, что send_message был вызван хотя бы один раз
            mock_context.bot.send_message.assert_awaited()

    @given(
        error_message=st.text(min_size=1, max_size=5000)
    )
    @settings(max_examples=5, deadline=1000, suppress_health_check=SUPPRESS)
    async def test_error_handler_truncates_long_traceback(
        self, middleware, mock_update, mock_context, error_message
    ):
        """
        Свойство: middleware обрезает длинные стектрейсы для Telegram

        Validates: Requirements 6.1, 6.2
        """
        mock_context.error = ValueError(error_message)

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            await middleware(mock_update, mock_context)

            # Проверяем, что send_message был вызван
            mock_context.bot.send_message.assert_awaited()

            # Получаем отправленное сообщение админу
            call_args = mock_context.bot.send_message.call_args
            text = call_args.kwargs.get('text', '')

            # Текст должен быть меньше 4000 символов (ограничение Telegram)
            assert len(text) <= 4000

    @given(
        user_id=st.integers(min_value=1, max_value=999999999),
        username=st.text(min_size=1, max_size=50).filter(lambda x: x and not x.isspace()),
        message_text=st.text(min_size=0, max_size=1000)
    )
    @settings(max_examples=10, deadline=1000, suppress_health_check=SUPPRESS)
    async def test_error_handler_preserves_user_info(
        self, middleware, mock_update, mock_context, user_id, username, message_text
    ):
        """
        Свойство: middleware сохраняет информацию о пользователе в уведомлениях

        Validates: Requirements 6.1, 6.2
        """
        mock_update.effective_user.id = user_id
        mock_update.effective_user.username = username
        mock_update.effective_message.text = message_text
        mock_context.error = ValueError("Test error")

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 999999

            await middleware(mock_update, mock_context)

            # Проверяем, что send_message был вызван
            mock_context.bot.send_message.assert_awaited()

            # Получаем уведомление админу
            admin_text = mock_context.bot.send_message.call_args.kwargs.get('text', "")

            # В уведомлении админу есть информация о пользователе
            assert str(user_id) in admin_text or username in admin_text

    @given(
        message_text=st.text(min_size=0, max_size=1000),
        admin_id=st.integers(min_value=1, max_value=999999999),
    )
    @settings(max_examples=10, deadline=1000, suppress_health_check=SUPPRESS)
    async def test_error_handler_message_format_consistency(
        self, middleware, mock_update, mock_context, message_text, admin_id
    ):
        """
        Свойство: формат сообщения пользователю всегда содержит ключевые элементы

        Validates: Requirements 6.1, 6.2
        """
        mock_update.effective_message.text = message_text
        mock_context.error = ValueError("Test error")

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = admin_id

            await middleware(mock_update, mock_context)

            # Сообщение пользователю отправлено
            mock_update.effective_message.reply_text.assert_awaited()
            user_text = mock_update.effective_message.reply_text.call_args.kwargs.get('text', "")
            user_text = user_text or (mock_update.effective_message.reply_text.call_args.args[0] if mock_update.effective_message.reply_text.call_args.args else "")

            # Сообщение содержит ключевые элементы
            assert "ошибка" in user_text.lower() or "ошибку" in user_text.lower()

    @given(
        admin_id=st.integers(min_value=1, max_value=999999999).filter(lambda x: x > 0),
        error_type=st.sampled_from([ValueError, RuntimeError, KeyError, TypeError]),
        error_message=st.text(min_size=1, max_size=100)
    )
    @settings(max_examples=10, deadline=1000, suppress_health_check=SUPPRESS)
    async def test_error_handler_admin_notification_format(
        self, middleware, mock_update, mock_context, admin_id, error_type, error_message
    ):
        """
        Свойство: формат уведомления администратору всегда содержит ключевые поля

        Validates: Requirements 6.1, 6.3
        """
        mock_context.error = error_type(error_message)

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = admin_id

            await middleware(mock_update, mock_context)

            # Проверяем, что send_message был вызван
            mock_context.bot.send_message.assert_awaited()

            # Получаем все вызовы send_message
            all_calls = mock_context.bot.send_message.call_args_list

            # Ищем уведомление администратору
            admin_notification_found = False
            for call in all_calls:
                text = call.kwargs.get('text', "")
                if "ОШИБКА БОТА" in text:
                    admin_notification_found = True
                    # Проверяем наличие ключевых полей
                    assert "Тип:" in text
                    assert "Сообщение:" in text
                    assert "Пользователь:" in text
                    break

            assert admin_notification_found, "Уведомление администратору не найдено"

    @given(
        admin_id=st.integers(min_value=1, max_value=999999999).filter(lambda x: x > 0),
        error_type=st.sampled_from([ValueError, RuntimeError, KeyError]),
        error_message=st.text(min_size=1, max_size=100)
    )
    @settings(max_examples=10, deadline=1000, suppress_health_check=SUPPRESS)
    async def test_error_handler_handles_admin_send_failure(
        self, middleware, mock_update, mock_context, admin_id, error_type, error_message
    ):
        """
        Свойство: middleware корректно обрабатывает ошибку отправки уведомления админу

        Validates: Requirements 6.1, 6.3
        """
        mock_context.error = error_type(error_message)

        # Настраиваем bot.send_message чтобы выбрасывал исключение
        mock_context.bot.send_message.side_effect = Exception("Failed to send message")

        with patch('bot.middleware.error_handler.settings') as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = admin_id

            # Middleware должен обработать ошибку без выброса исключения
            result = await middleware(mock_update, mock_context)

            assert result is None
