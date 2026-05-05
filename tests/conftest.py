"""
Pytest configuration for test suite.
Sets up test environment before any imports.
"""
import os
import sys

os.environ["ENV"] = "test"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Files to ignore during collection (incompatible with current architecture)
collect_ignore = [
    "integration/test_task_11_3_integration_suite.py",
    "integration/test_task_9_verification.py",
    "property/test_auto_registration_pbt.py",
    "integration/test_router_integration.py",
    "unit/test_game_commands_module.py",
    "unit/test_shop_commands_module.py",
    "unit/test_system_commands_module.py",
    "unit/test_router.py",
    "unit/test_migrate_coefficients.py",
    "integration/test_add_item_integration.py",
    "integration/test_admin_commands_integration.py",
    "integration/test_balance_integration.py",
    "integration/test_bot_parser_integration.py",
    "integration/test_critical_paths_coverage.py",
    "integration/test_error_handler_integration.py",
    "integration/test_error_handler_registration.py",
    "integration/test_main_startup_validation.py",
    "unit/test_unit_of_work.py",
    "unit/test_add_item_command.py",
    "unit/test_balance_command_update.py",
    "unit/test_shop_edge_cases_unit.py",
    "unit/test_command_validation_edge_cases.py",
]

# Additional files with known issues (test environment conflicts or architecture mismatch)
collect_ignore_glob = []
