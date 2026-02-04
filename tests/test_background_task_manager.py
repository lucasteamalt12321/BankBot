"""
Unit tests for BackgroundTaskManager class
Tests the background task management functionality for the advanced bot features
"""

import pytest
import asyncio
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.background_task_manager import BackgroundTaskManager
from core.advanced_models import CleanupResult, HealthStatus, BackgroundTaskError
from core.sticker_manager import StickerManager
from database.database import User, ParsedTransaction, ParsingRule, Base
from decimal import Decimal


class TestBackgroundTaskManager:
    """Test suite for BackgroundTaskManager class"""
    
    @pytest.fixture
    def db_session(self):
        """Create an in-memory SQLite database for testing"""
        engine = create_engine('sqlite:///:memory:', echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Add test data
        test_user = User(
            telegram_id=12345,
            username="testuser",
            first_name="Test",
            balance=100,
            sticker_unlimited=True,
            sticker_unlimited_until=datetime.utcnow() - timedelta(hours=1),  # Expired
            is_vip=True,
            vip_until=datetime.utcnow() - timedelta(days=1)  # Expired
        )
        session.add(test_user)
        
        # Add parsing rule
        parsing_rule = ParsingRule(
            id=1,
            bot_name="TestBot",
            pattern=r"Test: \+(\d+)",
            multiplier=Decimal('1.0'),
            currency_type="coins",
            is_active=True
        )
        session.add(parsing_rule)
        
        # Add old transaction
        old_transaction = ParsedTransaction(
            id=1,
            user_id=test_user.id,
            source_bot="TestBot",
            original_amount=Decimal('10'),
            converted_amount=Decimal('10'),
            currency_type="coins",
            parsed_at=datetime.utcnow() - timedelta(days=100),  # Old transaction
            message_text="Test: +10"
        )
        session.add(old_transaction)
        
        session.commit()
        yield session
        session.close()
    
    @pytest.fixture
    def mock_sticker_manager(self):
        """Create a mock StickerManager for testing"""
        mock_manager = Mock(spec=StickerManager)
        mock_manager.cleanup_expired_stickers = AsyncMock(return_value=2)
        return mock_manager
    
    @pytest.fixture
    def background_task_manager(self, db_session, mock_sticker_manager):
        """Create BackgroundTaskManager instance for testing"""
        return BackgroundTaskManager(db_session, mock_sticker_manager)
    
    def test_initialization(self, background_task_manager):
        """Test BackgroundTaskManager initialization"""
        assert background_task_manager.is_running is False
        assert background_task_manager.cleanup_interval_seconds == 300  # 5 minutes
        assert background_task_manager.monitoring_interval_seconds == 60  # 1 minute
        assert background_task_manager.cleanup_task is None
        assert background_task_manager.monitoring_task is None
    
    @pytest.mark.asyncio
    async def test_start_periodic_cleanup(self, background_task_manager):
        """Test starting periodic cleanup tasks"""
        # Start the tasks
        await background_task_manager.start_periodic_cleanup()
        
        assert background_task_manager.is_running is True
        assert background_task_manager.cleanup_task is not None
        assert background_task_manager.monitoring_task is not None
        
        # Clean up
        await background_task_manager.stop_periodic_cleanup()
    
    @pytest.mark.asyncio
    async def test_start_periodic_cleanup_already_running(self, background_task_manager):
        """Test starting periodic cleanup when already running"""
        # Start the tasks
        await background_task_manager.start_periodic_cleanup()
        
        # Try to start again - should not raise error
        await background_task_manager.start_periodic_cleanup()
        
        assert background_task_manager.is_running is True
        
        # Clean up
        await background_task_manager.stop_periodic_cleanup()
    
    @pytest.mark.asyncio
    async def test_stop_periodic_cleanup(self, background_task_manager):
        """Test stopping periodic cleanup tasks"""
        # Start the tasks first
        await background_task_manager.start_periodic_cleanup()
        assert background_task_manager.is_running is True
        
        # Stop the tasks
        await background_task_manager.stop_periodic_cleanup()
        
        assert background_task_manager.is_running is False
    
    @pytest.mark.asyncio
    async def test_stop_periodic_cleanup_not_running(self, background_task_manager):
        """Test stopping periodic cleanup when not running"""
        # Should not raise error
        await background_task_manager.stop_periodic_cleanup()
        
        assert background_task_manager.is_running is False
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_access_success(self, background_task_manager, mock_sticker_manager):
        """Test successful cleanup of expired access"""
        # Mock sticker manager to return cleanup count
        mock_sticker_manager.cleanup_expired_stickers.return_value = 3
        
        result = await background_task_manager.cleanup_expired_access()
        
        assert isinstance(result, CleanupResult)
        assert result.cleaned_users >= 1  # At least VIP cleanup
        assert result.cleaned_files >= 0
        assert len(result.errors) == 0
        assert "Cleanup completed" in result.completion_message
        
        # Verify sticker manager was called
        mock_sticker_manager.cleanup_expired_stickers.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_access_with_errors(self, background_task_manager, mock_sticker_manager):
        """Test cleanup with errors in sticker manager"""
        # Mock sticker manager to raise exception
        mock_sticker_manager.cleanup_expired_stickers.side_effect = Exception("Sticker cleanup failed")
        
        result = await background_task_manager.cleanup_expired_access()
        
        assert isinstance(result, CleanupResult)
        assert len(result.errors) > 0
        assert any("sticker access" in error.lower() for error in result.errors)
        assert "with" in result.completion_message and "errors" in result.completion_message
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_vip_access(self, background_task_manager, db_session):
        """Test cleanup of expired VIP access"""
        # Verify there's a user with expired VIP access
        expired_vip_user = db_session.query(User).filter(
            User.is_vip == True,
            User.vip_until < datetime.utcnow()
        ).first()
        assert expired_vip_user is not None
        
        # Run cleanup
        cleanup_count = await background_task_manager._cleanup_expired_vip_access()
        
        assert cleanup_count >= 1
        
        # Verify VIP access was revoked
        db_session.refresh(expired_vip_user)
        assert expired_vip_user.is_vip is False
        assert expired_vip_user.vip_until is None
    
    @pytest.mark.asyncio
    async def test_cleanup_old_transactions(self, background_task_manager, db_session):
        """Test cleanup of old transactions"""
        # Verify there's an old transaction
        old_transaction = db_session.query(ParsedTransaction).filter(
            ParsedTransaction.parsed_at < datetime.utcnow() - timedelta(days=90)
        ).first()
        assert old_transaction is not None
        
        # Run cleanup
        cleanup_count = await background_task_manager._cleanup_old_transactions(days_old=90)
        
        assert cleanup_count >= 1
        
        # Verify transaction was deleted
        remaining_old_transactions = db_session.query(ParsedTransaction).filter(
            ParsedTransaction.parsed_at < datetime.utcnow() - timedelta(days=90)
        ).count()
        assert remaining_old_transactions == 0
    
    @pytest.mark.asyncio
    async def test_monitor_parsing_health_healthy(self, background_task_manager, db_session):
        """Test health monitoring when system is healthy"""
        # Add recent transaction to make parsing appear active
        recent_transaction = ParsedTransaction(
            id=2,
            user_id=1,
            source_bot="TestBot",
            original_amount=Decimal('5'),
            converted_amount=Decimal('5'),
            currency_type="coins",
            parsed_at=datetime.utcnow() - timedelta(minutes=5),
            message_text="Test: +5"
        )
        db_session.add(recent_transaction)
        db_session.commit()
        
        health_status = await background_task_manager.monitor_parsing_health()
        
        assert isinstance(health_status, HealthStatus)
        assert health_status.database_connected is True
        assert health_status.parsing_active is True
        assert health_status.last_check is not None
        assert len(health_status.errors) == 0
    
    @pytest.mark.asyncio
    async def test_monitor_parsing_health_database_error(self, background_task_manager):
        """Test health monitoring with database error"""
        # Mock database session to raise exception
        with patch.object(background_task_manager.db, 'query', side_effect=Exception("Database error")):
            health_status = await background_task_manager.monitor_parsing_health()
            
            assert isinstance(health_status, HealthStatus)
            assert health_status.is_healthy is False
            assert health_status.database_connected is False
            assert len(health_status.errors) > 0
            assert any("database" in error.lower() for error in health_status.errors)
    
    @pytest.mark.asyncio
    async def test_monitor_parsing_health_no_recent_activity(self, background_task_manager):
        """Test health monitoring with no recent parsing activity"""
        health_status = await background_task_manager.monitor_parsing_health()
        
        assert isinstance(health_status, HealthStatus)
        assert health_status.database_connected is True
        # Should still be considered active due to active parsing rules
        assert health_status.parsing_active is True  # Due to active parsing rule
    
    def test_get_task_status(self, background_task_manager):
        """Test getting task status information"""
        status = background_task_manager.get_task_status()
        
        assert isinstance(status, dict)
        assert 'is_running' in status
        assert 'cleanup_interval_seconds' in status
        assert 'monitoring_interval_seconds' in status
        assert 'cleanup_task_running' in status
        assert 'monitoring_task_running' in status
        assert 'last_status_check' in status
        
        assert status['is_running'] is False
        assert status['cleanup_interval_seconds'] == 300
        assert status['monitoring_interval_seconds'] == 60
    
    @pytest.mark.asyncio
    async def test_periodic_cleanup_loop_single_iteration(self, background_task_manager, mock_sticker_manager):
        """Test a single iteration of the periodic cleanup loop"""
        # Mock sleep to prevent actual waiting
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Start the background task manager
            background_task_manager.is_running = True
            
            # Create a task that will run one iteration then stop
            async def single_iteration():
                await background_task_manager._periodic_cleanup_loop()
            
            # Stop after first iteration
            def stop_after_first_call(*args):
                background_task_manager.is_running = False
                return asyncio.sleep(0)  # Return immediately
            
            mock_sleep.side_effect = stop_after_first_call
            
            # Run the loop
            await single_iteration()
            
            # Verify cleanup was called
            mock_sticker_manager.cleanup_expired_stickers.assert_called()
    
    @pytest.mark.asyncio
    async def test_periodic_monitoring_loop_single_iteration(self, background_task_manager):
        """Test a single iteration of the periodic monitoring loop"""
        # Mock sleep to prevent actual waiting
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Start the background task manager
            background_task_manager.is_running = True
            
            # Create a task that will run one iteration then stop
            async def single_iteration():
                await background_task_manager._periodic_monitoring_loop()
            
            # Stop after first iteration
            def stop_after_first_call(*args):
                background_task_manager.is_running = False
                return asyncio.sleep(0)  # Return immediately
            
            mock_sleep.side_effect = stop_after_first_call
            
            # Run the loop
            await single_iteration()
            
            # The loop should have completed without errors
            assert background_task_manager.is_running is False
    
    @pytest.mark.asyncio
    async def test_error_handling_in_cleanup_loop(self, background_task_manager, mock_sticker_manager):
        """Test error handling in periodic cleanup loop"""
        # Mock sticker manager to raise exception
        mock_sticker_manager.cleanup_expired_stickers.side_effect = Exception("Cleanup error")
        
        # Mock sleep to prevent actual waiting
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            background_task_manager.is_running = True
            
            # Stop after first iteration
            def stop_after_first_call(*args):
                background_task_manager.is_running = False
                return asyncio.sleep(0)
            
            mock_sleep.side_effect = stop_after_first_call
            
            # Run the loop - should not raise exception
            await background_task_manager._periodic_cleanup_loop()
            
            # Verify the loop handled the error gracefully
            assert background_task_manager.is_running is False
    
    @pytest.mark.asyncio
    async def test_error_handling_in_monitoring_loop(self, background_task_manager):
        """Test error handling in periodic monitoring loop"""
        # Mock database to raise exception
        with patch.object(background_task_manager.db, 'query', side_effect=Exception("Database error")):
            # Mock sleep to prevent actual waiting
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                background_task_manager.is_running = True
                
                # Stop after first iteration
                def stop_after_first_call(*args):
                    background_task_manager.is_running = False
                    return asyncio.sleep(0)
                
                mock_sleep.side_effect = stop_after_first_call
                
                # Run the loop - should not raise exception
                await background_task_manager._periodic_monitoring_loop()
                
                # Verify the loop handled the error gracefully
                assert background_task_manager.is_running is False


class TestBackgroundTaskManagerEdgeCases:
    """Test edge cases and error conditions for BackgroundTaskManager"""
    
    @pytest.fixture
    def broken_db_session(self):
        """Create a database session that will fail operations"""
        mock_session = Mock()
        mock_session.query.side_effect = Exception("Database connection failed")
        mock_session.commit.side_effect = Exception("Commit failed")
        mock_session.rollback.return_value = None
        return mock_session
    
    @pytest.fixture
    def background_task_manager_broken_db(self, broken_db_session):
        """Create BackgroundTaskManager with broken database"""
        return BackgroundTaskManager(broken_db_session)
    
    @pytest.fixture
    def db_session(self):
        """Create an in-memory SQLite database for testing"""
        engine = create_engine('sqlite:///:memory:', echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
    
    @pytest.fixture
    def mock_sticker_manager(self):
        """Create a mock StickerManager for testing"""
        mock_manager = Mock(spec=StickerManager)
        mock_manager.cleanup_expired_stickers = AsyncMock(return_value=2)
        return mock_manager
    
    @pytest.fixture
    def background_task_manager(self, db_session, mock_sticker_manager):
        """Create BackgroundTaskManager instance for testing"""
        return BackgroundTaskManager(db_session, mock_sticker_manager)
    
    @pytest.mark.asyncio
    async def test_cleanup_with_database_failure(self, background_task_manager_broken_db):
        """Test cleanup behavior when database operations fail"""
        # The sticker manager will also fail, so we need to mock it to fail too
        mock_sticker_manager = Mock(spec=StickerManager)
        mock_sticker_manager.cleanup_expired_stickers = AsyncMock(side_effect=Exception("Sticker cleanup failed"))
        background_task_manager_broken_db.sticker_manager = mock_sticker_manager
        
        result = await background_task_manager_broken_db.cleanup_expired_access()
        
        assert isinstance(result, CleanupResult)
        assert result.cleaned_users == 0
        assert result.cleaned_files == 0
        assert len(result.errors) > 0  # Should have errors from sticker cleanup and VIP cleanup
    
    @pytest.mark.asyncio
    async def test_health_monitoring_with_database_failure(self, background_task_manager_broken_db):
        """Test health monitoring when database is unavailable"""
        health_status = await background_task_manager_broken_db.monitor_parsing_health()
        
        assert isinstance(health_status, HealthStatus)
        assert health_status.is_healthy is False
        assert health_status.database_connected is False
        assert len(health_status.errors) > 0
    
    @pytest.mark.asyncio
    async def test_start_with_exception(self, background_task_manager):
        """Test starting background tasks when asyncio.create_task fails"""
        with patch('asyncio.create_task', side_effect=Exception("Task creation failed")):
            with pytest.raises(BackgroundTaskError):
                await background_task_manager.start_periodic_cleanup()
            
            assert background_task_manager.is_running is False
    
    @pytest.mark.asyncio
    async def test_stop_with_exception(self, background_task_manager):
        """Test stopping background tasks when cancellation fails"""
        # Start tasks first
        await background_task_manager.start_periodic_cleanup()
        
        # Mock task cancellation to raise exception
        with patch.object(background_task_manager.cleanup_task, 'cancel', side_effect=Exception("Cancel failed")):
            with pytest.raises(BackgroundTaskError):
                await background_task_manager.stop_periodic_cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])