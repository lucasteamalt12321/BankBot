"""
Integration test for ShopManager with existing database
Tests ShopManager functionality against the real database schema
"""

import asyncio
import sys
import os
from decimal import Decimal

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database import Base, User, ShopItem
from core.shop_manager import ShopManager
from utils.config import settings


def test_shop_manager_integration():
    """Test ShopManager with real database schema"""
    
    # Create test database with unique name
    import time
    db_name = f"test_shop_manager_{int(time.time())}.db"
    engine = create_engine(f"sqlite:///{db_name}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Create test user
        test_user = User(
            telegram_id=123456789,
            username="integration_test_user",
            balance=10000,
            total_purchases=0
        )
        session.add(test_user)
        
        # Create test shop item
        test_item = ShopItem(
            name="Test Sticker Pack",
            description="Test sticker pack for integration testing",
            price=5000,
            item_type="sticker",
            is_active=True,
            meta_data={"duration_hours": 24}
        )
        session.add(test_item)
        session.commit()
        
        # Initialize ShopManager
        shop_manager = ShopManager(session)
        
        # Test balance validation
        print("Testing balance validation...")
        has_balance = asyncio.run(shop_manager.validate_balance(123456789, Decimal('5000')))
        assert has_balance is True, "User should have sufficient balance"
        
        insufficient_balance = asyncio.run(shop_manager.validate_balance(123456789, Decimal('15000')))
        assert insufficient_balance is False, "User should not have sufficient balance for expensive item"
        
        # Test purchase process
        print("Testing purchase process...")
        result = asyncio.run(shop_manager.process_purchase(123456789, 1))
        
        assert result.success is True, f"Purchase should succeed: {result.message}"
        assert result.new_balance == Decimal('5000'), f"New balance should be 5000, got {result.new_balance}"
        
        # Verify user state after purchase
        session.refresh(test_user)
        assert test_user.balance == 5000, f"User balance should be 5000, got {test_user.balance}"
        assert test_user.total_purchases == 1, f"User should have 1 purchase, got {test_user.total_purchases}"
        assert test_user.sticker_unlimited is True, "User should have unlimited stickers"
        assert test_user.sticker_unlimited_until is not None, "User should have sticker expiration set"
        
        # Test getting user balance
        print("Testing balance retrieval...")
        balance = shop_manager.get_user_balance(123456789)
        assert balance == Decimal('5000'), f"Retrieved balance should be 5000, got {balance}"
        
        # Test getting shop items
        print("Testing shop items retrieval...")
        items = shop_manager.get_shop_items()
        assert len(items) >= 1, "Should have at least one shop item"
        assert items[0].name == "Test Sticker Pack", "First item should be our test item"
        
        print("✅ All integration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()
        # Clean up test database (ignore errors on Windows)
        try:
            if os.path.exists(db_name):
                os.remove(db_name)
        except PermissionError:
            # File may be locked on Windows, ignore
            pass


if __name__ == "__main__":
    print("Running ShopManager integration test...")
    success = test_shop_manager_integration()
    if success:
        print("\n🎉 Integration test completed successfully!")
    else:
        print("\n❌ Integration test failed!")
        sys.exit(1)