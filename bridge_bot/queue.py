"""Очередь исходящих сообщений с rate limiting для Bridge-бота."""

import queue
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class OutboundMessage:
    """Message to be sent via the queue.

    Attributes:
        text: Message text content.
        platform: Target platform, either "vk" or "tg".
        sender_name: Display name of the original sender.
        retry_count: Number of delivery attempts made so far.
    """

    text: str
    platform: str  # "vk" or "tg"
    sender_name: str = ""
    retry_count: int = field(default=0)


class RateLimitError(Exception):
    """Raised when VK API returns 429 Too Many Requests.

    Attributes:
        retry_after: Seconds to wait before retrying, or None for exponential backoff.
    """

    def __init__(self, retry_after: Optional[float] = None) -> None:
        """Initialize with optional Retry-After value.

        Args:
            retry_after: Seconds to wait before retrying, or None for exponential backoff.
        """
        self.retry_after = retry_after
        super().__init__(f"Rate limited, retry after {retry_after}s")


class MessageQueue:
    """Thread-safe FIFO queue with rate limiting for outbound messages.

    Processes messages with 0.5–1s delay between sends.
    Handles VK API rate limiting (429) with Retry-After support.
    Uses exponential backoff when Retry-After is not provided.
    """

    MAX_RETRIES = 5
    BASE_DELAY = 0.5
    MAX_DELAY = 1.0

    def __init__(self, send_func: Callable[[OutboundMessage], None]) -> None:
        """Initialize queue with a send function and start the worker thread.

        Args:
            send_func: Callable that sends a message. Should raise
                       RateLimitError on 429 or Exception on other errors.
        """
        self._queue: queue.Queue[OutboundMessage] = queue.Queue()
        self._send_func = send_func
        self._stop_event = threading.Event()
        self._worker = threading.Thread(
            target=self._run,
            daemon=True,
            name="bridge-queue-worker",
        )
        self._worker.start()

    def put(self, message: OutboundMessage) -> None:
        """Add message to the queue.

        Args:
            message: Message to enqueue.
        """
        self._queue.put(message)

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the worker thread gracefully.

        Args:
            timeout: Maximum seconds to wait for worker to finish.
        """
        self._stop_event.set()
        self._worker.join(timeout=timeout)

    def _run(self) -> None:
        """Worker loop: dequeue and send messages with rate limiting."""
        backoff = 1.0
        while not self._stop_event.is_set():
            try:
                msg = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                self._send_func(msg)
                backoff = 1.0
                delay = random.uniform(self.BASE_DELAY, self.MAX_DELAY)
                time.sleep(delay)
            except RateLimitError as e:
                retry_after = e.retry_after if e.retry_after is not None else backoff
                logger.warning(
                    "Rate limited, requeueing",
                    retry_after=retry_after,
                    text=msg.text[:50],
                )
                self._queue.put(msg)
                time.sleep(retry_after)
                backoff = min(backoff * 2, 60.0)
            except Exception as e:
                if msg.retry_count < self.MAX_RETRIES:
                    msg.retry_count += 1
                    self._queue.put(msg)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)
                else:
                    logger.error(
                        "Message dropped after max retries",
                        error=str(e),
                        text=msg.text[:50],
                    )
            finally:
                self._queue.task_done()
