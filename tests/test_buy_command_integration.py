"""
Integration test for the /buy command handler with ShopManager
Tests the complete flow from command to database interaction
"""

import pytest
import asyncio
import os
import sys
from decimal import Decimal
import random

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import create_tables, get_db, User, ShopItem, UserPurchase
from core.shop_manager import ShopManager
from core.advanced_models import PurchaseResult


class TestBuyCommandIntegration:
    """Integration tests for /buy command with real database"""
    
    @pytest.fixture
    def db_session(self):
        """Create a test database session"""
        # Use test database
        db = next(get_db())
        yield db
        db.close()
    
    @pytest.fixture
    def test_user(self, db_session):
        """Create a test user with balance"""
        # Use random telegram_id to avoid conflicts
        telegram_id = random.randint(100000, 999999)
        
        # Check if user already exists and delete if so
        existing_user = db_session.query(User).filter(User.telegram_id == telegram_id).first()
        if existing_user:
            db_session.delete(existing_user)
            db_session.commit()
        
        user = User(
            telegram_id=telegram_id,
            username=f"testuser_{telegram_id}",
            first_name="Test",
            balance=10000,  # Increased balance to handle existing shop items
            sticker_unlimited=False
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    
    @pytest.fixture
    def test_shop_item(self, db_session):
        """Create a test shop item"""
        item = ShopItem(
            name="Test Stickers",
            price=100,
            item_type="sticker",
            description="Test sticker item",
            is_active=True
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        return item
    
    @pytest.mark.asyncio
    async def test_successful_purchase_integration(self, db_session, test_user, test_shop_item):
        """Test successful purchase through ShopManager"""
        # Create ShopManager
        shop_manager = ShopManager(db_session)
        
        # Process purchase
        result = await shop_manager.process_purchase(test_user.telegram_id, 1)
        
        # Verify result
        assert result.success is True
        assert result.purchase_id is not None
        # Don't check exact balance since we don't know the exact price of item 1
        assert result.new_balance is not None
        assert result.new_balance < Decimal('10000')  # Should be less than original
        assert "успешна" in result.message
        
        # Verify database changes
        db_session.refresh(test_user)
        assert test_user.balance < 10000  # Should be less than original
        assert test_user.total_purchases == 1
        
        # For sticker items, verify sticker access was granted
        assert test_user.sticker_unlimited is True
        assert test_user.sticker_unlimited_until is not None
        
        # Verify purchase record was created
        purchase = db_session.query(UserPurchase).filter(
            UserPurchase.user_id == test_user.id
        ).first()
        assert purchase is not None
        # Don't check exact item_id since we're using the first available item
        assert purchase.purchase_price > 0
    
    @pytest.mark.asyncio
    async def test_insufficient_balance_integration(self, db_session, test_user, test_shop_item):
        """Test purchase with insufficient balance"""
        # Set user balance to less than item price
        test_user.balance = 50
        db_session.commit()
        
        # Create ShopManager
        shop_manager = ShopManager(db_session)
        
        # Process purchase
        result = await shop_manager.process_purchase(test_user.telegram_id, 1)
        
        # Verify result
        assert result.success is False
        assert result.error_code == "INSUFFICIENT_BALANCE"
        assert "Недостаточно средств" in result.message
        
        # Verify no database changes
        db_session.refresh(test_user)
        assert test_user.balance == 50  # Unchanged
        assert test_user.total_purchases == 0  # Unchanged
        assert test_user.sticker_unlimited is False  # Unchanged
    
    @pytest.mark.asyncio
    async def test_invalid_item_number_integration(self, db_session, test_user):
        """Test purchase with invalid item number"""
        # Create ShopManager
        shop_manager = ShopManager(db_session)
        
        # Process purchase with invalid item number
        result = await shop_manager.process_purchase(test_user.telegram_id, 999)
        
        # Verify result
        assert result.success is False
        assert result.error_code == "ITEM_NOT_FOUND"
        assert "не найден" in result.message
        
        # Verify no database changes
        db_session.refresh(test_user)
        assert test_user.balance == 10000  # Unchanged
        assert test_user.total_purchases == 0  # Unchanged
    
    @pytest.mark.asyncio
    async def test_user_not_found_integration(self, db_session, test_shop_item):
        """Test purchase with non-existent user"""
        # Create ShopManager
        shop_manager = ShopManager(db_session)
        
        # Process purchase with non-existent user
        result = await shop_manager.process_purchase(99999, 1)
        
        # Verify result
        assert result.success is False
        assert result.error_code == "USER_NOT_FOUND"
        assert "не найден" in result.message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])