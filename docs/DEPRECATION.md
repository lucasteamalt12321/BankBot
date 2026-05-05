# Deprecated Code Tracking

This document tracks all deprecated code in the project with planned removal dates.

## Deprecated Modules

### core.parsers (Entire Package)
**Status:** DEPRECATED  
**Removal Date:** 2025-06-01  
**Reason:** Duplicate parsing system. Use `src.parsers` instead.  
**Alternative:** `src.parsers`

**Migration Guide:**
- Replace `from core.parsers import SimpleShmalalaParser` with `from src.parsers import ProfileParser, FishingParser, etc.`
- Replace `parse_game_message()` with appropriate parser from `src.parsers`
- Replace `parse_fishing_message()` with `FishingParser().parse()`
- Replace `parse_card_message()` with `AccrualParser().parse()`

**Affected Files:**
- `core/database/simple_bank.py` - uses `parse_shmalala_message`, `ParsedFishing`
- `tests/unit/test_card_parser.py` - uses `parse_game_message`, `parse_card_message`
- `tests/unit/test_manual_parsing.py` - uses `parse_game_message`
- `tests/integration/test_bot_parser_integration.py` - uses `parse_game_message`
- Various test files in `tests/` directory

### core.parsers.simple_parser
**Status:** DEPRECATED  
**Removal Date:** 2025-06-01  
**Reason:** Duplicate parsing functionality. Use `src.parsers` instead.  
**Alternative:** `src.parsers`

**Classes/Functions:**
- `SimpleShmalalaParser` → Use `src.parsers.ProfileParser`, `src.parsers.FishingParser`
- `parse_game_message()` → Use specific parsers from `src.parsers`
- `parse_fishing_message()` → Use `src.parsers.FishingParser`
- `parse_card_message()` → Use `src.parsers.AccrualParser`
- `parse_shmalala_message()` → Use `src.parsers.FishingParser`
- `ParsedFishing` → Use `src.parsers.ParsedFishing`
- `ParsedCard` → Use `src.parsers.ParsedAccrual`
- `ParsedProfile` → Use `src.parsers.ParsedProfile`
- `ParsedOrbDrop` → Use `src.parsers.ParsedOrbDrop` (to be added)

## Deleted Modules (Already Removed)

### core.parsers.base
**Status:** DELETED  
**Date Removed:** 2024  
**Reason:** Never used in production code. Duplicate of `src.parsers` functionality.

### core.parsers.registry
**Status:** DELETED  
**Date Removed:** 2024  
**Reason:** Never used in production code. No parser registration needed.

### core.parsers.gdcards
**Status:** DELETED  
**Date Removed:** 2024  
**Reason:** Never used in production code. Use `src.parsers` instead.

**Deleted Classes:**
- `GDCardsProfileParser` → Use `src.parsers.ProfileParser`
- `GDCardsCardParser` → Use `src.parsers.AccrualParser`
- `GDCardsOrbDropParser` → Use `src.parsers.OrbDropParser` (to be added)

### core.parsers.shmalala
**Status:** DELETED  
**Date Removed:** 2024  
**Reason:** Never used in production code. Use `src.parsers` instead.

**Deleted Classes:**
- `ShmalalaFishingParser` → Use `src.parsers.FishingParser`
- `ShmalalaKarmaParser` → Use `src.parsers.KarmaParser`

### core.parsers.truemafia
**Status:** DELETED  
**Date Removed:** 2024  
**Reason:** Never used in production code. Use `src.parsers` instead.

**Deleted Classes:**
- `TrueMafiaProfileParser` → Use `src.parsers.MafiaProfileParser`
- `TrueMafiaGameEndParser` → Use `src.parsers.MafiaGameEndParser`

### core.parsers.bunkerrp
**Status:** DELETED  
**Date Removed:** 2024  
**Reason:** Never used in production code. Use `src.parsers` instead.

**Deleted Classes:**
- `BunkerRPProfileParser` → Use `src.parsers.BunkerProfileParser`
- `BunkerRPGameEndParser` → Use `src.parsers.BunkerGameEndParser`

## Migration Timeline

### Phase 1: Deprecation Warnings (Current)
- ✅ Add deprecation warnings to `core.parsers`
- ✅ Delete unused modules (base, registry, game-specific parsers)
- ✅ Document all deprecated code

### Phase 2: Code Migration (2024-2025)
- [ ] Update `core/database/simple_bank.py` to use `src.parsers`
- [ ] Update all test files to use `src.parsers`
- [ ] Add `OrbDropParser` to `src.parsers` if needed
- [ ] Verify all functionality works with `src.parsers`

### Phase 3: Removal (2025-06-01)
- [ ] Remove `core.parsers.simple_parser`
- [ ] Remove `core.parsers/__init__.py` or make it empty
- [ ] Remove all deprecation warnings
- [ ] Update documentation

## How to Check for Deprecated Code Usage

Run the following command to find all uses of deprecated code:

```bash
# Find imports from core.parsers
grep -r "from core.parsers import" --include="*.py" .

# Find imports from core.parsers.simple_parser
grep -r "from core.parsers.simple_parser import" --include="*.py" .

# Find uses of SimpleShmalalaParser
grep -r "SimpleShmalalaParser" --include="*.py" .
```

## Deprecation Policy

1. **Warning Period:** Minimum 6 months before removal
2. **Documentation:** All deprecated code must be documented here
3. **Alternatives:** Always provide clear alternatives
4. **Tests:** Deprecated code must still pass all tests
5. **CI/CD:** Add checks to warn about deprecated code usage

## Notes

- All deprecated code will show `DeprecationWarning` when imported or used
- Run tests with `python -W default` to see deprecation warnings
- In production, deprecation warnings are suppressed by default
- Use `warnings.filterwarnings('default', category=DeprecationWarning)` to enable them

---

**Last Updated:** 2024  
**Next Review:** 2025-03-01 (3 months before removal date)
