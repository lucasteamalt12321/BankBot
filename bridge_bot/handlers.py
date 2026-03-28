"""Обработчики входящих сообщений из Telegram-канала."""

# Re-export из bot/bridge/telegram_forwarder.py
from bot.bridge.telegram_forwarder import (
    router,
    forward_to_vk,
    BridgeChatFilter,
    get_message_queue,
)

__all__ = ["router", "forward_to_vk", "BridgeChatFilter", "get_message_queue"]
