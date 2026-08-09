"""Property-based tests for ProcessManager.

These tests use Hypothesis to verify that ProcessManager properties hold
across a wide range of inputs and scenarios.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import psutil
from hypothesis import given, strategies as st, settings, HealthCheck

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


SUPPRESS = [HealthCheck.function_scoped_fixture]


class TestProcessManagerProperties:
    """Property-based tests for ProcessManager."""

    @given(pid=st.integers(min_value=1, max_value=2147483647))
    @settings(max_examples=20, deadline=2000, suppress_health_check=SUPPRESS)
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

    @given(invalid_content=st.text())
    @settings(max_examples=20, deadline=2000, suppress_health_check=SUPPRESS)
    def test_read_pid_handles_invalid_content_property(self, invalid_content, tmp_path):
        """Property: Reading invalid PID content should return None without crashing."""
        # Skip if the content is actually a valid integer
        try:
            int(invalid_content.strip())
            return
        except (ValueError, OverflowError):
            pass

        # Setup
        ProcessManager.PID_FILE = tmp_path / "test_bot.pid"

        try:
            ProcessManager.PID_FILE.parent.mkdir(exist_ok=True)
            ProcessManager.PID_FILE.write_text(invalid_content, encoding="utf-8")

            # Should return None without raising exception
            result = ProcessManager.read_pid()
            assert result is None
        finally:
            # Cleanup
            if ProcessManager.PID_FILE.exists():
                ProcessManager.PID_FILE.unlink()

    @given(pid=st.integers(min_value=1, max_value=2147483647))
    @settings(max_examples=20, deadline=2000, suppress_health_check=SUPPRESS)
    def test_write_pid_creates_readable_file_property(self, pid, tmp_path):
        """Property: After writing PID, the file should exist and be readable."""
        # Setup
        ProcessManager.PID_FILE = tmp_path / "test_bot.pid"

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

    @given(nonexistent_pid=st.integers(min_value=100000, max_value=999999))
    @settings(max_examples=10, deadline=2000, suppress_health_check=SUPPRESS)
    def test_kill_existing_always_cleans_pid_file_property(self, nonexistent_pid, tmp_path):
        """Property: kill_existing should always clean up PID file, even on errors."""
        # Setup
        ProcessManager.PID_FILE = tmp_path / "test_bot.pid"

        # Test with different error scenarios
        error_scenarios = [
            None,  # Success
            psutil.NoSuchProcess,  # Process not found
            psutil.AccessDenied,  # No permission
        ]

        for error in error_scenarios:
            try:
                # Create PID file
                ProcessManager.PID_FILE.parent.mkdir(exist_ok=True)
                ProcessManager.PID_FILE.write_text(str(nonexistent_pid))

                # Patch psutil methods to simulate scenarios
                def fake_pid_exists(pid, error=error):
                    return error is None

                with patch('src.process_manager.psutil.pid_exists', side_effect=fake_pid_exists) as mock_pid_exists, \
                     patch('src.process_manager.psutil.Process') as mock_process:
                    if error is None:
                        mock_process.return_value.terminate.return_value = None
                        mock_process.return_value.wait.return_value = None
                        mock_process.return_value.name.return_value = "test_bot"
                    else:
                        mock_process.return_value.terminate.side_effect = error

                    # Call kill_existing
                    ProcessManager.kill_existing()

                # PID file should always be removed
                assert not ProcessManager.PID_FILE.exists(), \
                    f"PID file should be removed even with error: {error}"

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
            pid = ProcessManager.read_pid()
            assert pid is not None
            assert psutil.pid_exists(pid) is True

            # Non-existent process should not be running
            ProcessManager.PID_FILE.write_text("999999")
            read_pid = ProcessManager.read_pid()
            assert read_pid is None or psutil.pid_exists(read_pid) is False

            # No PID file means not running
            ProcessManager.remove_pid()
            assert ProcessManager.read_pid() is None
        finally:
            # Cleanup
            if ProcessManager.PID_FILE.exists():
                ProcessManager.PID_FILE.unlink()
