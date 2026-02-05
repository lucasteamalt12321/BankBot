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
from database.database import get_db, engine, User, ParsedTransaction, ParsingRule
from telegram import Update, User as TelegramUser, Message, Chat
from telegram.ext import ContextTypes
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import tempfile


class TestAdvancedAdminCommandsIntegration:
    """Integration tests for advanced admin command handlers"""
    
    @pytest.fixture(autouse=True)
    def setup_database(self):
        """Set up test database"""
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp()
        test_engine = create_engine(f'sqlite:///{self.db_path}')
        
        # Create tables
        from database.database import Base
        Base.metadata.create_all(test_engine)
        
        # Create session
        TestSession = sessionmaker(bind=test_engine)
        self.db = TestSession()
        
        # Create test data
        self._create_test_data()
        
        yield
        
        # Cleanup
        self.db.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def _create_test_data(self):
        """Create test data for integration tests"""
        # Create test users
        admin_user = User(
            telegram_id=2091908459,  # Admin user
            username="test_admin",
            first_name="Test Admin",
            balance=Decimal('1000.00'),
            is_admin=True
        )
        
        regular_user = User(
            telegram_id=12345,
            username="test_user",
            first_name="Test User",
            balance=Decimal('150.75'),
            total_purchases=3
        )
        
        self.db.add(admin_user)
        self.db.add(regular_user)
        
        # Create parsing rules
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
        
        # Create parsed transactions
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
    
    def setup_method(self):
        """Set up test fixtures for each test"""
        self.admin_commands = AdvancedAdminCommands()
        
        # Mock admin system to use our test admin
        self.admin_commands.admin_system = Mock()
        self.admin_commands.admin_system.is_admin.return_value = True
        
        # Create mock update and context
        self.mock_user = Mock(spec=TelegramUser)
        self.mock_user.id = 2091908459  # Admin user ID
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
    
    @pytest.mark.asyncio
    async def test_parsing_stats_integration(self):
        """Test parsing_stats command with real database"""
        with patch('bot.advanced_admin_commands.get_db') as mock_get_db:
            mock_get_db.return_value.__next__.return_value = self.db
            
            # Execute command
            await self.admin_commands.parsing_stats_command(self.mock_update, self.mock_context)
            
            # Verify response was sent
            self.mock_message.reply_text.assert_called_once()
            call_args = self.mock_message.reply_text.call_args
            message_text = call_args[0][0]
            
            # Check that statistics are displayed
            assert "📊 <b>Статистика парсинга</b>" in message_text
            assert "Всего транзакций: 10" in message_text
            assert "Shmalala" in message_text
            assert "GDcards" in message_text
    
    @pytest.mark.asyncio
    async def test_user_stats_integration(self):
        """Test user_stats command with real database"""
        self.mock_context.args = ["test_user"]
        
        with patch('bot.advanced_admin_commands.get_db') as mock_get_db:
            mock_get_db.return_value.__next__.return_value = self.db
            
            # Execute command
            await self.admin_commands.user_stats_command(self.mock_update, self.mock_context)
            
            # Verify response was sent
            self.mock_message.reply_text.assert_called_once()
            call_args = self.mock_message.reply_text.call_args
            message_text = call_args[0][0]
            
            # Check that user statistics are displayed
            assert "👤 <b>Статистика пользователя</b>" in message_text
            assert "Username: @test_user" in message_text
            assert "Текущий баланс: 150.75 монет" in message_text
            assert "Всего покупок: 3" in message_text
    
    @pytest.mark.asyncio
    async def test_broadcast_integration(self):
        """Test broadcast command with real database"""
        self.mock_context.args = ["Test", "broadcast", "message"]
        
        with patch('bot.advanced_admin_commands.get_db') as mock_get_db, \
             patch('bot.advanced_admin_commands.BroadcastSystem') as mock_broadcast_system_class:
            
            mock_get_db.return_value.__next__.return_value = self.db
            
            # Mock broadcast system
            mock_broadcast_system = Mock()
            mock_broadcast_system_class.return_value = mock_broadcast_system
            
            # Mock AdminManager with successful broadcast
            from core.models.advanced_models import BroadcastResult
            mock_result = BroadcastResult(
                total_users=2,
                successful_sends=2,
                failed_sends=0,
                errors=[],
                completion_message="Broadcast completed",
                execution_time=1.5
            )
            
            with patch('bot.advanced_admin_commands.AdminManager') as mock_admin_manager_class:
                mock_admin_manager = Mock()
                mock_admin_manager.broadcast_admin_message = AsyncMock(return_value=mock_result)
                mock_admin_manager_class.return_value = mock_admin_manager
                
                # Execute command
                await self.admin_commands.broadcast_command(self.mock_update, self.mock_context)
                
                # Verify broadcast was called
                mock_admin_manager.broadcast_admin_message.assert_called_once_with(
                    "Test broadcast message", 2091908459
                )
                
                # Verify two messages were sent (confirmation + result)
                assert self.mock_message.reply_text.call_count == 2
                
                # Check confirmation message
                first_call = self.mock_message.reply_text.call_args_list[0]
                confirmation_text = first_call[0][0]
                assert "📢 <b>Начинаю рассылку...</b>" in confirmation_text
                
                # Check result message
                second_call = self.mock_message.reply_text.call_args_list[1]
                result_text = second_call[0][0]
                assert "✅ <b>Рассылка завершена!</b>" in result_text
                assert "Всего пользователей: 2" in result_text
    
    @pytest.mark.asyncio
    async def test_non_admin_access_integration(self):
        """Test that non-admin users are properly rejected"""
        # Set up non-admin user
        self.mock_user.id = 99999  # Non-admin ID
        self.admin_commands.admin_system.is_admin.return_value = False
        
        with patch('bot.advanced_admin_commands.get_db') as mock_get_db:
            mock_get_db.return_value.__next__.return_value = self.db
            
            # Test parsing_stats command
            await self.admin_commands.parsing_stats_command(self.mock_update, self.mock_context)
            
            # Verify access denied message
            self.mock_message.reply_text.assert_called_once()
            call_args = self.mock_message.reply_text.call_args
            message_text = call_args[0][0]
            assert "❌ <b>Доступ запрещен</b>" in message_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])