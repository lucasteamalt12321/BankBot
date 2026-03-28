# Core middleware package — aiogram BaseMiddleware для Bridge-модуля.
# Не путать с bot/middleware/ — тот пакет содержит обработчики для python-telegram-bot.
from .error_handling import ErrorHandlingMiddleware

try:
    from .activity_tracker import track_user_activity
    __all__ = ["track_user_activity", "ErrorHandlingMiddleware"]
except ImportError:
    __all__ = ["ErrorHandlingMiddleware"]