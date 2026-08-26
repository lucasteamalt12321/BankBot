"""
Integration test for error handler middleware registration (Task 6.2.1)

Проверяет, что ErrorHandlerMiddleware корректно регистрируется в PTB Application
через setup_error_handler(), и что обработчик корректно уведомляет пользователя
и администратора для различных типов исключений.

Validates: Requirements 6.1-6.4
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Update
from telegram.ext import Application

from bot.middleware.error_handler import ErrorHandlerMiddleware, setup_error_handler


def make_update_context(error, admin_id=123456789, command_text="/test"):
    """Строит mock update/context в стиле python-telegram-bot."""
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=12345, username="testuser", full_name="Test User")
    update.effective_chat = MagicMock(id=67890, type="private")
    update.to_dict = MagicMock(return_value={"update_id": 1})
    update.effective_message = MagicMock()
    update.effective_message.text = command_text
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    context.error = error
    return update, context


class TestErrorHandlerRegistration:
    """Test that error handler middleware is registered in the bot"""

    def test_error_handler_registered_in_bot(self):
        """Test that error handler is registered in the PTB Application (Task 6.2.1)"""
        app = Application.builder().token("test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ").build()

        # Регистрируем обработчик так же, как это делает TelegramBot.setup_error_handler
        setup_error_handler(app)

        # Проверяем, что middleware зарегистрирован в приложении
        assert hasattr(app, 'error_handlers')
        assert any(
            isinstance(handler, ErrorHandlerMiddleware) for handler in app.error_handlers
        ), "ErrorHandlerMiddleware should be registered in the application"

        print("✅ Error handler middleware successfully registered in application")

    def test_setup_error_handler_called(self):
        """Test that setup_error_handler method is available and registers handler"""
        from bot.bot import TelegramBot

        # Verify setup_error_handler method exists and is callable
        assert hasattr(TelegramBot, 'setup_error_handler')
        assert callable(TelegramBot.setup_error_handler)

        # Verify it actually registers the middleware in an application.
        # setup_error_handler is an instance method that operates on self.application,
        # so we provide a lightweight stand-in exposing the real Application.
        app = Application.builder().token("test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ").build()
        fake_bot = MagicMock()
        fake_bot.application = app
        TelegramBot.setup_error_handler(fake_bot)

        assert any(
            isinstance(handler, ErrorHandlerMiddleware) for handler in app.error_handlers
        ), "setup_error_handler should register ErrorHandlerMiddleware"

        print("✅ setup_error_handler method registers the error handler")

    def test_error_handler_middleware_configuration(self):
        """Test that error handler middleware is configured correctly"""
        middleware = ErrorHandlerMiddleware()

        # Check that logger is configured (Requirement 6.2)
        assert middleware.logger is not None, "Logger should be configured"

        # Check that the handler entry point is callable (Requirement 6.1, 6.4)
        assert hasattr(middleware, '__call__'), "Error handler should be callable"
        assert callable(middleware), "Error handler should be callable"

        # Поведенческая проверка: при ошибке уведомляются пользователь и админ
        update, context = make_update_context(ValueError("config check"), admin_id=123456789)
        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 123456789
            import asyncio
            asyncio.run(middleware(update, context))

        update.effective_message.reply_text.assert_called_once()
        context.bot.send_message.assert_called_once()

        print("✅ Error handler middleware configured correctly")


class TestErrorHandlerWithDifferentErrorTypes:
    """Integration tests for error handler with different error types (Task 6.2.2)"""

    @pytest.mark.asyncio
    async def test_handle_value_error(self):
        """Test handling of ValueError (business logic error)"""
        middleware = ErrorHandlerMiddleware()
        update, context = make_update_context(ValueError("Invalid value provided"), command_text="/test")

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 123456789
            await middleware(update, context)

        update.effective_message.reply_text.assert_called_once()
        user_message = update.effective_message.reply_text.call_args[0][0]
        assert "❌" in user_message
        assert "Произошла ошибка" in user_message

        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "ValueError" in admin_message

        print("✅ ValueError handled correctly")

    @pytest.mark.asyncio
    async def test_handle_key_error(self):
        """Test handling of KeyError (missing data error)"""
        middleware = ErrorHandlerMiddleware()
        update, context = make_update_context(KeyError("user_id"), command_text="/profile")

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 123456789
            await middleware(update, context)

        update.effective_message.reply_text.assert_called_once()
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "KeyError" in admin_message

        print("✅ KeyError handled correctly")

    @pytest.mark.asyncio
    async def test_handle_attribute_error(self):
        """Test handling of AttributeError (code error)"""
        middleware = ErrorHandlerMiddleware()
        update, context = make_update_context(
            AttributeError("'NoneType' object has no attribute 'balance'"), command_text="/balance"
        )

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 123456789
            await middleware(update, context)

        update.effective_message.reply_text.assert_called_once()
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "AttributeError" in admin_message

        print("✅ AttributeError handled correctly")

    @pytest.mark.asyncio
    async def test_handle_type_error(self):
        """Test handling of TypeError (type mismatch error)"""
        middleware = ErrorHandlerMiddleware()
        update, context = make_update_context(
            TypeError("unsupported operand type(s) for +: 'int' and 'str'"), command_text="/add_points"
        )

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 123456789
            await middleware(update, context)

        update.effective_message.reply_text.assert_called_once()
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "TypeError" in admin_message

        print("✅ TypeError handled correctly")

    @pytest.mark.asyncio
    async def test_handle_runtime_error(self):
        """Test handling of RuntimeError (runtime issue)"""
        middleware = ErrorHandlerMiddleware()
        update, context = make_update_context(RuntimeError("Database connection lost"), command_text="/shop")

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 123456789
            await middleware(update, context)

        update.effective_message.reply_text.assert_called_once()
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "RuntimeError" in admin_message

        print("✅ RuntimeError handled correctly")

    @pytest.mark.asyncio
    async def test_handle_zero_division_error(self):
        """Test handling of ZeroDivisionError (calculation error)"""
        middleware = ErrorHandlerMiddleware()
        update, context = make_update_context(ZeroDivisionError("division by zero"), command_text="/calculate")

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 123456789
            await middleware(update, context)

        update.effective_message.reply_text.assert_called_once()
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "ZeroDivisionError" in admin_message

        print("✅ ZeroDivisionError handled correctly")

    @pytest.mark.asyncio
    async def test_handle_index_error(self):
        """Test handling of IndexError (list access error)"""
        middleware = ErrorHandlerMiddleware()
        update, context = make_update_context(IndexError("list index out of range"), command_text="/list")

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 123456789
            await middleware(update, context)

        update.effective_message.reply_text.assert_called_once()
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "IndexError" in admin_message

        print("✅ IndexError handled correctly")

    @pytest.mark.asyncio
    async def test_handle_import_error(self):
        """Test handling of ImportError (module loading error)"""
        middleware = ErrorHandlerMiddleware()
        update, context = make_update_context(ImportError("No module named 'missing_module'"), command_text="/plugin")

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 123456789
            await middleware(update, context)

        update.effective_message.reply_text.assert_called_once()
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "ImportError" in admin_message

        print("✅ ImportError handled correctly")

    @pytest.mark.asyncio
    async def test_handle_assertion_error(self):
        """Test handling of AssertionError (validation error)"""
        middleware = ErrorHandlerMiddleware()
        update, context = make_update_context(AssertionError("Expected value to be positive"), command_text="/validate")

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 123456789
            await middleware(update, context)

        update.effective_message.reply_text.assert_called_once()
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "AssertionError" in admin_message

        print("✅ AssertionError handled correctly")

    @pytest.mark.asyncio
    async def test_handle_os_error(self):
        """Test handling of OSError (file system error)"""
        middleware = ErrorHandlerMiddleware()
        update, context = make_update_context(OSError("No space left on device"), command_text="/export")

        with patch('bot.middleware.error_handler.settings', new=MagicMock()) as mock_settings:
            mock_settings.ADMIN_TELEGRAM_ID = 123456789
            await middleware(update, context)

        update.effective_message.reply_text.assert_called_once()
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "OSError" in admin_message

        print("✅ OSError handled correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
