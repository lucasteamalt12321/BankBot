import sqlite3

# Проверяем структуру таблицы transactions
conn = sqlite3.connect('bot.db')
cursor = conn.cursor()

print("=== Transactions table structure ===")
cursor.execute("PRAGMA table_info(transactions)")
for row in cursor.fetchall():
    print(row)

print("\n=== Users table structure ===")
cursor.execute("PRAGMA table_info(users)")
for row in cursor.fetchall():
    print(row)

print("\n=== Current users ===")
cursor.execute("SELECT id, telegram_id, username, first_name, balance, is_admin FROM users")
for row in cursor.fetchall():
    print(row)

conn.close()