"""
Tests for BroadcastSystem class
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from core.systems.broadcast_system import BroadcastSystem
from core.models.advanced_models import BroadcastResult, NotificationResult
from database.database import User
from src.config import settings


class TestBroadcastSystem:
    """Test cases for BroadcastSystem"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_bot(self):
        """Mock Telegram bot"""
        bot = Mock()
        bot.send_message = AsyncMock()
        return bot
    
    @pytest.fixture
    def mock_admin_system(self):
        """Mock admin system"""
        return Mock()
    
    @pytest.fixture
    def broadcast_system(self, mock_db, mock_bot, mock_admin_system):
        """BroadcastSystem instance for testing"""
        return BroadcastSystem(mock_db, mock_bot, mock_admin_system)
    
    @pytest.fixture
    def sample_users(self):
        """Sample users for testing"""
        return [
            User(id=1, telegram_id=123, first_name="Alice", username="alice"),
            User(id=2, telegram_id=456, first_name="Bob", username="bob"),
            User(id=3, telegram_id=789, first_name="Charlie", username="charlie"),
        ]
    
    @pytest.mark.asyncio
    async def test_broadcast_to_all_success(self, broadcast_system, mock_db, mock_bot, sample_users):
        """Test successful broadcast to all users"""
        # Setup
        mock_db.query.return_value.filter.return_value.all.return_value = sample_users
        mock_db.query.return_value.filter.return_value.first.return_value = User(
            id=999, telegram_id=999, first_name="Sender"
        )
        
        # Execute
        result = await broadcast_system.broadcast_to_all("Test message", 999)
        
        # Verify
        assert isinstance(result, BroadcastResult)
        assert result.total_users == 3
        assert result.successful_sends == 3
        assert result.failed_sends == 0
        assert mock_bot.send_message.call_count == 3
    
    @pytest.mark.asyncio
    async def test_broadcast_to_all_no_users(self, broadcast_system, mock_db):
        """Test broadcast when no users exist"""
        # Setup
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        # Execute
        result = await broadcast_system.broadcast_to_all("Test message", 999)
        
        # Verify
        assert isinstance(result, BroadcastResult)
        assert result.total_users == 0
        assert result.successful_sends == 0
        assert result.failed_sends == 0
        assert "No registered users found" in result.errors
    
    @pytest.mark.asyncio
    async def test_mention_all_users_success(self, broadcast_system, mock_db, mock_bot, sample_users):
        """Test successful mention-all broadcast"""
        # Setup
        mock_db.query.return_value.filter.return_value.all.return_value = sample_users
        mock_db.query.return_value.filter.return_value.first.return_value = User(
            id=999, telegram_id=999, first_name="Sender"
        )
        
        # Execute
        result = await broadcast_system.mention_all_users("Test mention message", 999)
        
        # Verify
        assert isinstance(result, BroadcastResult)
        assert result.total_users == 3
        assert result.successful_sends == 3
        assert result.failed_sends == 0
        assert mock_bot.send_message.call_count == 3
        
        # Check that mentions were included in the message
        call_args = mock_bot.send_message.call_args_list[0]
        message_text = call_args[1]['text']
        assert "@alice" in message_text or "Alice" in message_text
    
    @pytest.mark.asyncio
    async def test_notify_admins_success(self, broadcast_system, mock_db, mock_bot):
        """Test successful admin notification"""
        # Setup
        admin_users = [
            User(id=1, telegram_id=111, first_name="Admin1", is_admin=True),
            User(id=2, telegram_id=222, first_name="Admin2", is_admin=True),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = admin_users
        mock_db.query.return_value.filter.return_value.first.return_value = User(
            id=999, telegram_id=999, first_name="User"
        )
        
        # Execute
        result = await broadcast_system.notify_admins("Test notification", 999)
        
        # Verify
        assert isinstance(result, NotificationResult)
        assert result.success is True
        assert result.notified_admins == 2
        assert result.failed_notifications == 0
        assert mock_bot.send_message.call_count == 2
    
    @pytest.mark.asyncio
    async def test_notify_admins_no_admins(self, broadcast_system, mock_db, mock_bot):
        """Test admin notification when no admins exist"""
        # Setup - no admin users, fallback to hardcoded admin
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [],  # First call returns no admins
            [User(id=1, telegram_id=settings.ADMIN_TELEGRAM_ID, first_name="FallbackAdmin")]  # Fallback call
        ]
        
        # Execute
        result = await broadcast_system.notify_admins("Test notification", 999)
        
        # Verify
        assert isinstance(result, NotificationResult)
        assert result.success is True
        assert result.notified_admins == 1
        assert mock_bot.send_message.call_count == 1
    
    @pytest.mark.asyncio
    async def test_send_message_with_retry_forbidden(self, broadcast_system):
        """Test message sending when user blocks bot"""
        from telegram.error import Forbidden
        
        # Setup
        broadcast_system.bot.send_message = AsyncMock(side_effect=Forbidden("User blocked bot"))
        
        # Execute
        result = await broadcast_system._send_message_with_retry(123, "Test message")
        
        # Verify
        assert result is False
        assert broadcast_system.bot.send_message.call_count == 1  # No retries for Forbidden
    
    @pytest.mark.asyncio
    async def test_send_message_with_retry_success_after_failure(self, broadcast_system):
        """Test message sending with retry success"""
        from telegram.error import TelegramError
        
        # Setup - fail first, succeed second
        broadcast_system.bot.send_message = AsyncMock(
            side_effect=[TelegramError("Temporary error"), None]
        )
        
        # Execute
        result = await broadcast_system._send_message_with_retry(123, "Test message")
        
        # Verify
        assert result is True
        assert broadcast_system.bot.send_message.call_count == 2
    
    def test_set_batch_size(self, broadcast_system):
        """Test setting batch size"""
        broadcast_system.set_batch_size(25)
        assert broadcast_system.batch_size == 25
        
        # Test invalid batch size
        broadcast_system.set_batch_size(0)
        assert broadcast_system.batch_size == 25  # Should remain unchanged
    
    def test_set_rate_limit_delay(self, broadcast_system):
        """Test setting rate limit delay"""
        broadcast_system.set_rate_limit_delay(0.5)
        assert broadcast_system.rate_limit_delay == 0.5
        
        # Test invalid delay
        broadcast_system.set_rate_limit_delay(-1)
        assert broadcast_system.rate_limit_delay == 0.5  # Should remain unchanged
    
    def test_set_max_retries(self, broadcast_system):
        """Test setting max retries"""
        broadcast_system.set_max_retries(5)
        assert broadcast_system.max_retries == 5
        
        # Test zero retries
        broadcast_system.set_max_retries(0)
        assert broadcast_system.max_retries == 0
    
    @pytest.mark.asyncio
    async def test_notify_admins_with_purchase_info(self, broadcast_system, mock_db, mock_bot):
        """Test admin notification with purchase information"""
        # Setup
        admin_users = [
            User(id=1, telegram_id=111, first_name="Admin1", is_admin=True),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = admin_users
        mock_db.query.return_value.filter.return_value.first.return_value = User(
            id=999, telegram_id=999, first_name="TestUser", username="testuser", balance=1000
        )
        
        purchase_info = {
            'item_name': 'Admin Item',
            'item_price': 500,
            'purchase_id': 123
        }
        
        # Execute
        result = await broadcast_system.notify_admins(
            "Admin item purchased", 999, purchase_info
        )
        
        # Verify
        assert isinstance(result, NotificationResult)
        assert result.success is True
        assert result.notified_admins == 1
        assert mock_bot.send_message.call_count == 1
        
        # Check message content includes purchase info
        call_args = mock_bot.send_message.call_args_list[0]
        message_text = call_args[1]['text']
        assert "Admin Item" in message_text
        assert "500" in message_text
        assert "123" in message_text
        assert "TestUser" in message_text
    
    def test_get_admin_user_ids(self, broadcast_system, mock_db):
        """Test getting admin user IDs"""
        # Setup
        admin_users = [
            User(id=1, telegram_id=111, is_admin=True),
            User(id=2, telegram_id=222, is_admin=True),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = admin_users
        
        # Execute
        admin_ids = broadcast_system.get_admin_user_ids()
        
        # Verify
        assert admin_ids == [111, 222]
    
    def test_get_admin_user_ids_fallback(self, broadcast_system, mock_db):
        """Test getting admin user IDs with fallback"""
        # Setup - no admin users
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        # Execute
        admin_ids = broadcast_system.get_admin_user_ids()
        
        # Verify fallback admin ID is returned
        assert settings.ADMIN_TELEGRAM_ID in admin_ids
    
    def test_add_admin_user_success(self, broadcast_system, mock_db):
        """Test adding admin user successfully"""
        # Setup
        user = User(id=1, telegram_id=123, is_admin=False)
        mock_db.query.return_value.filter.return_value.first.return_value = user
        
        # Execute
        result = broadcast_system.add_admin_user(123)
        
        # Verify
        assert result is True
        assert user.is_admin is True
        mock_db.commit.assert_called_once()
    
    def test_add_admin_user_not_found(self, broadcast_system, mock_db):
        """Test adding admin user when user not found"""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Execute
        result = broadcast_system.add_admin_user(123)
        
        # Verify
        assert result is False
        mock_db.commit.assert_not_called()
    
    def test_add_admin_user_already_admin(self, broadcast_system, mock_db):
        """Test adding admin user when already admin"""
        # Setup
        user = User(id=1, telegram_id=123, is_admin=True)
        mock_db.query.return_value.filter.return_value.first.return_value = user
        
        # Execute
        result = broadcast_system.add_admin_user(123)
        
        # Verify
        assert result is True
        mock_db.commit.assert_not_called()  # No need to commit if already admin
    
    def test_remove_admin_user_success(self, broadcast_system, mock_db):
        """Test removing admin user successfully"""
        # Setup
        user = User(id=1, telegram_id=123, is_admin=True)
        mock_db.query.return_value.filter.return_value.first.return_value = user
        
        # Execute
        result = broadcast_system.remove_admin_user(123)
        
        # Verify
        assert result is True
        assert user.is_admin is False
        mock_db.commit.assert_called_once()
    
    def test_remove_admin_user_not_admin(self, broadcast_system, mock_db):
        """Test removing admin user when not admin"""
        # Setup
        user = User(id=1, telegram_id=123, is_admin=False)
        mock_db.query.return_value.filter.return_value.first.return_value = user
        
        # Execute
        result = broadcast_system.remove_admin_user(123)
        
        # Verify
        assert result is True
        mock_db.commit.assert_not_called()  # No need to commit if not admin
    
    @pytest.mark.asyncio
    async def test_send_purchase_confirmation(self, broadcast_system, mock_bot):
        """Test sending purchase confirmation"""
        # Setup
        purchase_info = {
            'item_name': 'Test Item',
            'item_price': 100,
            'purchase_id': 456
        }
        
        # Execute
        result = await broadcast_system.send_purchase_confirmation(123, purchase_info)
        
        # Verify
        assert result is True
        mock_bot.send_message.assert_called_once()
        
        call_args = mock_bot.send_message.call_args
        assert call_args[1]['chat_id'] == 123
        message_text = call_args[1]['text']
        assert "Test Item" in message_text
        assert "100" in message_text
        assert "456" in message_text
        assert "Покупка подтверждена" in message_text
    
    def test_format_admin_notification_basic(self, broadcast_system):
        """Test basic admin notification formatting"""
        # Execute
        result = broadcast_system._format_admin_notification("Test notification")
        
        # Verify
        assert "Уведомление для администраторов" in result
        assert "Test notification" in result
    
    def test_format_admin_notification_with_purchase(self, broadcast_system, mock_db):
        """Test admin notification formatting with purchase info"""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = User(
            id=1, telegram_id=123, first_name="TestUser", username="testuser", balance=500
        )
        
        purchase_info = {
            'item_name': 'Premium Item',
            'item_price': 200,
            'purchase_id': 789
        }
        
        # Execute
        result = broadcast_system._format_admin_notification(
            "Purchase notification", 123, purchase_info
        )
        
        # Verify
        assert "покупке админ-товара" in result
        assert "TestUser" in result
        assert "@testuser" in result
        assert "Premium Item" in result
        assert "200" in result
        assert "789" in result


if __name__ == "__main__":
    pytest.main([__file__])