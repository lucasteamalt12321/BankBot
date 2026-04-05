"""
Apply Beta Features Migration
Applies the 002_beta_features_schema.sql migration
"""

import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def apply_migration():
    """Apply beta features migration"""
    db_path = "data/bot.db"
    migration_file = "database/migrations/002_beta_features_schema.sql"

    if not os.path.exists(db_path):
        logger.error(f"Database not found: {db_path}")
        return False

    if not os.path.exists(migration_file):
        logger.error(f"Migration file not found: {migration_file}")
        return False

    try:
        # Read migration SQL
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()

        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Execute migration
        logger.info("Applying beta features migration...")
        cursor.executescript(migration_sql)
        conn.commit()

        logger.info("✅ Migration applied successfully!")

        # Verify tables were created
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE '%marketplace%' OR name LIKE '%quest%' OR name LIKE '%tournament%'
            ORDER BY name
        """)

        tables = cursor.fetchall()
        logger.info(f"Created {len(tables)} new tables:")
        for table in tables:
            logger.info(f"  - {table[0]}")

        conn.close()
        return True

    except Exception as e:
        logger.error(f"Error applying migration: {e}")
        return False


if __name__ == "__main__":
    success = apply_migration()
    if success:
        print("\n✅ Beta features migration completed successfully!")
        print("You can now use all 27 beta commands.")
        print("\nTry: /beta to see the list of new commands")
    else:
        print("\n❌ Migration failed. Check the logs above.")
