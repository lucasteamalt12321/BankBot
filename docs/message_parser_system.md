# Message Parser System Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Supported Games](#supported-games)
3. [Architecture](#architecture)
4. [Components](#components)
5. [Configuration](#configuration)
6. [Usage Examples](#usage-examples)
7. [Error Handling](#error-handling)
8. [Testing](#testing)

## System Overview

The Message Parser System is a modular Python application that processes game-related text messages from five different games to manage player balances. The system extracts structured data from messages, tracks player balances across multiple games, and applies game-specific coefficients to convert in-game currencies to a unified bank coin system.

### Key Features

- **Multi-Game Support**: Handles 5 different games with 10 distinct message types
- **Balance Tracking**: Maintains both per-game balances and unified bank balances
- **Coefficient System**: Converts game-specific currencies using configurable multipliers
- **Idempotency**: Prevents duplicate message processing
- **Transaction Safety**: Atomic database operations with rollback on errors
- **Audit Logging**: Complete audit trail of all balance operations
- **Property-Based Testing**: Comprehensive test coverage with 26 correctness properties

### Core Workflow

```
Message Input → Classification → Parsing → Balance Processing → Database Update
```

1. **Classification**: Identify message type and game
2. **Parsing**: Extract structured data (player names, amounts)
3. **Balance Processing**: Apply business logic and coefficients
4. **Persistence**: Update database atomically with audit logging

## Supported Games

The system supports 5 games with different message types and coefficients:

### 1. GD Cards (Coefficient: 2)

**Message Types:**
- **Profile Messages**: Track player orbs balance
- **Accrual Messages**: Credit points from new cards

**Balance Logic:**
- Profile: Delta-based tracking (current - last balance)
- Accrual: Direct addition to balance

### 2. Shmalala Fishing (Coefficient: 1)

**Message Types:**
- **Fishing Messages**: Credit coins from fishing activities

**Balance Logic:**
- Accrual only: Direct addition to balance

### 3. Shmalala Karma (Coefficient: 10)

**Message Types:**
- **Karma Messages**: Credit karma points (always +1)

**Balance Logic:**
- Accrual only: Fixed +1 per message

### 4. True Mafia (Coefficient: 15)

**Message Types:**
- **Profile Messages**: Track player money balance
- **Game End Messages**: Credit winners with 10 money each

**Balance Logic:**
- Profile: Delta-based tracking
- Game End: Fixed 10 money per winner

### 5. Bunker RP (Coefficient: 20)

**Message Types:**
- **Profile Messages**: Track player money balance
- **Game End Messages**: Credit winners with 30 money each

**Balance Logic:**
- Profile: Delta-based tracking
- Game End: Fixed 30 money per winner

## Architecture

### High-Level Architecture

```
┌─────────────────┐
│  Message Input  │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│ Message Classifier  │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   Message Parser    │ (8 different parsers)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Balance Manager    │
└────────┬────────────┘
         │
         ├──────────────────┐
         │                  │
         ▼                  ▼
┌──────────────────┐  ┌──────────────────┐
│ Coefficient      │  │ Database         │
│ Provider         │  │ Repository       │
└──────────────────┘  └──────────────────┘
```

### Design Patterns

- **Strategy Pattern**: Extensible message parsing with type-specific parsers
- **Repository Pattern**: Database abstraction for testability
- **Dependency Injection**: Loose coupling between components
- **Transaction Script**: Business logic in BalanceManager

## Components

### 1. MessageClassifier

**Purpose**: Determines message type by matching key phrases

**Supported Types**:
- `GDCARDS_PROFILE`: Contains "ПРОФИЛЬ" and "Орбы:"
- `GDCARDS_ACCRUAL`: Contains "(🃏 НОВАЯ КАРТА 🃏"
- `SHMALALA_FISHING`: Contains "🎣 [Рыбалка] 🎣"
- `SHMALALA_KARMA`: Contains "Лайк! Вы повысили рейтинг пользователя"
- `TRUEMAFIA_GAME_END`: Contains "Игра окончена!" and "Победители:"
- `TRUEMAFIA_PROFILE`: Contains "💎 Камни:", "🎎 Активная роль:", "💵 Деньги:"
- `BUNKERRP_GAME_END`: Contains "Прошли в бункер:"
- `BUNKERRP_PROFILE`: Contains "💎 Кристаллики:", "🎯 Побед:", "💵 Деньги:"
- `UNKNOWN`: No matching patterns

**Example**:
```python
classifier = MessageClassifier()
message_type = classifier.classify(message_text)
```

### 2. Message Parsers

Eight specialized parsers extract structured data:

#### ProfileParser (GD Cards)
- Extracts: player_name, orbs
- Format: "ПРОФИЛЬ {name}" with "Орбы: {amount}"

#### AccrualParser (GD Cards)
- Extracts: player_name, points
- Format: "Игрок: {name}" with "Очки: +{amount}"

#### FishingParser (Shmalala)
- Extracts: player_name, coins
- Format: "Рыбак: {name}" with "Монеты: +{amount}"

#### KarmaParser (Shmalala)
- Extracts: player_name
- Format: "Лайк! Вы повысили рейтинг пользователя {name}"
- Always returns karma=1

#### MafiaGameEndParser (True Mafia)
- Extracts: list of winner names
- Format: "Победители:" section with "{name} - {role}"

#### MafiaProfileParser (True Mafia)
- Extracts: player_name, money
- Format: "👤 {name}" with "💵 Деньги: {amount}"

#### BunkerGameEndParser (Bunker RP)
- Extracts: list of winner names
- Format: "Прошли в бункер:" section with "{number}. {name}"

#### BunkerProfileParser (Bunker RP)
- Extracts: player_name, money
- Format: "👤 {name}" with "💵 Деньги: {amount}"

### 3. BalanceManager

**Purpose**: Orchestrates balance updates with business logic

**Key Methods**:

- `process_profile(parsed)`: Handle profile messages with delta calculation
- `process_accrual(parsed)`: Handle accrual messages
- `process_fishing(parsed)`: Handle fishing messages
- `process_karma(parsed)`: Handle karma messages (always +1)
- `process_game_winners(winners, game, amount)`: Handle game end messages
- `process_mafia_profile(parsed)`: Handle True Mafia profiles
- `process_bunker_profile(parsed)`: Handle Bunker RP profiles

**Balance Logic**:

1. **Profile Messages** (First Time):
   - Create bot_balance with last_balance = current amount
   - Set current_bot_balance = 0
   - Do NOT modify bank_balance

2. **Profile Messages** (Subsequent):
   - Calculate delta = current - last_balance
   - Update bank_balance += delta * coefficient
   - Update last_balance = current

3. **Accrual Messages**:
   - Update current_bot_balance += amount
   - Update bank_balance += amount * coefficient
   - Do NOT modify last_balance

4. **Game End Messages**:
   - For each winner: current_bot_balance += fixed_amount
   - For each winner: bank_balance += fixed_amount * coefficient

### 4. CoefficientProvider

**Purpose**: Provides game-specific conversion rates

**Configuration**:
```json
{
  "GD Cards": 2,
  "Shmalala": 1,
  "Shmalala Karma": 10,
  "True Mafia": 15,
  "Bunker RP": 20
}
```

**Usage**:
```python
provider = CoefficientProvider.from_config("config/coefficients.json")
coefficient = provider.get_coefficient("GD Cards")  # Returns 2
```

### 5. DatabaseRepository

**Purpose**: Abstracts database operations for persistence

**Data Models**:

- **UserBalance**: user_id, user_name, bank_balance
- **BotBalance**: user_id, game, last_balance, current_bot_balance

**Key Methods**:
- `get_or_create_user(user_name)`: Get or create user record
- `get_bot_balance(user_id, game)`: Get bot balance for game
- `create_bot_balance(...)`: Create new bot balance record
- `update_user_balance(user_id, new_balance)`: Update bank balance
- `update_bot_last_balance(...)`: Update last_balance field
- `update_bot_current_balance(...)`: Update current_bot_balance field
- `begin_transaction()`, `commit_transaction()`, `rollback_transaction()`

### 6. IdempotencyChecker

**Purpose**: Prevents duplicate message processing

**How It Works**:
- Generates SHA-256 hash from message content + timestamp
- Checks if message_id exists in processed_messages table
- Marks messages as processed after successful processing

**Usage**:
```python
checker = IdempotencyChecker(repository)
message_id = checker.generate_message_id(message, timestamp)
if not checker.is_processed(message_id):
    # Process message
    checker.mark_processed(message_id)
```

### 7. AuditLogger

**Purpose**: Records all balance operations for audit trail

**Log Types**:
- `log_profile_init()`: First-time profile initialization
- `log_profile_update()`: Profile balance changes
- `log_accrual()`: Accrual processing
- `log_error()`: Error conditions

**Example Log Output**:
```
INFO: Profile initialized - Player: Alice, Game: GD Cards, Initial balance: 100
INFO: Profile updated - Player: Alice, Game: GD Cards, Balance: 100 → 150 (Δ50), Bank change: 100 (coef: 2)
INFO: Accrual processed - Player: Bob, Game: Shmalala, Points: +25, Bank change: +25 (coef: 1)
```

### 8. MessageProcessor

**Purpose**: Main orchestrator that coordinates all components

**Workflow**:
1. Check idempotency
2. Begin database transaction
3. Classify message type
4. Route to appropriate parser
5. Process with BalanceManager
6. Mark as processed
7. Commit transaction
8. Handle errors with rollback

## Configuration

### coefficients.json

Location: `config/coefficients.json`

```json
{
  "GD Cards": 2,
  "Shmalala": 1,
  "Shmalala Karma": 10,
  "True Mafia": 15,
  "Bunker RP": 20
}
```

### Database Schema

```sql
-- User balances (unified bank balance)
CREATE TABLE user_balances (
    user_id TEXT PRIMARY KEY,
    user_name TEXT UNIQUE NOT NULL,
    bank_balance TEXT NOT NULL
);

-- Bot balances (per-game tracking)
CREATE TABLE bot_balances (
    user_id TEXT NOT NULL,
    game TEXT NOT NULL,
    last_balance TEXT NOT NULL,
    current_bot_balance TEXT NOT NULL,
    PRIMARY KEY (user_id, game),
    FOREIGN KEY (user_id) REFERENCES user_balances(user_id)
);

-- Processed messages (idempotency)
CREATE TABLE processed_messages (
    message_id TEXT PRIMARY KEY,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Logging Configuration

Location: `src/logging_config.py`

```python
import logging

def setup_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/message_parser.log'),
            logging.StreamHandler()
        ]
    )
```

## Usage Examples

### Example 1: GD Cards Profile Message

```python
from datetime import datetime
from src.message_processor import create_message_processor

# Initialize system
processor = create_message_processor(
    db_path="data/bot.db",
    config_path="config/coefficients.json"
)

# Process profile message
message = """
ПРОФИЛЬ Alice
Орбы: 150
Карты: 25
"""

processor.process_message(message, datetime.now())

# Result:
# - If first time: bot_balance created with last_balance=150, current_bot_balance=0
# - If subsequent: delta calculated, bank_balance updated by delta * 2
```

### Example 2: GD Cards Accrual Message

```python
message = """
🃏 НОВАЯ КАРТА 🃏
Игрок: Bob
Очки: +50
Редкость: Легендарная
"""

processor.process_message(message, datetime.now())

# Result:
# - current_bot_balance += 50
# - bank_balance += 50 * 2 = 100
```

### Example 3: Shmalala Fishing Message

```python
message = """
🎣 [Рыбалка] 🎣
Рыбак: Charlie
Монеты: +30 (Всего: 130)
Рыба: Золотая форель
"""

processor.process_message(message, datetime.now())

# Result:
# - current_bot_balance += 30
# - bank_balance += 30 * 1 = 30
```

### Example 4: Shmalala Karma Message

```python
message = """
Лайк! Вы повысили рейтинг пользователя Diana.
Теперь его рейтинг: 25
"""

processor.process_message(message, datetime.now())

# Result:
# - current_bot_balance += 1 (always +1)
# - bank_balance += 1 * 10 = 10
```

### Example 5: True Mafia Game End Message

```python
message = """
Игра окончена!

Победители:
Alice - Мафия
Bob - Дон

Остальные участники:
Charlie - Мирный
"""

processor.process_message(message, datetime.now())

# Result:
# - Alice: current_bot_balance += 10, bank_balance += 10 * 15 = 150
# - Bob: current_bot_balance += 10, bank_balance += 10 * 15 = 150
```

### Example 6: True Mafia Profile Message

```python
message = """
👤 Eve
💎 Камни: 5
🎎 Активная роль: Мирный
💵 Деньги: 200
"""

processor.process_message(message, datetime.now())

# Result:
# - If first time: bot_balance created with last_balance=200
# - If subsequent: delta calculated, bank_balance updated by delta * 15
```

### Example 7: Bunker RP Game End Message

```python
message = """
Прошли в бункер:
1. Frank
2. Grace

Не прошли в бункер:
3. Henry
"""

processor.process_message(message, datetime.now())

# Result:
# - Frank: current_bot_balance += 30, bank_balance += 30 * 20 = 600
# - Grace: current_bot_balance += 30, bank_balance += 30 * 20 = 600
```

### Example 8: Bunker RP Profile Message

```python
message = """
👤 Ivan
💎 Кристаллики: 10
🎯 Побед: 5
💵 Деньги: 500
"""

processor.process_message(message, datetime.now())

# Result:
# - If first time: bot_balance created with last_balance=500
# - If subsequent: delta calculated, bank_balance updated by delta * 20
```

### Example 9: Complete Setup

```python
from datetime import datetime
from src.message_processor import MessageProcessor
from src.classifier import MessageClassifier
from src.parsers import *
from src.balance_manager import BalanceManager
from src.coefficient_provider import CoefficientProvider
from src.repository import SQLiteRepository
from src.idempotency import IdempotencyChecker
from src.audit_logger import AuditLogger
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = AuditLogger(logging.getLogger(__name__))

# Initialize components
repository = SQLiteRepository("data/bot.db")
coefficient_provider = CoefficientProvider.from_config("config/coefficients.json")
balance_manager = BalanceManager(repository, coefficient_provider, logger)
idempotency_checker = IdempotencyChecker(repository)

# Initialize parsers
classifier = MessageClassifier()
profile_parser = ProfileParser()
accrual_parser = AccrualParser()
fishing_parser = FishingParser()
karma_parser = KarmaParser()
mafia_game_end_parser = MafiaGameEndParser()
mafia_profile_parser = MafiaProfileParser()
bunker_game_end_parser = BunkerGameEndParser()
bunker_profile_parser = BunkerProfileParser()

# Create processor
processor = MessageProcessor(
    classifier=classifier,
    profile_parser=profile_parser,
    accrual_parser=accrual_parser,
    fishing_parser=fishing_parser,
    karma_parser=karma_parser,
    mafia_game_end_parser=mafia_game_end_parser,
    mafia_profile_parser=mafia_profile_parser,
    bunker_game_end_parser=bunker_game_end_parser,
    bunker_profile_parser=bunker_profile_parser,
    balance_manager=balance_manager,
    idempotency_checker=idempotency_checker,
    logger=logger
)

# Process messages
messages = [
    ("ПРОФИЛЬ Alice\nОрбы: 100", datetime.now()),
    ("🃏 НОВАЯ КАРТА 🃏\nИгрок: Alice\nОчки: +50", datetime.now()),
]

for message, timestamp in messages:
    try:
        processor.process_message(message, timestamp)
        print(f"✓ Processed: {message[:30]}...")
    except Exception as e:
        print(f"✗ Error: {e}")
```

## Error Handling

### Error Types

1. **ParserError**: Raised when message parsing fails
   - Missing required fields
   - Malformed numeric values
   - Unknown message format

2. **ValueError**: Raised for configuration issues
   - Missing game coefficient
   - Invalid configuration format

3. **DatabaseError**: Raised for persistence failures
   - Connection failures
   - Constraint violations
   - Transaction failures

### Error Handling Strategy

- All errors are caught at the MessageProcessor level
- Errors are logged with full context
- Database transactions are rolled back on any error
- The system continues processing subsequent messages
- Error messages are descriptive and actionable

### Example Error Handling

```python
try:
    processor.process_message(message, timestamp)
except ParserError as e:
    logger.log_error(e, "parsing")
    # Handle parsing error (e.g., notify admin)
except ValueError as e:
    logger.log_error(e, "configuration")
    # Handle configuration error (e.g., check coefficients.json)
except Exception as e:
    logger.log_error(e, "processing")
    # Handle unexpected error
```

## Testing

### Test Organization

```
tests/
├── unit/                           # Specific examples and edge cases
│   ├── test_classifier.py          # All 10 message types
│   ├── test_parsers.py             # All 8 parsers
│   ├── test_balance_manager.py     # All balance operations
│   └── test_repository.py          # Database operations
├── property/                       # Universal properties (26 properties)
│   ├── test_classification_properties.py
│   ├── test_parsing_properties.py
│   ├── test_balance_properties.py
│   ├── test_coefficient_properties.py
│   ├── test_idempotency_properties.py
│   ├── test_transaction_atomicity_pbt.py
│   ├── test_database_persistence_pbt.py
│   └── test_error_properties.py
└── integration/                    # End-to-end scenarios
    ├── test_gdcards_profile_e2e.py
    ├── test_gdcards_accrual_e2e.py
    ├── test_shmalala_fishing_e2e.py
    ├── test_shmalala_karma_e2e.py
    ├── test_truemafia_e2e.py
    ├── test_bunkerrp_e2e.py
    └── test_advanced_scenarios_e2e.py
```

### Running Tests

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run property tests only
pytest tests/property/

# Run integration tests only
pytest tests/integration/

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_classifier.py

# Run with verbose output
pytest -v
```

### Property-Based Testing

The system uses Hypothesis for property-based testing with 26 correctness properties:

- **Properties 1-4**: Message classification
- **Properties 5-11**: Message parsing
- **Properties 12-16**: Balance operations
- **Properties 17-18**: Coefficient management
- **Property 19**: Idempotency
- **Property 20**: Transaction atomicity
- **Properties 21-23**: Data persistence
- **Properties 24-26**: Error handling

Each property test runs 100 iterations with randomly generated inputs to verify universal correctness.

### Coverage Goals

- ✓ 100% of correctness properties implemented
- ✓ All error paths covered by unit tests
- ✓ Integration tests for all 5 games
- ✓ >90% code coverage overall

## Troubleshooting

### Common Issues

1. **"No coefficient configured for game"**
   - Check `config/coefficients.json` exists
   - Verify game name matches exactly (case-sensitive)

2. **"Player name not found in message"**
   - Verify message format matches expected pattern
   - Check for encoding issues with special characters

3. **"Duplicate message detected"**
   - This is expected behavior (idempotency)
   - Message was already processed successfully

4. **Database locked errors**
   - Ensure only one process accesses the database
   - Check for uncommitted transactions

5. **Decimal precision issues**
   - All amounts stored as TEXT in SQLite
   - Use Decimal type throughout Python code

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Database Inspection

```python
from src.repository import SQLiteRepository

repo = SQLiteRepository("data/bot.db")
user = repo.get_or_create_user("Alice")
print(f"Bank balance: {user.bank_balance}")

bot_balance = repo.get_bot_balance(user.user_id, "GD Cards")
if bot_balance:
    print(f"Last balance: {bot_balance.last_balance}")
    print(f"Current bot balance: {bot_balance.current_bot_balance}")
```

## Performance Considerations

- **Database Indexing**: Indexes on user_name and (user_id, game) for fast lookups
- **Transaction Batching**: Process multiple messages in a single transaction when possible
- **Connection Pooling**: Reuse database connections
- **Logging Levels**: Use INFO in production, DEBUG only for troubleshooting

## Security Considerations

- **Input Validation**: All parsers validate input format
- **SQL Injection**: Use parameterized queries (handled by repository)
- **Decimal Precision**: Use Decimal type to prevent rounding errors
- **Transaction Safety**: Atomic operations prevent partial updates

## Future Enhancements

- Add support for new games without code changes
- Implement message queue for high-volume processing
- Add real-time monitoring dashboard
- Support for message replay and reprocessing
- Add backup and restore functionality
- Implement rate limiting per player

## Support

For issues, questions, or contributions:
- Check the test suite for usage examples
- Review the design document for architecture details
- Examine the requirements document for business rules
- Run tests with `-v` flag for detailed output

---

**Version**: 1.0.0  
**Last Updated**: 2025  
**License**: MIT
