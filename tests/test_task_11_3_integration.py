#!/usr/bin/env python3
"""
Integration test for Task 11.3: Initialize background task system
Tests that the bot can start up with background task system integration
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


class TestBackgroundTaskIntegration:
    """Integration test for background task system initialization"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        mock_session = Mock()
        mock_session.query.return_value.count.return_value = 0
        mock_session.query.return_value.filter.return_value.all.return_value = []
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
    
    def test_bot_initialization_with_background_tasks(self, mock_get_db, mock_settings, 
                                                     mock_create_tables, mock_application_builder):
        """Test that bot initializes correctly with background task system"""
        mock_builder, mock_app = mock_application_builder
        
        # Mock all the systems that get initialized
        with patch('bot.bot.EnhancedShopSystem') as mock_shop, \
             patch('bot.bot.AchievementSystem') as mock_achievements, \
             patch('bot.bot.MonitoringSystem') as mock_monitoring, \
             patch('bot.bot.AlertSystem') as mock_alert, \
             patch('bot.bot.BackupSystem') as mock_backup, \
             patch('bot.bot.ErrorHandlingSystem') as mock_error:
            
            # Configure mocks
            mock_shop.return_value.initialize_default_categories.return_value = None
            mock_shop.return_value.initialize_default_items.return_value = None
            
            # Create bot instance
            bot = TelegramBot()
            
            # Verify bot was created successfully
            assert bot is not None
            assert hasattr(bot, 'background_task_manager')
            assert hasattr(bot, 'sticker_manager')
            assert hasattr(bot, '_shutdown_requested')
            
            # Verify background task manager is initially None (not started yet)
            assert bot.background_task_manager is None
            assert bot.sticker_manager is None
            
            # Verify shutdown flag is False
            assert bot._shutdown_requested is False
    
    @pytest.mark.asyncio
    async def test_background_system_startup_sequence(self, mock_get_db, mock_settings,
                                                     mock_create_tables, mock_application_builder):
        """Test the complete background system startup sequence"""
        mock_builder, mock_app = mock_application_builder
        
        # Mock the background task manager to track initialization
        with patch.object(BackgroundTaskManager, '__init__', return_value=None) as mock_btm_init, \
             patch.object(BackgroundTaskManager, 'start_periodic_cleanup', new_callable=AsyncMock) as mock_start, \
             patch.object(BackgroundTaskManager, 'get_task_status') as mock_status:
            
            # Configure successful startup
            mock_status.return_value = {
                'is_running': True,
                'cleanup_interval_seconds': 300,
                'monitoring_interval_seconds': 60,
                'cleanup_task_running': True,
                'monitoring_task_running': True
            }
            
            # Create bot and initialize background systems
            bot = TelegramBot()
            await bot._initialize_background_systems()
            
            # Verify initialization sequence
            mock_btm_init.assert_called_once()
            mock_start.assert_called_once()
            mock_status.assert_called_once()
            
            # Verify bot state after initialization
            assert bot.background_task_manager is not None
            assert bot.sticker_manager is not None
            assert bot.is_background_system_running() is True
    
    @pytest.mark.asyncio
    async def test_complete_startup_shutdown_cycle(self, mock_get_db, mock_settings,
                                                  mock_create_tables, mock_application_builder):
        """Test complete startup and shutdown cycle"""
        mock_builder, mock_app = mock_application_builder
        
        # Mock the background task manager
        with patch.object(BackgroundTaskManager, '__init__', return_value=None) as mock_btm_init, \
             patch.object(BackgroundTaskManager, 'start_periodic_cleanup', new_callable=AsyncMock) as mock_start, \
             patch.object(BackgroundTaskManager, 'stop_periodic_cleanup', new_callable=AsyncMock) as mock_stop, \
             patch.object(BackgroundTaskManager, 'get_task_status') as mock_status:
            
            # Configure startup and shutdown sequence
            # First call during initialization, second call during status check, third call after shutdown
            mock_status.side_effect = [
                {'is_running': True, 'cleanup_task_running': True, 'monitoring_task_running': True},  # During initialization
                {'is_running': True, 'cleanup_task_running': True, 'monitoring_task_running': True},  # Status check
                {'is_running': False, 'cleanup_task_running': False, 'monitoring_task_running': False}  # After shutdown
            ]
            
            # Create bot and run startup/shutdown cycle
            bot = TelegramBot()
            
            # Initialize background systems
            await bot._initialize_background_systems()
            assert bot.is_background_system_running() is True
            
            # Shutdown background systems
            await bot._shutdown_background_tasks()
            
            # Verify shutdown sequence
            mock_stop.assert_called_once()
            assert bot.background_task_manager is None
            assert bot.sticker_manager is None
            assert bot.is_background_system_running() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])