# Migration 003: Add parsing_rules_config Table

## Overview

This migration creates the new `parsing_rules_config` table for unified parsing configuration. This table replaces the old approach of using `coefficients.json` and `ADVANCED_CURRENCY_CONFIG` from config files.

## What This Migration Does

1. Creates the `parsing_rules_config` table with the following columns:
   - `id`: Primary key (auto-increment)
   - `game_name`: Unique game identifier (e.g., 'gdcards', 'shmalala')
   - `parser_class`: Name of the parser class to use
   - `coefficient`: Multiplier coefficient for points calculation (default: 1.0)
   - `enabled`: Whether this parsing rule is active (default: true)
   - `config`: Additional JSON configuration for the parser (default: '{}')
   - `created_at`: Timestamp when the rule was created
   - `updated_at`: Timestamp when the rule was last updated

2. Creates indexes for performance:
   - `idx_parsing_rules_config_game_name`: Index on game_name for fast lookups
   - `idx_parsing_rules_config_enabled`: Index on enabled for filtering active rules

3. Inserts initial parsing rules for existing games (Python migration only):
   - gdcards
   - shmalala
   - truemafia
   - bunkerrp

## How to Apply

### Option 1: Using the Python Migration Script (Recommended)

```bash
python database/migrations/add_parsing_rules_config.py
```

This will:
- Create the table if it doesn't exist
- Add initial parsing rules for existing games
- Skip if the table already exists

### Option 2: Using the SQL Migration System

```bash
python database/migrations/migrate.py data/bot.db migrate
```

This will apply all pending migrations including this one.

### Option 3: Manual SQL Execution

```bash
sqlite3 data/bot.db < database/migrations/003_add_parsing_rules_config.sql
```

Note: This only creates the table structure, not the initial data.

## Verification

After applying the migration, verify it worked:

```python
from database.database import SessionLocal
from src.models.parsing_rule import ParsingRule

session = SessionLocal()
rules = session.query(ParsingRule).all()
print(f"Found {len(rules)} parsing rules")
for rule in rules:
    print(f"  - {rule.game_name}: {rule.parser_class} (enabled={rule.enabled})")
session.close()
```

Expected output:
```
Found 4 parsing rules
  - gdcards: GDCardsParser (enabled=True)
  - shmalala: ShmalalaParser (enabled=True)
  - truemafia: TrueMafiaParser (enabled=True)
  - bunkerrp: BunkerRPParser (enabled=True)
```

## Rollback

To rollback this migration:

```sql
DROP TABLE IF EXISTS parsing_rules_config;
DELETE FROM schema_migrations WHERE version = 3;
```

## Related Files

- Model: `src/models/parsing_rule.py`
- Tests: `tests/unit/test_parsing_rule_model.py`
- Migration Plan: `docs/MIGRATION_PLAN_SIMPLE_DB.md`

## Next Steps

After applying this migration:

1. Migrate data from `coefficients.json` to the database (Task 7.3)
2. Update parsers to use the database configuration (Task 7.4)
3. Remove old configuration files
