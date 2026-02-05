"""
Test for background task integration with main bot application
Tests Requirements 12.1, 12.5
"""

import pytest
import asyncio
import os
import sys
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.managers.background_task_manager import BackgroundTaskManager
from core.managers.sticker_manager import StickerManager
from database.database import get_db


class TestBackgroundIntegration:
    """Test background task integration with main bot application"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.count.return_value = 0
        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_session.commit.return_value = None
        mock_session.rollback.return_value = None
        mock_session.close.return_value = None
        return mock_session
    
    @pytest.fixture
    def mock_sticker_manager(self, mock_db_session):
        """Mock sticker manager"""
        sticker_manager = Mock(spec=StickerManager)
        sticker_manager.cleanup_expired_stickers = AsyncMock(return_value=0)
        return sticker_manager
    
    @pytest.fixture
    def background_task_manager(self, mock_db_session, mock_sticker_manager):
        """Create BackgroundTaskManager instance for testing"""
        return BackgroundTaskManager(mock_db_session, mock_sticker_manager)
    
    @pytest.mark.asyncio
    async def test_background_task_manager_initialization(self, background_task_manager):
        """Test that BackgroundTaskManager initializes correctly"""
        # Verify initialization
        assert background_task_manager is not None
        assert background_task_manager.is_running is False
        assert background_task_manager.cleanup_interval_seconds == 300  # 5 minutes
        assert background_task_manager.monitoring_interval_seconds == 60  # 1 minute
        
        # Verify task references are None initially
        assert background_task_manager.cleanup_task is None
        assert background_task_manager.monitoring_task is None
    
    @pytest.mark.asyncio
    async def test_background_task_startup_and_shutdown(self, background_task_manager):
        """Test background task startup and graceful shutdown"""
        # Test startup
        await background_task_manager.start_periodic_cleanup()
        
        # Verify tasks are running
        assert background_task_manager.is_running is True
        assert background_task_manager.cleanup_task is not None
        assert background_task_manager.monitoring_task is not None
        assert not background_task_manager.cleanup_task.done()
        assert not background_task_manager.monitoring_task.done()
        
        # Test graceful shutdown
        await background_task_manager.stop_periodic_cleanup()
        
        # Verify tasks are stopped
        assert background_task_manager.is_running is False
        
        # Wait a bit for tasks to complete cancellation
        await asyncio.sleep(0.1)
        
        # Tasks should be cancelled
        assert background_task_manager.cleanup_task.cancelled() or background_task_manager.cleanup_task.done()
        assert background_task_manager.monitoring_task.cancelled() or background_task_manager.monitoring_task.done()
    
    @pytest.mark.asyncio
    async def test_background_task_error_handling(self, background_task_manager, mock_sticker_manager):
        """Test that background tasks handle errors gracefully and continue operation"""
        # Make sticker manager raise an exception
        mock_sticker_manager.cleanup_expired_stickers.side_effect = Exception("Test error")
        
        # Start background tasks
        await background_task_manager.start_periodic_cleanup()
        
        # Verify tasks are still running despite errors
        assert background_task_manager.is_running is True
        
        # Perform cleanup - should handle error gracefully
        cleanup_result = await background_task_manager.cleanup_expired_access()
        
        # Verify error was handled gracefully
        assert cleanup_result is not None
        assert len(cleanup_result.errors) > 0
        assert "Error cleaning up sticker access" in str(cleanup_result.errors)
        
        # Verify tasks are still running
        assert background_task_manager.is_running is True
        
        # Clean up
        await background_task_manager.stop_periodic_cleanup()
    
    @pytest.mark.asyncio
    async def test_health_monitoring(self, background_task_manager):
        """Test system health monitoring functionality"""
        # Start background tasks
        await background_task_manager.start_periodic_cleanup()
        
        # Test health monitoring
        health_status = await background_task_manager.monitor_parsing_health()
        
        # Verify health status structure
        assert health_status is not None
        assert hasattr(health_status, 'is_healthy')
        assert hasattr(health_status, 'parsing_active')
        assert hasattr(health_status, 'background_tasks_running')
        assert hasattr(health_status, 'database_connected')
        assert hasattr(health_status, 'last_check')
        assert hasattr(health_status, 'errors')
        
        # Verify background tasks are reported as running
        assert health_status.background_tasks_running is True
        
        # Verify last_check is recent
        assert isinstance(health_status.last_check, datetime)
        
        # Clean up
        await background_task_manager.stop_periodic_cleanup()
    
    @pytest.mark.asyncio
    async def test_task_status_reporting(self, background_task_manager):
        """Test task status reporting functionality"""
        # Get initial status
        initial_status = background_task_manager.get_task_status()
        
        # Verify initial status
        assert initial_status['is_running'] is False
        assert initial_status['cleanup_task_running'] is False
        assert initial_status['monitoring_task_running'] is False
        assert 'cleanup_interval_seconds' in initial_status
        assert 'monitoring_interval_seconds' in initial_status
        assert 'last_status_check' in initial_status
        
        # Start tasks
        await background_task_manager.start_periodic_cleanup()
        
        # Get running status
        running_status = background_task_manager.get_task_status()
        
        # Verify running status
        assert running_status['is_running'] is True
        assert running_status['cleanup_task_running'] is True
        assert running_status['monitoring_task_running'] is True
        
        # Clean up
        await background_task_manager.stop_periodic_cleanup()
        
        # Get stopped status
        stopped_status = background_task_manager.get_task_status()
        
        # Verify stopped status
        assert stopped_status['is_running'] is False
    
    @pytest.mark.asyncio
    async def test_double_start_prevention(self, background_task_manager):
        """Test that starting already running tasks is handled gracefully"""
        # Start tasks first time
        await background_task_manager.start_periodic_cleanup()
        assert background_task_manager.is_running is True
        
        # Try to start again - should not raise error
        await background_task_manager.start_periodic_cleanup()
        assert background_task_manager.is_running is True
        
        # Clean up
        await background_task_manager.stop_periodic_cleanup()
    
    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, background_task_manager):
        """Test that stopping non-running tasks is handled gracefully"""
        # Verify not running initially
        assert background_task_manager.is_running is False
        
        # Try to stop - should not raise error
        await background_task_manager.stop_periodic_cleanup()
        assert background_task_manager.is_running is False
    
    def test_signal_handler_setup(self):
        """Test that signal handlers can be set up without errors"""
        # This test verifies that the signal handler setup code doesn't crash
        # We can't easily test the actual signal handling in unit tests
        
        # Import the bot class
        from bot.bot import TelegramBot
        
        # Create bot instance - this should set up signal handlers
        with patch('bot.bot.Application') as mock_app, \
             patch('bot.bot.AdvancedAdminCommands') as mock_advanced_admin, \
             patch('bot.bot.AdminSystem') as mock_admin_system:
            
            mock_app.builder.return_value.token.return_value.build.return_value = Mock()
            
            # Create proper mocks for command methods
            mock_commands = Mock()
            mock_commands.parsing_stats_command.__name__ = 'parsing_stats_command'
            mock_commands.broadcast_command.__name__ = 'broadcast_command'
            mock_commands.user_stats_command.__name__ = 'user_stats_command'
            mock_commands.add_item_command.__name__ = 'add_item_command'
            mock_advanced_admin.return_value = mock_commands
            
            mock_admin_system.return_value = Mock()
            
            # This should not raise any exceptions
            bot = TelegramBot()
            
            # Verify bot was created
            assert bot is not None
            assert hasattr(bot, '_shutdown_requested')
            assert bot._shutdown_requested is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])