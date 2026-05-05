"""Middleware для python-telegram-bot (основной бот).

Не путать с core/middleware/ — тот пакет содержит aiogram BaseMiddleware
для Bridge-модуля (bot/bridge/main_bridge.py).
"""

from bot.middleware.error_handler import ErrorHandlerMiddleware
from bot.middleware.dependency_injection import build_services, get_services, setup_di

__all__ = ["ErrorHandlerMiddleware", "build_services", "get_services", "setup_di"]
