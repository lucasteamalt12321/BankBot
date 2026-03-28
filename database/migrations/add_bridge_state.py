"""Migration: Add bridge_state table for Bridge module."""

import os
import sqlite3

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "bot.db"
)


def upgrade(db_path: str = DB_PATH) -> None:
    """Apply migration: create bridge_state table.

    Args:
        db_path: Path to the SQLite database file.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bridge_state (
                id               INTEGER PRIMARY KEY DEFAULT 1,
                last_tg_msg_id   INTEGER NOT NULL DEFAULT 0,
                last_vk_msg_id   INTEGER NOT NULL DEFAULT 0,
                updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            INSERT OR IGNORE INTO bridge_state (id, last_tg_msg_id, last_vk_msg_id, updated_at)
            VALUES (1, 0, 0, CURRENT_TIMESTAMP)
        """)
        conn.commit()
        print("Migration 004: bridge_state table created successfully")
    finally:
        conn.close()


def downgrade(db_path: str = DB_PATH) -> None:
    """Rollback migration: drop bridge_state table.

    Args:
        db_path: Path to the SQLite database file.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DROP TABLE IF EXISTS bridge_state")
        conn.commit()
        print("Migration 004: bridge_state table dropped")
    finally:
        conn.close()


if __name__ == "__main__":
    upgrade()
