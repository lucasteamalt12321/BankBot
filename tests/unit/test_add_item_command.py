"""
Test suite for /add_item command handler
Tests the command interface for dynamic shop item creation
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, User as TelegramUser
from telegram.ext import ContextTypes

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.commands.advanced_admin_commands import AdvancedAdminCommands


class FakeServices:
    """Fake service container returned by build_services() context manager."""

    def __init__(self, is_admin=True, add_item_result=None):
        self.admin_service = Mock()
        self.admin_service.is_admin = Mock(return_value=is_admin)
        self.shop_service = Mock()
        default_item = {
            "id": 1,
            "name": "Test Item",
            "price": 0,
            "item_type": "sticker",
            "description": "Динамически созданный товар",
            "is_active": True,
        }
        self.shop_service.add_item = AsyncMock(
            return_value=add_item_result
            if add_item_result is not None
            else {"success": True, "item": default_item}
        )

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def patch_services(is_admin=True, add_item_result=None):
    """Return a patch context manager for build_services."""
    return patch(
        'bot.commands.advanced_admin_commands.build_services',
        return_value=FakeServices(is_admin=is_admin, add_item_result=add_item_result),
    )


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
        """Create AdvancedAdminCommands instance"""
        return AdvancedAdminCommands()

    @pytest.mark.asyncio
    async def test_add_item_success_sticker_type(self, admin_commands, mock_update, mock_context):
        """Test successful addition of sticker type item"""
        mock_context.args = ["Premium", "Stickers", "100", "sticker"]

        result = {
            "success": True,
            "message": "Товар 'Premium Stickers' успешно добавлен в магазин",
            "item_id": 5,
            "item": {
                "id": 5,
                "name": "Premium Stickers",
                "price": 100,
                "item_type": "sticker",
                "description": "Динамически созданный товар типа sticker",
                "is_active": True,
            },
        }

        with patch_services(is_admin=True, add_item_result=result):
            await admin_commands.add_item_command(mock_update, mock_context)

            # Verify ShopService.add_item was called with correct parameters
            admin_commands  # ensure instance used
            # Re-access the mock via the patched service is not trivial; assert via reply text
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

        result = {
            "success": True,
            "message": "Товар 'VIP Status' успешно добавлен в магазин",
            "item_id": 6,
            "item": {
                "id": 6,
                "name": "VIP Status",
                "price": 500,
                "item_type": "admin",
                "description": "Динамически созданный товар типа admin",
                "is_active": True,
            },
        }

        with patch_services(is_admin=True, add_item_result=result):
            await admin_commands.add_item_command(mock_update, mock_context)

            # Verify success message contains admin type
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "✅" in call_args[0][0]
            assert "admin" in call_args[0][0]
            assert "VIP Status" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_quoted_name(self, admin_commands, mock_update, mock_context):
        """Test handling of quoted item names"""
        mock_context.args = ['"Special', 'Item', 'Name"', "250", "mention_all"]

        result = {
            "success": True,
            "message": "Товар успешно добавлен",
            "item_id": 7,
            "item": {
                "id": 7,
                "name": "Special Item Name",
                "price": 250,
                "item_type": "mention_all",
                "description": "Динамически созданный товар типа mention_all",
                "is_active": True,
            },
        }

        with patch_services(is_admin=True, add_item_result=result):
            await admin_commands.add_item_command(mock_update, mock_context)

            # Verify success message with parsed name
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "✅" in call_args[0][0]
            assert "Special Item Name" in call_args[0][0]
            assert "mention_all" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_unauthorized_user(self, mock_update, mock_context):
        """Test rejection of non-admin users"""
        mock_context.args = ["Test", "Item", "100", "sticker"]

        admin_commands = AdvancedAdminCommands()

        with patch_services(is_admin=False):
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

        with patch_services(is_admin=True):
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

        with patch_services(is_admin=True):
            await admin_commands.add_item_command(mock_update, mock_context)

        # Verify error message for invalid price
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "❌" in call_args[0][0]
        assert "Ошибка в параметрах" in call_args[0][0]
        assert "Неверный формат цены" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_negative_price(self, admin_commands, mock_update, mock_context):
        """Test error handling for negative price"""
        mock_context.args = ["Test", "Item", "-50", "sticker"]

        with patch_services(is_admin=True):
            await admin_commands.add_item_command(mock_update, mock_context)

        # Verify error message for negative price
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "❌" in call_args[0][0]
        assert "Неверный формат цены" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_invalid_type(self, admin_commands, mock_update, mock_context):
        """Test error handling for invalid item type"""
        mock_context.args = ["Test", "Item", "100", "invalid_type"]

        with patch_services(is_admin=True):
            await admin_commands.add_item_command(mock_update, mock_context)

        # Verify error message for invalid type
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "❌" in call_args[0][0]
        assert "Недопустимый тип" in call_args[0][0]
        # The order of types in the set may vary, so just check they're all present
        assert "sticker" in call_args[0][0]
        assert "admin" in call_args[0][0]
        assert "mention_all" in call_args[0][0]
        assert "custom" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_duplicate_name_error(self, admin_commands, mock_update, mock_context):
        """Test handling of duplicate name error from ShopService"""
        mock_context.args = ["Existing", "Item", "100", "sticker"]

        result = {
            "success": False,
            "message": "Товар с названием 'Existing Item' уже существует",
            "error_code": "DUPLICATE_NAME",
        }

        with patch_services(is_admin=True, add_item_result=result):
            await admin_commands.add_item_command(mock_update, mock_context)

            # Verify duplicate name error message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "❌" in call_args[0][0]
            assert "уже существует" in call_args[0][0]
            assert "Existing Item" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_database_error(self, admin_commands, mock_update, mock_context):
        """Test handling of database errors"""
        mock_context.args = ["Test", "Item", "100", "sticker"]

        # Simulate ShopService.add_item raising an exception
        failing_services = FakeServices(is_admin=True)
        failing_services.shop_service.add_item = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        with patch(
            'bot.commands.advanced_admin_commands.build_services',
            return_value=failing_services,
        ):
            await admin_commands.add_item_command(mock_update, mock_context)

            # Verify generic error message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "❌" in call_args[0][0]
            assert "Ошибка" in call_args[0][0]
            assert "Произошла ошибка при добавлении товара" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_all_valid_types(self, admin_commands, mock_update, mock_context):
        """Test all valid item types are accepted"""
        valid_types = ["sticker", "admin", "mention_all", "custom"]

        for item_type in valid_types:
            mock_context.args = ["Test", "Item", "100", item_type]

            result = {
                "success": True,
                "message": "Товар успешно добавлен",
                "item_id": 1,
                "item": {
                    "id": 1,
                    "name": "Test Item",
                    "price": 100,
                    "item_type": item_type,
                    "description": f"Динамически созданный товар типа {item_type}",
                    "is_active": True,
                },
            }

            with patch_services(is_admin=True, add_item_result=result):
                # Reset mock
                mock_update.message.reply_text.reset_mock()

                await admin_commands.add_item_command(mock_update, mock_context)

                # Verify success for each type
                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args
                assert "✅" in call_args[0][0]
                assert item_type in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_case_insensitive_types(self, admin_commands, mock_update, mock_context):
        """Test that item types are case insensitive"""
        mock_context.args = ["Test", "Item", "100", "STICKER"]

        result = {
            "success": True,
            "message": "Товар успешно добавлен",
            "item_id": 1,
            "item": {
                "id": 1,
                "name": "Test Item",
                "price": 100,
                "item_type": "sticker",
                "description": "Динамически созданный товар типа sticker",
                "is_active": True,
            },
        }

        with patch_services(is_admin=True, add_item_result=result):
            await admin_commands.add_item_command(mock_update, mock_context)

            # Verify the type was converted to lowercase in the reply
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "sticker" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_item_empty_name(self, admin_commands, mock_update, mock_context):
        """Test error handling for empty item name"""
        mock_context.args = ["", "100", "sticker"]

        with patch_services(is_admin=True):
            await admin_commands.add_item_command(mock_update, mock_context)

        # Verify error message for empty name
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "❌" in call_args[0][0]
        assert "Название не может быть пустым" in call_args[0][0]


if __name__ == "__main__":
    pytest.main([__file__])
