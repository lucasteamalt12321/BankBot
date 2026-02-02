#!/usr/bin/env python3
"""
Скрипт запуска Telegram-бота банк-аггрегатора LucasTeam
"""

import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Импортируем и запускаем main из папки bot
from bot.main import main

if __name__ == "__main__":
    main()