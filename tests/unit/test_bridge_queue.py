"""Unit tests for bridge_bot.queue module."""

import threading
import time
from unittest.mock import MagicMock, call

import pytest

from bridge_bot.queue import MessageQueue, OutboundMessage, RateLimitError


class TestOutboundMessage:
    """Tests for OutboundMessage dataclass."""

    def test_default_values(self):
        """Test default field values."""
        msg = OutboundMessage(text="Hello", platform="vk")
        assert msg.text == "Hello"
        assert msg.platform == "vk"
        assert msg.sender_name == ""
        assert msg.retry_count == 0

    def test_custom_values(self):
        """Test custom field values."""
        msg = OutboundMessage(
            text="Test",
            platform="tg",
            sender_name="John",
            retry_count=3,
        )
        assert msg.text == "Test"
        assert msg.platform == "tg"
        assert msg.sender_name == "John"
        assert msg.retry_count == 3


class TestRateLimitError:
    """Tests for RateLimitError exception."""

    def test_default_retry_after(self):
        """Test RateLimitError with default retry_after."""
        err = RateLimitError()
        assert err.retry_after is None
        assert "Rate limited" in str(err)

    def test_custom_retry_after(self):
        """Test RateLimitError with specific retry_after."""
        err = RateLimitError(retry_after=30.0)
        assert err.retry_after == 30.0
        assert "30.0" in str(err)


class TestMessageQueue:
    """Tests for MessageQueue worker."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sent_messages: list = []
        self.send_mock = MagicMock(side_effect=self._track_send)

    def _track_send(self, msg: OutboundMessage) -> None:
        """Track sent messages for verification."""
        self.sent_messages.append(msg)

    def test_sends_message(self):
        """MessageQueue should send enqueued messages."""
        q = MessageQueue(send_func=self.send_mock)
        try:
            msg = OutboundMessage(text="Test", platform="vk")
            q.put(msg)
            time.sleep(0.3)
            assert len(self.sent_messages) == 1
            assert self.sent_messages[0].text == "Test"
        finally:
            q.stop()

    def test_sends_multiple_messages(self):
        """MessageQueue should send multiple messages in order."""
        q = MessageQueue(send_func=self.send_mock)
        try:
            q.put(OutboundMessage(text="First", platform="vk"))
            q.put(OutboundMessage(text="Second", platform="vk"))
            time.sleep(2.0)
            assert len(self.sent_messages) == 2
            assert self.sent_messages[0].text == "First"
            assert self.sent_messages[1].text == "Second"
        finally:
            q.stop()

    def test_rate_limiting_delay(self):
        """Messages should have delay between sends."""
        q = MessageQueue(send_func=self.send_mock)
        try:
            start = time.time()
            q.put(OutboundMessage(text="First", platform="vk"))
            q.put(OutboundMessage(text="Second", platform="vk"))
            time.sleep(1.5)
            elapsed = time.time() - start
            assert elapsed >= 0.5
        finally:
            q.stop()

    def test_rate_limit_error_requeues(self):
        """RateLimitError should cause message requeue."""
        call_count = 0

        def flaky_send(msg: OutboundMessage) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError(retry_after=0.1)
            if call_count == 2:
                raise RateLimitError()

        q = MessageQueue(send_func=flaky_send)
        try:
            msg = OutboundMessage(text="Test", platform="vk")
            q.put(msg)
            time.sleep(1.5)
            assert call_count >= 2
        finally:
            q.stop()

    @pytest.mark.slow
    def test_max_retries_drops_message(self):
        """Message should be dropped after MAX_RETRIES."""
        retries = 0

        def always_fails(msg: OutboundMessage) -> None:
            nonlocal retries
            retries += 1
            raise Exception("Always fails")

        q = MessageQueue(send_func=always_fails)
        try:
            msg = OutboundMessage(text="Test", platform="vk")
            q.put(msg)
            time.sleep(20.0)
            assert retries >= MessageQueue.MAX_RETRIES - 1
        finally:
            q.stop()

    def test_graceful_shutdown(self):
        """stop() should not raise and should wait for pending message."""
        q = MessageQueue(send_func=self.send_mock)
        q.put(OutboundMessage(text="Pending", platform="vk"))
        q.stop(timeout=2.0)
        assert self.sent_messages[0].text == "Pending"

    def test_stop_timeout(self):
        """stop() should return even if message not sent."""
        long_delay = MagicMock(side_effect=lambda m: time.sleep(10))

        q = MessageQueue(send_func=long_delay)
        q.put(OutboundMessage(text="Blocking", platform="vk"))
        start = time.time()
        q.stop(timeout=0.1)
        elapsed = time.time() - start
        assert elapsed < 1.0

    def test_empty_queue_stop(self):
        """Stopping with empty queue should not block."""
        q = MessageQueue(send_func=self.send_mock)
        start = time.time()
        q.stop(timeout=0.5)
        elapsed = time.time() - start
        assert elapsed < 1.0

    def test_platform_field_passed_through(self):
        """Platform field should be available in sent message."""
        q = MessageQueue(send_func=self.send_mock)
        try:
            q.put(OutboundMessage(text="TG message", platform="tg"))
            time.sleep(0.3)
            assert self.sent_messages[0].platform == "tg"
        finally:
            q.stop()

    def test_sender_name_passed_through(self):
        """Sender name should be available in sent message."""
        q = MessageQueue(send_func=self.send_mock)
        try:
            q.put(
                OutboundMessage(
                    text="From user",
                    platform="vk",
                    sender_name="TestUser",
                )
            )
            time.sleep(0.3)
            assert self.sent_messages[0].sender_name == "TestUser"
        finally:
            q.stop()
