"""Unit tests for IdempotencyChecker class."""

import pytest
from datetime import datetime
from decimal import Decimal

from src.idempotency import IdempotencyChecker
from src.repository import SQLiteRepository


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test_idempotency.db"
    return SQLiteRepository(str(db_path))


@pytest.fixture
def idempotency_checker(temp_db):
    """Create an IdempotencyChecker instance with temporary database."""
    return IdempotencyChecker(temp_db)


def test_generate_message_id_returns_hex_string(idempotency_checker):
    """Test that generate_message_id returns a hexadecimal string."""
    message = "Test message"
    timestamp = datetime(2024, 1, 1, 12, 0, 0)
    
    message_id = idempotency_checker.generate_message_id(message, timestamp)
    
    # Should be a 64-character hex string (SHA-256)
    assert isinstance(message_id, str)
    assert len(message_id) == 64
    assert all(c in '0123456789abcdef' for c in message_id)


def test_generate_message_id_is_deterministic(idempotency_checker):
    """Test that same message and timestamp produce same ID."""
    message = "Test message"
    timestamp = datetime(2024, 1, 1, 12, 0, 0)
    
    id1 = idempotency_checker.generate_message_id(message, timestamp)
    id2 = idempotency_checker.generate_message_id(message, timestamp)
    
    assert id1 == id2


def test_generate_message_id_different_for_different_messages(idempotency_checker):
    """Test that different messages produce different IDs."""
    timestamp = datetime(2024, 1, 1, 12, 0, 0)
    
    id1 = idempotency_checker.generate_message_id("Message 1", timestamp)
    id2 = idempotency_checker.generate_message_id("Message 2", timestamp)
    
    assert id1 != id2


def test_generate_message_id_different_for_different_timestamps(idempotency_checker):
    """Test that different timestamps produce different IDs."""
    message = "Test message"
    
    id1 = idempotency_checker.generate_message_id(message, datetime(2024, 1, 1, 12, 0, 0))
    id2 = idempotency_checker.generate_message_id(message, datetime(2024, 1, 1, 12, 0, 1))
    
    assert id1 != id2


def test_is_processed_returns_false_for_new_message(idempotency_checker):
    """Test that is_processed returns False for a message ID that hasn't been stored."""
    message_id = "abc123"
    
    result = idempotency_checker.is_processed(message_id)
    
    assert result is False


def test_is_processed_returns_true_after_mark_processed(idempotency_checker):
    """Test that is_processed returns True after mark_processed is called."""
    message_id = "abc123"
    
    idempotency_checker.mark_processed(message_id)
    result = idempotency_checker.is_processed(message_id)
    
    assert result is True


def test_mark_processed_stores_message_id(idempotency_checker):
    """Test that mark_processed stores the message ID in the repository."""
    message_id = "test_message_id_12345"
    
    # Initially not processed
    assert not idempotency_checker.is_processed(message_id)
    
    # Mark as processed
    idempotency_checker.mark_processed(message_id)
    
    # Now should be processed
    assert idempotency_checker.is_processed(message_id)


def test_idempotency_full_workflow(idempotency_checker):
    """Test the complete idempotency workflow."""
    message = "🃏 НОВАЯ КАРТА 🃏\nИгрок: TestPlayer\nОчки: +100"
    timestamp = datetime(2024, 1, 15, 10, 30, 0)
    
    # Generate message ID
    message_id = idempotency_checker.generate_message_id(message, timestamp)
    
    # First check - should not be processed
    assert not idempotency_checker.is_processed(message_id)
    
    # Mark as processed
    idempotency_checker.mark_processed(message_id)
    
    # Second check - should be processed
    assert idempotency_checker.is_processed(message_id)
    
    # Generate same ID again - should still be processed
    same_message_id = idempotency_checker.generate_message_id(message, timestamp)
    assert same_message_id == message_id
    assert idempotency_checker.is_processed(same_message_id)


def test_multiple_messages_tracked_independently(idempotency_checker):
    """Test that multiple messages are tracked independently."""
    message1 = "Message 1"
    message2 = "Message 2"
    timestamp = datetime(2024, 1, 1, 12, 0, 0)
    
    id1 = idempotency_checker.generate_message_id(message1, timestamp)
    id2 = idempotency_checker.generate_message_id(message2, timestamp)
    
    # Mark only first message as processed
    idempotency_checker.mark_processed(id1)
    
    # First should be processed, second should not
    assert idempotency_checker.is_processed(id1)
    assert not idempotency_checker.is_processed(id2)
    
    # Mark second message as processed
    idempotency_checker.mark_processed(id2)
    
    # Both should now be processed
    assert idempotency_checker.is_processed(id1)
    assert idempotency_checker.is_processed(id2)
