#!/usr/bin/env python3
"""
Test for Task 11.3: Initialize background task system
Tests that BackgroundTaskManager is properly initialized on bot startup
"""

import os
import sys
import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.bot import TelegramBot
from core.background_task_manager import BackgroundTaskManager
from core.sticker_manager import StickerManager


class TestBackgroundTaskInitialization:
    """Test background task system initialization (Task 11.3)"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        mock_session = Mock()
        mock_session.query.return_value.count.return_value = 0
        mock_session.commit.return_value = None
        mock_session.close.return_value = None
        return mock_session
    
    @pytest.fixture
    def mock_get_db(self, mock_db_session):
        """Mock get_db function"""
        with patch('bot.bot.get_db') as mock:
            mock.return_value.__next__.return_value = mock_db_session
            yield mock
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings"""
        with patch('bot.bot.settings') as mock:
            mock.bot_token = "test_token"
            yield mock
    
    @pytest.fixture
    def mock_create_tables(self):
        """Mock create_tables function"""
        with patch('bot.bot.create_tables') as mock:
            yield mock
    
    @pytest.fixture
    def mock_application_builder(self):
        """Mock Telegram Application builder"""
        with patch('bot.bot.Application') as mock:
            mock_app = Mock()
            mock_app.add_handler = Mock()
            mock_app.add_error_handler = Mock()
            mock_app.run_polling = Mock()
            mock_app.stop_running = Mock()
            
            mock.builder.return_value.token.return_value.build.return_value = mock_app
            yield mock, mock_app
    
    @pytest.mark.asyncio
    async def test_background_system_initialization(self, mock_get_db, mock_settings, 
                                                   mock_create_tables, mock_application_builder):
        """Test that background task system initializes correctly on bot startup"""
        mock_builder, mock_app = mock_application_builder
        
        # Mock the background task manager methods
        with patch.object(BackgroundTaskManager, '__init__', return_value=None) as mock_btm_init, \
             patch.object(BackgroundTaskManager, 'start_periodic_cleanup', new_callable=AsyncMock) as mock_start, \
             patch.object(BackgroundTaskManager, 'get_task_status') as mock_status, \
             patch.object(StickerManager, '__init__', return_value=None) as mock_sm_init:
            
            # Configure mock returns
            mock_status.return_value = {
                'is_running': True,
                'cleanup_interval_seconds': 300,
                'monitoring_interval_seconds': 60,
                'cleanup_task_running': True,
                'monitoring_task_running': True
            }
            
            # Create bot instance
            bot = TelegramBot()
            
            # Test the background system initialization method directly
            await bot._initialize_background_systems()
            
            # Verify StickerManager was initialized
            mock_sm_init.assert_called_once()
            
            # Verify BackgroundTaskManager was initialized
            mock_btm_init.assert_called_once()
            
            # Verify periodic cleanup was started
            mock_start.assert_called_once()
            
            # Verify task status was checked
            mock_status.assert_called_once()
            
            # Verify bot has references to the managers
            assert bot.background_task_manager is not None
            assert bot.sticker_manager is not None
    
    @pytest.mark.asyncio
    async def test_background_system_initialization_failure(self, mock_get_db, mock_settings,
                                                           mock_create_tables, mock_application_builder):
        """Test that initialization failure is handled gracefully"""
        mock_builder, mock_app = mock_application_builder
        
        # Mock initialization to fail
        with patch.object(BackgroundTaskManager, '__init__', side_effect=Exception("Init failed")) as mock_btm_init, \
             patch.object(StickerManager, '__init__', return_value=None) as mock_sm_init:
            
            # Create bot instance
            bot = TelegramBot()
            
            # Test that initialization failure raises exception
            with pytest.raises(Exception, match="Init failed"):
                await bot._initialize_background_systems()
            
            # Verify cleanup occurred
            assert bot.background_task_manager is None
            assert bot.sticker_manager is None
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, mock_get_db, mock_settings, 
                                   mock_create_tables, mock_application_builder):
        """Test graceful shutdown of background tasks"""
        mock_builder, mock_app = mock_application_builder
        
        # Mock the background task manager methods
        with patch.object(BackgroundTaskManager, '__init__', return_value=None) as mock_btm_init, \
             patch.object(BackgroundTaskManager, 'start_periodic_cleanup', new_callable=AsyncMock) as mock_start, \
             patch.object(BackgroundTaskManager, 'stop_periodic_cleanup', new_callable=AsyncMock) as mock_stop, \
             patch.object(BackgroundTaskManager, 'get_task_status') as mock_status, \
             patch.object(StickerManager, '__init__', return_value=None) as mock_sm_init:
            
            # Configure mock returns - first call returns running, second call returns stopped
            mock_status.side_effect = [
                {
                    'is_running': True,  # Running after initialization
                    'cleanup_interval_seconds': 300,
                    'monitoring_interval_seconds': 60,
                    'cleanup_task_running': True,
                    'monitoring_task_running': True
                },
                {
                    'is_running': False,  # Stopped after shutdown
                    'cleanup_interval_seconds': 300,
                    'monitoring_interval_seconds': 60,
                    'cleanup_task_running': False,
                    'monitoring_task_running': False
                }
            ]
            
            # Create bot instance and initialize background systems
            bot = TelegramBot()
            await bot._initialize_background_systems()
            
            # Test graceful shutdown
            await bot._shutdown_background_tasks()
            
            # Verify stop was called
            mock_stop.assert_called_once()
            
            # Verify references were cleared
            assert bot.background_task_manager is None
            assert bot.sticker_manager is None
    
    def test_is_background_system_running(self, mock_get_db, mock_settings,
                                        mock_create_tables, mock_application_builder):
        """Test background system status checking"""
        mock_builder, mock_app = mock_application_builder
        
        # Create bot instance
        bot = TelegramBot()
        
        # Test when no background task manager
        assert bot.is_background_system_running() is False
        
        # Mock background task manager
        mock_btm = Mock()
        mock_btm.get_task_status.return_value = {'is_running': True}
        bot.background_task_manager = mock_btm
        
        # Test when running
        assert bot.is_background_system_running() is True
        
        # Test when not running
        mock_btm.get_task_status.return_value = {'is_running': False}
        assert bot.is_background_system_running() is False
        
        # Test when status check fails
        mock_btm.get_task_status.side_effect = Exception("Status check failed")
        assert bot.is_background_system_running() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])