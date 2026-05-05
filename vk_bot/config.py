"""VK Bot configuration.

DEPRECATED: Import from src.config instead.
This module exists for backward compatibility.
"""

from src.config import bot_settings, settings, BotSettings, get_bot_settings, get_settings

VK_TOKEN: str = bot_settings.VK_TOKEN
VK_PEER_ID: int = bot_settings.VK_PEER_ID

__all__ = ["bot_settings", "settings", "BotSettings", "get_bot_settings", "get_settings", "VK_TOKEN", "VK_PEER_ID"]
