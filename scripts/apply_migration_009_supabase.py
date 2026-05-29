#!/usr/bin/env python3
"""
Apply Phase 2 migration (009) to Supabase PostgreSQL.

Usage:
    python3 scripts/apply_migration_009_supabase.py

Requires DATABASE_URL environment variable with Supabase connection string.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import psycopg2
from psycopg2 import sql


def apply_migration():
    """Apply migration 009 to Supabase."""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ ERROR: DATABASE_URL environment variable not set")
        print("Please set it to your Supabase connection string:")
        print("  export DATABASE_URL='postgresql://postgres.xxx:password@aws-0-eu-west-1.pooler.supabase.com:5432/postgres'")
        sys.exit(1)
    
    # Normalize postgres:// to postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    print(f"🔗 Connecting to Supabase...")
    print(f"   Host: {database_url.split('@')[1].split('/')[0] if '@' in database_url else 'hidden'}")
    
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cursor = conn.cursor()
        
        print("✅ Connected successfully")
        print("\n📋 Reading migration SQL...")
        
        # Read SQL file
        sql_file = project_root / "database" / "migrations" / "009_phase2_tables_supabase.sql"
        
        if not sql_file.exists():
            print(f"❌ ERROR: Migration file not found: {sql_file}")
            sys.exit(1)
        
        with open(sql_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        print(f"✅ Loaded {len(migration_sql)} characters from {sql_file.name}")
        print("\n🚀 Applying migration...")
        
        # Execute migration
        cursor.execute(migration_sql)
        conn.commit()
        
        print("✅ Migration applied successfully!")
        
        # Verify tables
        print("\n🔍 Verifying created tables...")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN (
                'levels', 'submissions', 'player_stats', 'level_completions',
                'chess_accounts', 'user_coins',
                'infection_status', 'daily_prayer_log',
                'user_preferences'
            )
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        
        if tables:
            print(f"✅ Found {len(tables)} Phase 2 tables:")
            for (table_name,) in tables:
                print(f"   - {table_name}")
        else:
            print("⚠️  WARNING: No Phase 2 tables found (might be a timing issue)")
        
        cursor.close()
        conn.close()
        
        print("\n✅ Migration 009 completed successfully!")
        print("\n📝 Next steps:")
        print("   1. Verify tables in Supabase Dashboard")
        print("   2. Test table creation with sample data")
        print("   3. Start implementing Phase 2 modules")
        
    except psycopg2.Error as e:
        print(f"\n❌ Database error: {e}")
        print(f"   Error code: {e.pgcode}")
        print(f"   Error message: {e.pgerror}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 2 Migration (009) - Supabase PostgreSQL")
    print("=" * 60)
    print()
    
    apply_migration()
