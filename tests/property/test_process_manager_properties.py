"""Property-based tests for ProcessManager.

These tests use Hypothesis to verify that ProcessManager properties hold
across a wide range of inputs and scenarios.
"""

import os
import signal
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, strategies as st, assume

from src.process_manager import ProcessManager


@pytest.fixture
def temp_pid_file(tmp_path):
    """Create a temporary PID file for testing."""
    original_pid_file = ProcessManager.PID_FILE
    ProcessManager.PID_FILE = tmp_path / "test_bot.pid"
    yield ProcessManager.PID_FILE
    ProcessManager.PID_FILE = original_pid_file
    # Clean up
    if ProcessManager.PID_FILE.exists():
        ProcessManager.PID_FILE.unlink()


class TestProcessManagerProperties:
    """Property-based tests for ProcessManager."""
    
    @given(st.integers(min_value=1, max_value=2147483647))
    def test_write_read_pid_roundtrip_property(self, pid, tmp_path):
        """Property: Writing a PID and reading it back should return the same value."""
        # Setup
        ProcessManager.PID_FILE = tmp_path / "test_bot.pid"
        
        try:
            # Write the PID
            ProcessManager.PID_FILE.parent.mkdir(exist_ok=True)
            ProcessManager.PID_FILE.write_text(str(pid))
            
            # Read it back
            read_pid = ProcessManager.read_pid()
            
            # Should be the same
            assert read_pid == pid
        finally:
            # Cleanup
            if ProcessManager.PID_FILE.exists():
                ProcessManager.PID_FILE.unlink()
    
    @given(st.text())
    def test_read_pid_handles_invalid_content_property(self, invalid_content, tmp_path):
        """Property: Reading invalid PID content should return None without crashing."""
        # Assume the content is not a valid integer
        try:
            int(invalid_content.strip())
            assume(False)  # Skip if it's actually a valid integer
        except (ValueError, OverflowError):
            pass  # This is what we want to test
        
        # Setup
        ProcessManager.PID_FILE = tmp_path / "test_bot.pid"
        
        try:
            ProcessManager.PID_FILE.parent.mkdir(exist_ok=True)
            ProcessManager.PID_FILE.write_text(invalid_content)
            
            # Should return None without raising exception
            result = ProcessManager.read_pid()
            assert result is None
        finally:
            # Cleanup
            if ProcessManager.PID_FILE.exists():
                ProcessManager.PID_FILE.unlink()
    
    @given(st.integers(min_value=1, max_value=2147483647))
    def test_write_pid_creates_readable_file_property(self, pid, tmp_path):
        """Property: After writing PID, the file should exist and be readable."""
        # Setup
        ProcessManager.PID_FILE = tmp_path / "test_bot.pid"
        original_getpid = os.getpid
        
        try:
            # Mock os.getpid to return our test PID
            with patch('os.getpid', return_value=pid):
                ProcessManager.write_pid()
            
            # File should exist
            assert ProcessManager.PID_FILE.exists()
            
            # File should be readable
            content = ProcessManager.PID_FILE.read_text()
            assert content == str(pid)
            
            # read_pid should return the same value
            assert ProcessManager.read_pid() == pid
        finally:
            # Cleanup
            if ProcessManager.PID_FILE.exists():
                ProcessManager.PID_FILE.unlink()
    
    def test_remove_pid_idempotent_property(self, tmp_path):
        """Property: Removing PID file multiple times should be safe (idempotent)."""
        # Setup
        ProcessManager.PID_FILE = tmp_path / "test_bot.pid"
        
        try:
            # Create a PID file
            ProcessManager.PID_FILE.parent.mkdir(exist_ok=True)
            ProcessManager.PID_FILE.write_text("12345")
            
            # Remove it multiple times - should not raise exception
            ProcessManager.remove_pid()
            assert not ProcessManager.PID_FILE.exists()
            
            ProcessManager.remove_pid()  # Second time
            assert not ProcessManager.PID_FILE.exists()
            
            ProcessManager.remove_pid()  # Third time
            assert not ProcessManager.PID_FILE.exists()
        finally:
            # Cleanup
            if ProcessManager.PID_FILE.exists():
                ProcessManager.PID_FILE.unlink()
    
    @given(st.integers(min_value=100000, max_value=999999))
    @patch('os.kill')
    def test_kill_existing_always_cleans_pid_file_property(
        self, mock_kill, nonexistent_pid, tmp_path
    ):
        """Property: kill_existing should always clean up PID file, even on errors."""
        # Setup
        ProcessManager.PID_FILE = tmp_path / "test_bot.pid"
        
        # Test with different error scenarios
        error_scenarios = [
            None,  # Success
            ProcessLookupError(),  # Process not found
            PermissionError(),  # No permission
        ]
        
        for error in error_scenarios:
            try:
                # Create PID file
                ProcessManager.PID_FILE.parent.mkdir(exist_ok=True)
                ProcessManager.PID_FILE.write_text(str(nonexistent_pid))
                
                # Configure mock
                if error is None:
                    mock_kill.return_value = None
                else:
                    mock_kill.side_effect = error
                
                # Call kill_existing
                ProcessManager.kill_existing()
                
                # PID file should always be removed
                assert not ProcessManager.PID_FILE.exists(), \
                    f"PID file should be removed even with error: {error}"
                
                # Reset mock for next iteration
                mock_kill.reset_mock()
                mock_kill.side_effect = None
            finally:
                # Cleanup
                if ProcessManager.PID_FILE.exists():
                    ProcessManager.PID_FILE.unlink()
    
    def test_is_running_consistency_property(self, tmp_path):
        """Property: is_running should be consistent with process existence."""
        # Setup
        ProcessManager.PID_FILE = tmp_path / "test_bot.pid"
        
        try:
            # Current process should be running
            ProcessManager.write_pid()
            assert ProcessManager.is_running() is True
            
            # Non-existent process should not be running
            ProcessManager.PID_FILE.write_text("999999")
            assert ProcessManager.is_running() is False
            
            # No PID file means not running
            ProcessManager.remove_pid()
            assert ProcessManager.is_running() is False
        finally:
            # Cleanup
            if ProcessManager.PID_FILE.exists():
                ProcessManager.PID_FILE.unlink()
