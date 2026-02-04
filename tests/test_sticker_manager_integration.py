"""
Integration tests for StickerManager class
Tests integration with the existing database and real-world scenarios
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.database import get_db, SessionLocal, User
from core.sticker_manager import StickerManager
from core.advanced_models import StickerAccessError


class TestStickerManagerIntegration:
    """Integration tests for StickerManager with real database"""
    
    @pytest.fixture
    def db_session(self):
        """Use the actual database session"""
        db = next(get_db())
        yield db
        db.close()
    
    @pytest.fixture
    def sticker_manager(self, db_session):
        """Create StickerManager with real database session"""
        return StickerManager(db_session)
    
    @pytest.mark.asyncio
    async def test_integration_grant_and_check_access(self, sticker_manager, db_session):
        """Test complete workflow of granting and checking access"""
        # Create a test user
        test_user = User(
            telegram_id=999999,
            username="integration_test_user",
            first_name="Integration",
            last_name="Test",
            balance=1000
        )
        db_session.add(test_user)
        db_session.commit()
        
        try:
            user_id = test_user.telegram_id
            
            # Initially user should not have access
            has_access = await sticker_manager.check_access(user_id)
            assert has_access is False
            
            # Grant unlimited access
            await sticker_manager.grant_unlimited_access(user_id, duration_hours=1)
            
            # Now user should have access
            has_access = await sticker_manager.check_access(user_id)
            assert has_access is True
            
            # Check user status
            status = sticker_manager.get_user_sticker_status(user_id)
            assert status["found"] is True
            assert status["has_unlimited"] is True
            assert status["is_expired"] is False
            
            # Revoke access
            revoke_result = await sticker_manager.revoke_access(user_id)
            assert revoke_result is True
            
            # User should no longer have access
            has_access = await sticker_manager.check_access(user_id)
            assert has_access is False
            
        finally:
            # Clean up test user
            db_session.delete(test_user)
            db_session.commit()
    
    @pytest.mark.asyncio
    async def test_integration_cleanup_workflow(self, sticker_manager, db_session):
        """Test cleanup workflow with real database"""
        # Create test users with different access states
        test_users = []
        
        # User with expired access
        expired_user = User(
            telegram_id=888881,
            username="expired_test_user",
            balance=500,
            sticker_unlimited=True,
            sticker_unlimited_until=datetime.utcnow() - timedelta(minutes=30)
        )
        test_users.append(expired_user)
        
        # User with valid access
        valid_user = User(
            telegram_id=888882,
            username="valid_test_user",
            balance=500,
            sticker_unlimited=True,
            sticker_unlimited_until=datetime.utcnow() + timedelta(hours=2)
        )
        test_users.append(valid_user)
        
        # Add users to database
        for user in test_users:
            db_session.add(user)
        db_session.commit()
        
        try:
            # Run cleanup
            cleanup_count = await sticker_manager.cleanup_expired_stickers()
            
            # Should clean up 1 expired user
            assert cleanup_count == 1
            
            # Verify expired user lost access
            db_session.refresh(expired_user)
            assert expired_user.sticker_unlimited is False
            assert expired_user.sticker_unlimited_until is None
            
            # Verify valid user still has access
            db_session.refresh(valid_user)
            assert valid_user.sticker_unlimited is True
            assert valid_user.sticker_unlimited_until is not None
            
            # Check access for both users
            expired_access = await sticker_manager.check_access(expired_user.telegram_id)
            valid_access = await sticker_manager.check_access(valid_user.telegram_id)
            
            assert expired_access is False
            assert valid_access is True
            
        finally:
            # Clean up test users
            for user in test_users:
                db_session.delete(user)
            db_session.commit()
    
    @pytest.mark.asyncio
    async def test_integration_auto_delete_scheduling(self, sticker_manager, db_session):
        """Test auto-delete sticker scheduling with real database"""
        message_id = 777777
        delay_minutes = 1
        
        # Schedule auto-deletion
        await sticker_manager.auto_delete_sticker(message_id, delay_minutes)
        
        # Verify scheduled task exists in database
        from database.database import ScheduledTask
        scheduled_task = db_session.query(ScheduledTask).filter(
            ScheduledTask.message_id == message_id,
            ScheduledTask.task_type == "auto_delete_sticker"
        ).first()
        
        try:
            assert scheduled_task is not None
            assert scheduled_task.message_id == message_id
            assert scheduled_task.task_type == "auto_delete_sticker"
            assert scheduled_task.is_completed is False
            
            # Verify task data
            assert scheduled_task.task_data["message_id"] == message_id
            assert scheduled_task.task_data["delay_minutes"] == delay_minutes
            
        finally:
            # Clean up scheduled task
            if scheduled_task:
                db_session.delete(scheduled_task)
                db_session.commit()
    
    def test_integration_get_all_users_with_access(self, sticker_manager, db_session):
        """Test getting all users with access from real database"""
        # Create test users
        test_users = []
        
        for i in range(3):
            user = User(
                telegram_id=777000 + i,
                username=f"access_test_user_{i}",
                balance=500,
                sticker_unlimited=True,
                sticker_unlimited_until=datetime.utcnow() + timedelta(hours=i+1)
            )
            test_users.append(user)
            db_session.add(user)
        
        db_session.commit()
        
        try:
            # Get all users with access
            users_with_access = sticker_manager.get_all_users_with_access()
            
            # Should include our test users (and possibly others from previous tests)
            test_user_ids = [user.telegram_id for user in test_users]
            found_user_ids = [user["user_id"] for user in users_with_access]
            
            for test_user_id in test_user_ids:
                assert test_user_id in found_user_ids
            
            # Verify user data structure
            for user_data in users_with_access:
                if user_data["user_id"] in test_user_ids:
                    assert "username" in user_data
                    assert "expires_at" in user_data
                    assert "is_expired" in user_data
                    assert "time_remaining" in user_data
                    assert user_data["is_expired"] is False  # All our test users have valid access
            
        finally:
            # Clean up test users
            for user in test_users:
                db_session.delete(user)
            db_session.commit()


if __name__ == "__main__":
    pytest.main([__file__])