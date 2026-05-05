# Integration Tests for Message Parsing System

This directory contains comprehensive end-to-end integration tests for the message parsing system, covering all 5 games and their message flows.

## Test Files

### Individual Game Flow Tests

1. **test_gdcards_profile_e2e.py** - GD Cards profile flow
   - First-time profile initialization
   - Subsequent profile updates (positive/negative/zero delta)
   - Coefficient application (2x)
   - Multiple players isolation

2. **test_gdcards_accrual_e2e.py** - GD Cards accrual flow
   - First-time accrual
   - Subsequent accruals accumulation
   - Coefficient application (2x)
   - Multiple players isolation
   - Decimal precision preservation

3. **test_shmalala_fishing_e2e.py** - Shmalala fishing flow
   - First-time fishing accrual
   - Subsequent fishing accruals
   - Coefficient application (1x)

4. **test_shmalala_karma_e2e.py** - Shmalala karma flow
   - First-time karma accrual (always +1)
   - Multiple karma accruals
   - Coefficient application (10x)

5. **test_truemafia_e2e.py** - True Mafia flows
   - Game end with multiple winners (10 money each)
   - First-time profile initialization
   - Profile updates with positive delta
   - Coefficient application (15x)

6. **test_bunkerrp_e2e.py** - BunkerRP flows
   - Game end with multiple winners (30 money each)
   - First-time profile initialization
   - Profile updates with positive delta
   - Coefficient application (20x)

### Advanced Scenario Tests

7. **test_advanced_scenarios_e2e.py** - Complex integration scenarios
   - Multiple games in sequence for same player
   - Duplicate message handling (idempotency)
   - Transaction rollback on error
   - Sequential message processing (SQLite limitation)

## Running Tests

### Run all integration tests:
```bash
python -m pytest tests/integration/test_gdcards_accrual_e2e.py \
                 tests/integration/test_shmalala_fishing_e2e.py \
                 tests/integration/test_shmalala_karma_e2e.py \
                 tests/integration/test_truemafia_e2e.py \
                 tests/integration/test_bunkerrp_e2e.py \
                 tests/integration/test_advanced_scenarios_e2e.py -v
```

### Run individual test files:
```bash
python tests/integration/test_gdcards_profile_e2e.py
python tests/integration/test_gdcards_accrual_e2e.py
python tests/integration/test_shmalala_fishing_e2e.py
python tests/integration/test_shmalala_karma_e2e.py
python tests/integration/test_truemafia_e2e.py
python tests/integration/test_bunkerrp_e2e.py
python tests/integration/test_advanced_scenarios_e2e.py
```

## Test Coverage

### Complete Flow Validation
Each test validates the complete pipeline:
1. **Classification** - Message type detection
2. **Parsing** - Structured data extraction
3. **Balance Processing** - Business logic application
4. **Database Updates** - Persistence verification

### Game-Specific Coefficients
- GD Cards: 2x
- Shmalala: 1x
- Shmalala Karma: 10x
- True Mafia: 15x
- Bunker RP: 20x

### Requirements Validated
- Requirements 1.1-1.8: Message classification
- Requirements 2.1-9.3: Parsing and balance processing
- Requirements 10.1-10.5: Data persistence
- Requirements 13.1-13.5: Game end processing
- Requirements 14.1-14.2: Coefficient management
- Requirements 15.1-15.4: Idempotency
- Requirements 16.1-16.3: Transaction atomicity

## Test Results

All 29 integration tests pass successfully:
- 6 tests for GD Cards profile flow
- 5 tests for GD Cards accrual flow
- 3 tests for Shmalala fishing flow
- 3 tests for Shmalala karma flow
- 4 tests for True Mafia flows
- 4 tests for BunkerRP flows
- 4 tests for advanced scenarios

## Notes

### SQLite Thread Safety
The concurrent processing test uses sequential processing due to SQLite's thread-safety limitations. In production, use a thread-safe database (PostgreSQL, MySQL) or implement a message queue for true concurrent processing.

### Test Isolation
Each test uses a temporary database that is cleaned up after the test completes, ensuring complete isolation between tests.

### Decimal Precision
All tests verify that Decimal precision is maintained throughout the system for accurate financial calculations.
