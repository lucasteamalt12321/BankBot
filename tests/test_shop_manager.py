"""
Unit tests for ShopManager class
Tests purchase validation logic and item activation behaviors
"""

import pytest
import asyncio
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the modules we're testing
from core.shop_manager import ShopManager
from core.advanced_models import PurchaseResult
from database.database import Base, User, ShopItem, UserPurchase


class TestShopManager:
    """Test suite for ShopManager class"""
    
    @pytest.fixture
    def db_session(self):
        """Create an in-memory SQLite database for testing"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Create test data
        self._create_test_data(session)
        
        yield session
        session.close()
    
    def _create_test_data(self, session):
        """Create test users and shop items"""
        # Create test user
        user = User(
            id=1,
            telegram_id=12345,
            username="testuser",
            balance=10000,
            total_purchases=0
        )
        session.add(user)
        
        # Create test shop items
        sticker_item = ShopItem(
            id=1,
            name="Безлимитные стикеры",
            description="24 часа безлимитных стикеров",
            price=5000,
            item_type="sticker",
            is_active=True,
            meta_data={"duration_hours": 24}
        )
        
        admin_item = ShopItem(
            id=2,
            name="Админ уведомление",
            description="Уведомить всех админов",
            price=3000,
            item_type="admin",
            is_active=True
        )
        
        mention_all_item = ShopItem(
            id=3,
            name="Рассылка всем",
            description="Отправить сообщение всем пользователям",
            price=8000,
            item_type="mention_all",
            is_active=True
        )
        
        expensive_item = ShopItem(
            id=4,
            name="Дорогой товар",
            description="Товар дороже баланса пользователя",
            price=15000,
            item_type="custom",
            is_active=True
        )
        
        session.add_all([sticker_item, admin_item, mention_all_item, expensive_item])
        session.commit()
    
    @pytest.fixture
    def shop_manager(self, db_session):
        """Create ShopManager instance with test database"""
        return ShopManager(db_session)
    
    def test_validate_balance_sufficient_funds(self, shop_manager):
        """Test balance validation with sufficient funds"""
        # Test with sufficient balance
        result = asyncio.run(shop_manager.validate_balance(12345, Decimal('5000')))
        assert result is True
    
    def test_validate_balance_insufficient_funds(self, shop_manager):
        """Test balance validation with insufficient funds"""
        # Test with insufficient balance
        result = asyncio.run(shop_manager.validate_balance(12345, Decimal('15000')))
        assert result is False
    
    def test_validate_balance_exact_amount(self, shop_manager):
        """Test balance validation with exact balance amount"""
        # Test with exact balance
        result = asyncio.run(shop_manager.validate_balance(12345, Decimal('10000')))
        assert result is True
    
    def test_validate_balance_user_not_found(self, shop_manager):
        """Test balance validation with non-existent user"""
        # Test with non-existent user
        result = asyncio.run(shop_manager.validate_balance(99999, Decimal('1000')))
        assert result is False
    
    def test_process_purchase_successful_sticker_item(self, shop_manager, db_session):
        """Test successful purchase of sticker item"""
        # Purchase sticker item (item number 1)
        result = asyncio.run(shop_manager.process_purchase(12345, 1))
        
        assert result.success is True
        assert "активирован" in result.message.lower()
        assert result.new_balance == Decimal('5000')  # 10000 - 5000
        assert result.purchase_id is not None
        
        # Verify user balance was updated
        user = db_session.query(User).filter(User.telegram_id == 12345).first()
        assert user.balance == 5000
        assert user.total_purchases == 1
        assert user.sticker_unlimited is True
        assert user.sticker_unlimited_until is not None
    
    def test_process_purchase_successful_admin_item(self, shop_manager, db_session):
        """Test successful purchase of admin item"""
        # Purchase admin item (item number 2)
        result = asyncio.run(shop_manager.process_purchase(12345, 2))
        
        assert result.success is True
        assert "админ" in result.message.lower()
        assert result.new_balance == Decimal('7000')  # 10000 - 3000
        
        # Verify purchase record was created
        purchase = db_session.query(UserPurchase).filter(
            UserPurchase.user_id == 1,
            UserPurchase.item_id == 2
        ).first()
        assert purchase is not None
        assert purchase.purchase_price == 3000
    
    def test_process_purchase_insufficient_balance(self, shop_manager):
        """Test purchase with insufficient balance"""
        # Try to purchase expensive item (item number 4)
        result = asyncio.run(shop_manager.process_purchase(12345, 4))
        
        assert result.success is False
        assert "недостаточно средств" in result.message.lower()
        assert result.error_code == "INSUFFICIENT_BALANCE"
    
    def test_process_purchase_invalid_item_number(self, shop_manager):
        """Test purchase with invalid item number"""
        # Try to purchase non-existent item
        result = asyncio.run(shop_manager.process_purchase(12345, 99))
        
        assert result.success is False
        assert "не найден" in result.message.lower()
        assert result.error_code == "ITEM_NOT_FOUND"
    
    def test_process_purchase_user_not_found(self, shop_manager):
        """Test purchase with non-existent user"""
        # Try to purchase with non-existent user
        result = asyncio.run(shop_manager.process_purchase(99999, 1))
        
        assert result.success is False
        assert "пользователь не найден" in result.message.lower()
        assert result.error_code == "USER_NOT_FOUND"
    
    def test_activate_sticker_item(self, shop_manager, db_session):
        """Test sticker item activation"""
        user = db_session.query(User).filter(User.telegram_id == 12345).first()
        item = db_session.query(ShopItem).filter(ShopItem.id == 1).first()
        
        result = asyncio.run(shop_manager._activate_sticker_item(user, item))
        
        assert result["activated"] is True
        assert "стикеры активированы" in result["message"].lower()
        assert result["feature_type"] == "unlimited_stickers"
        assert "expires_at" in result
        
        # Verify user sticker access was set
        db_session.refresh(user)
        assert user.sticker_unlimited is True
        assert user.sticker_unlimited_until is not None
    
    def test_activate_admin_item(self, shop_manager, db_session):
        """Test admin item activation"""
        user = db_session.query(User).filter(User.telegram_id == 12345).first()
        item = db_session.query(ShopItem).filter(ShopItem.id == 2).first()
        
        result = asyncio.run(shop_manager._activate_admin_item(user, item))
        
        assert result["activated"] is True
        assert "админ-товар активирован" in result["message"].lower()
        assert result["feature_type"] == "admin_notification"
        assert result["notification_sent"] is True
        assert "notification_message" in result
    
    def test_activate_mention_all_item(self, shop_manager, db_session):
        """Test mention-all item activation"""
        user = db_session.query(User).filter(User.telegram_id == 12345).first()
        item = db_session.query(ShopItem).filter(ShopItem.id == 3).first()
        
        result = asyncio.run(shop_manager._activate_mention_all_item(user, item))
        
        assert result["activated"] is True
        assert "право на рассылку активировано" in result["message"].lower()
        assert result["feature_type"] == "mention_all_broadcast"
        assert result["requires_input"] is True
        assert result["input_type"] == "broadcast_message"
    
    def test_get_user_balance(self, shop_manager):
        """Test getting user balance"""
        balance = shop_manager.get_user_balance(12345)
        assert balance == Decimal('10000')
        
        # Test non-existent user
        balance = shop_manager.get_user_balance(99999)
        assert balance is None
    
    def test_get_shop_items(self, shop_manager):
        """Test getting shop items"""
        items = shop_manager.get_shop_items()
        assert len(items) == 4
        assert all(item.is_active for item in items)
    
    def test_purchase_creates_correct_purchase_record(self, shop_manager, db_session):
        """Test that purchase creates correct database records"""
        # Purchase an item
        result = asyncio.run(shop_manager.process_purchase(12345, 2))
        assert result.success is True
        
        # Check purchase record
        purchase = db_session.query(UserPurchase).filter(
            UserPurchase.id == result.purchase_id
        ).first()
        
        assert purchase is not None
        assert purchase.user_id == 1
        assert purchase.item_id == 2
        assert purchase.purchase_price == 3000
        assert purchase.purchased_at is not None
        assert purchase.meta_data is not None
        assert "activation_result" in purchase.meta_data
    
    def test_sticker_expiration_time_set_correctly(self, shop_manager, db_session):
        """Test that sticker expiration is set to exactly 24 hours"""
        before_purchase = datetime.utcnow()
        
        # Purchase sticker item
        result = asyncio.run(shop_manager.process_purchase(12345, 1))
        assert result.success is True
        
        after_purchase = datetime.utcnow()
        
        # Check user sticker expiration
        user = db_session.query(User).filter(User.telegram_id == 12345).first()
        
        # Should be approximately 24 hours from now
        expected_expiry = before_purchase + timedelta(hours=24)
        actual_expiry = user.sticker_unlimited_until
        
        # Allow for small time differences (within 1 minute)
        time_diff = abs((actual_expiry - expected_expiry).total_seconds())
        assert time_diff < 60, f"Expiry time difference too large: {time_diff} seconds"
    
    def test_balance_precision_with_decimals(self, shop_manager, db_session):
        """Test that balance calculations work correctly with decimal precision"""
        # Set user balance to a decimal amount
        user = db_session.query(User).filter(User.telegram_id == 12345).first()
        user.balance = 5000  # Exactly enough for sticker item
        db_session.commit()
        
        # Purchase should succeed
        result = asyncio.run(shop_manager.process_purchase(12345, 1))
        assert result.success is True
        assert result.new_balance == Decimal('0')
        
        # User balance should be exactly 0
        db_session.refresh(user)
        assert user.balance == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])