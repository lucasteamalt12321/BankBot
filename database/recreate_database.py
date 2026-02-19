#!/usr/bin/env python3
"""
Unified database reset script with backup functionality
Combines functionality from reset_db.py and recreate_database.py

Features:
- Creates automatic backup before reset
- Drops all tables in correct order (respects foreign keys)
- Recreates database with proper structure
- Optionally adds test user
- Validates database structure after creation

UPDATED: Uses centralized database connection from database.connection
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
import shutil
from datetime import datetime
import sqlite3
import argparse

from database.connection import get_connection
from database.database import Base, create_engine, User
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect


def backup_database(db_path: Path) -> Path:
    """
    Creates a backup copy of the database
    
    Args:
        db_path: Path to the database file
        
    Returns:
        Path to the backup file, or None if database doesn't exist
    """
    if not db_path.exists():
        print("ℹ️  База данных не существует, резервная копия не требуется")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    backup_path = backup_dir / f"bot_backup_{timestamp}.db"
    
    print(f"💾 Создание резервной копии: {backup_path}")
    shutil.copy2(db_path, backup_path)
    print(f"✅ Резервная копия создана")
    
    return backup_path


def drop_all_tables(engine):
    """
    Drops all tables in correct order (respects foreign keys)
    
    Args:
        engine: SQLAlchemy engine
    """
    print("🗑️  Удаление всех таблиц...")
    
    # Tables in correct order (respecting foreign key constraints)
    tables = [
        'user_notifications', 'user_achievements', 'achievements',
        'gifts', 'clan_members', 'clans', 'friendships',
        'dnd_quests', 'dnd_dice_rolls', 'dnd_characters', 'dnd_sessions',
        'game_players', 'game_sessions', 'user_purchases', 'shop_items',
        'shop_categories', 'transactions', 'user_aliases', 'users'
    ]
    
    with engine.connect() as conn:
        for table in tables:
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
                print(f"  ✓ Удалена таблица: {table}")
            except Exception as e:
                print(f"  ⚠️  Не удалось удалить таблицу {table}: {e}")
        conn.commit()
    
    print("✅ Все таблицы удалены")


def create_all_tables(engine):
    """
    Creates all tables using SQLAlchemy models
    
    Args:
        engine: SQLAlchemy engine
    """
    print("🔨 Создание таблиц...")
    Base.metadata.create_all(engine)
    print("✅ Все таблицы созданы")


def validate_database_structure(db_path: Path):
    """
    Validates database structure after creation
    
    Args:
        db_path: Path to the database file
    """
    print("\n📋 Проверка структуры базы данных...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    
    print(f"\n✅ Созданные таблицы ({len(tables)}):")
    for table in tables:
        print(f"   - {table[0]}")
    
    # Check users table structure
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    
    print(f"\n✅ Колонки таблицы users ({len(columns)}):")
    for col in columns:
        col_id, name, col_type, not_null, default, pk = col
        pk_marker = " [PRIMARY KEY]" if pk else ""
        not_null_marker = " NOT NULL" if not_null else ""
        print(f"   - {name} ({col_type}){pk_marker}{not_null_marker}")
    
    conn.close()


def add_test_user(engine):
    """
    Adds a test user to the database
    
    Args:
        engine: SQLAlchemy engine
    """
    print("\n👤 Добавление тестового пользователя...")
    
    session = Session(bind=engine)
    
    try:
        user = User(
            telegram_id=7956794368,
            username="CrazyTimeI",
            first_name="Crazy",
            last_name="Time",
            balance=1000
        )
        session.add(user)
        session.commit()
        print(f"✅ Добавлен тестовый пользователь: {user.username} (ID: {user.telegram_id})")
    except Exception as e:
        print(f"❌ Ошибка при добавлении тестового пользователя: {e}")
        session.rollback()
    finally:
        session.close()


def recreate_database(add_test_data: bool = False, skip_backup: bool = False):
    """
    Main function to recreate the database
    
    Args:
        add_test_data: Whether to add test user after recreation
        skip_backup: Skip backup creation (use with caution!)
    """
    db_path = Path("data/bot.db")
    
    # Create backup unless skipped
    backup_path = None
    if not skip_backup:
        backup_path = backup_database(db_path)
    
    # Delete old database
    if db_path.exists():
        print(f"\n🗑️  Удаление старой базы данных: {db_path}")
        db_path.unlink()
        print("✅ Старая база данных удалена")
    
    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create engine
    print(f"\n🔨 Создание новой базы данных: {db_path}")
    engine = create_engine(f"sqlite:///{db_path}")
    
    # Create all tables
    create_all_tables(engine)
    
    # Validate structure
    validate_database_structure(db_path)
    
    # Add test data if requested
    if add_test_data:
        add_test_user(engine)
    
    return backup_path


def main():
    """Main entry point with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Recreate database with backup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python recreate_database.py                    # Recreate with backup
  python recreate_database.py --test-data        # Recreate with test user
  python recreate_database.py --skip-backup      # Recreate without backup (dangerous!)
        """
    )
    
    parser.add_argument(
        '--test-data',
        action='store_true',
        help='Add test user after database recreation'
    )
    
    parser.add_argument(
        '--skip-backup',
        action='store_true',
        help='Skip backup creation (use with caution!)'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("DATABASE RECREATION SCRIPT")
    print("=" * 70)
    print()
    
    if args.skip_backup:
        print("⚠️  WARNING: Backup creation is DISABLED!")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Operation cancelled")
            return
        print()
    
    try:
        backup_path = recreate_database(
            add_test_data=args.test_data,
            skip_backup=args.skip_backup
        )
        
        print()
        print("=" * 70)
        print("✅ База данных успешно пересоздана")
        if backup_path:
            print(f"💾 Резервная копия сохранена: {backup_path}")
        if args.test_data:
            print("👤 Тестовый пользователь добавлен")
        print("=" * 70)
        
    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ Ошибка при пересоздании базы данных: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
