"""Loop guard — предотвращает циклы пересылки через метку [BOT]."""

# Re-export из bot/bridge/loop_guard.py для обратной совместимости
from bot.bridge.loop_guard import BOT_MARK, has_bot_mark, add_bot_mark

__all__ = ["BOT_MARK", "has_bot_mark", "add_bot_mark"]
