# Examples Directory

This directory contains example code demonstrating how to use various systems in the bot.

## Available Examples

### 1. `main.py` - Message Parsing System (Comprehensive)
**NEW** - Comprehensive demonstration of the complete message parsing system for all 5 games.

Demonstrates:
- Complete system initialization with all components
- Processing messages from all 5 games:
  - GD Cards (profile tracking + accruals, coefficient 2)
  - Shmalala Fishing (accruals, coefficient 1)
  - Shmalala Karma (accruals always +1, coefficient 10)
  - True Mafia (profile tracking + game winners get 10 money, coefficient 15)
  - BunkerRP (profile tracking + game winners get 30 money, coefficient 20)
- Profile tracking with delta calculation
- Accrual processing with coefficient application
- Game winner rewards
- Error handling and recovery
- Idempotency protection against duplicates
- Balance queries across multiple games

**Usage:**
```bash
python examples/main.py
```

**Output:**
- Creates `example.db` with sample data
- Shows detailed processing logs for each message type
- Displays balance updates after each operation
- Demonstrates error handling with malformed messages
- Shows idempotency protection in action

**Components Demonstrated:**
- `SQLiteRepository` - Database operations
- `CoefficientProvider` - Game coefficient management
- `AuditLogger` - Operation logging
- `BalanceManager` - Business logic for balance updates
- All 8 parsers (ProfileParser, AccrualParser, FishingParser, KarmaParser, MafiaGameEndParser, MafiaProfileParser, BunkerGameEndParser, BunkerProfileParser)
- `MessageClassifier` - Message type detection
- `IdempotencyChecker` - Duplicate prevention
- `MessageProcessor` - Main orchestrator

### 2. `test_parsers.py`
Quick test script for all message parsers showing classification and parsing for each game.

**Usage:**
```bash
python examples/test_parsers.py
```

### 3. `admin_notification_example.py`
Demonstrates the Admin Notification System functionality:
- How admin notifications work when users purchase admin items
- Admin user ID management
- Purchase confirmation messages
- Message formatting

**Usage:**
```bash
python examples/admin_notification_example.py
```

### 4. `broadcast_system_usage.py`
Shows how to integrate BroadcastSystem with bot commands:
- Admin broadcast command implementation
- Mention-all broadcast after purchase
- Admin notification sending
- Optimal configuration settings

**Key Features:**
- `/broadcast` command for admins
- Batch processing with rate limiting
- Error handling and reporting
- Integration with shop system

## Removed Examples

The following examples were removed as they used outdated APIs:

- `admin_integration_example.py` - Used old admin middleware and imports
- `parser_integration_example.py` - Referenced non-existent `simple_parser` module

## Notes

All examples have been updated to use:
- Centralized database connection from `database.connection`
- Current API and import paths
- Best practices for error handling

## Creating New Examples

When creating new examples:
1. Use centralized imports (`database.connection`, etc.)
2. Include clear docstrings explaining the purpose
3. Add error handling and logging
4. Provide usage instructions in comments
5. Update this README with the new example
