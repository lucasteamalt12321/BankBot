#!/usr/bin/env python3
"""
Безопасная миграция базы данных - добавление поля is_admin
"""
import sqlite3
import os
import shutil
from datetime import datetime

def safe_migrate_database():
    """Безопасно добавляет поле is_admin в базу данных"""
    
    original_db = 'bot.db'
    backup_db = f'bot_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    
    if not os.path.exists(original_db):
        print(f"База данных {original_db} не найдена")
        return False
    
    try:
        # Создаем резервную копию
        print(f"Создаем резервную копию: {backup_db}")
        shutil.copy2(original_db, backup_db)
        
        # Пытаемся подключиться к базе данных
        conn = sqlite3.connect(original_db, timeout=1.0)
        cursor = conn.cursor()
        
        # Проверяем существует ли поле is_admin
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'is_admin' in column_names:
            print("Поле is_admin уже существует")
            conn.close()
            return True
        
        print("Добавляем поле is_admin...")
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE")
        
        # Устанавливаем права администратора для пользователя 2091908459
        cursor.execute("UPDATE users SET is_admin = TRUE WHERE telegram_id = ?", (2091908459,))
        
        conn.commit()
        conn.close()
        
        print("Миграция завершена успешно")
        print(f"Резервная копия сохранена как: {backup_db}")
        return True
        
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            print("База данных заблокирована (бот работает)")
            print("Миграция будет выполнена автоматически при следующем запуске бота")
            return False
        else:
            print(f"Ошибка SQLite: {e}")
            return False
    except Exception as e:
        print(f"Ошибка миграции: {e}")
        return False

if __name__ == "__main__":
    success = safe_migrate_database()
    if success:
        print("✅ Миграция выполнена успешно")
    else:
        print("❌ Миграция не выполнена (возможно, база заблокирована)")