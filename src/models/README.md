# Models Package

This package contains SQLAlchemy models for the application that are separate from the main database models.

## ParsingRule Model

The `ParsingRule` model provides database-backed configuration for parsing rules, replacing the previous `coefficients.json` file approach.

### Schema

```python
class ParsingRule(Base):
    __tablename__ = 'parsing_rules_config'
    
    id: int                    # Primary key
    game_name: str             # Unique game identifier (e.g., 'gdcards', 'shmalala')
    parser_class: str          # Name of the parser class to use
    coefficient: float         # Multiplier for points calculation (default: 1.0)
    enabled: bool              # Whether this rule is active (default: True)
    config: dict               # Additional JSON configuration (default: {})
```

### Usage Example

```python
from database.database import SessionLocal
from src.models import ParsingRule

# Create a new parsing rule
session = SessionLocal()
rule = ParsingRule(
    game_name="gdcards",
    parser_class="GDCardsParser",
    coefficient=1.5,
    enabled=True,
    config={"max_retries": 3, "timeout": 30}
)
session.add(rule)
session.commit()

# Query parsing rules
active_rules = session.query(ParsingRule).filter_by(enabled=True).all()
gdcards_rule = session.query(ParsingRule).filter_by(game_name="gdcards").first()

# Update a rule
gdcards_rule.coefficient = 2.0
session.commit()

session.close()
```

### Migration Notes

This model is part of the parsing configuration unification effort (Requirement 7 in the project-critical-fixes spec). It will eventually replace:
- The `coefficients.json` file
- The `ADVANCED_CURRENCY_CONFIG` in `config.py`
- The old `ParsingRule` model in `database/database.py`

The model uses a separate table name (`parsing_rules_config`) to avoid conflicts during the migration period.

### Related Components

- **ParsingConfigManager** (to be implemented in task 7.2): API for managing parsing rules
- **Migration Script** (to be implemented in task 7.3): Script to migrate data from coefficients.json
- **Parser Updates** (to be implemented in task 7.4): Updates to parsers to use database configuration

### Testing

Unit tests are available in `tests/unit/test_parsing_rule_model.py`. Run them with:

```bash
pytest tests/unit/test_parsing_rule_model.py -v
```

### Future Work

1. Create database migration (task 7.1.2)
2. Implement ParsingConfigManager (task 7.2)
3. Migrate data from coefficients.json (task 7.3)
4. Update parsers to use database configuration (task 7.4)
