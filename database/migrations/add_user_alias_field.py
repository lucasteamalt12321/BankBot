"""Migration 005: Add alias field to users table."""

import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def run_migration(db_path: str = "bot.db") -> None:
    """Add alias column to users table if it doesn't exist.

    Args:
        db_path: Path to the SQLite database file.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]

    if "alias" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN alias VARCHAR(32) DEFAULT NULL")
        print("✓ Added 'alias' column to users table")
    else:
        print("✓ Column 'alias' already exists in users table")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    run_migration()
