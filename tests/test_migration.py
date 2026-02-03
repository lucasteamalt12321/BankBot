#!/usr/bin/env python3
"""
Simple test script to run the shop migration
"""

import sqlite3
from datetime import datetime

def create_shop_tables():
    """Create the new shop system tables"""
    
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    
    # Create shop_items table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shop_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) NOT NULL,
        price INTEGER NOT NULL DEFAULT 100,
        description TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Create user_purchases table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL,
        purchase_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NULL,
        data JSON NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (item_id) REFERENCES shop_items(id)
    );
    """)
    
    # Create scheduled_tasks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scheduled_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message_id INTEGER NULL,
        chat_id INTEGER NOT NULL,
        task_type VARCHAR(50) NOT NULL,
        execute_at TIMESTAMP NOT NULL,
        task_data JSON NULL,
        is_completed BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)
    
    conn.commit()
    print("Shop system tables created successfully")
    
    # Initialize default items
    cursor.execute("SELECT COUNT(*) FROM shop_items")
    count = cursor.fetchone()[0]
    
    if count == 0:
        default_items = [
            ('Безлимитные стикеры на 24 часа', 100, 'Получите возможность отправлять неограниченное количество стикеров в течение 24 часов'),
            ('Запрос на админ-права', 100, 'Отправить запрос владельцу бота на получение прав администратора'),
            ('Рассылка сообщения всем пользователям', 100, 'Отправить ваше сообщение всем пользователям бота')
        ]
        
        for name, price, description in default_items:
            cursor.execute("""
            INSERT INTO shop_items (name, price, description, is_active, created_at)
            VALUES (?, ?, ?, TRUE, ?)
            """, (name, price, description, datetime.utcnow().isoformat()))
        
        conn.commit()
        print(f"Initialized {len(default_items)} default shop items")
    else:
        print(f"Shop items already exist ({count} items), skipping initialization")
    
    conn.close()
    print("Migration completed successfully!")

if __name__ == "__main__":
    create_shop_tables()