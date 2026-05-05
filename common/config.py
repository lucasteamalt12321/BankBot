"""Common configuration module.

DEPRECATED: Use src.config instead.
This module exists for backward compatibility and will be removed in future versions.
"""

from src.config import (
    settings,
    bot_settings,
    BotSettings,
    get_settings,
    get_bot_settings,
    ADVANCED_CURRENCY_CONFIG,
    update_currency_rate,
    get_currency_config,
    TRANSACTION_SECURITY,
)

__all__ = [
    "settings",
    "bot_settings",
    "BotSettings",
    "get_settings",
    "get_bot_settings",
    "ADVANCED_CURRENCY_CONFIG",
    "update_currency_rate",
    "get_currency_config",
    "TRANSACTION_SECURITY",
]
