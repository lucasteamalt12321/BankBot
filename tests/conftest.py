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

import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Clear in-memory rate-limit counters between tests.

    The counters live in module-level dicts on ``api.index`` and are shared by
    every test in a session, so without this a handful of register/login calls
    in one test makes the next unrelated test fail with 429.
    """
    import api.index as api

    for name in ("_AI_RATE_LIMITS", "_LOGIN_ATTEMPTS"):
        store = getattr(api, name, None)
        if isinstance(store, dict):
            store.clear()
    yield
    for name in ("_AI_RATE_LIMITS", "_LOGIN_ATTEMPTS"):
        store = getattr(api, name, None)
        if isinstance(store, dict):
            store.clear()


@pytest.fixture(autouse=True)
def _no_telegram_network(monkeypatch):
    """В тестовом окружении нет сети: log_error→Telegram завис бы навсегда.

    Патчим send_telegram_message на no-op, чтобы любые ошибочные пути
    (log_error/notify_admin) не блокировали прогон. Явные Telegram-тесты
    должны мокать сами.
    """
    try:
        import api.index as api
        monkeypatch.setattr(api, "send_telegram_message", lambda *a, **k: False)
    except Exception:
        pass
    yield

# Files to ignore during collection (incompatible with current architecture)
collect_ignore = []

# Additional files with known issues (test environment conflicts or architecture mismatch)
collect_ignore_glob = []
