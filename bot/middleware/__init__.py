"""Middleware modules for the Telegram bot."""

from bot.middleware.error_handler import ErrorHandlerMiddleware
from bot.middleware.dependency_injection import DependencyInjectionMiddleware

__all__ = ["ErrorHandlerMiddleware", "DependencyInjectionMiddleware"]
