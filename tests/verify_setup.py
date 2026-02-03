import sqlite3
import os

# Simple verification without imports
db_path = "bot.db"

if not os.path.exists(db_path):
    print(f"❌ Database file {db_path} does not exist")
    exit(1)

print(f"✓ Database file {db_path} exists")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if our tables exist
    tables_to_check = ['shop_items', 'user_purchases', 'scheduled_tasks']
    
    for table in tables_to_check:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';")
        if cursor.fetchone():
            print(f"✓ Table {table} exists")
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  Records: {count}")
        else:
            print(f"❌ Table {table} does not exist")
    
    # Check shop items specifically
    cursor.execute("SELECT id, name, price FROM shop_items WHERE is_active = 1")
    items = cursor.fetchall()
    
    if items:
        print("\n✓ Shop items found:")
        for item_id, name, price in items:
            print(f"  - ID {item_id}: {name} ({price} coins)")
    else:
        print("❌ No shop items found")
    
    conn.close()
    print("\n🎉 Database verification completed!")
    
except Exception as e:
    print(f"❌ Database error: {e}")