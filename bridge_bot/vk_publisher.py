"""Отправка сообщений в VK API."""

# Re-export из bot/bridge/vk_sender.py
from bot.bridge.vk_sender import send_text

__all__ = ["send_text"]
