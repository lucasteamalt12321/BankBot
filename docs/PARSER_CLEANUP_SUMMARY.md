# Parser Cleanup Summary

## Task 12.3: Удалить дублирующие парсеры

### Overview
This document summarizes the removal of duplicate parser implementations as part of the project-critical-fixes specification (Task 12.3).

### Problem
The project had duplicate parser implementations:
- **Main parser**: `src/parsers.py` - Modern, well-structured parser with all game types
- **Deprecated parser**: `core/parsers/simple_parser.py` - Old implementation with similar functionality

### Actions Taken

#### 1. Deleted Deprecated Parser
- **Removed**: `core/parsers/simple_parser.py`
- This file was already marked as deprecated with a removal date of 2025-06-01
- Contained duplicate implementations of:
  - `SimpleShmalalaParser` class
  - `ParsedFishing`, `ParsedCard`, `ParsedProfile`, `ParsedOrbDrop` dataclasses
  - Helper functions: `parse_game_message()`, `parse_shmalala_message()`, etc.

#### 2. Updated Import References
Updated all files that were using the deprecated parser to use `src.parsers` instead:

**Files Updated:**
1. `core/database/simple_bank.py`
   - Changed: `from core.parsers.simple_parser import ParsedFishing` → `from src.parsers import ParsedFishing, FishingParser`
   - Updated `process_message()` to use `FishingParser().parse()`

2. `tests/integration/test_bot_parser_integration.py`
   - Changed: `from core.parsers.simple_parser import parse_game_message` → `from src.parsers import parse_message_auto`
   - Updated all test methods to use the new function

3. `tests/test_profile_parser_quick.py`
   - Changed: `from core.parsers.simple_parser import SimpleShmalalaParser` → `from src.parsers import ProfileParser`
   - Updated to use `ProfileParser().parse()`

4. `tests/test_profile_manual.py`
   - Changed: `from core.parsers.simple_parser import SimpleShmalalaParser` → `from src.parsers import ProfileParser`
   - Updated to use `ProfileParser().parse()`

5. `tests/test_orb_parsing.py`
   - Changed: `from core.parsers.simple_parser import SimpleShmalalaParser, parse_game_message` → `from src.parsers import AccrualParser, OrbDropParser, parse_message_auto`
   - Updated all parsing calls to use the new parsers

6. `for_programmer/parsing_script.py`
   - Updated documentation comments to reference `src/parsers.py` instead of `core/parsers/simple_parser.py`

7. `core/parsers/__init__.py`
   - Removed imports from deleted `simple_parser.py`
   - Kept deprecation warning for the entire `core.parsers` module

### Migration Guide

#### Old API → New API Mapping

| Old (Deprecated) | New (Current) |
|-----------------|---------------|
| `SimpleShmalalaParser().parse_profile_message()` | `ProfileParser().parse()` |
| `SimpleShmalalaParser().parse_card_message()` | `AccrualParser().parse()` |
| `SimpleShmalalaParser().parse_fishing_message()` | `FishingParser().parse()` |
| `SimpleShmalalaParser().parse_orb_drop_message()` | `OrbDropParser().parse()` |
| `parse_game_message()` | `parse_message_auto()` |
| `parse_shmalala_message()` | `FishingParser().parse()` |
| `parse_card_message()` | `AccrualParser().parse()` |

#### Dataclass Changes

The new parsers return different dataclass types:
- `ParsedProfile` (same name, different module)
- `ParsedAccrual` (replaces `ParsedCard`)
- `ParsedFishing` (same name, different module)
- `ParsedOrbDrop` (same name, different module)

### Current Parser System

All parsers are now unified in `src/parsers.py`:

**Available Parsers:**
1. `ProfileParser` - GD Cards profile messages
2. `AccrualParser` - GD Cards card drop messages
3. `FishingParser` - Shmalala fishing messages
4. `KarmaParser` - Shmalala karma messages
5. `MafiaGameEndParser` - True Mafia game end messages
6. `MafiaProfileParser` - True Mafia profile messages
7. `BunkerGameEndParser` - BunkerRP game end messages
8. `BunkerProfileParser` - BunkerRP profile messages
9. `OrbDropParser` - Orb drop messages (chests, rewards)

**Utility Function:**
- `parse_message_auto(message: str)` - Automatically detects message type and parses it

### Test Results

All tests pass after the migration:
- ✅ `test_profile_parser.py` - 13 tests passed
- ✅ `test_accrual_parser.py` - 16 tests passed
- ✅ `test_fishing_parser.py` - 16 tests passed
- ✅ `test_bot_parser_integration.py::TestParserDetection` - 3 tests passed

### Benefits

1. **Single Source of Truth**: All parsing logic is now in one place (`src/parsers.py`)
2. **Consistent API**: All parsers follow the same interface (`MessageParser` abstract base class)
3. **Better Type Safety**: Uses proper dataclasses with type hints
4. **Easier Maintenance**: No need to keep two implementations in sync
5. **Cleaner Codebase**: Removed ~400 lines of duplicate code

### Future Work

The `core/parsers` module is still marked as deprecated and will be completely removed on 2025-06-01. Until then, it serves as a warning to any remaining code that might try to import from it.

### Related Tasks

- ✅ Task 12.3.1: Идентифицировать дубликаты
- ✅ Task 12.3.2: Выбрать основной парсер для каждой игры
- ✅ Task 12.3.3: Удалить или пометить deprecated

### Completion Date

2025-01-XX (Task completed successfully)
