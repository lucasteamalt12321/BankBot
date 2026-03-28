# ⚠️ DEPRECATION NOTICE: Coefficient JSON Files

## Status: DEPRECATED as of 2026-02-23

The following coefficient configuration files are **DEPRECATED** and will be removed in a future release:

- `coefficients.json`
- `coefficients.development.json`
- `coefficients.production.json`
- `coefficients.test.json`

## Migration Path

All coefficient configuration has been migrated to the database using the `parsing_rules` table.

### For Production Code

**OLD (Deprecated):**
```python
from src.coefficient_provider import CoefficientProvider

# Loading from JSON file (deprecated)
provider = CoefficientProvider.from_config('config/coefficients.json')
```

**NEW (Recommended):**
```python
from database.database import SessionLocal
from src.models.parsing_rule import ParsingRule
from src.repository.base import BaseRepository
from core.managers.parsing_config_manager import ParsingConfigManager
from src.coefficient_provider import CoefficientProvider

# Using database-backed configuration
session = SessionLocal()
repo = BaseRepository(ParsingRule, session)
manager = ParsingConfigManager(repo)
provider = CoefficientProvider.from_database(manager)

# Get coefficient
coefficient = provider.get_coefficient("gdcards")
```

### For Tests

Tests can continue using the dictionary-based initialization for simplicity:

```python
from src.coefficient_provider import CoefficientProvider

# For testing purposes only
provider = CoefficientProvider({
    "GD Cards": 2,
    "Shmalala": 1,
    "True Mafia": 15,
    "Bunker RP": 20
})
```

## Database Migration

Coefficients have been migrated to the database using the migration script:

```bash
python scripts/migrate_coefficients.py
```

This creates entries in the `parsing_rules` table with the following structure:

| game_name   | parser_class      | coefficient | enabled |
|-------------|-------------------|-------------|---------|
| gdcards     | GDCardsParser     | 2.0         | true    |
| shmalala    | ShmalalaParser    | 1.0         | true    |
| truemafia   | TrueMafiaParser   | 15.0        | true    |
| bunkerrp    | BunkerRPParser    | 20.0        | true    |

## Managing Coefficients

Use the `ParsingConfigManager` API to manage coefficients:

```python
# Get coefficient
coefficient = manager.get_coefficient("gdcards")

# Update coefficient
manager.update_coefficient("gdcards", 2.5)

# Get all active rules
active_rules = manager.get_all_active_rules()

# Enable/disable a rule
manager.enable_rule("gdcards")
manager.disable_rule("gdcards")
```

## Admin Commands

Administrators can manage parsing rules through bot commands:

- `/list_parsing_rules` - List all parsing rules
- `/add_parsing_rule` - Add a new parsing rule
- `/update_parsing_rule` - Update an existing rule
- `/config_status` - View configuration status

## Timeline

- **2026-02-23**: Deprecation notice added
- **2026-03-23**: Warning messages added to code
- **2026-04-23**: JSON files will be removed (30 days notice)

## Questions?

See the following documentation:
- `docs/CONFIG_MIGRATION.md` - Full migration guide
- `core/managers/parsing_config_manager.py` - API documentation
- `scripts/migrate_coefficients.py` - Migration script

## Related Tasks

This deprecation is part of:
- Task 7.3: Migrate data from coefficients.json
- Task 7.4: Update parsers to use database
- Requirement 7: Unify parsing configuration
