"""Централизованная обработка ошибок — re-export из core/middleware/."""

from core.middleware import ErrorHandlingMiddleware
from bot.middleware.error_handler import ErrorHandlerMiddleware, setup_error_handler

__all__ = [
    "ErrorHandlingMiddleware",   # aiogram BaseMiddleware (Bridge)
    "ErrorHandlerMiddleware",    # PTB error handler (BankBot)
    "setup_error_handler",
]
