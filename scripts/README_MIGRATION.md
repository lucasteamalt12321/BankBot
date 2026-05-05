# Coefficients Migration Script

## Overview

This script migrates parsing configuration from `config/coefficients.json` to the database using the `ParsingRule` model and `ParsingConfigManager`.

## Purpose

The migration script is part of the effort to unify parsing configuration by moving from JSON files to a database-backed solution. This provides:

- Centralized configuration management
- Runtime configuration updates without file changes
- Better integration with the application's data layer
- Audit trail for configuration changes

## Usage

### Basic Usage

Run the migration script from the project root:

```bash
python scripts/migrate_coefficients.py
```

### What It Does

1. **Reads** the `config/coefficients.json` file
2. **Normalizes** game names to standardized format (e.g., "GD Cards" → "gdcards")
3. **Maps** each game to its corresponding parser class
4. **Checks** if parsing rules already exist in the database
5. **Creates** new rules for games not in the database
6. **Updates** existing rules if coefficients have changed
7. **Skips** rules that are already up-to-date
8. **Reports** a detailed summary of the migration

### Output

The script provides detailed output including:

- ✅ Success indicators for each step
- ⚠️ Warnings for existing rules
- ❌ Error messages if something goes wrong
- 📊 Summary statistics (migrated, skipped, errors)
- 📋 Current state of all parsing rules in the database

### Example Output

```
============================================================
Parsing Configuration Migration
============================================================

📂 Loading coefficients from: /path/to/config/coefficients.json
✅ Loaded 5 game configurations

🔌 Connecting to database...
✅ Database connection established

🔄 Migrating configurations...
------------------------------------------------------------

📝 Processing: GD Cards
   → Game name: gdcards
   → Parser class: GDCardsParser
   → Coefficient: 2
   ✅ Created new rule (ID: 1)

...

------------------------------------------------------------
📊 Migration Summary:
   • Total games processed: 5
   • Successfully migrated: 5
   • Skipped (no changes): 0
   • Errors: 0

📋 Current parsing rules in database:
------------------------------------------------------------
   gdcards              | Coef:    2.0 | ✅ Enabled
   shmalala             | Coef:    1.0 | ✅ Enabled
   truemafia            | Coef:   15.0 | ✅ Enabled
   bunkerrp             | Coef:   20.0 | ✅ Enabled
   shmalala_karma       | Coef:   10.0 | ✅ Enabled

============================================================
✅ Migration completed successfully!
============================================================
```

## Game Name Mappings

The script uses the following mappings:

| Original Name (JSON) | Normalized Name | Parser Class |
|---------------------|-----------------|--------------|
| GD Cards | gdcards | GDCardsParser |
| Shmalala | shmalala | ShmalalaParser |
| Shmalala Karma | shmalala_karma | ShmalalaKarmaParser |
| True Mafia | truemafia | TrueMafiaParser |
| Bunker RP | bunkerrp | BunkerRPParser |

## Error Handling

The script handles various error scenarios gracefully:

- **Missing coefficients.json**: Reports error and exits
- **Invalid JSON**: Reports parsing error and exits
- **Database connection errors**: Reports error and exits
- **Individual game errors**: Continues processing other games, reports errors in summary
- **Session cleanup**: Always closes database session, even on errors

## Exit Codes

- `0`: Migration completed successfully (no errors)
- `1`: Migration completed with errors or failed to start

## Safety Features

- **Idempotent**: Safe to run multiple times - won't create duplicates
- **Non-destructive**: Only creates or updates, never deletes existing rules
- **Transactional**: Each rule operation is committed separately
- **Detailed logging**: Clear output for debugging and verification

## Testing

Unit tests are available in `tests/unit/test_migrate_coefficients.py`:

```bash
# Run migration script tests
python -m pytest tests/unit/test_migrate_coefficients.py -v

# Run with coverage
python -m pytest tests/unit/test_migrate_coefficients.py --cov=scripts.migrate_coefficients
```

## Related Files

- **Script**: `scripts/migrate_coefficients.py`
- **Source data**: `config/coefficients.json`
- **Model**: `src/models/parsing_rule.py`
- **Manager**: `core/managers/parsing_config_manager.py`
- **Tests**: `tests/unit/test_migrate_coefficients.py`

## Next Steps

After running the migration:

1. Verify the data in the database matches expectations
2. Update parsers to use `ParsingConfigManager` instead of reading JSON
3. Consider deprecating or removing `coefficients.json` once migration is complete
4. Update documentation to reflect the new configuration approach

## Troubleshooting

### "File not found" error

Ensure you're running the script from the project root directory where `config/coefficients.json` exists.

### Database connection errors

Check that:
- The database is accessible
- `DATABASE_URL` in your `.env` file is correct
- Database tables have been created (run migrations if needed)

### "Rule already exists" warnings

This is normal behavior. The script detects existing rules and only updates them if coefficients have changed.

## Support

For issues or questions about the migration script, refer to:
- Task 7.3.1 in `.kiro/specs/project-critical-fixes/tasks.md`
- Design document: `.kiro/specs/project-critical-fixes/design.md` (Section 7)
- Requirements: `.kiro/specs/project-critical-fixes/requirements.md` (Requirement 7)
