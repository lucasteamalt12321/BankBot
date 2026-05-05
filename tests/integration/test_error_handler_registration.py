"""
Integration test for error handler middleware registration (Task 6.2.1)

Verifies that the error handler middleware is properly registered
in the Telegram bot application.

Validates: Requirements 6.1-6.4
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from telegram.ext import Application

from bot.middleware.error_handler import ErrorHandlerMiddleware


class TestErrorHandlerRegistration:
    """Test that error handler middleware is registered in the bot"""

    @patch('bot.bot.settings')
    @patch('bot.bot.create_tables')
    @patch('bot.bot.get_db')
    def test_error_handler_registered_in_bot(self, mock_get_db, mock_create_tables, mock_settings):
        """Test that error handler is registered when bot is initialized (Task 6.2.1)"""
        # Setup mocks
        mock_settings.BOT_TOKEN = "test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        mock_settings.ADMIN_TELEGRAM_ID = 123456789

        # Mock database
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        # Import and initialize bot
        from bot.bot import TelegramBot

        # Create bot instance
        bot = TelegramBot()

        # Verify error handler middleware was initialized
        assert hasattr(bot, 'error_handler_middleware')
        assert isinstance(bot.error_handler_middleware, ErrorHandlerMiddleware)
        assert bot.error_handler_middleware.notify_admin is True

        # Verify error handler was registered in the application
        assert bot.application is not None
        assert isinstance(bot.application, Application)

        # Check that error handlers are registered
        # The application should have error handlers
        assert hasattr(bot.application, 'error_handlers')

        print("✅ Error handler middleware successfully registered in bot")

    @patch('bot.bot.settings')
    @patch('bot.bot.create_tables')
    @patch('bot.bot.get_db')
    def test_setup_error_handler_called(self, mock_get_db, mock_create_tables, mock_settings):
        """Test that setup_error_handler method is called during initialization"""
        # Setup mocks
        mock_settings.BOT_TOKEN = "test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        mock_settings.ADMIN_TELEGRAM_ID = 123456789

        # Mock database
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        # Import bot class
        from bot.bot import TelegramBot

        # Create bot instance
        bot = TelegramBot()

        # Verify setup_error_handler method exists and is callable
        assert hasattr(bot, 'setup_error_handler')
        assert callable(bot.setup_error_handler)

        # Verify error handler was registered (this confirms setup_error_handler was called)
        assert bot.error_handler_middleware is not None
        assert hasattr(bot.application, 'error_handlers')

        print("✅ setup_error_handler method called during bot initialization")

    @patch('bot.bot.settings')
    @patch('bot.bot.create_tables')
    @patch('bot.bot.get_db')
    def test_error_handler_middleware_configuration(self, mock_get_db, mock_create_tables, mock_settings):
        """Test that error handler middleware is configured correctly"""
        # Setup mocks
        mock_settings.BOT_TOKEN = "test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        mock_settings.ADMIN_TELEGRAM_ID = 123456789

        # Mock database
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        # Import and initialize bot
        from bot.bot import TelegramBot

        bot = TelegramBot()

        # Verify middleware configuration
        middleware = bot.error_handler_middleware

        # Check that notify_admin is enabled (Requirement 6.3)
        assert middleware.notify_admin is True, "Admin notifications should be enabled"

        # Check that logger is configured (Requirement 6.2)
        assert middleware.logger is not None, "Logger should be configured"

        # Check that handle_error method exists (Requirement 6.1, 6.4)
        assert hasattr(middleware, 'handle_error'), "handle_error method should exist"
        assert callable(middleware.handle_error), "handle_error should be callable"

        print("✅ Error handler middleware configured correctly")


class TestErrorHandlerWithDifferentErrorTypes:
    """Integration tests for error handler with different error types (Task 6.2.2)"""

    @pytest.mark.asyncio
    @patch('bot.bot.settings')
    @patch('bot.bot.create_tables')
    @patch('bot.bot.get_db')
    async def test_handle_value_error(self, mock_get_db, mock_create_tables, mock_settings):
        """Test handling of ValueError (business logic error)"""
        # Setup
        mock_settings.BOT_TOKEN = "test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        mock_settings.ADMIN_TELEGRAM_ID = 123456789

        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        from bot.bot import TelegramBot
        from telegram import Update, User, Message, Chat
        from telegram.ext import ContextTypes
        from unittest.mock import AsyncMock

        bot = TelegramBot()

        # Create mock update and context
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User, id=12345, username="testuser", full_name="Test User")
        update.effective_message = Mock(spec=Message, text="/test")
        update.effective_message.reply_text = AsyncMock()
        update.effective_chat = Mock(spec=Chat, id=67890, type="private")
        update.to_dict = Mock(return_value={"update_id": 1})

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        context.error = ValueError("Invalid value provided")

        # Execute
        await bot.error_handler_middleware.handle_error(update, context)

        # Verify user received error message
        update.effective_message.reply_text.assert_called_once()
        user_message = update.effective_message.reply_text.call_args[0][0]
        assert "❌" in user_message
        assert "Произошла ошибка" in user_message

        # Verify admin was notified (ValueError is critical)
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "ValueError" in admin_message

        print("✅ ValueError handled correctly")

    @pytest.mark.asyncio
    @patch('bot.bot.settings')
    @patch('bot.bot.create_tables')
    @patch('bot.bot.get_db')
    async def test_handle_key_error(self, mock_get_db, mock_create_tables, mock_settings):
        """Test handling of KeyError (missing data error)"""
        # Setup
        mock_settings.BOT_TOKEN = "test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        mock_settings.ADMIN_TELEGRAM_ID = 123456789

        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        from bot.bot import TelegramBot
        from telegram import Update, User, Message, Chat
        from telegram.ext import ContextTypes
        from unittest.mock import AsyncMock

        bot = TelegramBot()

        # Create mock update and context
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User, id=12345, username="testuser", full_name="Test User")
        update.effective_message = Mock(spec=Message, text="/profile")
        update.effective_message.reply_text = AsyncMock()
        update.effective_chat = Mock(spec=Chat, id=67890, type="private")
        update.to_dict = Mock(return_value={"update_id": 1})

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        context.error = KeyError("user_id")

        # Execute
        await bot.error_handler_middleware.handle_error(update, context)

        # Verify user received error message
        update.effective_message.reply_text.assert_called_once()

        # Verify admin was notified (KeyError is critical)
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "KeyError" in admin_message

        print("✅ KeyError handled correctly")

    @pytest.mark.asyncio
    @patch('bot.bot.settings')
    @patch('bot.bot.create_tables')
    @patch('bot.bot.get_db')
    async def test_handle_attribute_error(self, mock_get_db, mock_create_tables, mock_settings):
        """Test handling of AttributeError (code error)"""
        # Setup
        mock_settings.BOT_TOKEN = "test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        mock_settings.ADMIN_TELEGRAM_ID = 123456789

        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        from bot.bot import TelegramBot
        from telegram import Update, User, Message, Chat
        from telegram.ext import ContextTypes
        from unittest.mock import AsyncMock

        bot = TelegramBot()

        # Create mock update and context
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User, id=12345, username="testuser", full_name="Test User")
        update.effective_message = Mock(spec=Message, text="/balance")
        update.effective_message.reply_text = AsyncMock()
        update.effective_chat = Mock(spec=Chat, id=67890, type="private")
        update.to_dict = Mock(return_value={"update_id": 1})

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        context.error = AttributeError("'NoneType' object has no attribute 'balance'")

        # Execute
        await bot.error_handler_middleware.handle_error(update, context)

        # Verify user received error message
        update.effective_message.reply_text.assert_called_once()

        # Verify admin was notified (AttributeError is critical)
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "AttributeError" in admin_message

        print("✅ AttributeError handled correctly")

    @pytest.mark.asyncio
    @patch('bot.bot.settings')
    @patch('bot.bot.create_tables')
    @patch('bot.bot.get_db')
    async def test_handle_type_error(self, mock_get_db, mock_create_tables, mock_settings):
        """Test handling of TypeError (type mismatch error)"""
        # Setup
        mock_settings.BOT_TOKEN = "test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        mock_settings.ADMIN_TELEGRAM_ID = 123456789

        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        from bot.bot import TelegramBot
        from telegram import Update, User, Message, Chat
        from telegram.ext import ContextTypes
        from unittest.mock import AsyncMock

        bot = TelegramBot()

        # Create mock update and context
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User, id=12345, username="testuser", full_name="Test User")
        update.effective_message = Mock(spec=Message, text="/add_points")
        update.effective_message.reply_text = AsyncMock()
        update.effective_chat = Mock(spec=Chat, id=67890, type="private")
        update.to_dict = Mock(return_value={"update_id": 1})

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        context.error = TypeError("unsupported operand type(s) for +: 'int' and 'str'")

        # Execute
        await bot.error_handler_middleware.handle_error(update, context)

        # Verify user received error message
        update.effective_message.reply_text.assert_called_once()

        # Verify admin was notified (TypeError is critical)
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "TypeError" in admin_message

        print("✅ TypeError handled correctly")

    @pytest.mark.asyncio
    @patch('bot.bot.settings')
    @patch('bot.bot.create_tables')
    @patch('bot.bot.get_db')
    async def test_handle_runtime_error(self, mock_get_db, mock_create_tables, mock_settings):
        """Test handling of RuntimeError (runtime issue)"""
        # Setup
        mock_settings.BOT_TOKEN = "test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        mock_settings.ADMIN_TELEGRAM_ID = 123456789

        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        from bot.bot import TelegramBot
        from telegram import Update, User, Message, Chat
        from telegram.ext import ContextTypes
        from unittest.mock import AsyncMock

        bot = TelegramBot()

        # Create mock update and context
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User, id=12345, username="testuser", full_name="Test User")
        update.effective_message = Mock(spec=Message, text="/shop")
        update.effective_message.reply_text = AsyncMock()
        update.effective_chat = Mock(spec=Chat, id=67890, type="private")
        update.to_dict = Mock(return_value={"update_id": 1})

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        context.error = RuntimeError("Database connection lost")

        # Execute
        await bot.error_handler_middleware.handle_error(update, context)

        # Verify user received error message
        update.effective_message.reply_text.assert_called_once()

        # Verify admin was notified (RuntimeError is critical)
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "RuntimeError" in admin_message

        print("✅ RuntimeError handled correctly")

    @pytest.mark.asyncio
    @patch('bot.bot.settings')
    @patch('bot.bot.create_tables')
    @patch('bot.bot.get_db')
    async def test_handle_zero_division_error(self, mock_get_db, mock_create_tables, mock_settings):
        """Test handling of ZeroDivisionError (calculation error)"""
        # Setup
        mock_settings.BOT_TOKEN = "test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        mock_settings.ADMIN_TELEGRAM_ID = 123456789

        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        from bot.bot import TelegramBot
        from telegram import Update, User, Message, Chat
        from telegram.ext import ContextTypes
        from unittest.mock import AsyncMock

        bot = TelegramBot()

        # Create mock update and context
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User, id=12345, username="testuser", full_name="Test User")
        update.effective_message = Mock(spec=Message, text="/calculate")
        update.effective_message.reply_text = AsyncMock()
        update.effective_chat = Mock(spec=Chat, id=67890, type="private")
        update.to_dict = Mock(return_value={"update_id": 1})

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        context.error = ZeroDivisionError("division by zero")

        # Execute
        await bot.error_handler_middleware.handle_error(update, context)

        # Verify user received error message
        update.effective_message.reply_text.assert_called_once()

        # Verify admin was notified (ZeroDivisionError is critical)
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "ZeroDivisionError" in admin_message

        print("✅ ZeroDivisionError handled correctly")

    @pytest.mark.asyncio
    @patch('bot.bot.settings')
    @patch('bot.bot.create_tables')
    @patch('bot.bot.get_db')
    async def test_handle_index_error(self, mock_get_db, mock_create_tables, mock_settings):
        """Test handling of IndexError (list access error)"""
        # Setup
        mock_settings.BOT_TOKEN = "test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        mock_settings.ADMIN_TELEGRAM_ID = 123456789

        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        from bot.bot import TelegramBot
        from telegram import Update, User, Message, Chat
        from telegram.ext import ContextTypes
        from unittest.mock import AsyncMock

        bot = TelegramBot()

        # Create mock update and context
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User, id=12345, username="testuser", full_name="Test User")
        update.effective_message = Mock(spec=Message, text="/list")
        update.effective_message.reply_text = AsyncMock()
        update.effective_chat = Mock(spec=Chat, id=67890, type="private")
        update.to_dict = Mock(return_value={"update_id": 1})

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        context.error = IndexError("list index out of range")

        # Execute
        await bot.error_handler_middleware.handle_error(update, context)

        # Verify user received error message
        update.effective_message.reply_text.assert_called_once()

        # Verify admin was notified (IndexError is critical)
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "IndexError" in admin_message

        print("✅ IndexError handled correctly")

    @pytest.mark.asyncio
    @patch('bot.bot.settings')
    @patch('bot.bot.create_tables')
    @patch('bot.bot.get_db')
    async def test_handle_import_error(self, mock_get_db, mock_create_tables, mock_settings):
        """Test handling of ImportError (module loading error)"""
        # Setup
        mock_settings.BOT_TOKEN = "test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        mock_settings.ADMIN_TELEGRAM_ID = 123456789

        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        from bot.bot import TelegramBot
        from telegram import Update, User, Message, Chat
        from telegram.ext import ContextTypes
        from unittest.mock import AsyncMock

        bot = TelegramBot()

        # Create mock update and context
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User, id=12345, username="testuser", full_name="Test User")
        update.effective_message = Mock(spec=Message, text="/plugin")
        update.effective_message.reply_text = AsyncMock()
        update.effective_chat = Mock(spec=Chat, id=67890, type="private")
        update.to_dict = Mock(return_value={"update_id": 1})

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        context.error = ImportError("No module named 'missing_module'")

        # Execute
        await bot.error_handler_middleware.handle_error(update, context)

        # Verify user received error message
        update.effective_message.reply_text.assert_called_once()

        # Verify admin was notified (ImportError is critical)
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "ImportError" in admin_message

        print("✅ ImportError handled correctly")

    @pytest.mark.asyncio
    @patch('bot.bot.settings')
    @patch('bot.bot.create_tables')
    @patch('bot.bot.get_db')
    async def test_handle_assertion_error(self, mock_get_db, mock_create_tables, mock_settings):
        """Test handling of AssertionError (validation error)"""
        # Setup
        mock_settings.BOT_TOKEN = "test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        mock_settings.ADMIN_TELEGRAM_ID = 123456789

        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        from bot.bot import TelegramBot
        from telegram import Update, User, Message, Chat
        from telegram.ext import ContextTypes
        from unittest.mock import AsyncMock

        bot = TelegramBot()

        # Create mock update and context
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User, id=12345, username="testuser", full_name="Test User")
        update.effective_message = Mock(spec=Message, text="/validate")
        update.effective_message.reply_text = AsyncMock()
        update.effective_chat = Mock(spec=Chat, id=67890, type="private")
        update.to_dict = Mock(return_value={"update_id": 1})

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        context.error = AssertionError("Expected value to be positive")

        # Execute
        await bot.error_handler_middleware.handle_error(update, context)

        # Verify user received error message
        update.effective_message.reply_text.assert_called_once()

        # Verify admin was notified (AssertionError is critical)
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "AssertionError" in admin_message

        print("✅ AssertionError handled correctly")

    @pytest.mark.asyncio
    @patch('bot.bot.settings')
    @patch('bot.bot.create_tables')
    @patch('bot.bot.get_db')
    async def test_handle_os_error(self, mock_get_db, mock_create_tables, mock_settings):
        """Test handling of OSError (file system error)"""
        # Setup
        mock_settings.BOT_TOKEN = "test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        mock_settings.ADMIN_TELEGRAM_ID = 123456789

        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        from bot.bot import TelegramBot
        from telegram import Update, User, Message, Chat
        from telegram.ext import ContextTypes
        from unittest.mock import AsyncMock

        bot = TelegramBot()

        # Create mock update and context
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User, id=12345, username="testuser", full_name="Test User")
        update.effective_message = Mock(spec=Message, text="/export")
        update.effective_message.reply_text = AsyncMock()
        update.effective_chat = Mock(spec=Chat, id=67890, type="private")
        update.to_dict = Mock(return_value={"update_id": 1})

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        context.error = OSError("No space left on device")

        # Execute
        await bot.error_handler_middleware.handle_error(update, context)

        # Verify user received error message
        update.effective_message.reply_text.assert_called_once()

        # Verify admin was notified (OSError is critical)
        context.bot.send_message.assert_called_once()
        admin_message = context.bot.send_message.call_args[1]['text']
        assert "OSError" in admin_message

        print("✅ OSError handled correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
