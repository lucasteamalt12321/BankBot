"""Commands module — exports aiogram routers and python-telegram-bot handlers.

Архитектура:
- aiogram роутеры (Bridge-модуль): balance, shop_commands
- python-telegram-bot хендлеры (основной бот): admin_commands, user_commands,
  shop_commands (PTB), game_commands, system_commands
"""

from aiogram import Router as _Router

from bot.commands import config_commands  # noqa: F401
from bot.commands.balance import router as user_router
from bot.commands.shop_commands import router as shop_router

# Stub routers для game и system (aiogram, пока не реализованы)
game_router = _Router(name="game")
system_router = _Router(name="system")
admin_router = _Router(name="admin")

__all__ = [
    "config_commands",
    "admin_router",
    "user_router",
    "shop_router",
    "game_router",
    "system_router",
]
