"""
Unit tests for StickerManager class
Tests sticker access management functionality including granting access, checking permissions, and cleanup
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.database import Base, User, ScheduledTask
from core.managers.sticker_manager import StickerManager
from core.models.advanced_models import StickerAccessError


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()


@pytest.fixture
def sticker_manager(db_session):
    """Create StickerManager instance with test database session"""
    return StickerManager(db_session)


@pytest.fixture
def test_user(db_session):
    """Create a test user in the database"""
    user = User(
        telegram_id=12345,
        username="testuser",
        first_name="Test",
        last_name="User",
        balance=1000,
        sticker_unlimited=False,
        sticker_unlimited_until=None
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestStickerManager:
    """Test cases for StickerManager functionality"""
    
    @pytest.mark.asyncio
    async def test_grant_unlimited_access_success(self, sticker_manager, test_user, db_session):
        """Test successful granting of unlimited sticker access"""
        user_id = test_user.telegram_id
        
        # Grant unlimited access
        await sticker_manager.grant_unlimited_access(user_id, duration_hours=24)
        
        # Verify user has unlimited access
        db_session.refresh(test_user)
        assert test_user.sticker_unlimited is True
        assert test_user.sticker_unlimited_until is not None
        
        # Verify expiration time is approximately 24 hours from now
        expected_expiry = datetime.utcnow() + timedelta(hours=24)
        time_diff = abs((test_user.sticker_unlimited_until - expected_expiry).total_seconds())
        assert time_diff < 60  # Within 1 minute tolerance
    
    @pytest.mark.asyncio
    async def test_grant_unlimited_access_custom_duration(self, sticker_manager, test_user, db_session):
        """Test granting unlimited access with custom duration"""
        user_id = test_user.telegram_id
        custom_hours = 12
        
        # Grant unlimited access with custom duration
        await sticker_manager.grant_unlimited_access(user_id, duration_hours=custom_hours)
        
        # Verify user has unlimited access with correct expiration
        db_session.refresh(test_user)
        assert test_user.sticker_unlimited is True
        
        expected_expiry = datetime.utcnow() + timedelta(hours=custom_hours)
        time_diff = abs((test_user.sticker_unlimited_until - expected_expiry).total_seconds())
        assert time_diff < 60  # Within 1 minute tolerance
    
    @pytest.mark.asyncio
    async def test_grant_unlimited_access_user_not_found(self, sticker_manager):
        """Test granting access to non-existent user raises error"""
        non_existent_user_id = 99999
        
        with pytest.raises(StickerAccessError) as exc_info:
            await sticker_manager.grant_unlimited_access(non_existent_user_id)
        
        assert "not found in database" in str(exc_info.value)
        assert exc_info.value.user_id == non_existent_user_id
    
    @pytest.mark.asyncio
    async def test_check_access_valid_unlimited(self, sticker_manager, test_user, db_session):
        """Test checking access for user with valid unlimited access"""
        user_id = test_user.telegram_id
        
        # Grant unlimited access first
        await sticker_manager.grant_unlimited_access(user_id, duration_hours=24)
        
        # Check access
        has_access = await sticker_manager.check_access(user_id)
        
        assert has_access is True
    
    @pytest.mark.asyncio
    async def test_check_access_no_unlimited(self, sticker_manager, test_user):
        """Test checking access for user without unlimited access"""
        user_id = test_user.telegram_id
        
        # User should not have unlimited access by default
        has_access = await sticker_manager.check_access(user_id)
        
        assert has_access is False
    
    @pytest.mark.asyncio
    async def test_check_access_expired(self, sticker_manager, test_user, db_session):
        """Test checking access for user with expired unlimited access"""
        user_id = test_user.telegram_id
        
        # Set expired unlimited access
        test_user.sticker_unlimited = True
        test_user.sticker_unlimited_until = datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
        db_session.commit()
        
        # Check access - should automatically revoke expired access
        has_access = await sticker_manager.check_access(user_id)
        
        assert has_access is False
        
        # Verify access was revoked in database
        db_session.refresh(test_user)
        assert test_user.sticker_unlimited is False
        assert test_user.sticker_unlimited_until is None
    
    @pytest.mark.asyncio
    async def test_check_access_user_not_found(self, sticker_manager):
        """Test checking access for non-existent user"""
        non_existent_user_id = 99999
        
        has_access = await sticker_manager.check_access(non_existent_user_id)
        
        assert has_access is False
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_stickers_single_user(self, sticker_manager, db_session):
        """Test cleanup of expired sticker access for single user"""
        # Create user with expired access
        expired_user = User(
            telegram_id=11111,
            username="expired_user",
            balance=500,
            sticker_unlimited=True,
            sticker_unlimited_until=datetime.utcnow() - timedelta(hours=2)  # Expired 2 hours ago
        )
        db_session.add(expired_user)
        db_session.commit()
        
        # Run cleanup
        cleanup_count = await sticker_manager.cleanup_expired_stickers()
        
        # Verify cleanup results
        assert cleanup_count == 1
        
        # Verify user access was revoked
        db_session.refresh(expired_user)
        assert expired_user.sticker_unlimited is False
        assert expired_user.sticker_unlimited_until is None
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_stickers_multiple_users(self, sticker_manager, db_session):
        """Test cleanup of expired sticker access for multiple users"""
        # Create multiple users with expired access
        expired_users = []
        for i in range(3):
            user = User(
                telegram_id=20000 + i,
                username=f"expired_user_{i}",
                balance=500,
                sticker_unlimited=True,
                sticker_unlimited_until=datetime.utcnow() - timedelta(hours=i+1)  # Different expiry times
            )
            expired_users.append(user)
            db_session.add(user)
        
        # Create user with valid access (should not be cleaned up)
        valid_user = User(
            telegram_id=30000,
            username="valid_user",
            balance=500,
            sticker_unlimited=True,
            sticker_unlimited_until=datetime.utcnow() + timedelta(hours=12)  # Valid for 12 more hours
        )
        db_session.add(valid_user)
        db_session.commit()
        
        # Run cleanup
        cleanup_count = await sticker_manager.cleanup_expired_stickers()
        
        # Verify cleanup results
        assert cleanup_count == 3
        
        # Verify expired users had access revoked
        for user in expired_users:
            db_session.refresh(user)
            assert user.sticker_unlimited is False
            assert user.sticker_unlimited_until is None
        
        # Verify valid user still has access
        db_session.refresh(valid_user)
        assert valid_user.sticker_unlimited is True
        assert valid_user.sticker_unlimited_until is not None
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_stickers_no_expired_users(self, sticker_manager, test_user):
        """Test cleanup when no users have expired access"""
        # User has no unlimited access, so nothing to clean up
        cleanup_count = await sticker_manager.cleanup_expired_stickers()
        
        assert cleanup_count == 0
    
    @pytest.mark.asyncio
    async def test_auto_delete_sticker_success(self, sticker_manager, db_session):
        """Test scheduling automatic sticker deletion"""
        message_id = 12345
        delay_minutes = 2
        
        # Schedule auto-deletion
        await sticker_manager.auto_delete_sticker(message_id, delay_minutes)
        
        # Verify scheduled task was created
        scheduled_task = db_session.query(ScheduledTask).filter(
            ScheduledTask.message_id == message_id,
            ScheduledTask.task_type == "auto_delete_sticker"
        ).first()
        
        assert scheduled_task is not None
        assert scheduled_task.message_id == message_id
        assert scheduled_task.task_type == "auto_delete_sticker"
        assert scheduled_task.is_completed is False
        
        # Verify execution time is approximately delay_minutes from now
        expected_execute_at = datetime.utcnow() + timedelta(minutes=delay_minutes)
        time_diff = abs((scheduled_task.execute_at - expected_execute_at).total_seconds())
        assert time_diff < 60  # Within 1 minute tolerance
        
        # Verify task data
        assert scheduled_task.task_data["message_id"] == message_id
        assert scheduled_task.task_data["delay_minutes"] == delay_minutes
    
    @pytest.mark.asyncio
    async def test_auto_delete_sticker_default_delay(self, sticker_manager, db_session):
        """Test scheduling automatic sticker deletion with default delay"""
        message_id = 54321
        
        # Schedule auto-deletion with default delay
        await sticker_manager.auto_delete_sticker(message_id)
        
        # Verify scheduled task was created with default 2-minute delay
        scheduled_task = db_session.query(ScheduledTask).filter(
            ScheduledTask.message_id == message_id
        ).first()
        
        assert scheduled_task is not None
        assert scheduled_task.task_data["delay_minutes"] == 2
    
    def test_get_user_sticker_status_with_access(self, sticker_manager, test_user, db_session):
        """Test getting sticker status for user with unlimited access"""
        user_id = test_user.telegram_id
        
        # Set unlimited access
        expiry_time = datetime.utcnow() + timedelta(hours=12)
        test_user.sticker_unlimited = True
        test_user.sticker_unlimited_until = expiry_time
        db_session.commit()
        
        # Get status
        status = sticker_manager.get_user_sticker_status(user_id)
        
        assert status["found"] is True
        assert status["has_unlimited"] is True
        assert status["expires_at"] == expiry_time.isoformat()
        assert status["is_expired"] is False
        assert status["time_remaining"] is not None
    
    def test_get_user_sticker_status_expired(self, sticker_manager, test_user, db_session):
        """Test getting sticker status for user with expired access"""
        user_id = test_user.telegram_id
        
        # Set expired access
        expiry_time = datetime.utcnow() - timedelta(hours=1)
        test_user.sticker_unlimited = True
        test_user.sticker_unlimited_until = expiry_time
        db_session.commit()
        
        # Get status
        status = sticker_manager.get_user_sticker_status(user_id)
        
        assert status["found"] is True
        assert status["has_unlimited"] is True
        assert status["expires_at"] == expiry_time.isoformat()
        assert status["is_expired"] is True
        assert status["time_remaining"] is None
    
    def test_get_user_sticker_status_user_not_found(self, sticker_manager):
        """Test getting sticker status for non-existent user"""
        non_existent_user_id = 99999
        
        status = sticker_manager.get_user_sticker_status(non_existent_user_id)
        
        assert status["found"] is False
        assert status["has_unlimited"] is False
        assert status["expires_at"] is None
        assert status["is_expired"] is True
    
    @pytest.mark.asyncio
    async def test_revoke_access_success(self, sticker_manager, test_user, db_session):
        """Test manually revoking sticker access"""
        user_id = test_user.telegram_id
        
        # Grant access first
        await sticker_manager.grant_unlimited_access(user_id)
        
        # Verify access was granted
        db_session.refresh(test_user)
        assert test_user.sticker_unlimited is True
        
        # Revoke access
        result = await sticker_manager.revoke_access(user_id)
        
        assert result is True
        
        # Verify access was revoked
        db_session.refresh(test_user)
        assert test_user.sticker_unlimited is False
        assert test_user.sticker_unlimited_until is None
    
    @pytest.mark.asyncio
    async def test_revoke_access_user_not_found(self, sticker_manager):
        """Test revoking access for non-existent user"""
        non_existent_user_id = 99999
        
        result = await sticker_manager.revoke_access(non_existent_user_id)
        
        assert result is False
    
    def test_get_all_users_with_access(self, sticker_manager, db_session):
        """Test getting all users with unlimited sticker access"""
        # Create users with different access states
        users_data = [
            (10001, "user1", True, datetime.utcnow() + timedelta(hours=12)),  # Valid access
            (10002, "user2", True, datetime.utcnow() - timedelta(hours=1)),   # Expired access
            (10003, "user3", False, None),                                     # No access
            (10004, "user4", True, datetime.utcnow() + timedelta(hours=6)),   # Valid access
        ]
        
        for telegram_id, username, has_unlimited, expires_at in users_data:
            user = User(
                telegram_id=telegram_id,
                username=username,
                balance=500,
                sticker_unlimited=has_unlimited,
                sticker_unlimited_until=expires_at
            )
            db_session.add(user)
        
        db_session.commit()
        
        # Get all users with access
        users_with_access = sticker_manager.get_all_users_with_access()
        
        # Should return 3 users (excluding the one with no access)
        assert len(users_with_access) == 3
        
        # Verify user data
        user_ids = [user["user_id"] for user in users_with_access]
        assert 10001 in user_ids
        assert 10002 in user_ids
        assert 10003 not in user_ids  # This user has no unlimited access
        assert 10004 in user_ids
        
        # Check expired status
        expired_user = next(user for user in users_with_access if user["user_id"] == 10002)
        assert expired_user["is_expired"] is True
        
        valid_user = next(user for user in users_with_access if user["user_id"] == 10001)
        assert valid_user["is_expired"] is False
        assert valid_user["time_remaining"] is not None


if __name__ == "__main__":
    pytest.main([__file__])