#!/usr/bin/env python3
"""
Скрипт для создания первого администратора
"""

import sqlite3
import sys

DB_PATH = 'telegram_bot.db'

def create_admin():
    """Создание первого администратора"""
    print("Создание первого администратора")
    print("Для получения user_id отправьте любое сообщение боту и посмотрите в логи")
    
    try:
        user_id = int(input("Введите Telegram ID пользователя: "))
        username = input("Введите username (без @): ")
        first_name = input("Введите имя: ")
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем, существует ли пользователь
        cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,))
        if cursor.fetchone():
            # Обновляем существующего пользователя
            cursor.execute('''
                UPDATE users 
                SET is_admin = TRUE, username = ?, first_name = ?
                WHERE id = ?
            ''', (username, first_name, user_id))
            print(f"✅ Пользователь {user_id} обновлен и назначен администратором")
        else:
            # Создаем нового пользователя-администратора
            cursor.execute('''
                INSERT INTO users (id, username, first_name, balance, is_admin)
                VALUES (?, ?, ?, 0, TRUE)
            ''', (user_id, username, first_name))
            print(f"✅ Создан новый пользователь-администратор: {user_id}")
        
        conn.commit()
        conn.close()
        
        print("\nТеперь вы можете использовать команды администратора:")
        print("/admin - панель администратора")
        print("/add_points @username [число] - начислить очки")
        print("/add_admin @username - добавить администратора")
        
    except ValueError:
        print("❌ Неверный формат ID")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == '__main__':
    create_admin()