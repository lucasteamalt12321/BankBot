"""Shim: re-export из bridge_bot/vk_publisher.py."""

from bridge_bot.vk_publisher import send_text

__all__ = ["send_text"]
