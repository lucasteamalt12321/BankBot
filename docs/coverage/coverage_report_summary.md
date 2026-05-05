# Coverage Report Summary

**Date:** 2026-02-21 19:59 +0300  
**Tool:** pytest-cov v7.0.0 with coverage.py v7.13.4

## Overall Coverage

**Total Coverage: 45%**

- **Total Statements:** 28,133
- **Missing (Not Covered):** 15,599
- **Excluded:** 0

## Test Execution Summary

- **Tests Collected:** 788 tests
- **Tests Passed:** 691
- **Tests Failed:** 65
- **Tests Skipped:** 32
- **Collection Errors:** 39 (import errors preventing test loading)
- **Warnings:** 1,213

## Key Findings

### 1. Coverage Below Target
The current coverage of **45%** is significantly below the project requirements:
- **Requirement 20:** Code coverage should be at least **80%**
- **Design Goal:** Coverage of critical paths should be at least **90%**
- **Gap:** 35 percentage points below minimum requirement

### 2. Import Errors Blocking Tests
39 test modules cannot be loaded due to import errors, primarily:
- `ImportError: cannot import name 'BotBalance' from 'src.models'`
- This affects integration tests, property-based tests, and unit tests
- These errors prevent accurate coverage measurement of affected modules

### 3. Test Failures
65 tests are currently failing, including:
- Integration tests for error handling
- Property-based tests for repository operations
- Unit tests for configuration management
- Parser property tests

### 4. Coverage by Module Type

Based on the partial output visible:

**Well-Covered Modules (>90%):**
- `tests/unit/test_accrual_parser.py` - 100%
- `tests/unit/test_base_repository.py` - 100%
- `tests/unit/test_bunker_game_end_parser.py` - 100%
- `tests/unit/test_bunker_profile_parser.py` - 100%
- `tests/unit/test_card_parser.py` - 99%
- `tests/unit/test_classifier.py` - 100%
- `tests/unit/test_error_handler_middleware.py` - 100%
- `tests/unit/test_settings.py` - 99%
- `tests/unit/test_background_task_manager.py` - 99%
- `tests/unit/test_admin_id_validation_comprehensive.py` - 99%

**Poorly Covered Modules (<10%):**
- `bot/bot.py` - 1% (1,706 of 1,730 statements missing)
- `src/balance_manager.py` - 1% (461 of 465 statements missing)
- `src/repository.py` - 2%
- `utils/admin/admin_system.py` - 5%
- Various integration test modules - 3-5%

**Moderately Covered Modules (50-80%):**
- Parser modules - 74-79%
- Property-based test modules - 71-84%
- Configuration management - 56%

## Critical Issues

### 1. Main Bot Module Uncovered
The main `bot/bot.py` file has only **1% coverage** with 1,706 uncovered statements. This is the core of the application and represents a significant risk.

### 2. Balance Manager Uncovered
The `src/balance_manager.py` has only **1% coverage**, which is critical since it handles financial transactions.

### 3. Repository Layer Uncovered
The repository layer has very low coverage (2-5%), which is concerning for data integrity.

### 4. Import Errors Masking True Coverage
The 39 import errors mean we cannot measure coverage for:
- 16 integration test modules
- 5 property-based test modules
- 18 unit test modules

## Recommendations

### Immediate Actions (Priority 1)
1. **Fix Import Errors:** Resolve the `BotBalance` import issue in `src/models/__init__.py`
2. **Re-run Coverage:** After fixing imports, re-run to get accurate coverage metrics
3. **Fix Failing Tests:** Address the 65 failing tests to ensure accurate coverage measurement

### Short-term Actions (Priority 2)
4. **Increase Bot Module Coverage:** Add integration tests for `bot/bot.py` (currently 1%)
5. **Increase Balance Manager Coverage:** Add tests for `src/balance_manager.py` (currently 1%)
6. **Increase Repository Coverage:** Add tests for repository layer (currently 2-5%)

### Medium-term Actions (Priority 3)
7. **Add Integration Tests:** Focus on E2E scenarios to cover critical paths
8. **Add Property-Based Tests:** Increase property-based testing for business logic
9. **Target 80% Minimum:** Systematically add tests to reach 80% coverage baseline
10. **Target 90% for Critical Paths:** Focus on achieving 90% coverage for:
    - Balance management
    - Transaction processing
    - User authentication
    - Payment processing

## HTML Report Location

Detailed HTML coverage report available at: `htmlcov/index.html`

Open this file in a browser to:
- View line-by-line coverage for each file
- Identify specific uncovered code sections
- Prioritize testing efforts

## Next Steps for Task 20.4

1. ✅ **Task 20.4.1 Complete:** Coverage report generated
2. **Task 20.4.2:** Identify uncovered areas (see "Poorly Covered Modules" above)
3. **Task 20.4.3:** Add tests to reach 90% coverage for critical paths
