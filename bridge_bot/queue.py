"""Очередь исходящих сообщений с rate limiting."""

# Re-export из bot/bridge/message_queue.py
from bot.bridge.message_queue import OutboundMessage, RateLimitError, MessageQueue

__all__ = ["OutboundMessage", "RateLimitError", "MessageQueue"]
