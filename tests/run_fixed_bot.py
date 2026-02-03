#!/usr/bin/env python3
"""
Запуск исправленного бота
"""
import os
import sys
import logging

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.main import main

if __name__ == "__main__":
    print("[FIXED] Запуск исправленного Telegram-бота...")
    print("[FIXED] Исправления:")
    print("  - Добавлена обработка отсутствующего поля is_admin")
    print("  - Улучшена логика регистрации пользователей")
    print("  - Добавлены fallback механизмы")
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n[FIXED] Бот остановлен пользователем")
    except Exception as e:
        print(f"[FIXED] Ошибка: {e}")
        logging.exception("Критическая ошибка бота")