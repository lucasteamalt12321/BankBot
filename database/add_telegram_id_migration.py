#!/usr/bin/env python3
"""
Миграция для добавления колонки telegram_id в таблицу users
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from pathlib import Path

def add_telegram_id_column():
    """Добавляет колонку telegram_id в таблицу users если её нет"""
    
    db_path = Path("data/bot.db")
    
    if not db_path.exists():
        print(f"❌ База данных не найдена: {db_path}")
        return False
    
    print(f"📊 Подключение к базе данных: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем существующие колонки
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print(f"📋 Существующие колонки: {', '.join(column_names)}")
        
        if 'telegram_id' in column_names:
            print("✅ Колонка telegram_id уже существует")
            conn.close()
            return True
        
        print("➕ Добавление колонки telegram_id...")
        
        # Добавляем колонку telegram_id
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN telegram_id INTEGER
        """)
        
        # Создаем индекс для быстрого поиска
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_telegram_id 
            ON users(telegram_id)
        """)
        
        conn.commit()
        
        # Проверяем результат
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'telegram_id' in column_names:
            print("✅ Колонка telegram_id успешно добавлена")
            print(f"📋 Обновленные колонки: {', '.join(column_names)}")
            conn.close()
            return True
        else:
            print("❌ Не удалось добавить колонку telegram_id")
            conn.close()
            return False
            
    except sqlite3.Error as e:
        print(f"❌ Ошибка SQLite: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Миграция: Добавление колонки telegram_id")
    print("=" * 60)
    
    success = add_telegram_id_column()
    
    print("=" * 60)
    if success:
        print("✅ Миграция выполнена успешно")
    else:
        print("❌ Миграция завершилась с ошибками")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
