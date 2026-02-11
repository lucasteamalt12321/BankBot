#!/usr/bin/env python3
"""
Простой скрипт инициализации базы данных
"""
import os
import sys

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.database import create_tables

def main():
    """Создание таблиц базы данных"""
    print("[INIT] Создание таблиц базы данных...")
    try:
        create_tables()
        print("[SUCCESS] Таблицы созданы успешно!")
    except Exception as e:
        print(f"[ERROR] Ошибка при создании таблиц: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()