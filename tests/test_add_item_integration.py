"""
Integration test for add_item functionality with existing ShopManager
"""

import asyncio
import sys
import os
from decimal import Decimal
import time

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database import Base, User, ShopItem
from core.shop_manager import ShopManager


def test_add_item_integration():
    """Test add_item method integration with existing ShopManager"""
    
    # Create test database with unique name
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
        
        # Initialize ShopManager
        shop_manager = ShopManager(session)
        
        # Test adding a new item
        print("Testing add_item functionality...")
        result = asyncio.run(shop_manager.add_item(
            name="Dynamic Test Item",
            price=Decimal('1500'),
            item_type="sticker"
        ))
        
        assert result["success"] is True, f"Add item should succeed: {result.get('message', 'No message')}"
        assert result["item"]["name"] == "Dynamic Test Item"
        assert result["item"]["price"] == 1500
        assert result["item"]["item_type"] == "sticker"
        
        print("✅ Item added successfully")
        
        # Test that the item is immediately available
        print("Testing immediate availability...")
        shop_items = shop_manager.get_shop_items()
        item_names = [item.name for item in shop_items]
        assert "Dynamic Test Item" in item_names, "New item should be in shop items list"
        
        print("✅ Item is immediately available")
        
        # Test purchasing the new item
        print("Testing purchase of new item...")
        item_number = None
        for i, item in enumerate(shop_items):
            if item.name == "Dynamic Test Item":
                item_number = i + 1
                break
        
        assert item_number is not None, "Should find the new item in shop list"
        
        purchase_result = asyncio.run(shop_manager.process_purchase(987654321, item_number))
        assert purchase_result.success is True, f"Purchase should succeed: {purchase_result.message}"
        assert purchase_result.new_balance == Decimal('8500'), f"Balance should be 8500, got {purchase_result.new_balance}"
        
        print("✅ New item can be purchased successfully")
        
        # Test adding item with duplicate name (should fail)
        print("Testing duplicate name validation...")
        duplicate_result = asyncio.run(shop_manager.add_item(
            name="Dynamic Test Item",
            price=Decimal('2000'),
            item_type="admin"
        ))
        
        assert duplicate_result["success"] is False, "Duplicate name should be rejected"
        assert duplicate_result["error_code"] == "DUPLICATE_NAME"
        
        print("✅ Duplicate name validation works")
        
        # Test adding item with invalid type (should fail)
        print("Testing invalid type validation...")
        invalid_type_result = asyncio.run(shop_manager.add_item(
            name="Invalid Type Item",
            price=Decimal('1000'),
            item_type="invalid"
        ))
        
        assert invalid_type_result["success"] is False, "Invalid type should be rejected"
        assert invalid_type_result["error_code"] == "INVALID_ITEM_TYPE"
        
        print("✅ Invalid type validation works")
        
        # Test all valid item types
        print("Testing all valid item types...")
        valid_types = ["admin", "mention_all", "custom"]
        
        for item_type in valid_types:
            type_result = asyncio.run(shop_manager.add_item(
                name=f"Test {item_type.title()} Item",
                price=Decimal('500'),
                item_type=item_type
            ))
            
            assert type_result["success"] is True, f"Should accept {item_type} type"
            assert type_result["item"]["item_type"] == item_type
        
        print("✅ All valid item types accepted")
        
        # Verify all items are in the database
        all_items = session.query(ShopItem).all()
        created_item_names = [item.name for item in all_items]
        
        expected_names = [
            "Dynamic Test Item",
            "Test Admin Item", 
            "Test Mention_All Item",
            "Test Custom Item"
        ]
        
        for name in expected_names:
            assert name in created_item_names, f"Item '{name}' should be in database"
        
        print("✅ All items persisted in database")
        
        print("\n🎉 All add_item integration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()
        # Clean up test database
        try:
            if os.path.exists(db_name):
                os.remove(db_name)
        except PermissionError:
            # File may be locked on Windows, ignore
            pass


if __name__ == "__main__":
    print("Running add_item integration test...")
    success = test_add_item_integration()
    if not success:
        sys.exit(1)