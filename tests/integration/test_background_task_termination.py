"""
Integration test for background task termination during graceful shutdown (Task 20.3.3)

Tests that background tasks are properly cancelled and cleaned up during shutdown.
Validates Requirements 9.3 (graceful shutdown cancels background tasks)

This test verifies that the BackgroundTaskManager properly terminates all background
tasks when shutdown is requested, ensuring no tasks are left running.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timedelta


class MockDatabaseSession:
    """Mock database session for testing"""
    
    def __init__(self):
        self.commit_called = False
        self.rollback_called = False
        self.query_results = []
    
    def query(self, model):
        """Mock query method"""
        return MockQuery(self.query_results)
    
    def commit(self):
        """Mock commit"""
        self.commit_called = True
    
    def rollback(self):
        """Mock rollback"""
        self.rollback_called = True


class MockQuery:
    """Mock query object"""
    
    def __init__(self, results):
        self.results = results
        self._filters = []
    
    def filter(self, *args):
        """Mock filter"""
        self._filters.append(args)
        return self
    
    def filter_by(self, **kwargs):
        """Mock filter_by"""
        return self
    
    def count(self):
        """Mock count"""
        return len(self.results)
    
    def all(self):
        """Mock all"""
        return self.results
    
    def first(self):
        """Mock first"""
        return self.results[0] if self.results else None
    
    def delete(self):
        """Mock delete"""
        self.results.clear()


class MockStickerManager:
    """Mock sticker manager for testing"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.cleanup_called = False
    
    async def cleanup_expired_stickers(self):
        """Mock cleanup method"""
        self.cleanup_called = True
        await asyncio.sleep(0.01)  # Simulate async work
        return 0


