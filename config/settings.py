"""Settings module.

DEPRECATED: Use src.config instead.
This module exists for backward compatibility and will be removed in future versions.
"""

from src.config import (
    bot_settings,
    BotSettings,
    get_bot_settings,
    settings,
    get_settings,
)

__all__ = ["bot_settings", "BotSettings", "get_bot_settings", "settings", "get_settings"]
