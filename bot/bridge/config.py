"""Bridge module configuration (shim: re-export from bridge_bot)."""

from bridge_bot.config import (
    BRIDGE_ENABLED,
    BRIDGE_TG_CHAT_ID,
    VK_TOKEN,
    VK_PEER_ID,
    BRIDGE_ADMIN_CHAT_ID,
)

__all__ = ["BRIDGE_ENABLED", "BRIDGE_TG_CHAT_ID", "VK_TOKEN", "VK_PEER_ID", "BRIDGE_ADMIN_CHAT_ID"]
