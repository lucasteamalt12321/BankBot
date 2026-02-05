"""
Integration tests for AdminManager class
Tests the AdminManager with actual database connections and real data
"""

import pytest
import asyncio
import os
import sys
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.managers.admin_manager import AdminManager
from database.database import Base, User, ParsedTransaction, ParsingRule, UserPurchase, ShopItem
from utils.admin.admin_system import AdminSystem


class TestAdminManagerIntegration:
    """Integration test cases for AdminManager with real database"""
    
    def setup_method(self):
        """Set up test database and fixtures"""
        # Create temporary database
        self.db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_file.close()
        
        # Create engine and session
        self.engine = create_engine(f'sqlite:///{self.db_file.name}')
        Base.metadata.create_all(self.engine)
        
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Create AdminManager
        self.admin_system = AdminSystem(self.db_file.name)
        self.admin_manager = AdminManager(
            db_session=self.session,
            admin_system=self.admin_system
        )
        
        # Create test data
        self._create_test_data()
    
    def teardown_method(self):
        """Clean up test database"""
        self.session.close()
        self.engine.dispose()
        os.unlink(self.db_file.name)
    
    def _create_test_data(self):
        """Create test data in the database"""
        # Create test users
        self.test_user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=1000,
            total_purchases=3,
            total_earned=2000,
            is_admin=False,
            is_vip=True,
            vip_until=datetime.utcnow() + timedelta(days=30),
            sticker_unlimited=True,
            sticker_unlimited_until=datetime.utcnow() + timedelta(hours=12),
            daily_streak=5,
            created_at=datetime.utcnow() - timedelta(days=30),
            last_activity=datetime.utcnow() - timedelta(hours=2)
        )
        
        self.admin_user = User(
            telegram_id=789012,
            username="adminuser",
            first_name="Admin",
            balance=5000,
            total_purchases=10,
            total_earned=10000,
            is_admin=True,
            created_at=datetime.utcnow() - timedelta(days=60),
            last_activity=datetime.utcnow() - timedelta(minutes=30)
        )
        
        self.session.add(self.test_user)
        self.session.add(self.admin_user)
        self.session.commit()
        
        # Create parsing rules
        self.parsing_rule = ParsingRule(
            bot_name="TestBot",
            pattern=r"Coins: \+(\d+)",
            multiplier=Decimal('1.5'),
            currency_type="coins",
            is_active=True
        )
        
        self.session.add(self.parsing_rule)
        self.session.commit()
        
        # Create parsed transactions
        self.parsed_transaction = ParsedTransaction(
            user_id=self.test_user.id,
            source_bot="TestBot",
            original_amount=Decimal('100'),
            converted_amount=Decimal('150'),
            currency_type="coins",
            parsed_at=datetime.utcnow() - timedelta(hours=1),
            message_text="TestBot: Coins: +100"
        )
        
        self.session.add(self.parsed_transaction)
        self.session.commit()
        
        # Create shop item and purchase
        self.shop_item = ShopItem(
            name="Test Item",
            price=500,
            item_type="custom",
            description="Test item for integration test"
        )
        
        self.session.add(self.shop_item)
        self.session.commit()
        
        self.user_purchase = UserPurchase(
            user_id=self.test_user.id,
            item_id=self.shop_item.id,
            purchase_price=500,
            purchased_at=datetime.utcnow() - timedelta(days=1),
            is_active=True
        )
        
        self.session.add(self.user_purchase)
        self.session.commit()
    
    def test_is_admin_integration(self):
        """Test admin verification with real database"""
        # Test admin user
        assert self.admin_manager.is_admin(789012) == True
        
        # Test non-admin user
        assert self.admin_manager.is_admin(123456) == False
        
        # Test fallback admin
        assert self.admin_manager.is_admin(2091908459) == True
        
        # Test non-existent user
        assert self.admin_manager.is_admin(999999) == False
    
    @pytest.mark.asyncio
    async def test_get_user_stats_integration(self):
        """Test user statistics retrieval with real database"""
        # Test existing user
        stats = await self.admin_manager.get_user_stats("testuser")
        
        assert stats is not None
        assert stats.user_id == 123456
        assert stats.username == "testuser"
        assert stats.first_name == "Test"
        assert stats.current_balance == 1000
        assert stats.total_purchases == 3
        assert stats.total_earned == 2000
        assert stats.is_admin == False
        assert stats.is_vip == True
        assert stats.daily_streak == 5
        
        # Check active subscriptions
        assert len(stats.active_subscriptions) >= 2  # VIP and sticker_unlimited
        subscription_types = [sub['type'] for sub in stats.active_subscriptions]
        assert 'vip' in subscription_types
        assert 'sticker_unlimited' in subscription_types
        
        # Check parsing history
        assert len(stats.parsing_transaction_history) == 1
        assert stats.parsing_transaction_history[0]['source_bot'] == "TestBot"
        assert stats.parsing_transaction_history[0]['original_amount'] == 100.0
        assert stats.parsing_transaction_history[0]['converted_amount'] == 150.0
        
        # Check recent purchases
        assert len(stats.recent_purchases) == 1
        assert stats.recent_purchases[0]['item_name'] == "Test Item"
        assert stats.recent_purchases[0]['price_paid'] == 500
    
    @pytest.mark.asyncio
    async def test_get_user_stats_not_found(self):
        """Test user statistics for non-existent user"""
        stats = await self.admin_manager.get_user_stats("nonexistent")
        assert stats is None
    
    @pytest.mark.asyncio
    async def test_get_parsing_stats_integration(self):
        """Test parsing statistics with real database"""
        # Test 24h stats
        stats = await self.admin_manager.get_parsing_stats("24h")
        
        assert stats is not None
        assert stats.timeframe == "24h"
        assert stats.period_name == "Last 24 Hours"
        assert stats.total_transactions == 1
        assert stats.successful_parses == 1
        assert stats.failed_parses == 0
        assert stats.total_amount_converted == 150.0
        assert stats.success_rate == 100.0
        assert stats.active_bots == 1
        assert stats.total_configured_bots == 1
        
        # Check bot statistics
        assert len(stats.bot_statistics) == 1
        bot_stat = stats.bot_statistics[0]
        assert bot_stat['bot_name'] == "TestBot"
        assert bot_stat['transaction_count'] == 1
        assert bot_stat['total_original_amount'] == 100.0
        assert bot_stat['total_converted_amount'] == 150.0
        assert bot_stat['successful_parses'] == 1
        assert bot_stat['percentage_of_total'] == 100.0
        
        # Check parsing rules
        assert len(stats.parsing_rules) == 1
        rule = stats.parsing_rules[0]
        assert rule['bot_name'] == "TestBot"
        assert rule['pattern'] == r"Coins: \+(\d+)"
        assert rule['multiplier'] == 1.5
        assert rule['currency_type'] == "coins"
    
    @pytest.mark.asyncio
    async def test_get_parsing_stats_empty(self):
        """Test parsing statistics with no data"""
        # Clear existing transactions
        self.session.query(ParsedTransaction).delete()
        self.session.commit()
        
        stats = await self.admin_manager.get_parsing_stats("24h")
        
        assert stats is not None
        assert stats.total_transactions == 0
        assert stats.successful_parses == 0
        assert stats.total_amount_converted == 0.0
        assert stats.success_rate == 0.0
        assert len(stats.bot_statistics) == 0
    
    def test_add_remove_admin_integration(self):
        """Test adding and removing admin users"""
        # Test adding admin
        result = self.admin_manager.add_admin_user(123456)
        assert result == True
        
        # Verify user is now admin
        self.session.refresh(self.test_user)
        assert self.test_user.is_admin == True
        assert self.admin_manager.is_admin(123456) == True
        
        # Test removing admin
        result = self.admin_manager.remove_admin_user(123456)
        assert result == True
        
        # Verify user is no longer admin
        self.session.refresh(self.test_user)
        assert self.test_user.is_admin == False
        assert self.admin_manager.is_admin(123456) == False
    
    def test_get_admin_user_ids_integration(self):
        """Test getting admin user IDs from database"""
        admin_ids = self.admin_manager.get_admin_user_ids()
        
        # Should include the admin user we created
        assert 789012 in admin_ids
        
        # Test fallback behavior by removing all admin users
        self.admin_user.is_admin = False
        self.session.commit()
        
        admin_ids_fallback = self.admin_manager.get_admin_user_ids()
        assert 2091908459 in admin_ids_fallback
    
    def test_get_system_stats_integration(self):
        """Test system statistics with real database"""
        stats = self.admin_manager.get_system_stats()
        
        assert 'total_users' in stats
        assert 'admin_users' in stats
        assert 'vip_users' in stats
        assert 'active_users_24h' in stats
        assert 'total_parsed_transactions' in stats
        assert 'parsed_transactions_24h' in stats
        assert 'total_purchases' in stats
        assert 'purchases_24h' in stats
        assert 'generated_at' in stats
        
        # Verify actual counts
        assert stats['total_users'] == 2  # test_user and admin_user
        assert stats['admin_users'] == 1  # admin_user
        assert stats['vip_users'] == 1   # test_user
        assert stats['total_parsed_transactions'] == 1
        assert stats['total_purchases'] == 1


if __name__ == "__main__":
    pytest.main([__file__])