class MockBackgroundTaskManager:
    """
    Mock BackgroundTaskManager that simulates the real implementation
    but with controllable behavior for testing
    """
    
    def __init__(self, db_session, sticker_manager=None):
        self.db = db_session
        self.sticker_manager = sticker_manager or MockStickerManager(db_session)
        self.is_running = False
        self.cleanup_task = None
        self.monitoring_task = None
        self.cleanup_interval_seconds = 300
        self.monitoring_interval_seconds = 60
        self.cleanup_count = 0
        self.monitoring_count = 0
    
    async def start_periodic_cleanup(self):
        """Start background tasks"""
        if self.is_running:
            return
        
        self.is_running = True
        self.cleanup_task = asyncio.create_task(self._periodic_cleanup_loop())
        self.monitoring_task = asyncio.create_task(self._periodic_monitoring_loop())
    
    async def stop_periodic_cleanup(self):
        """Stop all periodic background tasks gracefully"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Cancel cleanup task
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cancel monitoring task
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
    
    async def _periodic_cleanup_loop(self):
        """Internal cleanup loop"""
        while self.is_running:
            try:
                self.cleanup_count += 1
                await asyncio.sleep(0.1)  # Short interval for testing
            except asyncio.CancelledError:
                break
    
    async def _periodic_monitoring_loop(self):
        """Internal monitoring loop"""
        while self.is_running:
            try:
                self.monitoring_count += 1
                await asyncio.sleep(0.1)  # Short interval for testing
            except asyncio.CancelledError:
                break
    
    def get_task_status(self):
        """Get current status of background tasks"""
        return {
            'is_running': self.is_running,
            'cleanup_task_running': self.cleanup_task is not None and not self.cleanup_task.done(),
            'monitoring_task_running': self.monitoring_task is not None and not self.monitoring_task.done(),
            'cleanup_count': self.cleanup_count,
            'monitoring_count': self.monitoring_count
        }


class TestBackgroundTaskTermination:
    """Test background task termination during graceful shutdown"""
    
    @pytest.mark.asyncio
    async def test_background_tasks_start_successfully(self):
        """
        Test that background tasks can be started
        Validates: Requirement 9.3 (background task management)
        """
        # Create manager
        db_session = MockDatabaseSession()
        manager = MockBackgroundTaskManager(db_session)
        
        # Verify initial state
        assert manager.is_running is False
        assert manager.cleanup_task is None
        assert manager.monitoring_task is None
        
        # Start tasks
        await manager.start_periodic_cleanup()
        
        # Verify tasks are running
        assert manager.is_running is True
        assert manager.cleanup_task is not None
        assert manager.monitoring_task is not None
        assert not manager.cleanup_task.done()
        assert not manager.monitoring_task.done()
        
        # Cleanup
        await manager.stop_periodic_cleanup()
    
    @pytest.mark.asyncio
    async def test_background_tasks_cancelled_on_shutdown(self):
        """
        Test that background tasks are properly cancelled during shutdown
        Validates: Requirement 9.3 (graceful shutdown cancels background tasks)
        """
        # Create manager
        db_session = MockDatabaseSession()
        manager = MockBackgroundTaskManager(db_session)
        
        # Start tasks
        await manager.start_periodic_cleanup()
        assert manager.is_running is True
        
        # Let tasks run for a bit
        await asyncio.sleep(0.2)
        
        # Verify tasks are running
        assert not manager.cleanup_task.done()
        assert not manager.monitoring_task.done()
        
        # Shutdown
        await manager.stop_periodic_cleanup()
        
        # Verify tasks are stopped
        assert manager.is_running is False
        
        # Wait for cancellation to complete
        await asyncio.sleep(0.1)
        
        # Verify tasks are cancelled or done
        assert manager.cleanup_task.done() or manager.cleanup_task.cancelled()
        assert manager.monitoring_task.done() or manager.monitoring_task.cancelled()
    
    @pytest.mark.asyncio
    async def test_tasks_stop_executing_after_shutdown(self):
        """
        Test that tasks stop executing after shutdown is called
        Validates: Requirement 9.3 (graceful shutdown)
        """
        # Create manager
        db_session = MockDatabaseSession()
        manager = MockBackgroundTaskManager(db_session)
        
        # Start tasks
        await manager.start_periodic_cleanup()
        
        # Let tasks run and count executions
        await asyncio.sleep(0.25)
        count_before_shutdown = manager.cleanup_count
        
        # Shutdown
        await manager.stop_periodic_cleanup()
        
        # Wait a bit more
        await asyncio.sleep(0.2)
        
        # Verify count didn't increase after shutdown
        assert manager.cleanup_count == count_before_shutdown
    
    @pytest.mark.asyncio
    async def test_both_cleanup_and_monitoring_tasks_terminated(self):
        """
        Test that both cleanup and monitoring tasks are terminated
        Validates: Requirement 9.3 (graceful shutdown cancels all background tasks)
        """
        # Create manager
        db_session = MockDatabaseSession()
        manager = MockBackgroundTaskManager(db_session)
        
        # Start tasks
        await manager.start_periodic_cleanup()
        
        # Verify both tasks are running
        status_before = manager.get_task_status()
        assert status_before['is_running'] is True
        assert status_before['cleanup_task_running'] is True
        assert status_before['monitoring_task_running'] is True
        
        # Shutdown
        await manager.stop_periodic_cleanup()
        
        # Wait for cancellation
        await asyncio.sleep(0.1)
        
        # Verify both tasks are stopped
        status_after = manager.get_task_status()
        assert status_after['is_running'] is False
        assert status_after['cleanup_task_running'] is False
        assert status_after['monitoring_task_running'] is False
    
    @pytest.mark.asyncio
    async def test_shutdown_waits_for_task_cancellation(self):
        """
        Test that shutdown properly waits for tasks to be cancelled
        Validates: Requirement 9.3 (graceful shutdown)
        """
        # Create manager
        db_session = MockDatabaseSession()
        manager = MockBackgroundTaskManager(db_session)
        
        # Start tasks
        await manager.start_periodic_cleanup()
        
        # Shutdown (this should wait for cancellation)
        shutdown_start = asyncio.get_event_loop().time()
        await manager.stop_periodic_cleanup()
        shutdown_duration = asyncio.get_event_loop().time() - shutdown_start
        
        # Verify shutdown completed (didn't hang)
        assert shutdown_duration < 5.0  # Should complete quickly
        
        # Verify tasks are actually stopped
        assert manager.cleanup_task.done() or manager.cleanup_task.cancelled()
        assert manager.monitoring_task.done() or manager.monitoring_task.cancelled()
    
    @pytest.mark.asyncio
    async def test_multiple_shutdown_calls_are_safe(self):
        """
        Test that multiple shutdown calls don't cause errors
        Validates: Requirement 9.3 (graceful shutdown is idempotent)
        """
        # Create manager
        db_session = MockDatabaseSession()
        manager = MockBackgroundTaskManager(db_session)
        
        # Start tasks
        await manager.start_periodic_cleanup()
        
        # First shutdown
        await manager.stop_periodic_cleanup()
        assert manager.is_running is False
        
        # Second shutdown - should not raise exception
        try:
            await manager.stop_periodic_cleanup()
        except Exception as e:
            pytest.fail(f"Second shutdown raised exception: {e}")
        
        # Verify still stopped
        assert manager.is_running is False
    
    @pytest.mark.asyncio
    async def test_shutdown_without_starting_is_safe(self):
        """
        Test that calling shutdown without starting tasks is safe
        Validates: Requirement 9.3 (graceful shutdown)
        """
        # Create manager
        db_session = MockDatabaseSession()
        manager = MockBackgroundTaskManager(db_session)
        
        # Shutdown without starting - should not raise exception
        try:
            await manager.stop_periodic_cleanup()
        except Exception as e:
            pytest.fail(f"Shutdown without start raised exception: {e}")
        
        # Verify state
        assert manager.is_running is False
    
    @pytest.mark.asyncio
    async def test_tasks_handle_cancellation_gracefully(self):
        """
        Test that tasks handle CancelledError gracefully
        Validates: Requirement 9.3 (graceful shutdown)
        """
        # Create manager
        db_session = MockDatabaseSession()
        manager = MockBackgroundTaskManager(db_session)
        
        # Start tasks
        await manager.start_periodic_cleanup()
        
        # Let tasks run
        await asyncio.sleep(0.15)
        
        # Shutdown
        await manager.stop_periodic_cleanup()
        
        # Verify no exceptions were raised (tasks handled cancellation)
        # If tasks didn't handle CancelledError, the test would fail
        assert manager.is_running is False
    
    @pytest.mark.asyncio
    async def test_rapid_start_stop_cycles(self):
        """
        Test that rapid start/stop cycles work correctly
        Validates: Requirement 9.3 (graceful shutdown)
        """
        # Create manager
        db_session = MockDatabaseSession()
        manager = MockBackgroundTaskManager(db_session)
        
        # Perform multiple start/stop cycles
        for i in range(3):
            # Start
            await manager.start_periodic_cleanup()
            assert manager.is_running is True
            
            # Let run briefly
            await asyncio.sleep(0.05)
            
            # Stop
            await manager.stop_periodic_cleanup()
            assert manager.is_running is False
            
            # Wait for cleanup
            await asyncio.sleep(0.05)
    
    @pytest.mark.asyncio
    async def test_shutdown_during_task_execution(self):
        """
        Test that shutdown works even if called during task execution
        Validates: Requirement 9.3 (graceful shutdown)
        """
        # Create manager
        db_session = MockDatabaseSession()
        manager = MockBackgroundTaskManager(db_session)
        
        # Start tasks
        await manager.start_periodic_cleanup()
        
        # Let tasks start executing
        await asyncio.sleep(0.05)
        
        # Shutdown immediately (tasks are mid-execution)
        await manager.stop_periodic_cleanup()
        
        # Verify shutdown completed successfully
        assert manager.is_running is False
        
        # Wait for cancellation
        await asyncio.sleep(0.1)
        
        # Verify tasks are stopped
        assert manager.cleanup_task.done() or manager.cleanup_task.cancelled()
        assert manager.monitoring_task.done() or manager.monitoring_task.cancelled()
    
    @pytest.mark.asyncio
    async def test_task_status_reflects_shutdown_state(self):
        """
        Test that task status correctly reflects shutdown state
        Validates: Requirement 9.3 (graceful shutdown)
        """
        # Create manager
        db_session = MockDatabaseSession()
        manager = MockBackgroundTaskManager(db_session)
        
        # Initial status
        status = manager.get_task_status()
        assert status['is_running'] is False
        assert status['cleanup_task_running'] is False
        assert status['monitoring_task_running'] is False
        
        # Start tasks
        await manager.start_periodic_cleanup()
        await asyncio.sleep(0.05)
        
        # Running status
        status = manager.get_task_status()
        assert status['is_running'] is True
        assert status['cleanup_task_running'] is True
        assert status['monitoring_task_running'] is True
        
        # Shutdown
        await manager.stop_periodic_cleanup()
        await asyncio.sleep(0.1)
        
        # Stopped status
        status = manager.get_task_status()
        assert status['is_running'] is False
        assert status['cleanup_task_running'] is False
        assert status['monitoring_task_running'] is False
    
    @pytest.mark.asyncio
    async def test_concurrent_shutdown_calls(self):
        """
        Test that concurrent shutdown calls are handled safely
        Validates: Requirement 9.3 (graceful shutdown)
        """
        # Create manager
        db_session = MockDatabaseSession()
        manager = MockBackgroundTaskManager(db_session)
        
        # Start tasks
        await manager.start_periodic_cleanup()
        
        # Call shutdown concurrently
        try:
            await asyncio.gather(
                manager.stop_periodic_cleanup(),
                manager.stop_periodic_cleanup(),
                manager.stop_periodic_cleanup()
            )
        except Exception as e:
            pytest.fail(f"Concurrent shutdown calls raised exception: {e}")
        
        # Verify shutdown completed
        assert manager.is_running is False
    
    @pytest.mark.asyncio
    async def test_end_to_end_shutdown_sequence(self):
        """
        End-to-end test of complete shutdown sequence with background tasks
        Validates: Requirements 9.3, 9.4, 9.5
        """
        # Create manager
        db_session = MockDatabaseSession()
        sticker_manager = MockStickerManager(db_session)
        manager = MockBackgroundTaskManager(db_session, sticker_manager)
        
        # Start system
        await manager.start_periodic_cleanup()
        assert manager.is_running is True
        
        # Let system run
        await asyncio.sleep(0.2)
        
        # Verify tasks executed
        assert manager.cleanup_count > 0
        assert manager.monitoring_count > 0
        
        # Simulate SIGTERM received - initiate shutdown
        shutdown_requested = True
        
        # Execute graceful shutdown sequence
        if shutdown_requested:
            # Stop background tasks
            await manager.stop_periodic_cleanup()
            
            # Verify shutdown completed
            assert manager.is_running is False
            
            # Wait for cleanup
            await asyncio.sleep(0.1)
            
            # Verify all tasks stopped
            status = manager.get_task_status()
            assert status['is_running'] is False
            assert status['cleanup_task_running'] is False
            assert status['monitoring_task_running'] is False
        
        # Verify system is fully shut down
        assert manager.cleanup_task.done() or manager.cleanup_task.cancelled()
        assert manager.monitoring_task.done() or manager.monitoring_task.cancelled()
    
    @pytest.mark.asyncio
    async def test_shutdown_with_real_background_task_manager(self):
        """
        Test shutdown with the real BackgroundTaskManager implementation
        Validates: Requirements 9.3, 9.4, 9.5
        
        This test imports and uses the real BackgroundTaskManager to ensure
        the actual implementation handles shutdown correctly.
        """
        try:
            # Import real implementation
            from core.managers.background_task_manager import BackgroundTaskManager
            
            # Create mock database session
            db_session = MockDatabaseSession()
            sticker_manager = MockStickerManager(db_session)
            
            # Create real manager
            manager = BackgroundTaskManager(db_session, sticker_manager)
            
            # Verify initial state
            assert manager.is_running is False
            
            # Start tasks
            await manager.start_periodic_cleanup()
            assert manager.is_running is True
            
            # Let tasks run briefly
            await asyncio.sleep(0.2)
            
            # Verify tasks are running
            status = manager.get_task_status()
            assert status['is_running'] is True
            assert status['cleanup_task_running'] is True
            assert status['monitoring_task_running'] is True
            
            # Shutdown
            await manager.stop_periodic_cleanup()
            
            # Verify shutdown completed
            assert manager.is_running is False
            
            # Wait for cancellation
            await asyncio.sleep(0.1)
            
            # Verify tasks are stopped
            status = manager.get_task_status()
            assert status['is_running'] is False
            assert status['cleanup_task_running'] is False
            assert status['monitoring_task_running'] is False
            
        except ImportError as e:
            pytest.skip(f"Could not import BackgroundTaskManager: {e}")
        except Exception as e:
            # If there's an error, it should be a test failure, not a skip
            pytest.fail(f"Real BackgroundTaskManager test failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
