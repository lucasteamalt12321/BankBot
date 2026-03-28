"""Общая конфигурация проекта BankBot.

Единая точка входа для всех настроек.
Re-export из config/settings.py (BotSettings) и src/config.py (Settings).

Использование:
    from common.config import bot_settings, settings
"""

# Re-export из config/settings.py (Bridge + основные настройки)
from config.settings import BotSettings, BotSettings as Settings, bot_settings, get_bot_settings

# Re-export из src/config.py (legacy Settings с валидаторами)
from src.config import (
    settings,
    get_settings,
    update_currency_rate,
    get_currency_config,
    ADVANCED_CURRENCY_CONFIG,
)

__all__ = [
    "BotSettings",
    "Settings",
    "bot_settings",
    "get_bot_settings",
    "settings",
    "get_settings",
    "update_currency_rate",
    "get_currency_config",
    "ADVANCED_CURRENCY_CONFIG",
]
