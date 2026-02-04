"""
Unit tests for ShopManager add_item functionality
Tests dynamic item creation with validation
"""

import asyncio
import sys
import os
from decimal import Decimal
import pytest

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database import Base, User, ShopItem
from core.shop_manager import ShopManager


class TestShopManagerAddItem:
    """Test cases for ShopManager add_item method"""
    
    def setup_method(self):
        """Set up test database and ShopManager"""
        # Create in-memory test database
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Initialize ShopManager
        self.shop_manager = ShopManager(self.session)
        
        # Create a test user
        test_user = User(
            telegram_id=123456789,
            username="test_user",
            balance=10000,
            total_purchases=0
        )
        self.session.add(test_user)
        self.session.commit()
    
    def teardown_method(self):
        """Clean up after each test"""
        self.session.close()
    
    def test_add_item_success_sticker_type(self):
        """Test successful addition of sticker type item"""
        result = asyncio.run(self.shop_manager.add_item(
            name="Test Sticker Pack",
            price=Decimal('500'),
            item_type="sticker"
        ))
        
        assert result["success"] is True
        assert "Test Sticker Pack" in result["message"]
        assert result["item"]["name"] == "Test Sticker Pack"
        assert result["item"]["price"] == 500
        assert result["item"]["item_type"] == "sticker"
        assert result["item"]["is_active"] is True
        
        # Verify item is in database
        item = self.session.query(ShopItem).filter(ShopItem.name == "Test Sticker Pack").first()
        assert item is not None
        assert item.item_type == "sticker"
        assert item.meta_data["duration_hours"] == 24
    
    def test_add_item_success_admin_type(self):
        """Test successful addition of admin type item"""
        result = asyncio.run(self.shop_manager.add_item(
            name="Admin Request",
            price=Decimal('1000'),
            item_type="admin"
        ))
        
        assert result["success"] is True
        assert result["item"]["item_type"] == "admin"
        
        # Verify metadata
        item = self.session.query(ShopItem).filter(ShopItem.name == "Admin Request").first()
        assert item.meta_data["feature_type"] == "admin_notification"
        assert item.meta_data["notify_admins"] is True
    
    def test_add_item_success_mention_all_type(self):
        """Test successful addition of mention_all type item"""
        result = asyncio.run(self.shop_manager.add_item(
            name="Broadcast Message",
            price=Decimal('750'),
            item_type="mention_all"
        ))
        
        assert result["success"] is True
        assert result["item"]["item_type"] == "mention_all"
        
        # Verify metadata
        item = self.session.query(ShopItem).filter(ShopItem.name == "Broadcast Message").first()
        assert item.meta_data["feature_type"] == "mention_all_broadcast"
        assert item.meta_data["requires_input"] is True
    
    def test_add_item_success_custom_type(self):
        """Test successful addition of custom type item"""
        result = asyncio.run(self.shop_manager.add_item(
            name="Custom Feature",
            price=Decimal('300'),
            item_type="custom"
        ))
        
        assert result["success"] is True
        assert result["item"]["item_type"] == "custom"
        
        # Verify metadata
        item = self.session.query(ShopItem).filter(ShopItem.name == "Custom Feature").first()
        assert item.meta_data["feature_type"] == "custom"
    
    def test_add_item_invalid_type(self):
        """Test rejection of invalid item type"""
        result = asyncio.run(self.shop_manager.add_item(
            name="Invalid Item",
            price=Decimal('100'),
            item_type="invalid_type"
        ))
        
        assert result["success"] is False
        assert result["error_code"] == "INVALID_ITEM_TYPE"
        assert "Недопустимый тип товара" in result["message"]
        
        # Verify item was not created
        item = self.session.query(ShopItem).filter(ShopItem.name == "Invalid Item").first()
        assert item is None
    
    def test_add_item_duplicate_name(self):
        """Test rejection of duplicate item names"""
        # Add first item
        result1 = asyncio.run(self.shop_manager.add_item(
            name="Duplicate Name",
            price=Decimal('100'),
            item_type="sticker"
        ))
        assert result1["success"] is True
        
        # Try to add item with same name
        result2 = asyncio.run(self.shop_manager.add_item(
            name="Duplicate Name",
            price=Decimal('200'),
            item_type="admin"
        ))
        
        assert result2["success"] is False
        assert result2["error_code"] == "DUPLICATE_NAME"
        assert "уже существует" in result2["message"]
        
        # Verify only one item exists
        items = self.session.query(ShopItem).filter(ShopItem.name == "Duplicate Name").all()
        assert len(items) == 1
        assert items[0].item_type == "sticker"  # First item should remain
    
    def test_add_item_invalid_price_zero(self):
        """Test rejection of zero price"""
        result = asyncio.run(self.shop_manager.add_item(
            name="Zero Price Item",
            price=Decimal('0'),
            item_type="sticker"
        ))
        
        assert result["success"] is False
        assert result["error_code"] == "INVALID_PRICE"
        assert "больше нуля" in result["message"]
    
    def test_add_item_invalid_price_negative(self):
        """Test rejection of negative price"""
        result = asyncio.run(self.shop_manager.add_item(
            name="Negative Price Item",
            price=Decimal('-100'),
            item_type="sticker"
        ))
        
        assert result["success"] is False
        assert result["error_code"] == "INVALID_PRICE"
        assert "больше нуля" in result["message"]
    
    def test_add_item_immediate_availability(self):
        """Test that new items are immediately available for purchase"""
        # Add new item
        result = asyncio.run(self.shop_manager.add_item(
            name="Immediate Item",
            price=Decimal('100'),
            item_type="sticker"
        ))
        assert result["success"] is True
        
        # Verify item is immediately available in shop items list
        shop_items = self.shop_manager.get_shop_items()
        item_names = [item.name for item in shop_items]
        assert "Immediate Item" in item_names
        
        # Verify item can be purchased immediately
        # Find the item number (1-based index)
        item_number = None
        for i, item in enumerate(shop_items):
            if item.name == "Immediate Item":
                item_number = i + 1
                break
        
        assert item_number is not None
        
        # Test purchase
        purchase_result = asyncio.run(self.shop_manager.process_purchase(123456789, item_number))
        assert purchase_result.success is True
    
    def test_add_item_all_valid_types(self):
        """Test that all valid item types are accepted"""
        valid_types = ["sticker", "admin", "mention_all", "custom"]
        
        for item_type in valid_types:
            result = asyncio.run(self.shop_manager.add_item(
                name=f"Test {item_type.title()} Item",
                price=Decimal('100'),
                item_type=item_type
            ))
            
            assert result["success"] is True, f"Failed to add {item_type} item"
            assert result["item"]["item_type"] == item_type
        
        # Verify all items were created
        items = self.session.query(ShopItem).all()
        created_types = [item.item_type for item in items]
        
        for item_type in valid_types:
            assert item_type in created_types


if __name__ == "__main__":
    # Run tests
    test_class = TestShopManagerAddItem()
    
    test_methods = [
        "test_add_item_success_sticker_type",
        "test_add_item_success_admin_type", 
        "test_add_item_success_mention_all_type",
        "test_add_item_success_custom_type",
        "test_add_item_invalid_type",
        "test_add_item_duplicate_name",
        "test_add_item_invalid_price_zero",
        "test_add_item_invalid_price_negative",
        "test_add_item_immediate_availability",
        "test_add_item_all_valid_types"
    ]
    
    passed = 0
    failed = 0
    
    for test_method in test_methods:
        try:
            test_class.setup_method()
            getattr(test_class, test_method)()
            test_class.teardown_method()
            print(f"✅ {test_method}")
            passed += 1
        except Exception as e:
            print(f"❌ {test_method}: {e}")
            failed += 1
            test_class.teardown_method()
    
    print(f"\nTest Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
    else:
        sys.exit(1)