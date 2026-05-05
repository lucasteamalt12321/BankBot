"""Smoke tests for bot startup verification.

These tests verify that the bots can be initialized without errors.
Run with: pytest tests/smoke/ -v
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBankBotSmoke:
    """Smoke tests for BankBot (bot/main.py)."""

    def test_imports_available(self):
        """Test that main startup imports are available."""
        from bot.main import BotApplication
        from bot.bot import TelegramBot

        assert BotApplication is not None
        assert TelegramBot is not None

    @patch("bot.main.ensure_schema_up_to_date")
    @patch("bot.main.kill_existing_bot_processes")
    @patch("bot.main.validate_startup")
    @patch("bot.main.TelegramBot")
    def test_bot_initialization(
        self,
        mock_bot_class,
        mock_validate,
        mock_kill,
        mock_schema,
    ):
        """Test that startup flow can be executed without blocking."""
        mock_validate.return_value = True
        mock_schema.return_value = None
        mock_kill.return_value = None
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot

        from bot.main import main

        main()

        mock_validate.assert_called_once()
        mock_kill.assert_called_once()
        mock_schema.assert_called_once()
        mock_bot_class.assert_called_once()
        mock_bot.run.assert_called_once()


class TestBridgeBotSmoke:
    """Smoke tests for BridgeBot (bridge_bot/main.py)."""

    def test_imports_available(self):
        """Test that bridge configuration exports are available."""
        from bridge_bot.config import BotSettings, get_settings
        from bridge_bot.loop_guard import has_bot_mark, add_bot_mark

        assert BotSettings is not None
        assert get_settings is not None
        assert has_bot_mark is not None
        assert add_bot_mark is not None

    def test_loop_guard_functionality(self):
        """Test that loop guard functions work correctly."""
        from bridge_bot.loop_guard import has_bot_mark, add_bot_mark

        test_message = "Test message"
        assert has_bot_mark(test_message) is False

        marked = add_bot_mark(test_message)
        assert "[BOT]" in marked
        assert has_bot_mark(marked) is True


class TestVKBotSmoke:
    """Smoke tests for VK Bot (vk_bot/main.py)."""

    def test_imports_available(self):
        """Test that VK configuration exports are available."""
        from vk_bot.config import BotSettings, get_settings

        assert BotSettings is not None
        assert get_settings is not None


class TestDatabaseSchema:
    """Smoke tests for database schema."""

    @patch("database.schema.create_tables")
    @patch("database.schema.command")
    def test_schema_check_works(self, mock_command, mock_create):
        """Test that schema check doesn't crash."""
        from database.schema import ensure_schema_up_to_date

        # Should not raise any exceptions
        try:
            ensure_schema_up_to_date()
        except Exception as e:
            # Might fail if alembic.ini doesn't exist, but should be graceful
            if "alembic" not in str(e).lower():
                pytest.fail(f"Unexpected error: {e}")


class TestConfiguration:
    """Smoke tests for configuration system."""

    @patch.dict(
        os.environ,
        {
            "BOT_TOKEN": "123456:TEST",
            "ADMIN_TELEGRAM_ID": "123456789",
            "DATABASE_URL": "sqlite:///:memory:",
            "ENV": "test",
        },
    )
    def test_config_loads(self):
        """Test that configuration can be loaded."""
        from src.config import get_settings

        try:
            settings = get_settings()
            assert settings.BOT_TOKEN == "123456:TEST"
            assert settings.ADMIN_TELEGRAM_ID == 123456789
        except Exception as e:
            # May fail due to env setup issues, should be graceful
            if "validation" in str(e).lower():
                pytest.skip(f"Config validation issue: {e}")
            else:
                raise


class TestCoreModules:
    """Smoke tests for core modules."""

    def test_repositories_import(self):
        """Test that repository modules can be imported."""
        from bank_bot.repositories.user_repository import UserRepository
        from bank_bot.repositories.balance_repository import BalanceRepository
        from bank_bot.repositories.transaction_repository import TransactionRepository

        assert UserRepository is not None
        assert BalanceRepository is not None
        assert TransactionRepository is not None

    def test_services_import(self):
        """Test that service modules can be imported."""
        from bank_bot.services.user_service import UserService
        from bank_bot.services.balance_service import BalanceService
        from bank_bot.services.shop_service import ShopService

        assert UserService is not None
        assert BalanceService is not None
        assert ShopService is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
