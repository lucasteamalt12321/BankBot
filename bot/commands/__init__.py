"""Commands module for Telegram bot."""

from bot.commands.admin_commands import router as admin_router
from bot.commands.user_commands import router as user_router
from bot.commands.shop_commands import router as shop_router
from bot.commands.game_commands import router as game_router
from bot.commands.system_commands import router as system_router

__all__ = [
    'admin_router',
    'user_router',
    'shop_router',
    'game_router',
    'system_router',
]
