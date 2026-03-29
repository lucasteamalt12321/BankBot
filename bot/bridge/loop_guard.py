"""Shim: re-export из bridge_bot/loop_guard.py."""

from bridge_bot.loop_guard import BOT_MARK, has_bot_mark, add_bot_mark

__all__ = ["BOT_MARK", "has_bot_mark", "add_bot_mark"]
