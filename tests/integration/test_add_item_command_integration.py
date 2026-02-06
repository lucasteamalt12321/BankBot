"""
Integration test for /add_item command handler
Tests the complete workflow from command to database
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal
from telegram import Update, Message, User as TelegramUser
from telegram.ext import ContextTypes

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.commands.advanced_admin_commands import AdvancedAdminCommands
from database.database import get_db, User, ShopItem
from core.managers.shop_manager import ShopManager


class TestAddItemCommandIntegration:
    """Integration tests for the /add_item command handler"""
    
    @pytest.fixture
    def mock_update(self):
        """Create a mock Telegram update"""
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=TelegramUser)
        update.effective_user.id = 12345
        update.effective_user.username = "admin_user"
        update.effective_user.first_name = "Admin"
        
        update.message = Mock(spec=Message)
        update.message.reply_text = AsyncMock()
        
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock context"""
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        return context
    
    @pytest.fixture
    def admin_commands(self):
        """Create AdvancedAdminCommands instance with mocked admin system"""
        with patch('bot.advanced_admin_commands.AdminSystem') as mock_admin_system:
            mock_admin_system.return_value.is_admin.return_value = True
            return AdvancedAdminCommands()
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session"""
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None  # No existing item
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        db.close = Mock()
        return db
    
    @pytest.mark.asyncio
    async def test_add_item_integration_success(self, admin_commands, mock_update, mock_context, mock_db_session):
        """Test complete integration of add_item command with ShopManager"""
        mock_context.args = ["Integration", "Test", "Item", "150", "sticker"]
        
        # Mock the new item that will be created
        new_item = Mock()
        new_item.id = 10
        new_item.name = "Integration Test Item"
        new_item.price = 150
        new_item.item_type = "sticker"
        new_item.description = "Динамически созданный товар типа sticker"
        new_item.is_active = True
        
        mock_db_session.refresh.side_effect = lambda item: setattr(item, 'id', 10)
        
        with patch('bot.advanced_admin_commands.get_db') as mock_get_db, \
             patch('core.shop_manager.ShopItem') as mock_shop_item_class:
            
            mock_get_db.return_value.__next__.return_value = mock_db_session
            mock_shop_item_class.return_value = new_item
            
            await admin_commands.add_item_command(mock_update, mock_context)
            
            # Verify database operations were called
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()
            mock_db_session.refresh.assert_called_once()
            
            # Verify success message was sent
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "✅" in call_args[0][0]
            assert "Integration Test Item" in call_args[0][0]
            assert "150 монет" in call_args[0][0]
            assert "sticker" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_add_item_integration_duplicate_name(self, admin_commands, mock_update, mock_context, mock_db_session):
        """Test integration with duplicate name detection"""
        mock_context.args = ["Existing", "Item", "100", "admin"]
        
        # Mock existing item in database
        existing_item = Mock()
        existing_item.name = "Existing Item"
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_item
        
        with patch('bot.advanced_admin_commands.get_db') as mock_get_db:
            mock_get_db.return_value.__next__.return_value = mock_db_session
            
            await admin_commands.add_item_command(mock_update, mock_context)
            
            # Verify no database modifications were made
            mock_db_session.add.assert_not_called()
            mock_db_session.commit.assert_not_called()
            
            # Verify error message was sent
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "❌" in call_args[0][0]
            assert "Товар уже существует" in call_args[0][0]
            assert "Existing Item" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_add_item_integration_all_item_types(self, admin_commands, mock_update, mock_context, mock_db_session):
        """Test integration with all valid item types"""
        item_types = ["sticker", "admin", "mention_all", "custom"]
        
        for item_type in item_types:
            mock_context.args = ["Test", item_type.title(), "100", item_type]
            
            # Reset mocks
            mock_db_session.reset_mock()
            mock_update.message.reply_text.reset_mock()
            
            # Mock the new item
            new_item = Mock()
            new_item.id = 1
            new_item.name = f"Test {item_type.title()}"
            new_item.price = 100
            new_item.item_type = item_type
            new_item.description = f"Динамически созданный товар типа {item_type}"
            new_item.is_active = True
            
            with patch('bot.advanced_admin_commands.get_db') as mock_get_db, \
                 patch('core.shop_manager.ShopItem') as mock_shop_item_class:
                
                mock_get_db.return_value.__next__.return_value = mock_db_session
                mock_shop_item_class.return_value = new_item
                
                await admin_commands.add_item_command(mock_update, mock_context)
                
                # Verify success for each type
                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args
                assert "✅" in call_args[0][0]
                assert item_type in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_add_item_integration_database_error(self, admin_commands, mock_update, mock_context, mock_db_session):
        """Test integration with database error handling"""
        mock_context.args = ["Error", "Test", "100", "sticker"]
        
        # Mock database error
        mock_db_session.commit.side_effect = Exception("Database connection failed")
        
        with patch('bot.advanced_admin_commands.get_db') as mock_get_db, \
             patch('core.shop_manager.ShopItem') as mock_shop_item_class:
            
            mock_get_db.return_value.__next__.return_value = mock_db_session
            mock_shop_item_class.return_value = Mock()
            
            await admin_commands.add_item_command(mock_update, mock_context)
            
            # Verify rollback was called
            mock_db_session.rollback.assert_called_once()
            
            # Verify error message was sent
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "❌" in call_args[0][0]
            assert "Ошибка" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_add_item_integration_complex_name_parsing(self, admin_commands, mock_update, mock_context, mock_db_session):
        """Test integration with complex name parsing scenarios"""
        test_cases = [
            # (args, expected_name)
            (["Simple", "Name", "100", "sticker"], "Simple Name"),
            (['"Quoted', 'Name"', "200", "admin"], "Quoted Name"),
            (["'Single", "Quoted'", "300", "mention_all"], "Single Quoted"),
            (["Very", "Long", "Item", "Name", "With", "Many", "Words", "400", "custom"], "Very Long Item Name With Many Words"),
        ]
        
        for args, expected_name in test_cases:
            mock_context.args = args
            
            # Reset mocks
            mock_db_session.reset_mock()
            mock_update.message.reply_text.reset_mock()
            
            # Mock the new item
            new_item = Mock()
            new_item.id = 1
            new_item.name = expected_name
            new_item.price = int(args[-2])
            new_item.item_type = args[-1]
            new_item.description = f"Динамически созданный товар типа {args[-1]}"
            new_item.is_active = True
            
            with patch('bot.advanced_admin_commands.get_db') as mock_get_db, \
                 patch('core.shop_manager.ShopItem') as mock_shop_item_class:
                
                mock_get_db.return_value.__next__.return_value = mock_db_session
                mock_shop_item_class.return_value = new_item
                
                await admin_commands.add_item_command(mock_update, mock_context)
                
                # Verify success message contains the expected name
                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args
                assert "✅" in call_args[0][0]
                assert expected_name in call_args[0][0]


if __name__ == "__main__":
    pytest.main([__file__])