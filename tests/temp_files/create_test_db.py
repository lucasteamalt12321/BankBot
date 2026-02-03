#!/usr/bin/env python3
"""
Создание тестовой базы данных
"""
import sqlite3
import os
from datetime import datetime

def create_test_database():
    """Создает тестовую базу данных с правильной структурой"""
    
    db_path = 'test_bot.db'
    
    # Удаляем старую базу если есть
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Создаем таблицу users с полем is_admin
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
            is_vip BOOLEAN DEFAULT FALSE,
            vip_until DATETIME,
            is_admin BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # Создаем таблицу transactions
    cursor.execute('''
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            transaction_type TEXT,
            source_game TEXT,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    
    print(f"Тестовая база данных {db_path} создана успешно")

if __name__ == "__main__":
    create_test_database()