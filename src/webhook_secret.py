"""Единый источник webhook-секрета для бота, Vercel-бэкенда и CI-watchdog.

Bug BUG-07: секрет вычислялся в трёх местах по-разному — `run_bot.py` и
`.github/workflows/hf-watchdog.yml` выводили HMAC от `BOT_TOKEN`, а
`api/index.py` использовал литерал ``"fallback_not_configured"``. При
отсутствии переменной ``WEBHOOK_SECRET`` URL вебхука содержал один секрет, а
проверка в приложении ожидала другой, поэтому **все** апдейты Telegram
отбраковывались (403).

Этот модуль — единственная точка правды. Алгоритм продублирован агентом
watchdog (`.github/workflows/hf-watchdog.yml`); при изменении соли обновить оба
места.
"""

from __future__ import annotations

import hashlib
import hmac

# Соль фолбэка. Менять нельзя без синхронного обновления hf-watchdog.yml.
_FALLBACK_MESSAGE = b"bankbot-hf-webhook"


def derive_webhook_secret(bot_token: str) -> str:
    """Стабильный webhook-секрет, производный от ``BOT_TOKEN``.

    Совпадает с алгоритмом в `run_bot.py` и `hf-watchdog.yml`.
    """
    token = (bot_token or "").strip()
    if not token:
        return ""
    return hmac.new(token.encode(), _FALLBACK_MESSAGE, hashlib.sha256).hexdigest()


def resolve_webhook_secret(bot_token: str, explicit: str | None = None) -> str:
    """Явный ``WEBHOOK_SECRET``, иначе производный от ``BOT_TOKEN``; иначе ``""``."""
    explicit_secret = (explicit or "").strip()
    if explicit_secret:
        return explicit_secret
    return derive_webhook_secret(bot_token)
