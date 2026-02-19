"""
Unified integration tests for /add_item command and ShopManager.add_item()
Combines command handler testing and direct ShopManager method testing

MERGED from test_add_item_command_integration.py and test_add_item_integration.py
during Phase 4 refactoring
"""

import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal
import time
from telegram import Update, Message, User as TelegramUser
from telegram.ext import ContextTypes

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bot.commands.advanced_admin_commands import AdvancedAdminCommands
from database.database import Base, get_db, User, ShopItem
from core.managers.shop_manager import ShopManager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# ========== COMMAND HANDLER TESTS ==========

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
        db.query.return_value.filter.return_value.first.return_value = None
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        db.close = Mock()
        return db
    
    @pytest.mark.asyncio
    async def test_add_item_command_success(self, admin_commands, mock_update, mock_context, mock_db_session):
        """Test complete integration of add_item command with ShopManager"""
        mock_context.args = ["Integration", "Test", "Item", "150", "sticker"]
        
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
            
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()
            mock_db_session.refresh.assert_called_once()
            
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "✅" in call_args[0][0]
            assert "Integration Test Item" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_add_item_command_duplicate_name(self, admin_commands, mock_update, mock_context, mock_db_session):
        """Test integration with duplicate name detection"""
        mock_context.args = ["Existing", "Item", "100", "admin"]
        
        existing_item = Mock()
        existing_item.name = "Existing Item"
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_item
        
        with patch('bot.advanced_admin_commands.get_db') as mock_get_db:
            mock_get_db.return_value.__next__.return_value = mock_db_session
            
            await admin_commands.add_item_command(mock_update, mock_context)
            
            mock_db_session.add.assert_not_called()
            mock_db_session.commit.assert_not_called()
            
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "❌" in call_args[0][0]
            assert "Товар уже существует" in call_args[0][0]


# ========== SHOP MANAGER TESTS ==========

def test_shop_manager_add_item_integration():
    """Test add_item method integration with existing ShopManager"""
    
    db_name = f"test_add_item_{int(time.time())}.db"
    engine = create_engine(f"sqlite:///{db_name}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Create test user
        test_user = User(
            telegram_id=987654321,
            username="add_item_test_user",
            balance=10000,
            total_purchases=0
        )
        session.add(test_user)
        session.commit()
        
        shop_manager = ShopManager(session)
        
        # Test adding a new item
        print("Testing add_item functionality...")
        result = asyncio.run(shop_manager.add_item(
            name="Dynamic Test Item",
            price=Decimal('1500'),
            item_type="sticker"
        ))
        
        assert result["success"] is True
        assert result["item"]["name"] == "Dynamic Test Item"
        assert result["item"]["price"] == 1500
        print("✅ Item added successfully")
        
        # Test immediate availability
        shop_items = shop_manager.get_shop_items()
        item_names = [item.name for item in shop_items]
        assert "Dynamic Test Item" in item_names
        print("✅ Item is immediately available")
        
        # Test purchasing the new item
        item_number = None
        for i, item in enumerate(shop_items):
            if item.name == "Dynamic Test Item":
                item_number = i + 1
                break
        
        purchase_result = asyncio.run(shop_manager.process_purchase(987654321, item_number))
        assert purchase_result.success is True
        assert purchase_result.new_balance == Decimal('8500')
        print("✅ New item can be purchased successfully")
        
        # Test duplicate name validation
        duplicate_result = asyncio.run(shop_manager.add_item(
            name="Dynamic Test Item",
            price=Decimal('2000'),
            item_type="admin"
        ))
        
        assert duplicate_result["success"] is False
        assert duplicate_result["error_code"] == "DUPLICATE_NAME"
        print("✅ Duplicate name validation works")
        
        # Test invalid type validation
        invalid_type_result = asyncio.run(shop_manager.add_item(
            name="Invalid Type Item",
            price=Decimal('1000'),
            item_type="invalid"
        ))
        
        assert invalid_type_result["success"] is False
        assert invalid_type_result["error_code"] == "INVALID_ITEM_TYPE"
        print("✅ Invalid type validation works")
        
        # Test all valid item types
        valid_types = ["admin", "mention_all", "custom"]
        for item_type in valid_types:
            type_result = asyncio.run(shop_manager.add_item(
                name=f"Test {item_type.title()} Item",
                price=Decimal('500'),
                item_type=item_type
            ))
            assert type_result["success"] is True
        print("✅ All valid item types accepted")
        
        print("\n🎉 All add_item integration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()
        try:
            if os.path.exists(db_name):
                os.remove(db_name)
        except PermissionError:
            pass


if __name__ == "__main__":
    # Run pytest tests
    pytest.main([__file__, "-v"])
    
    # Run standalone test
    print("\nRunning standalone ShopManager test...")
    success = test_shop_manager_add_item_integration()
    if not success:
        sys.exit(1)
