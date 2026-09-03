"""Commands module — exports aiogram routers and python-telegram-bot handlers.

Архитектура:
- aiogram роутеры (Bridge-модуль): balance
- python-telegram-bot хендлеры (основной бот): admin_commands, user_commands,
  shop_commands (PTB), game_commands, system_commands
"""

from bot.commands import config_commands  # noqa: F401
from bot.commands.balance import router as user_router

__all__ = [
    "config_commands",
    "user_router",
]
