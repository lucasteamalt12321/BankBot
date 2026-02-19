#!/usr/bin/env python3
"""Database migration script."""

import sqlite3
import sys
from pathlib import Path
from typing import List, Tuple


def get_applied_migrations(conn: sqlite3.Connection) -> List[int]:
    """
    Get list of applied migration versions.
    
    Args:
        conn: Database connection
        
    Returns:
        List of applied migration version numbers
    """
    cursor = conn.cursor()
    
    # Check if migrations table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='schema_migrations'
    """)
    
    if not cursor.fetchone():
        return []
    
    # Get applied migrations
    cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
    return [row[0] for row in cursor.fetchall()]


def get_available_migrations() -> List[Tuple[int, str, Path]]:
    """
    Get list of available migration files.
    
    Returns:
        List of tuples (version, name, path)
    """
    migrations_dir = Path(__file__).parent
    migrations = []
    
    for sql_file in sorted(migrations_dir.glob('*.sql')):
        # Parse filename: 001_initial_schema.sql
        filename = sql_file.stem
        parts = filename.split('_', 1)
        
        if len(parts) == 2 and parts[0].isdigit():
            version = int(parts[0])
            name = parts[1]
            migrations.append((version, name, sql_file))
    
    return sorted(migrations, key=lambda x: x[0])


def apply_migration(conn: sqlite3.Connection, version: int, name: str, path: Path) -> None:
    """
    Apply a single migration.
    
    Args:
        conn: Database connection
        version: Migration version number
        name: Migration name
        path: Path to SQL file
    """
    print(f"Applying migration {version:03d}: {name}...")
    
    # Read SQL file
    with open(path, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    # Execute migration
    try:
        conn.executescript(sql)
        conn.commit()
        print(f"✅ Migration {version:03d} applied successfully")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error applying migration {version:03d}: {e}")
        raise


def migrate(db_path: str, target_version: int = None) -> None:
    """
    Run database migrations.
    
    Args:
        db_path: Path to database file
        target_version: Target version to migrate to (None = latest)
    """
    print(f"Migrating database: {db_path}")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    
    try:
        # Get applied and available migrations
        applied = get_applied_migrations(conn)
        available = get_available_migrations()
        
        if not available:
            print("⚠️  No migration files found")
            return
        
        print(f"Applied migrations: {applied if applied else 'none'}")
        print(f"Available migrations: {[v for v, _, _ in available]}")
        
        # Determine which migrations to apply
        to_apply = []
        for version, name, path in available:
            if version not in applied:
                if target_version is None or version <= target_version:
                    to_apply.append((version, name, path))
        
        if not to_apply:
            print("✅ Database is up to date")
            return
        
        # Apply migrations
        print(f"\nApplying {len(to_apply)} migration(s)...")
        for version, name, path in to_apply:
            apply_migration(conn, version, name, path)
        
        print(f"\n✅ Successfully applied {len(to_apply)} migration(s)")
        
    finally:
        conn.close()


def rollback(db_path: str, target_version: int) -> None:
    """
    Rollback database to a specific version.
    
    Note: This is a destructive operation and should be used with caution.
    Currently not implemented - manual rollback required.
    
    Args:
        db_path: Path to database file
        target_version: Version to rollback to
    """
    print("⚠️  Rollback not implemented")
    print("To rollback, restore from backup or manually drop tables")


def status(db_path: str) -> None:
    """
    Show migration status.
    
    Args:
        db_path: Path to database file
    """
    print(f"Migration status for: {db_path}")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    
    try:
        applied = get_applied_migrations(conn)
        available = get_available_migrations()
        
        print(f"\nApplied migrations: {len(applied)}")
        for version in applied:
            print(f"  ✅ {version:03d}")
        
        print(f"\nAvailable migrations: {len(available)}")
        for version, name, _ in available:
            status_icon = "✅" if version in applied else "⏳"
            print(f"  {status_icon} {version:03d}: {name}")
        
        pending = [v for v, _, _ in available if v not in applied]
        if pending:
            print(f"\n⏳ Pending migrations: {pending}")
        else:
            print("\n✅ Database is up to date")
        
    finally:
        conn.close()


def main():
    """Main migration command."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python migrate.py <db_path> [command] [version]")
        print()
        print("Commands:")
        print("  migrate [version]  - Apply migrations up to version (default: all)")
        print("  status             - Show migration status")
        print("  rollback <version> - Rollback to version (not implemented)")
        print()
        print("Examples:")
        print("  python migrate.py data/bot.db migrate")
        print("  python migrate.py data/bot.db migrate 1")
        print("  python migrate.py data/bot.db status")
        sys.exit(1)
    
    db_path = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else 'migrate'
    
    if command == 'migrate':
        target_version = int(sys.argv[3]) if len(sys.argv) > 3 else None
        migrate(db_path, target_version)
    elif command == 'status':
        status(db_path)
    elif command == 'rollback':
        if len(sys.argv) < 4:
            print("❌ Error: rollback requires version number")
            sys.exit(1)
        target_version = int(sys.argv[3])
        rollback(db_path, target_version)
    else:
        print(f"❌ Error: Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
