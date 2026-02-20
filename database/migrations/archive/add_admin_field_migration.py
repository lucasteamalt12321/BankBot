#!/usr/bin/env python3
"""
Миграция для добавления поля is_admin в таблицу users
"""
import sqlite3
import os
import sys
from src.config import settings

def add_admin_field():
    """Добавляет поле is_admin в таблицу users если его нет"""
    
    db_path = 'data/bot.db'
    if not os.path.exists(db_path):
        print(f"База данных {db_path} не найдена")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем существует ли поле is_admin
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'is_admin' in column_names:
            print("Поле is_admin уже существует")
            conn.close()
            return True
        
        # Добавляем поле is_admin
        print("Добавляем поле is_admin...")
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE")
        
        # Устанавливаем права администратора для пользователя из конфигурации
        cursor.execute("UPDATE users SET is_admin = TRUE WHERE telegram_id = ?", (settings.ADMIN_TELEGRAM_ID,))
        
        conn.commit()
        print("Поле is_admin успешно добавлено")
        print(f"Права администратора установлены для пользователя {settings.ADMIN_TELEGRAM_ID}")
        
        # Проверяем результат
        cursor.execute("SELECT telegram_id, username, first_name, is_admin FROM users WHERE telegram_id = ?", (settings.ADMIN_TELEGRAM_ID,))
        user = cursor.fetchone()
        if user:
            print(f"Пользователь: ID={user[0]}, Username={user[1]}, Name={user[2]}, Admin={user[3]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Ошибка при добавлении поля is_admin: {e}")
        return False

if __name__ == "__main__":
    success = add_admin_field()
    sys.exit(0 if success else 1)