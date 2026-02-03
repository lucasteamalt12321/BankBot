#!/usr/bin/env python3
import sqlite3
import sys

def check_db_structure():
    try:
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        
        # Проверяем структуру таблицы users
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        
        print("Структура таблицы users:")
        for col in columns:
            print(f"  {col[1]} ({col[2]}) - nullable: {not col[3]}")
        
        # Проверяем есть ли поле is_admin
        has_is_admin = any(col[1] == 'is_admin' for col in columns)
        print(f"\nПоле is_admin существует: {has_is_admin}")
        
        # Проверяем количество пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"Количество пользователей: {user_count}")
        
        # Проверяем пользователей с telegram_id
        cursor.execute("SELECT telegram_id, username, first_name FROM users WHERE telegram_id IS NOT NULL")
        users = cursor.fetchall()
        print(f"\nПользователи с telegram_id:")
        for user in users:
            print(f"  ID: {user[0]}, Username: {user[1]}, Name: {user[2]}")
        
        conn.close()
        
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    check_db_structure()