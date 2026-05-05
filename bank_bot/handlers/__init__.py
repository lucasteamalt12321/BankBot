"""Handlers — re-export из bot/handlers/ и bot/commands/."""

from bot.handlers import ParsingHandler
from bot.commands import (
    admin_router,
    user_router,
    shop_router,
    game_router,
    system_router,
)

__all__ = [
    "ParsingHandler",
    "admin_router",
    "user_router",
    "shop_router",
    "game_router",
    "system_router",
]
