"""
Test suite for /add_item command handler
Tests the command interface for dynamic shop item creation
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from decimal import Decimal
from telegram import Update, Message, User as TelegramUser
from telegram.ext import ContextTypes

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.commands.advanced_admin_commands import AdvancedAdminCommands


class TestAddItemCommand:
    """Test cases for the /add_item command handler"""

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
        """Create AdvancedAdminCommands instance with mocked dependencies"""
        with patch('bot.commands.advanced_admin_commands.AdminSystem') as mock_admin_system:
            mock_admin_system.return_value.is_admin.return_value = True
            return AdvancedAdminCommands()

    @pytest.mark.asyncio
    async def test_add_item_success_sticker_type(self, admin_commands, mock_update, mock_context):
        """Test successful addition of sticker type item"""
        mock_context.args = ["Premium", "Stickers", "100", "sticker"]

        mock_db = Mock()
        mock_shop_manager = Mock()
        mock_shop_manager.add_item = AsyncMock(return_value={
            "success": True,
            "message": "Товар 'Premium Stickers' успешно добавлен в магазин",
            "item_id": 5,
            "item": {
                "id": 5,
                "name": "Premium Stickers",
                "price": 100,
                "item_type": "sticker",
                "description": "Динамически созданный товар типа sticker",
                "is_active": True
            }
        })

        with patch('bot.commands.advanced_admin_commands.get_db') as mock_get_db, \
             patch('bot.commands.advanced_admin_commands.ShopManager') as mock_shop_manager_class:

            mock_get_db.return_value.__next__.return_value = mock_db
            mock_shop_manager_class.return_value = mock_shop_manager

            await admin_commands.add_item_command(mock_update, mock_context)

            # Verify ShopManager.add_item was called with correct parameters
            mock_shop_manager.add_item.assert_called_once_with("Premium Stickers", Decimal("100"), "sticker")

            # Verify success message was sent
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "✅" in call_args[0][0]  # Success emoji
            assert "Premium Stickers" in call_args[0][0]
            assert "100 монет" in call_args[0][0]
            assert "sticker" in call_args[0][0]
            assert call_args[1]["parse_mode"] == "HTML"

    @pytest.mark.asyncio
    async def test_add_item_success_admin_type(self, admin_commands, mock_update, mock_context):
        """Test successful addition of admin type item"""
        mock_context.args = ["VIP", "Status", "500", "admin"]

        mock_db = Mock()
        mock_shop_manager = Mock()
        mock_shop_manager.add_item = AsyncMock(return_value={
            "success": True,
            "message": "Товар 'VIP Status' успешно добавлен в магазин",
            "item_id": 6,
            "item": {
                "id": 6,
                "name": "VIP Status",
                "price": 500,
                "item_type": "admin",
                "description": "Динамически созданный товар типа admin",
                "is_active": True
            }
        })

        with patch('bot.commands.advanced_admin_commands.get_db') as mock_get_db, \
             patch('bot.commands.advanced_admin_commands.ShopManager') as mock_shop_manager_class:

            mock_get_db.return_value.__next__.return_value = mock_db
            mock_shop_manager_class.return_value = mock_shop_manager

            await admin_commands.add_item_command(mock_update, mock_context)

            # Verify ShopManager.add_item was called with correct parameters
            mock_shop_manager.add_item.assert_called_once_with("VIP Status", Decimal("500"), "admin")

            # Verify success message contains admin-specific description
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "👨‍💼 Товар с уведомлением администраторов" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_quoted_name(self, admin_commands, mock_update, mock_context):
        """Test handling of quoted item names"""
        mock_context.args = ['"Special', 'Item', 'Name"', "250", "mention_all"]

        mock_db = Mock()
        mock_shop_manager = Mock()
        mock_shop_manager.add_item = AsyncMock(return_value={
            "success": True,
            "message": "Товар успешно добавлен",
            "item_id": 7,
            "item": {
                "id": 7,
                "name": "Special Item Name",
                "price": 250,
                "item_type": "mention_all",
                "description": "Динамически созданный товар типа mention_all",
                "is_active": True
            }
        })

        with patch('bot.commands.advanced_admin_commands.get_db') as mock_get_db, \
             patch('bot.commands.advanced_admin_commands.ShopManager') as mock_shop_manager_class:

            mock_get_db.return_value.__next__.return_value = mock_db
            mock_shop_manager_class.return_value = mock_shop_manager

            await admin_commands.add_item_command(mock_update, mock_context)

            # Verify the quoted name was parsed correctly
            mock_shop_manager.add_item.assert_called_once_with("Special Item Name", Decimal("250"), "mention_all")

    @pytest.mark.asyncio
    async def test_add_item_unauthorized_user(self, mock_update, mock_context):
        """Test rejection of non-admin users"""
        mock_context.args = ["Test", "Item", "100", "sticker"]

        with patch('bot.commands.advanced_admin_commands.AdminSystem') as mock_admin_system:
            mock_admin_system.return_value.is_admin.return_value = False
            admin_commands = AdvancedAdminCommands()

            await admin_commands.add_item_command(mock_update, mock_context)

            # Verify access denied message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "❌" in call_args[0][0]
            assert "Доступ запрещен" in call_args[0][0]
            assert "администраторам" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_insufficient_parameters(self, admin_commands, mock_update, mock_context):
        """Test error handling for insufficient parameters"""
        mock_context.args = ["Item", "100"]  # Missing item type

        await admin_commands.add_item_command(mock_update, mock_context)

        # Verify error message with usage instructions
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "❌" in call_args[0][0]
        assert "Неверные параметры" in call_args[0][0]
        assert "/add_item" in call_args[0][0]
        assert "sticker" in call_args[0][0]
        assert "admin" in call_args[0][0]
        assert "mention_all" in call_args[0][0]
        assert "custom" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_invalid_price(self, admin_commands, mock_update, mock_context):
        """Test error handling for invalid price"""
        mock_context.args = ["Test", "Item", "invalid_price", "sticker"]

        await admin_commands.add_item_command(mock_update, mock_context)

        # Verify error message for invalid price
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "❌" in call_args[0][0]
        assert "Ошибка в параметрах" in call_args[0][0]
        assert "Invalid price format" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_negative_price(self, admin_commands, mock_update, mock_context):
        """Test error handling for negative price"""
        mock_context.args = ["Test", "Item", "-50", "sticker"]

        await admin_commands.add_item_command(mock_update, mock_context)

        # Verify error message for negative price
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "❌" in call_args[0][0]
        assert "Price must be positive" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_invalid_type(self, admin_commands, mock_update, mock_context):
        """Test error handling for invalid item type"""
        mock_context.args = ["Test", "Item", "100", "invalid_type"]

        await admin_commands.add_item_command(mock_update, mock_context)

        # Verify error message for invalid type
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "❌" in call_args[0][0]
        assert "Invalid item type" in call_args[0][0]
        # The order of types in the set may vary, so just check they're all present
        assert "sticker" in call_args[0][0]
        assert "admin" in call_args[0][0]
        assert "mention_all" in call_args[0][0]
        assert "custom" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_duplicate_name_error(self, admin_commands, mock_update, mock_context):
        """Test handling of duplicate name error from ShopManager"""
        mock_context.args = ["Existing", "Item", "100", "sticker"]

        mock_db = Mock()
        mock_shop_manager = Mock()
        mock_shop_manager.add_item = AsyncMock(return_value={
            "success": False,
            "message": "Товар с названием 'Existing Item' уже существует",
            "error_code": "DUPLICATE_NAME"
        })

        with patch('bot.commands.advanced_admin_commands.get_db') as mock_get_db, \
             patch('bot.commands.advanced_admin_commands.ShopManager') as mock_shop_manager_class:

            mock_get_db.return_value.__next__.return_value = mock_db
            mock_shop_manager_class.return_value = mock_shop_manager

            await admin_commands.add_item_command(mock_update, mock_context)

            # Verify duplicate name error message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "❌" in call_args[0][0]
            assert "Товар уже существует" in call_args[0][0]
            assert "Existing Item" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_database_error(self, admin_commands, mock_update, mock_context):
        """Test handling of database errors"""
        mock_context.args = ["Test", "Item", "100", "sticker"]

        mock_db = Mock()
        mock_shop_manager = Mock()
        mock_shop_manager.add_item = AsyncMock(side_effect=Exception("Database connection failed"))

        with patch('bot.commands.advanced_admin_commands.get_db') as mock_get_db, \
             patch('bot.commands.advanced_admin_commands.ShopManager') as mock_shop_manager_class:

            mock_get_db.return_value.__next__.return_value = mock_db
            mock_shop_manager_class.return_value = mock_shop_manager

            await admin_commands.add_item_command(mock_update, mock_context)

            # Verify generic error message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "❌" in call_args[0][0]
            assert "Ошибка" in call_args[0][0]
            assert "Попробуйте позже" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_all_valid_types(self, admin_commands, mock_update, mock_context):
        """Test all valid item types are accepted"""
        valid_types = ["sticker", "admin", "mention_all", "custom"]

        for item_type in valid_types:
            mock_context.args = ["Test", "Item", "100", item_type]

            mock_db = Mock()
            mock_shop_manager = Mock()
            mock_shop_manager.add_item = AsyncMock(return_value={
                "success": True,
                "message": "Товар успешно добавлен",
                "item_id": 1,
                "item": {
                    "id": 1,
                    "name": "Test Item",
                    "price": 100,
                    "item_type": item_type,
                    "description": f"Динамически созданный товар типа {item_type}",
                    "is_active": True
                }
            })

            with patch('bot.commands.advanced_admin_commands.get_db') as mock_get_db, \
                 patch('bot.commands.advanced_admin_commands.ShopManager') as mock_shop_manager_class:

                mock_get_db.return_value.__next__.return_value = mock_db
                mock_shop_manager_class.return_value = mock_shop_manager

                # Reset mock
                mock_update.message.reply_text.reset_mock()

                await admin_commands.add_item_command(mock_update, mock_context)

                # Verify success for each type
                mock_shop_manager.add_item.assert_called_once_with("Test Item", Decimal("100"), item_type)
                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args
                assert "✅" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_case_insensitive_types(self, admin_commands, mock_update, mock_context):
        """Test that item types are case insensitive"""
        mock_context.args = ["Test", "Item", "100", "STICKER"]

        mock_db = Mock()
        mock_shop_manager = Mock()
        mock_shop_manager.add_item = AsyncMock(return_value={
            "success": True,
            "message": "Товар успешно добавлен",
            "item_id": 1,
            "item": {
                "id": 1,
                "name": "Test Item",
                "price": 100,
                "item_type": "sticker",
                "description": "Динамически созданный товар типа sticker",
                "is_active": True
            }
        })

        with patch('bot.commands.advanced_admin_commands.get_db') as mock_get_db, \
             patch('bot.commands.advanced_admin_commands.ShopManager') as mock_shop_manager_class:

            mock_get_db.return_value.__next__.return_value = mock_db
            mock_shop_manager_class.return_value = mock_shop_manager

            await admin_commands.add_item_command(mock_update, mock_context)

            # Verify the type was converted to lowercase
            mock_shop_manager.add_item.assert_called_once_with("Test Item", Decimal("100"), "sticker")

    @pytest.mark.asyncio
    async def test_add_item_empty_name(self, admin_commands, mock_update, mock_context):
        """Test error handling for empty item name"""
        mock_context.args = ["", "100", "sticker"]

        await admin_commands.add_item_command(mock_update, mock_context)

        # Verify error message for empty name
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "❌" in call_args[0][0]
        assert "Item name is empty" in call_args[0][0]


if __name__ == "__main__":
    pytest.main([__file__])
