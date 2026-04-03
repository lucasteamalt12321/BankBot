"""Tests for bridge_bot.queue module."""

from __future__ import annotations

import time
from unittest.mock import MagicMock


from bridge_bot.queue import (
    MessageQueue,
    OutboundMessage,
    RateLimitError,
)


class TestOutboundMessage:
    """Tests for OutboundMessage dataclass."""

    def test_create_message(self):
        """Test creating OutboundMessage."""
        msg = OutboundMessage(text="Hello", platform="vk", sender_name="Test")
        assert msg.text == "Hello"
        assert msg.platform == "vk"
        assert msg.sender_name == "Test"
        assert msg.retry_count == 0

    def test_message_defaults(self):
        """Test message default values."""
        msg = OutboundMessage(text="Hello", platform="vk")
        assert msg.sender_name == ""
        assert msg.retry_count == 0

    def test_message_retry_count(self):
        """Test message retry count increment."""
        msg = OutboundMessage(text="Hello", platform="vk")
        msg.retry_count = 3
        assert msg.retry_count == 3


class TestRateLimitError:
    """Tests for RateLimitError exception."""

    def test_rate_limit_error_no_retry(self):
        """Test RateLimitError without retry_after."""
        error = RateLimitError()
        assert error.retry_after is None
        assert "retry after None" in str(error)

    def test_rate_limit_error_with_retry(self):
        """Test RateLimitError with retry_after."""
        error = RateLimitError(retry_after=30.0)
        assert error.retry_after == 30.0
        assert "retry after 30.0" in str(error)


class TestMessageQueue:
    """Tests for MessageQueue class."""

    def test_queue_initialization(self):
        """Test queue initialization and worker start."""
        send_func = MagicMock()
        mq = MessageQueue(send_func)
        assert mq._send_func is send_func
        assert not mq._stop_event.is_set()
        mq.stop()

    def test_queue_put(self):
        """Test adding message to queue."""
        send_func = MagicMock()
        mq = MessageQueue(send_func)

        msg = OutboundMessage(text="Test", platform="vk")
        mq.put(msg)

        assert not mq._queue.empty()
        mq.stop()

    def test_queue_send_success(self):
        """Test successful message send."""
        send_func = MagicMock(return_value=None)
        mq = MessageQueue(send_func)

        msg = OutboundMessage(text="Test", platform="vk", sender_name="Test")
        mq.put(msg)

        time.sleep(0.5)
        mq.stop(timeout=2.0)

        assert send_func.called

    def test_queue_rate_limit_retry(self):
        """Test message retry on rate limit."""
        call_count = 0

        def flaky_send(msg):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError(retry_after=0.1)
            return None

        mq = MessageQueue(flaky_send)
        msg = OutboundMessage(text="Test", platform="vk")
        mq.put(msg)

        time.sleep(1.0)
        mq.stop(timeout=3.0)

        assert call_count >= 2

    def test_queue_max_retries(self):
        """Test message dropped after max retries."""
        send_func = MagicMock(side_effect=Exception("API Error"))
        mq = MessageQueue(send_func)

        msg = OutboundMessage(text="Test", platform="vk")
        mq.put(msg)

        time.sleep(20.0)
        mq.stop(timeout=25.0)

        assert send_func.call_count >= MessageQueue.MAX_RETRIES

    def test_queue_stop(self):
        """Test graceful queue stop."""
        send_func = MagicMock()
        mq = MessageQueue(send_func)

        mq.stop()
        assert mq._stop_event.is_set()

    def test_queue_multiple_messages(self):
        """Test handling multiple messages."""
        send_func = MagicMock()
        mq = MessageQueue(send_func)

        for i in range(3):
            msg = OutboundMessage(text=f"Message {i}", platform="vk")
            mq.put(msg)

        time.sleep(4.0)
        mq.stop(timeout=5.0)

        assert send_func.call_count == 3
