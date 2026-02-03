import sqlite3

conn = sqlite3.connect('bot.db')
cursor = conn.cursor()

print("=== Users table structure ===")
cursor.execute("PRAGMA table_info(users)")
for row in cursor.fetchall():
    print(row)

print("\n=== Current users ===")
cursor.execute("SELECT id, telegram_id, username, first_name, balance, is_admin FROM users")
for row in cursor.fetchall():
    print(row)

print("\n=== Transactions table structure ===")
cursor.execute("PRAGMA table_info(transactions)")
for row in cursor.fetchall():
    print(row)

conn.close()