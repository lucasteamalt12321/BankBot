#!/usr/bin/env python3
"""
Миграция: Добавление таблицы bot_balances для отслеживания балансов в играх
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.database import engine, Base, BotBalance
from sqlalchemy import inspect

def run_migration():
    """Создает таблицу bot_balances если её нет"""
    inspector = inspect(engine)
    
    if 'bot_balances' not in inspector.get_table_names():
        print("Creating bot_balances table...")
        BotBalance.__table__.create(engine)
        print("✅ Table bot_balances created successfully")
    else:
        print("ℹ️ Table bot_balances already exists")

if __name__ == "__main__":
    run_migration()
