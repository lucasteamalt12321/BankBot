"""Shim: re-export из bridge_bot/queue.py."""

from bridge_bot.queue import OutboundMessage, RateLimitError, MessageQueue

__all__ = ["OutboundMessage", "RateLimitError", "MessageQueue"]
