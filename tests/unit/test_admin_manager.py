"""
Unit tests for AdminManager class
Tests the administrative functions including user statistics, parsing statistics, and admin verification
"""

import pytest
import asyncio
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.managers.admin_manager import AdminManager
from core.models.advanced_models import UserStats, ParsingStats, BroadcastResult
from database.database import User, ParsedTransaction, ParsingRule, UserPurchase, ShopItem
from utils.admin.admin_system import AdminSystem
from core.systems.broadcast_system import BroadcastSystem


class TestAdminManager:
    """Test cases for AdminManager functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.mock_broadcast_system = Mock(spec=BroadcastSystem)
        self.mock_admin_system = Mock(spec=AdminSystem)
        
        self.admin_manager = AdminManager(
            db_session=self.mock_db,
            broadcast_system=self.mock_broadcast_system,
            admin_system=self.mock_admin_system
        )
    
    def test_init(self):
        """Test AdminManager initialization"""
        assert self.admin_manager.db == self.mock_db
        assert self.admin_manager.broadcast_system == self.mock_broadcast_system
        assert self.admin_manager.admin_system == self.mock_admin_system
        assert 2091908459 in self.admin_manager.fallback_admin_ids
    
    def test_is_admin_with_admin_system(self):
        """Test admin verification using AdminSystem"""
        # Test admin user (not fallback admin)
        self.mock_admin_system.is_admin.return_value = True
        assert self.admin_manager.is_admin(123456) == True
        self.mock_admin_system.is_admin.assert_called_with(123456)
        
        # Test non-admin user (not fallback admin)
        self.mock_admin_system.is_admin.return_value = False
        assert self.admin_manager.is_admin(789012) == False
        self.mock_admin_system.is_admin.assert_called_with(789012)
    
    def test_is_admin_fallback(self):
        """Test admin verification with fallback admin IDs"""
        # Test with fallback admin ID (should return True regardless of AdminSystem)
        assert self.admin_manager.is_admin(2091908459) == True
        
        # Test with non-admin ID (AdminSystem returns False)
        self.mock_admin_system.is_admin.return_value = False
        assert self.admin_manager.is_admin(999999) == False
    
    def test_is_admin_database_fallback(self):
        """Test admin verification falling back to database when AdminSystem is None"""
        # Create AdminManager without AdminSystem
        admin_manager = AdminManager(
            db_session=self.mock_db,
            broadcast_system=self.mock_broadcast_system,
            admin_system=None
        )
        
        # Mock database query
        mock_user = Mock()
        mock_user.is_admin = True
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        assert admin_manager.is_admin(123456) == True
    
    def test_is_admin_error_handling(self):
        """Test admin verification error handling"""
        # Mock AdminSystem to raise exception
        self.mock_admin_system.is_admin.side_effect = Exception("Database error")
        
        # Should fall back to hardcoded admin IDs
        assert self.admin_manager.is_admin(2091908459) == True
        assert self.admin_manager.is_admin(999999) == False
    
    @pytest.mark.asyncio
    async def test_get_user_stats_success(self):
        """Test successful user statistics retrieval"""
        # Mock user data
        mock_user = Mock()
        mock_user.id = 1
        mock_user.telegram_id = 123456
        mock_user.username = "testuser"
        mock_user.first_name = "Test"
        mock_user.balance = 1000
        mock_user.total_purchases = 5
        mock_user.last_activity = datetime.utcnow()
        mock_user.created_at = datetime.utcnow() - timedelta(days=30)
        mock_user.sticker_unlimited = True
        mock_user.sticker_unlimited_until = datetime.utcnow() + timedelta(hours=12)
        mock_user.is_vip = False
        mock_user.vip_until = None
        mock_user.is_admin = False
        mock_user.total_earned = 2000
        mock_user.daily_streak = 7
        
        # Mock database queries
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        # Mock parsing transactions
        mock_transaction = Mock()
        mock_transaction.id = 1
        mock_transaction.source_bot = "TestBot"
        mock_transaction.original_amount = Decimal('100')
        mock_transaction.converted_amount = Decimal('150')
        mock_transaction.currency_type = "coins"
        mock_transaction.parsed_at = datetime.utcnow()
        mock_transaction.message_text = "Test message"
        
        self.mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_transaction]
        
        # Mock purchases
        self.mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        # Mock parsing earnings sum
        self.mock_db.query.return_value.filter.return_value.scalar.return_value = Decimal('500')
        
        # Test the method
        result = await self.admin_manager.get_user_stats("testuser")
        
        assert result is not None
        assert isinstance(result, UserStats)
        assert result.user_id == 123456
        assert result.username == "testuser"
        assert result.first_name == "Test"
        assert result.current_balance == 1000
        assert result.total_purchases == 5
        assert result.total_parsing_earnings == 500.0
        assert len(result.active_subscriptions) == 1
        assert result.active_subscriptions[0]['type'] == 'sticker_unlimited'
    
    @pytest.mark.asyncio
    async def test_get_user_stats_user_not_found(self):
        """Test user statistics when user is not found"""
        # Mock database to return None
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = await self.admin_manager.get_user_stats("nonexistent")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_parsing_stats_24h(self):
        """Test parsing statistics for 24 hour timeframe"""
        # Mock parsing transactions
        mock_transaction = Mock()
        mock_transaction.source_bot = "TestBot"
        mock_transaction.original_amount = Decimal('100')
        mock_transaction.converted_amount = Decimal('150')
        mock_transaction.currency_type = "coins"
        
        # Mock parsing rules
        mock_rule = Mock()
        mock_rule.id = 1
        mock_rule.bot_name = "TestBot"
        mock_rule.pattern = r"test: \+(\d+)"
        mock_rule.multiplier = Decimal('1.5')
        mock_rule.currency_type = "coins"
        mock_rule.is_active = True
        
        # Set up mock database queries to return different results for different queries
        def mock_query_side_effect(model):
            mock_query = Mock()
            if model == ParsedTransaction:
                mock_query.filter.return_value.all.return_value = [mock_transaction]
            elif model == ParsingRule:
                mock_query.filter.return_value.all.return_value = [mock_rule]
            return mock_query
        
        self.mock_db.query.side_effect = mock_query_side_effect
        
        result = await self.admin_manager.get_parsing_stats("24h")
        
        assert result is not None
        assert isinstance(result, ParsingStats)
        assert result.timeframe == "24h"
        assert result.period_name == "Last 24 Hours"
        assert result.total_transactions == 1
        assert result.successful_parses == 1
        assert result.total_amount_converted == 150.0
        assert result.success_rate == 100.0
        assert len(result.bot_statistics) == 1
        assert result.bot_statistics[0]['bot_name'] == "TestBot"
    
    @pytest.mark.asyncio
    async def test_get_parsing_stats_different_timeframes(self):
        """Test parsing statistics for different timeframes"""
        # Mock empty results for both ParsedTransaction and ParsingRule queries
        def mock_query_side_effect(model):
            mock_query = Mock()
            mock_query.filter.return_value.all.return_value = []
            return mock_query
        
        self.mock_db.query.side_effect = mock_query_side_effect
        
        # Test 7 days
        result_7d = await self.admin_manager.get_parsing_stats("7d")
        assert result_7d.timeframe == "7d"
        assert result_7d.period_name == "Last 7 Days"
        
        # Test 30 days
        result_30d = await self.admin_manager.get_parsing_stats("30d")
        assert result_30d.timeframe == "30d"
        assert result_30d.period_name == "Last 30 Days"
        
        # Test invalid timeframe (should default to 24h)
        result_invalid = await self.admin_manager.get_parsing_stats("invalid")
        assert result_invalid.timeframe == "24h"
        assert result_invalid.period_name == "Last 24 Hours"
    
    @pytest.mark.asyncio
    async def test_broadcast_admin_message_success(self):
        """Test successful admin broadcast"""
        # Mock admin verification
        self.mock_admin_system.is_admin.return_value = True
        
        # Mock broadcast result
        mock_result = BroadcastResult(
            total_users=100,
            successful_sends=95,
            failed_sends=5,
            errors=["Some error"],
            completion_message="Broadcast completed"
        )
        self.mock_broadcast_system.broadcast_to_all = AsyncMock(return_value=mock_result)
        
        result = await self.admin_manager.broadcast_admin_message("Test message", 123456)
        
        assert result is not None
        assert result.total_users == 100
        assert result.successful_sends == 95
        assert result.failed_sends == 5
        self.mock_broadcast_system.broadcast_to_all.assert_called_once_with("Test message", 123456)
    
    @pytest.mark.asyncio
    async def test_broadcast_admin_message_unauthorized(self):
        """Test admin broadcast with unauthorized user"""
        # Create AdminManager with a mock that will return False for non-fallback admin
        admin_manager = AdminManager(
            db_session=self.mock_db,
            broadcast_system=self.mock_broadcast_system,
            admin_system=self.mock_admin_system
        )
        
        # Mock admin verification to return False for non-fallback admin
        self.mock_admin_system.is_admin.return_value = False
        
        result = await admin_manager.broadcast_admin_message("Test message", 999999)
        
        assert result is None
        self.mock_broadcast_system.broadcast_to_all.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_broadcast_admin_message_no_broadcast_system(self):
        """Test admin broadcast without BroadcastSystem"""
        # Create AdminManager without BroadcastSystem
        admin_manager = AdminManager(
            db_session=self.mock_db,
            broadcast_system=None,
            admin_system=self.mock_admin_system
        )
        
        # Mock admin verification
        self.mock_admin_system.is_admin.return_value = True
        
        result = await admin_manager.broadcast_admin_message("Test message", 123456)
        
        assert result is None
    
    def test_get_admin_user_ids(self):
        """Test getting admin user IDs"""
        # Mock admin users
        mock_admin1 = Mock()
        mock_admin1.telegram_id = 111111
        mock_admin2 = Mock()
        mock_admin2.telegram_id = 222222
        
        self.mock_db.query.return_value.filter.return_value.all.return_value = [mock_admin1, mock_admin2]
        
        result = self.admin_manager.get_admin_user_ids()
        
        assert 111111 in result
        assert 222222 in result
        assert len(result) == 2
    
    def test_get_admin_user_ids_fallback(self):
        """Test getting admin user IDs with fallback"""
        # Mock empty admin users
        self.mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = self.admin_manager.get_admin_user_ids()
        
        assert 2091908459 in result
        assert len(result) == 1
    
    def test_add_admin_user_success(self):
        """Test successfully adding admin user"""
        # Mock user
        mock_user = Mock()
        mock_user.is_admin = False
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        result = self.admin_manager.add_admin_user(123456)
        
        assert result == True
        assert mock_user.is_admin == True
        self.mock_db.commit.assert_called_once()
    
    def test_add_admin_user_already_admin(self):
        """Test adding user who is already admin"""
        # Mock user who is already admin
        mock_user = Mock()
        mock_user.is_admin = True
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        result = self.admin_manager.add_admin_user(123456)
        
        assert result == True
        self.mock_db.commit.assert_not_called()
    
    def test_add_admin_user_not_found(self):
        """Test adding admin user when user not found"""
        # Mock user not found
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = self.admin_manager.add_admin_user(999999)
        
        assert result == False
    
    def test_remove_admin_user_success(self):
        """Test successfully removing admin user"""
        # Mock admin user
        mock_user = Mock()
        mock_user.is_admin = True
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        result = self.admin_manager.remove_admin_user(123456)
        
        assert result == True
        assert mock_user.is_admin == False
        self.mock_db.commit.assert_called_once()
    
    def test_remove_admin_user_not_admin(self):
        """Test removing user who is not admin"""
        # Mock user who is not admin
        mock_user = Mock()
        mock_user.is_admin = False
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        result = self.admin_manager.remove_admin_user(123456)
        
        assert result == True
        self.mock_db.commit.assert_not_called()
    
    def test_get_system_stats(self):
        """Test getting system statistics"""
        # Mock database counts
        self.mock_db.query.return_value.count.return_value = 100
        self.mock_db.query.return_value.filter.return_value.count.return_value = 10
        
        result = self.admin_manager.get_system_stats()
        
        assert 'total_users' in result
        assert 'admin_users' in result
        assert 'vip_users' in result
        assert 'active_users_24h' in result
        assert 'total_parsed_transactions' in result
        assert 'parsed_transactions_24h' in result
        assert 'total_purchases' in result
        assert 'purchases_24h' in result
        assert 'generated_at' in result
    
    def test_get_system_stats_error_handling(self):
        """Test system statistics error handling"""
        # Mock database error
        self.mock_db.query.side_effect = Exception("Database error")
        
        result = self.admin_manager.get_system_stats()
        
        assert 'error' in result
        assert 'generated_at' in result


if __name__ == "__main__":
    pytest.main([__file__])