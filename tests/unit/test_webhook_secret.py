"""BUG-07: единый webhook-секрет и отсутствие хардкода admin-ID.

Секрет вычисляется одинаково в `src/webhook_secret.py`, `run_bot.py`,
`api/index.py` и `.github/workflows/hf-watchdog.yml`; при отсутствии env он
выводится из `BOT_TOKEN`, а не подменяется литералом.
"""

import hashlib
import hmac

import api.index as api
from src.webhook_secret import derive_webhook_secret, resolve_webhook_secret


def test_derive_matches_legacy_algorithm():
    token = "123456:ABC-DEF"
    expected = hmac.new(token.encode(), b"bankbot-hf-webhook", hashlib.sha256).hexdigest()
    assert derive_webhook_secret(token) == expected


def test_resolve_prefers_explicit_secret():
    assert resolve_webhook_secret("tok", "explicit-secret") == "explicit-secret"


def test_resolve_falls_back_to_derived():
    assert resolve_webhook_secret("tok") == derive_webhook_secret("tok")


def test_resolve_empty_without_token_or_env():
    assert resolve_webhook_secret("", "") == ""


def test_api_index_secret_is_derived_not_literal():
    """Без env WEBHOOK_SECRET больше не превращается в «fallback_not_configured»."""
    assert api.WEBHOOK_SECRET != "fallback_not_configured"
    if not api._raw_webhook_secret:
        assert api.WEBHOOK_SECRET == derive_webhook_secret(api.BOT_TOKEN)


def test_api_index_admin_id_from_env():
    """ID администратора не захардкожен — берётся из окружения."""
    assert api.ADMIN_TELEGRAM_ID == 123456789


def test_redact_webhook_url_hides_secret():
    url = "https://bank-bot-ruby.vercel.app/telegram/webhook/super-secret"
    redacted = api._redact_webhook_url(url)
    assert "super-secret" not in redacted
    assert redacted.endswith("/telegram/webhook/***")
    assert api._redact_webhook_url(None) is None
