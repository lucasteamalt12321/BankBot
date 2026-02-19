#!/usr/bin/env python3
"""
Создание тестовой базы данных
Используется для быстрого создания чистой БД для тестирования
"""
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.connection import get_connection

def create_test_database(db_path: str = "test_bot.db"):
    """
    Создание тестовой базы данных SQLite
    
    Args:
        db_path: Путь к файлу БД (по умолчанию test_bot.db)
    """
    # Удаляем старую базу если есть
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"[INFO] Удалена старая база данных: {db_path}")
    
    # Создаем новую базу
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    print("[INFO] Создание таблицы users...")
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            balance INTEGER DEFAULT 0,
            daily_streak INTEGER DEFAULT 0,
            last_daily DATETIME,
            total_earned INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_vip BOOLEAN DEFAULT 0,
            vip_until DATETIME,
            is_admin BOOLEAN DEFAULT 0,
            sticker_unlimited BOOLEAN DEFAULT 0,
            sticker_unlimited_until DATETIME,
            total_purchases INTEGER DEFAULT 0
        )
    ''')
    
    print("[INFO] Создание таблицы transactions...")
    cursor.execute('''
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            transaction_type TEXT,
            source_game TEXT,
            description TEXT,
            meta_data TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    print("[INFO] Создание таблицы shop_categories...")
    cursor.execute('''
        CREATE TABLE shop_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    print("[INFO] Создание таблицы shop_items...")
    cursor.execute('''
        CREATE TABLE shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            name TEXT,
            description TEXT,
            price INTEGER,
            item_type TEXT,
            meta_data TEXT,
            purchase_limit INTEGER DEFAULT 0,
            cooldown_hours INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (category_id) REFERENCES shop_categories (id)
        )
    ''')
    
    print("[INFO] Создание базовых категорий магазина...")
    cursor.execute("INSERT INTO shop_categories (name, description, sort_order) VALUES (?, ?, ?)", 
                   ("Привилегии", "Различные привилегии и улучшения", 1))
    cursor.execute("INSERT INTO shop_categories (name, description, sort_order) VALUES (?, ?, ?)", 
                   ("Стикеры", "Доступ к стикерам", 2))
    cursor.execute("INSERT INTO shop_categories (name, description, sort_order) VALUES (?, ?, ?)", 
                   ("Игры", "Игровые возможности", 3))
    
    print("[INFO] Создание базовых товаров...")
    cursor.execute('''INSERT INTO shop_items 
                      (category_id, name, description, price, item_type, meta_data) 
                      VALUES (?, ?, ?, ?, ?, ?)''', 
                   (1, "VIP статус (1 день)", "VIP привилегии на 1 день", 100, "vip", '{"duration": 1}'))
    cursor.execute('''INSERT INTO shop_items 
                      (category_id, name, description, price, item_type, meta_data) 
                      VALUES (?, ?, ?, ?, ?, ?)''', 
                   (2, "Стикеры (1 день)", "Доступ к стикерам на 1 день", 50, "stickers", '{"duration": 1}'))
    
    conn.commit()
    conn.close()
    
    print(f"[SUCCESS] Тестовая база данных создана: {db_path}")
    return db_path

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Создание тестовой базы данных')
    parser.add_argument('--path', type=str, default='test_bot.db', 
                       help='Путь к файлу БД (по умолчанию: test_bot.db)')
    
    args = parser.parse_args()
    create_test_database(args.path)
