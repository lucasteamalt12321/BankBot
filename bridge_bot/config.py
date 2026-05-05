"""Bridge Bot configuration.

DEPRECATED: Import from src.config instead.
This module exists for backward compatibility.
"""

from src.config import bot_settings, settings, BotSettings, get_bot_settings, get_settings

VK_TOKEN: str = bot_settings.VK_TOKEN
VK_PEER_ID: int = bot_settings.VK_PEER_ID
VK_GROUP_ID: int = bot_settings.VK_GROUP_ID
BRIDGE_ENABLED: bool = bot_settings.BRIDGE_ENABLED
BRIDGE_TG_CHAT_ID: int = bot_settings.BRIDGE_TG_CHAT_ID
BRIDGE_ADMIN_CHAT_ID: int | None = bot_settings.BRIDGE_ADMIN_CHAT_ID

__all__ = ["bot_settings", "settings", "BotSettings", "get_bot_settings", "get_settings", "VK_TOKEN", "VK_PEER_ID", "VK_GROUP_ID", "BRIDGE_ENABLED", "BRIDGE_TG_CHAT_ID", "BRIDGE_ADMIN_CHAT_ID"]
