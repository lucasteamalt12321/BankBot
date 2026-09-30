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
def _no_telegram_network(request, monkeypatch):
    """В тестовом окружении нет сети: log_error→Telegram завис бы навсегда.

    Патчим send_telegram_message на no-op, чтобы любые ошибочные пути
    (log_error/notify_admin) не блокировали прогон. Тесты, которые сами
    проверяют исходящие вызовы Telegram, помечаются маркером
    ``@pytest.mark.allow_telegram``: для них глушатся только служебные
    каналы log_error/notify_admin, а сам send_telegram_message остаётся
    нетронутым - тест мокает api.index.requests.post и проверяет payload.
    """
    try:
        import api.index as api
    except Exception:
        yield
        return
    if request.node.get_closest_marker("allow_telegram"):
        for _name in ("log_error", "notify_admin"):
            if hasattr(api, _name):
                monkeypatch.setattr(api, _name, lambda *a, **k: None)
        yield
        return
    monkeypatch.setattr(api, "send_telegram_message", lambda *a, **k: False)
    yield

# Files to ignore during collection (incompatible with current architecture)
collect_ignore = []

# Additional files with known issues (test environment conflicts or architecture mismatch)
collect_ignore_glob = []
