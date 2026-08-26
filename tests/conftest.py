"""
Pytest configuration for test suite.
Sets up test environment before any imports.
"""
import os
import sys

os.environ["ENV"] = "test"
os.environ.setdefault("BOT_TOKEN", "test_token_123456:ABC")
os.environ.setdefault("ADMIN_TELEGRAM_ID", "123456789")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Files to ignore during collection (incompatible with current architecture)
collect_ignore = []

# Additional files with known issues (test environment conflicts or architecture mismatch)
collect_ignore_glob = []
