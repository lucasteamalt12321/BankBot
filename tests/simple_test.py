import sqlite3

# Проверяем структуру базы данных
conn = sqlite3.connect('bot.db')
cursor = conn.cursor()

print("=== Структура таблицы users ===")
cursor.execute("PRAGMA table_info(users)")
for row in cursor.fetchall():
    print(f"  {row[1]} ({row[2]})")

print("\n=== Текущие пользователи ===")
cursor.execute("SELECT id, telegram_id, username, first_name, balance, is_admin FROM users")
for row in cursor.fetchall():
    print(f"  ID: {row[0]}, Telegram ID: {row[1]}, Username: {row[2]}, Name: {row[3]}, Balance: {row[4]}, Admin: {row[5]}")

print("\n=== Структура таблицы transactions ===")
cursor.execute("PRAGMA table_info(transactions)")
for row in cursor.fetchall():
    print(f"  {row[1]} ({row[2]})")

print("\n=== Последние транзакции ===")
cursor.execute("SELECT id, user_id, amount, transaction_type, description FROM transactions ORDER BY id DESC LIMIT 5")
for row in cursor.fetchall():
    print(f"  ID: {row[0]}, User ID: {row[1]}, Amount: {row[2]}, Type: {row[3]}, Desc: {row[4]}")

conn.close()