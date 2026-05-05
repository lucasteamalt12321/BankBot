"""Shim: re-export из bridge_bot/handlers.py."""

from bridge_bot.handlers import router, forward_to_vk, BridgeChatFilter, get_message_queue

__all__ = ["router", "forward_to_vk", "BridgeChatFilter", "get_message_queue"]
