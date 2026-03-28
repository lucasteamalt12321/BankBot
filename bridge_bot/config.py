"""Конфигурация Bridge-бота."""

from common.config import bot_settings

BRIDGE_ENABLED: bool = bot_settings.BRIDGE_ENABLED
BRIDGE_TG_CHAT_ID: int = bot_settings.BRIDGE_TG_CHAT_ID
VK_TOKEN: str = bot_settings.VK_TOKEN
VK_PEER_ID: int = bot_settings.VK_PEER_ID
BRIDGE_ADMIN_CHAT_ID: int | None = bot_settings.BRIDGE_ADMIN_CHAT_ID
