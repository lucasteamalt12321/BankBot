"""Vercel serverless entrypoint for Telegram webhooks.

Vercel cannot keep a long-running Flask/PTB process alive.  This module exposes
one WSGI app that initializes the Telegram application lazily per warm function
instance and processes each webhook update synchronously.
"""

from __future__ import annotations

import asyncio
import hmac
import os
import sys
import threading
import traceback
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request
from telegram import Update

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

app = Flask(__name__)

_bot = None
_loop: asyncio.AbstractEventLoop | None = None
_init_lock = threading.Lock()
_initialized = False
_startup_error: str | None = None


def _get_webhook_secret() -> str:
    explicit_secret = os.environ.get("WEBHOOK_SECRET", "").strip()
    if explicit_secret:
        return explicit_secret

    from src.config import settings

    return hmac.new(
        settings.BOT_TOKEN.strip().encode(),
        b"bankbot-hf-webhook",
        "sha256",
    ).hexdigest()


def _run_coro(coro: Any, timeout: int = 25) -> Any:
    if _loop is None:
        raise RuntimeError("Telegram event loop is not initialized")
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result(timeout=timeout)


async def _initialize_bot() -> None:
    global _bot

    from bot.bot import TelegramBot
    from database.schema import ensure_schema_up_to_date
    from src.startup_validator import validate_startup

    ensure_schema_up_to_date()
    validate_startup()

    telegram_bot = TelegramBot()
    telegram_bot.initialize_runtime_systems(
        start_background_tasks=False,
        initialize_shop=False,
    )
    await telegram_bot.application.initialize()
    await telegram_bot.application.start()
    _bot = telegram_bot


def _ensure_initialized() -> None:
    global _initialized, _loop, _startup_error

    if _initialized:
        return

    with _init_lock:
        if _initialized:
            return

        try:
            _loop = asyncio.new_event_loop()
            thread = threading.Thread(target=_loop.run_forever, daemon=True)
            thread.start()
            _run_coro(_initialize_bot(), timeout=25)
            _startup_error = None
            _initialized = True
        except Exception as exc:
            _startup_error = str(exc)
            raise


@app.route("/")
def index():
    return jsonify({"service": "BankBot", "runtime": "vercel", "status": "ok"})


@app.route("/health")
def health():
    return jsonify(
        {
            "service": "BankBot",
            "runtime": "vercel-serverless",
            "initialized": _initialized,
            "startup_error": _startup_error,
        }
    )


@app.route("/telegram/webhook/<secret>", methods=["POST"])
def telegram_webhook(secret: str):
    expected_secret = _get_webhook_secret()
    if not hmac.compare_digest(secret, expected_secret):
        return jsonify({"error": "not_found"}), 404

    header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if header_secret and not hmac.compare_digest(header_secret, expected_secret):
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"ok": True})

    try:
        _ensure_initialized()
        if _bot is None or _bot.application.bot is None:
            return jsonify({"error": "bot_not_initialized"}), 503

        update = Update.de_json(payload, _bot.application.bot)
        _run_coro(_bot.application.process_update(update), timeout=25)
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify(
            {
                "error": "processing_failed",
                "details": str(exc),
                "type": type(exc).__name__,
                "traceback": traceback.format_exc()[-2000:],
            }
        ), 500


application = app
