#!/usr/bin/env python3
"""
Integration tests for Advanced Admin Commands
Tests the command handlers with real database integration
"""

import os
import sys
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.commands.advanced_admin_commands import AdvancedAdminCommands
from bot.middleware.dependency_injection import (
    Services,
    UserRepository,
    UserService,
    AdminService,
    ShopService,
    TransactionService,
)
from database.database import Base, get_db, User, ParsedTransaction, ParsingRule
from telegram import Update, User as TelegramUser, Message, Chat
from telegram.ext import ContextTypes
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from src.config import settings
from core.models.advanced_models import BroadcastResult
import tempfile


class _ServicesContextManager:
    """Wraps a Services object so it can be used with `with build_services()`."""

    def __init__(self, services):
        self._services = services

    def __enter__(self):
        return self._services

    def __exit__(self, *exc):
        return False


class TestAdvancedAdminCommandsIntegration:
    """Integration tests for advanced admin command handlers"""

    def setup_method(self):
        """Set up test database and fixtures for each test"""
        self.db_fd, self.db_path = tempfile.mkstemp()
        test_engine = create_engine(f'sqlite:///{self.db_path}')

        Base.metadata.create_all(test_engine)

        TestSession = sessionmaker(bind=test_engine)
        self.test_engine = test_engine
        self.db = TestSession()

        self._create_test_data()

        self._setup_fixtures()

    def teardown_method(self):
        """Clean up test database"""
        self.db.close()
        self.test_engine.dispose()
        os.close(self.db_fd)
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _create_test_data(self):
        """Create test data for integration tests"""
        admin_user = User(
            telegram_id=settings.ADMIN_TELEGRAM_ID,
            username="test_admin",
            first_name="Test Admin",
            balance=1000,
            is_admin=True
        )

        regular_user = User(
            telegram_id=12345,
            username="test_user",
            first_name="Test User",
            balance=150,
            total_purchases=3
        )

        self.db.add(admin_user)
        self.db.add(regular_user)

        rule1 = ParsingRule(
            id=1,
            bot_name="Shmalala",
            pattern=r"Монеты: \+(\d+)",
            multiplier=Decimal('1.0'),
            currency_type="coins",
            is_active=True
        )

        rule2 = ParsingRule(
            id=2,
            bot_name="GDcards",
            pattern=r"Очки: \+(\d+)",
            multiplier=Decimal('0.5'),
            currency_type="points",
            is_active=True
        )

        self.db.add(rule1)
        self.db.add(rule2)

        from datetime import datetime, timedelta
        now = datetime.utcnow()

        for i in range(10):
            transaction = ParsedTransaction(
                user_id=regular_user.id,
                source_bot="Shmalala" if i % 2 == 0 else "GDcards",
                original_amount=Decimal('50.0'),
                converted_amount=Decimal('50.0') if i % 2 == 0 else Decimal('25.0'),
                currency_type="coins" if i % 2 == 0 else "points",
                parsed_at=now - timedelta(hours=i),
                message_text=f"Test message {i}"
            )
            self.db.add(transaction)

        self.db.commit()

    def _setup_fixtures(self):
        """Set up command/test fixtures (after DB is ready)."""
        self.admin_commands = AdvancedAdminCommands()

        user_repo = UserRepository(self.db)
        services = Services(
            session=self.db,
            user_repo=user_repo,
            user_service=UserService(user_repo),
            admin_service=AdminService(user_repo),
            shop_service=ShopService(user_repo),
            transaction_service=TransactionService(user_repo),
        )
        services.admin_service.is_admin = Mock(return_value=True)
        self.services = services

        self.mock_user = Mock(spec=TelegramUser)
        self.mock_user.id = settings.ADMIN_TELEGRAM_ID
        self.mock_user.username = "test_admin"
        self.mock_user.first_name = "Test Admin"

        self.mock_message = Mock(spec=Message)
        self.mock_message.reply_text = AsyncMock()

        self.mock_chat = Mock(spec=Chat)
        self.mock_chat.id = 12345

        self.mock_update = Mock(spec=Update)
        self.mock_update.effective_user = self.mock_user
        self.mock_update.message = self.mock_message
        self.mock_update.effective_chat = self.mock_chat

        self.mock_context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        self.mock_context.args = []

    def _patch_services(self):
        return patch(
            'bot.commands.advanced_admin_commands.build_services',
            return_value=_ServicesContextManager(self.services),
        )

    @pytest.mark.asyncio
    async def test_parsing_stats_integration(self):
        """Test parsing_stats command with real database"""
        with self._patch_services():
            await self.admin_commands.parsing_stats_command(self.mock_update, self.mock_context)

            self.mock_message.reply_text.assert_called_once()
            call_args = self.mock_message.reply_text.call_args
            message_text = call_args[0][0]

            assert "📊 <b>Статистика парсинга</b>" in message_text
            assert "Всего транзакций: 10" in message_text
            assert "Shmalala" in message_text
            assert "GDcards" in message_text

    @pytest.mark.asyncio
    async def test_user_stats_integration(self):
        """Test user_stats command with real database"""
        self.mock_context.args = ["test_user"]

        with self._patch_services():
            await self.admin_commands.user_stats_command(self.mock_update, self.mock_context)

            self.mock_message.reply_text.assert_called_once()
            call_args = self.mock_message.reply_text.call_args
            message_text = call_args[0][0]

            assert "👤 <b>Статистика пользователя</b>" in message_text
            assert "@test_user" in message_text
            assert "Баланс:" in message_text
            assert "150.00" in message_text
            assert "Покупок: 3" in message_text

    @pytest.mark.asyncio
    async def test_broadcast_integration(self):
        """Test broadcast command with real database"""
        self.mock_context.args = ["Test", "broadcast", "message"]

        result = BroadcastResult(
            total_users=2,
            successful_sends=2,
            failed_sends=0,
            errors=[],
            completion_message="Broadcast completed",
            execution_time=1.5
        )
        mock_broadcast_service = Mock()
        mock_broadcast_service.broadcast_to_all = AsyncMock(return_value=result)

        with self._patch_services(), \
             patch('core.services.broadcast_service.BroadcastService',
                   return_value=mock_broadcast_service):

            await self.admin_commands.broadcast_command(self.mock_update, self.mock_context)

            mock_broadcast_service.broadcast_to_all.assert_called_once_with(
                "Test broadcast message", settings.ADMIN_TELEGRAM_ID
            )

            assert self.mock_message.reply_text.call_count == 2

            first_call = self.mock_message.reply_text.call_args_list[0]
            confirmation_text = first_call[0][0]
            assert "📢 <b>Начинаю рассылку...</b>" in confirmation_text

            second_call = self.mock_message.reply_text.call_args_list[1]
            result_text = second_call[0][0]
            assert "✅ <b>Рассылка завершена!</b>" in result_text
            assert "Всего пользователей: 2" in result_text

    @pytest.mark.asyncio
    async def test_non_admin_access_integration(self):
        """Test that non-admin users are properly rejected"""
        self.mock_user.id = 99999
        self.services.admin_service.is_admin = Mock(return_value=False)

        with self._patch_services():
            await self.admin_commands.parsing_stats_command(self.mock_update, self.mock_context)

            self.mock_message.reply_text.assert_called_once()
            call_args = self.mock_message.reply_text.call_args
            message_text = call_args[0][0]
            assert "❌ <b>Доступ запрещен</b>" in message_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
