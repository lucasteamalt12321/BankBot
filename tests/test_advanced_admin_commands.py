#!/usr/bin/env python3
"""
Test suite for Advanced Admin Commands
Tests the implementation of /parsing_stats, /broadcast, and /user_stats commands
"""

import os
import sys
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.advanced_admin_commands import AdvancedAdminCommands
from core.advanced_models import ParsingStats, UserStats, BroadcastResult
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes


class TestAdvancedAdminCommands:
    """Test suite for advanced admin command handlers"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.admin_commands = AdvancedAdminCommands()
        
        # Mock admin system
        self.admin_commands.admin_system = Mock()
        
        # Create mock update and context
        self.mock_user = Mock(spec=User)
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
    async def test_parsing_stats_command_admin_access(self):
        """Test parsing_stats command with admin access"""
        # Setup
        self.admin_commands.admin_system.is_admin.return_value = True
        
        # Mock parsing stats data
        mock_stats = ParsingStats(
            timeframe="24h",
            period_name="Last 24 Hours",
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-02T00:00:00",
            total_transactions=100,
            successful_parses=95,
            failed_parses=5,
            total_amount_converted=1500.50,
            success_rate=95.0,
            active_bots=2,
            total_configured_bots=3,
            bot_statistics=[
                {
                    'bot_name': 'Shmalala',
                    'transaction_count': 60,
                    'total_original_amount': 600.0,
                    'total_converted_amount': 600.0,
                    'successful_parses': 60,
                    'failed_parses': 0,
                    'currency_type': 'coins',
                    'percentage_of_total': 60.0
                }
            ],
            parsing_rules=[
                {
                    'id': 1,
                    'bot_name': 'Shmalala',
                    'pattern': r'Монеты: \+(\d+)',
                    'multiplier': 1.0,
                    'currency_type': 'coins',
                    'is_active': True
                }
            ]
        )
        
        with patch('bot.advanced_admin_commands.get_db') as mock_get_db, \
             patch('bot.advanced_admin_commands.AdminManager') as mock_admin_manager_class:
            
            # Setup mocks
            mock_db = Mock()
            mock_get_db.return_value.__next__.return_value = mock_db
            
            mock_admin_manager = Mock()
            mock_admin_manager.get_parsing_stats = AsyncMock(return_value=mock_stats)
            mock_admin_manager_class.return_value = mock_admin_manager
            
            # Execute
            await self.admin_commands.parsing_stats_command(self.mock_update, self.mock_context)
            
            # Verify
            self.admin_commands.admin_system.is_admin.assert_called_once_with(2091908459)
            mock_admin_manager.get_parsing_stats.assert_called_once_with("24h")
            
            # Check that reply was sent with statistics
            self.mock_message.reply_text.assert_called_once()
            call_args = self.mock_message.reply_text.call_args
            message_text = call_args[0][0]
            
            assert "📊 <b>Статистика парсинга</b>" in message_text
            assert "Всего транзакций: 100" in message_text
            assert "Успешных парсингов: 95" in message_text
            assert "Процент успеха: 95.0%" in message_text
            assert "Shmalala" in message_text
    
    @pytest.mark.asyncio
    async def test_parsing_stats_command_non_admin_access(self):
        """Test parsing_stats command with non-admin access"""
        # Setup
        self.admin_commands.admin_system.is_admin.return_value = False
        
        # Execute
        await self.admin_commands.parsing_stats_command(self.mock_update, self.mock_context)
        
        # Verify
        self.admin_commands.admin_system.is_admin.assert_called_once_with(2091908459)
        
        # Check that access denied message was sent
        self.mock_message.reply_text.assert_called_once()
        call_args = self.mock_message.reply_text.call_args
        message_text = call_args[0][0]
        
        assert "❌ <b>Доступ запрещен</b>" in message_text
        assert "только администраторам" in message_text
    
    @pytest.mark.asyncio
    async def test_broadcast_command_admin_access(self):
        """Test broadcast command with admin access"""
        # Setup
        self.admin_commands.admin_system.is_admin.return_value = True
        self.mock_context.args = ["Важное", "объявление", "для", "всех"]
        
        # Mock broadcast result
        mock_result = BroadcastResult(
            total_users=100,
            successful_sends=95,
            failed_sends=5,
            errors=[],
            completion_message="Broadcast completed successfully",
            execution_time=2.5
        )
        
        with patch('bot.advanced_admin_commands.get_db') as mock_get_db, \
             patch('bot.advanced_admin_commands.BroadcastSystem') as mock_broadcast_system_class, \
             patch('bot.advanced_admin_commands.AdminManager') as mock_admin_manager_class:
            
            # Setup mocks
            mock_db = Mock()
            mock_get_db.return_value.__next__.return_value = mock_db
            
            mock_broadcast_system = Mock()
            mock_broadcast_system_class.return_value = mock_broadcast_system
            
            mock_admin_manager = Mock()
            mock_admin_manager.broadcast_admin_message = AsyncMock(return_value=mock_result)
            mock_admin_manager_class.return_value = mock_admin_manager
            
            # Execute
            await self.admin_commands.broadcast_command(self.mock_update, self.mock_context)
            
            # Verify
            self.admin_commands.admin_system.is_admin.assert_called_once_with(2091908459)
            mock_admin_manager.broadcast_admin_message.assert_called_once_with(
                "Важное объявление для всех", 2091908459
            )
            
            # Check that confirmation and result messages were sent
            assert self.mock_message.reply_text.call_count == 2
            
            # Check confirmation message
            first_call = self.mock_message.reply_text.call_args_list[0]
            confirmation_text = first_call[0][0]
            assert "📢 <b>Начинаю рассылку...</b>" in confirmation_text
            
            # Check result message
            second_call = self.mock_message.reply_text.call_args_list[1]
            result_text = second_call[0][0]
            assert "✅ <b>Рассылка завершена!</b>" in result_text
            assert "Всего пользователей: 100" in result_text
            assert "Успешно доставлено: 95" in result_text
    
    @pytest.mark.asyncio
    async def test_broadcast_command_no_message(self):
        """Test broadcast command without message text"""
        # Setup
        self.admin_commands.admin_system.is_admin.return_value = True
        self.mock_context.args = []
        
        # Execute
        await self.admin_commands.broadcast_command(self.mock_update, self.mock_context)
        
        # Verify
        self.mock_message.reply_text.assert_called_once()
        call_args = self.mock_message.reply_text.call_args
        message_text = call_args[0][0]
        
        assert "❌ <b>Не указан текст сообщения</b>" in message_text
        assert "/broadcast <текст_сообщения>" in message_text
    
    @pytest.mark.asyncio
    async def test_user_stats_command_admin_access(self):
        """Test user_stats command with admin access"""
        # Setup
        self.admin_commands.admin_system.is_admin.return_value = True
        self.mock_context.args = ["@test_user"]
        
        # Mock user stats data
        mock_user_stats = UserStats(
            user_id=12345,
            username="test_user",
            first_name="Test User",
            current_balance=150.75,
            total_purchases=5,
            total_earned=500.0,
            total_parsing_earnings=200.0,
            last_activity="2024-01-02T10:30:00",
            created_at="2024-01-01T00:00:00",
            active_subscriptions=[
                {
                    'type': 'sticker_unlimited',
                    'expires_at': '2024-01-03T00:00:00',
                    'description': 'Unlimited Sticker Access'
                }
            ],
            parsing_transaction_history=[
                {
                    'id': 1,
                    'source_bot': 'Shmalala',
                    'original_amount': 50.0,
                    'converted_amount': 50.0,
                    'currency_type': 'coins',
                    'parsed_at': '2024-01-02T09:00:00',
                    'message_preview': 'Монеты: +50'
                }
            ],
            recent_purchases=[
                {
                    'id': 1,
                    'item_name': 'Stickers',
                    'price_paid': 100.0,
                    'purchased_at': '2024-01-01T12:00:00',
                    'expires_at': '2024-01-02T12:00:00',
                    'is_active': True
                }
            ],
            is_admin=False,
            is_vip=False,
            daily_streak=3
        )
        
        with patch('bot.advanced_admin_commands.get_db') as mock_get_db, \
             patch('bot.advanced_admin_commands.AdminManager') as mock_admin_manager_class:
            
            # Setup mocks
            mock_db = Mock()
            mock_get_db.return_value.__next__.return_value = mock_db
            
            mock_admin_manager = Mock()
            mock_admin_manager.get_user_stats = AsyncMock(return_value=mock_user_stats)
            mock_admin_manager_class.return_value = mock_admin_manager
            
            # Execute
            await self.admin_commands.user_stats_command(self.mock_update, self.mock_context)
            
            # Verify
            self.admin_commands.admin_system.is_admin.assert_called_once_with(2091908459)
            mock_admin_manager.get_user_stats.assert_called_once_with("@test_user")
            
            # Check that reply was sent with user statistics
            self.mock_message.reply_text.assert_called_once()
            call_args = self.mock_message.reply_text.call_args
            message_text = call_args[0][0]
            
            assert "👤 <b>Статистика пользователя</b>" in message_text
            assert "ID: 12345" in message_text
            assert "Username: @test_user" in message_text
            assert "Текущий баланс: 150.75 монет" in message_text
            assert "Всего покупок: 5" in message_text
            assert "Unlimited Sticker Access" in message_text
            assert "Shmalala" in message_text
    
    @pytest.mark.asyncio
    async def test_user_stats_command_user_not_found(self):
        """Test user_stats command when user is not found"""
        # Setup
        self.admin_commands.admin_system.is_admin.return_value = True
        self.mock_context.args = ["@nonexistent_user"]
        
        with patch('bot.advanced_admin_commands.get_db') as mock_get_db, \
             patch('bot.advanced_admin_commands.AdminManager') as mock_admin_manager_class:
            
            # Setup mocks
            mock_db = Mock()
            mock_get_db.return_value.__next__.return_value = mock_db
            
            mock_admin_manager = Mock()
            mock_admin_manager.get_user_stats = AsyncMock(return_value=None)
            mock_admin_manager_class.return_value = mock_admin_manager
            
            # Execute
            await self.admin_commands.user_stats_command(self.mock_update, self.mock_context)
            
            # Verify
            self.mock_message.reply_text.assert_called_once()
            call_args = self.mock_message.reply_text.call_args
            message_text = call_args[0][0]
            
            assert "❌ <b>Пользователь не найден</b>" in message_text
            assert "@nonexistent_user" in message_text
    
    @pytest.mark.asyncio
    async def test_user_stats_command_no_username(self):
        """Test user_stats command without username parameter"""
        # Setup
        self.admin_commands.admin_system.is_admin.return_value = True
        self.mock_context.args = []
        
        # Execute
        await self.admin_commands.user_stats_command(self.mock_update, self.mock_context)
        
        # Verify
        self.mock_message.reply_text.assert_called_once()
        call_args = self.mock_message.reply_text.call_args
        message_text = call_args[0][0]
        
        assert "❌ <b>Не указан пользователь</b>" in message_text
        assert "/user_stats <@username>" in message_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])