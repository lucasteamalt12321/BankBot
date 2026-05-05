"""
Unit tests for shutdown resource cleanup (Task 9.2.2)

Tests cover:
- Database connection cleanup
- Background task cancellation
- Bot session/application closure
- PID file removal
- Error handling during cleanup
- Graceful degradation when resources are missing

Validates: Requirements 9.2, 9.3 - Graceful shutdown with resource cleanup
Validates: Design section 9 - Resource cleanup implementation
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestShutdownResourceCleanup:
    """Test resource cleanup during shutdown (Task 9.2.2)"""

    @pytest.mark.asyncio
    async def test_shutdown_closes_database_connections(self):
        """
        Test that shutdown closes database connections
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import BotApplication

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid'):

            app = BotApplication()
            await app.shutdown()

            # Verify database engine dispose was called
            mock_engine.dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_stops_background_tasks(self):
        """
        Test that shutdown stops background tasks
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import BotApplication

        app = BotApplication()

        # Create mock bot with background task manager
        mock_bot = MagicMock()
        mock_task_manager = MagicMock()
        mock_task_manager.stop_periodic_cleanup = AsyncMock()
        mock_bot.background_task_manager = mock_task_manager
        app.bot = mock_bot

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid'):

            mock_engine.dispose = MagicMock()
            await app.shutdown()

            # Verify background tasks were stopped
            mock_task_manager.stop_periodic_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_stops_bot_application(self):
        """
        Test that shutdown stops bot application
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import BotApplication

        app = BotApplication()

        # Create mock bot with application
        mock_bot = MagicMock()
        mock_application = MagicMock()
        mock_application.running = True
        mock_application.stop = AsyncMock()
        mock_bot.application = mock_application
        app.bot = mock_bot

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid'):

            mock_engine.dispose = MagicMock()
            await app.shutdown()

            # Verify bot application stop was called
            mock_application.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_removes_pid_file(self):
        """
        Test that shutdown removes PID file
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import BotApplication

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid') as mock_remove:

            mock_engine.dispose = MagicMock()
            app = BotApplication()
            await app.shutdown()

            # Verify PID file is removed
            mock_remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_order_of_operations(self):
        """
        Test that shutdown performs operations in correct order:
        1. Close database
        2. Stop background tasks
        3. Stop bot application
        4. Remove PID file
        
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import BotApplication

        operations = []

        def track_db_dispose():
            operations.append('database')

        async def track_task_stop():
            operations.append('background_tasks')

        async def track_bot_stop():
            operations.append('bot_application')

        def track_pid_remove():
            operations.append('pid_file')

        app = BotApplication()

        # Create mock bot with all components
        mock_bot = MagicMock()
        mock_task_manager = MagicMock()
        mock_task_manager.stop_periodic_cleanup = track_task_stop
        mock_bot.background_task_manager = mock_task_manager

        mock_application = MagicMock()
        mock_application.running = True
        mock_application.stop = track_bot_stop
        mock_bot.application = mock_application
        app.bot = mock_bot

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid', side_effect=track_pid_remove):

            mock_engine.dispose = track_db_dispose
            await app.shutdown()

            # Verify order
            assert operations == ['database', 'background_tasks', 'bot_application', 'pid_file']

    @pytest.mark.asyncio
    async def test_shutdown_handles_database_error(self):
        """
        Test that shutdown continues even if database cleanup fails
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import BotApplication

        app = BotApplication()

        # Create mock bot
        mock_bot = MagicMock()
        mock_task_manager = MagicMock()
        mock_task_manager.stop_periodic_cleanup = AsyncMock()
        mock_bot.background_task_manager = mock_task_manager

        mock_application = MagicMock()
        mock_application.running = True
        mock_application.stop = AsyncMock()
        mock_bot.application = mock_application
        app.bot = mock_bot

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid') as mock_remove:

            # Simulate database error
            mock_engine.dispose.side_effect = Exception("Database error")

            # Should not raise exception
            result = await app.shutdown()

            # Should still stop background tasks
            mock_task_manager.stop_periodic_cleanup.assert_called_once()

            # Should still stop bot
            mock_application.stop.assert_called_once()

            # Should still remove PID file
            mock_remove.assert_called_once()

            # Should return False indicating errors occurred
            assert result is False

    @pytest.mark.asyncio
    async def test_shutdown_handles_background_task_error(self):
        """
        Test that shutdown continues even if background task cleanup fails
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import BotApplication

        app = BotApplication()

        # Create mock bot with failing background task manager
        mock_bot = MagicMock()
        mock_task_manager = MagicMock()

        async def failing_stop():
            raise Exception("Background task error")

        mock_task_manager.stop_periodic_cleanup = failing_stop
        mock_bot.background_task_manager = mock_task_manager

        mock_application = MagicMock()
        mock_application.running = True
        mock_application.stop = AsyncMock()
        mock_bot.application = mock_application
        app.bot = mock_bot

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid') as mock_remove:

            mock_engine.dispose = MagicMock()

            # Should not raise exception
            result = await app.shutdown()

            # Should still stop bot
            mock_application.stop.assert_called_once()

            # Should still remove PID file
            mock_remove.assert_called_once()

            # Should return False indicating errors occurred
            assert result is False

    @pytest.mark.asyncio
    async def test_shutdown_handles_bot_stop_error(self):
        """
        Test that shutdown continues even if bot stop fails
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import BotApplication

        app = BotApplication()

        # Create mock bot with failing stop
        mock_bot = MagicMock()
        mock_application = MagicMock()
        mock_application.running = True

        async def failing_stop():
            raise Exception("Bot stop error")

        mock_application.stop = failing_stop
        mock_bot.application = mock_application
        app.bot = mock_bot

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid') as mock_remove:

            mock_engine.dispose = MagicMock()

            # Should not raise exception
            result = await app.shutdown()

            # Should still remove PID file
            mock_remove.assert_called_once()

            # Should return False indicating errors occurred
            assert result is False

    @pytest.mark.asyncio
    async def test_shutdown_handles_missing_bot(self):
        """
        Test that shutdown handles case when bot is not initialized
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import BotApplication

        app = BotApplication()
        app.bot = None

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid') as mock_remove:

            mock_engine.dispose = MagicMock()

            # Should not raise exception
            result = await app.shutdown()

            # Should still close database
            mock_engine.dispose.assert_called_once()

            # Should still remove PID file
            mock_remove.assert_called_once()

            # Should return True (no errors)
            assert result is True

    @pytest.mark.asyncio
    async def test_shutdown_handles_missing_background_task_manager(self):
        """
        Test that shutdown handles case when background task manager is not initialized
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import BotApplication

        app = BotApplication()

        # Create mock bot without background task manager
        mock_bot = MagicMock()
        mock_bot.background_task_manager = None

        mock_application = MagicMock()
        mock_application.running = True
        mock_application.stop = AsyncMock()
        mock_bot.application = mock_application
        app.bot = mock_bot

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid') as mock_remove:

            mock_engine.dispose = MagicMock()

            # Should not raise exception
            result = await app.shutdown()

            # Should still stop bot
            mock_application.stop.assert_called_once()

            # Should still remove PID file
            mock_remove.assert_called_once()

            # Should return True (no errors)
            assert result is True

    @pytest.mark.asyncio
    async def test_shutdown_handles_bot_not_running(self):
        """
        Test that shutdown handles case when bot application is not running
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import BotApplication

        app = BotApplication()

        # Create mock bot with non-running application
        mock_bot = MagicMock()
        mock_application = MagicMock()
        mock_application.running = False
        mock_application.stop = AsyncMock()
        mock_bot.application = mock_application
        mock_bot.background_task_manager = None  # No background task manager
        app.bot = mock_bot

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid') as mock_remove:

            mock_engine.dispose = MagicMock()

            # Should not raise exception
            result = await app.shutdown()

            # Should not try to stop bot (it's not running)
            mock_application.stop.assert_not_called()

            # Should still remove PID file
            mock_remove.assert_called_once()

            # Should return True (no errors)
            assert result is True

    @pytest.mark.asyncio
    async def test_shutdown_removes_pid_even_on_multiple_errors(self):
        """
        Test that PID file is removed even when multiple cleanup steps fail
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import BotApplication

        app = BotApplication()

        # Create mock bot with all components failing
        mock_bot = MagicMock()

        async def failing_task_stop():
            raise Exception("Task error")

        mock_task_manager = MagicMock()
        mock_task_manager.stop_periodic_cleanup = failing_task_stop
        mock_bot.background_task_manager = mock_task_manager

        async def failing_bot_stop():
            raise Exception("Bot error")

        mock_application = MagicMock()
        mock_application.running = True
        mock_application.stop = failing_bot_stop
        mock_bot.application = mock_application
        app.bot = mock_bot

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid') as mock_remove:

            # Database also fails
            mock_engine.dispose.side_effect = Exception("Database error")

            # Should not raise exception
            result = await app.shutdown()

            # Should still remove PID file
            mock_remove.assert_called_once()

            # Should return False indicating errors occurred
            assert result is False

    @pytest.mark.asyncio
    async def test_shutdown_returns_true_on_success(self):
        """
        Test that shutdown returns True when all cleanup succeeds
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import BotApplication

        app = BotApplication()

        # Create mock bot with all components
        mock_bot = MagicMock()
        mock_task_manager = MagicMock()
        mock_task_manager.stop_periodic_cleanup = AsyncMock()
        mock_bot.background_task_manager = mock_task_manager

        mock_application = MagicMock()
        mock_application.running = True
        mock_application.stop = AsyncMock()
        mock_bot.application = mock_application
        app.bot = mock_bot

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid'):

            mock_engine.dispose = MagicMock()

            # Should return True on success
            result = await app.shutdown()
            assert result is True

    @pytest.mark.asyncio
    async def test_shutdown_returns_false_on_any_error(self):
        """
        Test that shutdown returns False when any cleanup step fails
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import BotApplication

        app = BotApplication()

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid'):

            # Simulate database error
            mock_engine.dispose.side_effect = Exception("Database error")

            # Should return False on error
            result = await app.shutdown()
            assert result is False


class TestShutdownLogging:
    """Test logging during shutdown"""

    @pytest.mark.asyncio
    async def test_shutdown_logs_start(self):
        """Test that shutdown logs start message"""
        from bot.main import BotApplication

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.logger') as mock_logger:

            mock_engine.dispose = MagicMock()
            app = BotApplication()
            await app.shutdown()

            # Verify start message was logged
            start_calls = [call for call in mock_logger.info.call_args_list 
                          if 'Starting graceful shutdown' in str(call)]
            assert len(start_calls) > 0

    @pytest.mark.asyncio
    async def test_shutdown_logs_success(self):
        """Test that shutdown logs success message"""
        from bot.main import BotApplication

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.logger') as mock_logger:

            mock_engine.dispose = MagicMock()
            app = BotApplication()
            await app.shutdown()

            # Verify success message was logged
            success_calls = [call for call in mock_logger.info.call_args_list 
                            if 'completed successfully' in str(call)]
            assert len(success_calls) > 0

    @pytest.mark.asyncio
    async def test_shutdown_logs_errors(self):
        """Test that shutdown logs errors"""
        from bot.main import BotApplication

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.logger') as mock_logger:

            # Simulate error
            mock_engine.dispose.side_effect = Exception("Test error")

            app = BotApplication()
            await app.shutdown()

            # Verify error was logged
            error_calls = [call for call in mock_logger.error.call_args_list 
                          if 'error' in str(call).lower()]
            assert len(error_calls) > 0

    @pytest.mark.asyncio
    async def test_shutdown_logs_each_step(self):
        """Test that shutdown logs each cleanup step"""
        from bot.main import BotApplication

        app = BotApplication()

        # Create mock bot with all components
        mock_bot = MagicMock()
        mock_task_manager = MagicMock()
        mock_task_manager.stop_periodic_cleanup = AsyncMock()
        mock_bot.background_task_manager = mock_task_manager

        mock_application = MagicMock()
        mock_application.running = True
        mock_application.stop = AsyncMock()
        mock_bot.application = mock_application
        app.bot = mock_bot

        with patch('database.database.engine') as mock_engine, \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.logger') as mock_logger:

            mock_engine.dispose = MagicMock()
            await app.shutdown()

            # Verify each step was logged
            log_messages = [str(call) for call in mock_logger.info.call_args_list]

            # Check for key log messages
            assert any('database' in msg.lower() for msg in log_messages)
            assert any('background' in msg.lower() for msg in log_messages)
            assert any('bot' in msg.lower() or 'application' in msg.lower() for msg in log_messages)
            assert any('pid' in msg.lower() for msg in log_messages)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
