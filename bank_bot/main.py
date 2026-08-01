"""LTHub — точка входа.

Запускает основной Telegram-бот.
"""

from bot.main import main, kill_existing_bot_processes

__all__ = ["main", "kill_existing_bot_processes"]

if __name__ == "__main__":
    main()
