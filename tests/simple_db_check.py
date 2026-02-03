import sqlite3

# Check existing tables
conn = sqlite3.connect('bot.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Existing tables:")
for table in tables:
    print(f"  - {table[0]}")

# Check if our new tables exist
new_tables = ['shop_items', 'user_purchases', 'scheduled_tasks']
for table_name in new_tables:
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
    exists = cursor.fetchone()
    if exists:
        print(f"✓ {table_name} table exists")
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  Records: {count}")
    else:
        print(f"✗ {table_name} table does not exist")

conn.close()