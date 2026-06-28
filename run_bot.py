#!/usr/bin/env python3
"""Hugging Face entrypoint for BankBot.

Production HF runs BankBot through a Telegram webhook. Polling stays available only
through ``bot.main`` / local development paths.
"""

from __future__ import annotations

import asyncio
import collections
import hmac
import json
import os
import sys
import threading
from typing import Any

from flask import Flask, Response, jsonify, request
from telegram import Update

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Микро-сервер для Hugging Face и мониторинга
app = Flask(__name__)

# Глобальный буфер для логов
log_buffer: collections.deque[str] = collections.deque(maxlen=100)
FEEDBACK_FILE = "data/feedback.jsonl"

telegram_bot = None
telegram_loop: asyncio.AbstractEventLoop | None = None
telegram_ready = threading.Event()
telegram_startup_error: str | None = None


class LogCapture:
    def write(self, data: str) -> None:
        if data.strip():
            log_buffer.append(data.strip())
        sys.__stdout__.write(data)

    def flush(self) -> None:
        sys.__stdout__.flush()


sys.stdout = LogCapture()
sys.stderr = LogCapture()


def _is_authorized_feedback_request() -> bool:
    """Validate feedback API token from Authorization header or query string."""
    expected_token = os.environ.get("FEEDBACK_READ_TOKEN") or os.environ.get("HF_TOKEN")
    if not expected_token:
        try:
            from src.config import settings

            expected_token = settings.BOT_TOKEN.strip()
        except Exception:
            expected_token = ""

    if not expected_token:
        return False

    auth_header = request.headers.get("Authorization", "")
    bearer_prefix = "Bearer "
    if auth_header.startswith(bearer_prefix):
        return hmac.compare_digest(auth_header[len(bearer_prefix) :], expected_token)

    return hmac.compare_digest(request.args.get("token", ""), expected_token)


def _get_webhook_secret() -> str:
    """Return configured webhook secret or derive a stable fallback from BOT_TOKEN."""
    explicit_secret = os.environ.get("WEBHOOK_SECRET", "").strip()
    if explicit_secret:
        return explicit_secret

    from src.config import settings

    return hmac.new(
        settings.BOT_TOKEN.strip().encode(),
        b"bankbot-hf-webhook",
        "sha256",
    ).hexdigest()


def _get_public_webhook_base_url() -> str:
    """Build public HF Space base URL for Telegram webhook registration."""
    explicit_url = os.environ.get("WEBHOOK_BASE_URL", "").strip().rstrip("/")
    if explicit_url:
        return explicit_url

    space_host = os.environ.get("SPACE_HOST", "").strip()
    if space_host:
        return f"https://{space_host}".rstrip("/")

    space_id = os.environ.get("SPACE_ID", "").strip()
    if space_id and "/" in space_id:
        owner, space = space_id.split("/", maxsplit=1)
        return f"https://{owner.lower()}-{space.lower()}.hf.space"

    return "https://lucasteam-bankbot.hf.space"


def _run_coro(coro: Any, timeout: int = 30) -> Any:
    """Run coroutine on the bot event loop from Flask's sync request thread."""
    if telegram_loop is None:
        raise RuntimeError("Telegram event loop is not initialized")
    future = asyncio.run_coroutine_threadsafe(coro, telegram_loop)
    return future.result(timeout=timeout)


def _start_telegram_webhook_runtime() -> None:
    """Start PTB Application on a dedicated asyncio loop for Flask webhooks."""
    global telegram_bot, telegram_loop, telegram_startup_error

    telegram_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(telegram_loop)

    async def startup() -> None:
        global telegram_bot

        from bot.bot import TelegramBot
        from database.schema import ensure_schema_up_to_date
        from src.startup_validator import validate_startup

        print("[START] Starting BankBot HF webhook runtime...")
        print(f"[DIAG] PROXY_URL={os.environ.get('PROXY_URL', 'not set')}")
        print(f"[DIAG] TELEGRAM_BASE_URL={os.environ.get('TELEGRAM_BASE_URL', 'not set')}")
        print(f"[DIAG] VPN_SUBSCRIPTION_URL={'set' if os.environ.get('VPN_SUBSCRIPTION_URL') else 'not set'}")
        # Check if proxy port is listening
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        proxy_host, proxy_port_str = "127.0.0.1", os.environ.get("PROXY_URL", "http://127.0.0.1:1080").split(":")[-1].rstrip("/")
        try:
            proxy_port = int(proxy_port_str)
            result = s.connect_ex((proxy_host, proxy_port))
            print(f"[DIAG] Proxy port {proxy_host}:{proxy_port} connect result: {'open' if result == 0 else f'closed ({result})'}")
        except Exception as e:
            print(f"[DIAG] Proxy check error: {e}")
        finally:
            s.close()

        ensure_schema_up_to_date()
        validate_startup()

        webhook_secret = _get_webhook_secret()
        webhook_url = f"{_get_public_webhook_base_url()}/telegram/webhook/{webhook_secret}"

        telegram_bot = TelegramBot()
        await telegram_bot.initialize_for_webhook(webhook_url, webhook_secret)
        print(f"[WEBHOOK] BankBot webhook runtime ready: {webhook_url}")

    try:
        telegram_loop.run_until_complete(startup())
        telegram_ready.set()
        print("[WEBHOOK] Startup complete, entering run_forever loop")
        telegram_loop.run_forever()
    except Exception as exc:
        import traceback
        telegram_startup_error = f"{exc}\n{traceback.format_exc()}"
        telegram_ready.set()
        print(f"[WEBHOOK] Startup failed: {exc}")
        print(f"[WEBHOOK] Startup traceback: {traceback.format_exc()}")
    finally:
        if telegram_bot is not None:
            try:
                telegram_loop.run_until_complete(telegram_bot.shutdown_for_webhook())
            except Exception as exc:
                print(f"[WEBHOOK] Shutdown failed: {exc}")
        telegram_loop.close()


def create_app() -> Flask:
    """Return the Flask app for tests and WSGI-compatible launchers."""
    return app


@app.route("/logs")
def get_logs() -> Response:
    """Endpoint to view recent logs."""
    return Response("<pre>" + "\n".join(log_buffer) + "</pre>", mimetype="text/html")


@app.route("/feedback")
def get_feedback():
    """Read recent feedback entries from DB storage for external diagnostics."""
    if not _is_authorized_feedback_request():
        return jsonify({"error": "unauthorized"}), 401

    try:
        limit = max(1, min(int(request.args.get("limit", 20)), 100))
    except ValueError:
        limit = 20

    try:
        from bot.commands.feedback_commands import _read_feedback_entries_db
        from database.connection import get_database_backend

        entries = _read_feedback_entries_db(limit)
        return jsonify(
            {
                "entries": entries,
                "count": len(entries),
                "storage": get_database_backend(),
            }
        )
    except Exception as e:
        print(f"[FEEDBACK] DB read failed, falling back to JSONL: {e}")

    if not os.path.exists(FEEDBACK_FILE):
        return jsonify({"entries": [], "count": 0, "path": FEEDBACK_FILE, "storage": "jsonl"})

    entries = []
    with open(FEEDBACK_FILE, encoding="utf-8") as file:
        lines = file.readlines()[-limit:]

    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return jsonify({"entries": entries, "count": len(entries), "path": FEEDBACK_FILE, "storage": "jsonl"})


@app.route("/")
def index() -> str:
    return "BankBot System is Active. Check <a href='/logs'>/logs</a> for status."


@app.route("/health")
def health_check():
    """Health check endpoint with DB and webhook runtime state."""
    if telegram_startup_error:
        return jsonify({"status": "unhealthy", "service": "BankBot", "error": telegram_startup_error}), 500

    try:
        from database.connection import get_database_backend
        from database.database import engine
        from sqlalchemy import text

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        webhook_info = {}
        if telegram_ready.is_set() and telegram_bot and telegram_bot.application and telegram_bot.application.bot:
            try:
                info = _run_coro(telegram_bot.application.bot.get_webhook_info(), timeout=10)
                webhook_info = {
                    "url": info.url,
                    "pending_updates": info.pending_update_count,
                    "last_error": info.last_error_message,
                }
            except Exception as exc:
                webhook_info = {"error": str(exc)}

        return jsonify(
            {
                "status": "healthy",
                "service": "BankBot",
                "telegram_runtime": "webhook",
                "webhook_configured": telegram_ready.is_set(),
                "database": get_database_backend(),
                "webhook_info": webhook_info,
            }
        )
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@app.route("/metrics")
def metrics() -> Response:
    """Prometheus-compatible metrics endpoint."""
    from database.database import Transaction, User, get_db

    import time

    db = next(get_db())
    try:
        total_users = db.query(User).count()
        today = time.time() - 86400
        today_transactions = db.query(Transaction).filter(Transaction.created_at >= today).count()

        metrics_text = f"""# HELP bot_users_total Total number of users
# TYPE bot_users_total gauge
bot_users_total {total_users}

# HELP bot_transactions_24h Transactions in last 24 hours
# TYPE bot_transactions_24h counter
bot_transactions_24h {today_transactions}
"""
        return Response(metrics_text, mimetype="text/plain")
    finally:
        db.close()


@app.route("/reading_trainer")
@app.route("/reading_trainer/")
def reading_trainer():
    """Serve reading trainer web app."""
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Тренажёр чтения</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; }
        h1 { text-align: center; margin-bottom: 30px; }
        .sentence { font-size: 20px; margin: 15px 0; font-weight: bold; }
        button { padding: 12px 24px; font-size: 16px; margin: 10px 5px; cursor: pointer; border: none; border-radius: 8px; }
        .btn-primary { background: #007AFF; color: white; }
        .btn-secondary { background: #8E8E93; color: white; }
        input { width: 100%; padding: 10px; font-size: 16px; margin: 10px 0; border: 2px solid #ddd; border-radius: 8px; }
        .question { margin: 20px 0; }
        .result { padding: 10px; margin: 10px 0; border-radius: 8px; font-weight: bold; }
        .correct { background: #D1F2DD; color: #248A3D; }
        .incorrect { background: #FFD7D9; color: #D70015; }
        #questions-screen { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧸 Тренажёр чтения и понимания</h1>
        
        <div id="reading-screen">
            <div id="sentences"></div>
            <button class="btn-primary" onclick="goToQuestions()">Дальше →</button>
            <button class="btn-secondary" onclick="loadNewText()">Новый текст</button>
        </div>

        <div id="questions-screen">
            <div id="questions-container"></div>
            <button class="btn-primary" onclick="checkAnswers()">Проверить</button>
            <button class="btn-secondary" onclick="goBackToReading()">← Назад</button>
        </div>
    </div>

    <script>
        let currentData = null;

        async function loadNewText() {
            try {
                const response = await fetch('/reading_generate', { method: 'POST' });
                currentData = await response.json();
                displayReading();
            } catch (error) {
                alert('Ошибка загрузки');
            }
        }

        function displayReading() {
            document.getElementById('sentences').innerHTML = currentData.sentences
                .map(s => '<div class="sentence">' + s + '</div>').join('');
            document.getElementById('reading-screen').style.display = 'block';
            document.getElementById('questions-screen').style.display = 'none';
        }

        function goToQuestions() {
            document.getElementById('questions-container').innerHTML = currentData.questions.map((q, i) => 
                '<div class="question"><div>' + (i+1) + '. ' + q.question + '</div>' +
                '<input type="text" id="answer-' + i + '"><div class="result" id="result-' + i + '" style="display:none;"></div></div>'
            ).join('');
            document.getElementById('reading-screen').style.display = 'none';
            document.getElementById('questions-screen').style.display = 'block';
        }

        function goBackToReading() {
            document.getElementById('reading-screen').style.display = 'block';
            document.getElementById('questions-screen').style.display = 'none';
        }

        function checkAnswers() {
            currentData.questions.forEach((q, i) => {
                const input = document.getElementById('answer-' + i);
                const result = document.getElementById('result-' + i);
                const userAnswer = input.value.trim().toLowerCase();
                const correctAnswer = q.answer.toLowerCase();

                if (userAnswer === correctAnswer) {
                    result.textContent = '✓ Правильно!';
                    result.className = 'result correct';
                } else {
                    result.textContent = '✗ Правильный ответ: ' + q.answer;
                    result.className = 'result incorrect';
                }
                result.style.display = 'block';
            });
        }

        loadNewText();
    </script>
</body>
</html>"""
    return Response(html, mimetype='text/html')


@app.route("/reading_generate", methods=["POST"])
def reading_generate():
    """Generate reading comprehension content for Mom Module using HF API."""
    import json
    import random
    import os
    import httpx
    
    fallback_sets = [
        {
            "sentences": [
                "Кот спит.",
                "Мама мыла раму.",
                "Солнце светит ярко.",
                "Дети играют в парке.",
                "Папа читает книгу.",
                "Бабушка печёт пирог."
            ],
            "questions": [
                {"question": "Кто спит?", "answer": "кот"},
                {"question": "Что делала мама?", "answer": "мыла раму"},
                {"question": "Где играют дети?", "answer": "в парке"}
            ]
        },
        {
            "sentences": [
                "Собака лает.",
                "Птица поёт песню.",
                "Дождь идёт сильно.",
                "Цветы растут в саду.",
                "Машина едет быстро.",
                "Река течёт медленно."
            ],
            "questions": [
                {"question": "Кто лает?", "answer": "собака"},
                {"question": "Что делает птица?", "answer": "поёт песню"},
                {"question": "Где растут цветы?", "answer": "в саду"}
            ]
        },
        {
            "sentences": [
                "Мальчик рисует дом.",
                "Девочка поёт песню.",
                "Учитель пишет мелом.",
                "Ученик читает текст.",
                "Повар готовит суп.",
                "Врач лечит людей."
            ],
            "questions": [
                {"question": "Что рисует мальчик?", "answer": "дом"},
                {"question": "Кто поёт песню?", "answer": "девочка"},
                {"question": "Что готовит повар?", "answer": "суп"}
            ]
        }
    ]
    
    # Try HF API first
    hf_token = os.getenv("HF_INFERENCE_TOKEN") or os.getenv("HF_TOKEN")
    
    if hf_token:
        try:
            # Use text generation model to create simple sentences
            prompt = """Создай 6 простых предложений для детей 6-7 лет (3-4 слова каждое) и 3 вопроса по содержанию.
Формат JSON:
{
  "sentences": ["Кот спит.", "Мама читает.", ...],
  "questions": [
    {"question": "Кто спит?", "answer": "кот"},
    ...
  ]
}"""
            
            url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
            headers = {"Authorization": f"Bearer {hf_token}"}
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 500,
                    "temperature": 0.8,
                    "return_full_text": False,
                }
            }
            
            response = httpx.post(url, headers=headers, json=payload, timeout=15.0)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    generated_text = data[0].get("generated_text", "")
                    
                    # Try to parse JSON from response
                    try:
                        # Find JSON in response
                        start = generated_text.find("{")
                        end = generated_text.rfind("}") + 1
                        if start >= 0 and end > start:
                            json_str = generated_text[start:end]
                            result = json.loads(json_str)
                            
                            # Validate structure
                            if "sentences" in result and "questions" in result:
                                if len(result["sentences"]) >= 6 and len(result["questions"]) >= 2:
                                    return jsonify(result)
                    except (json.JSONDecodeError, ValueError):
                        pass
        except Exception as e:
            print(f"[HF API] Error: {e}")
    
    # Fallback to predefined sets
    result = random.choice(fallback_sets)
    return jsonify(result)


@app.route("/telegram/webhook/<secret>", methods=["POST"])
def telegram_webhook(secret: str):
    """Receive Telegram updates and pass them into PTB without polling."""
    expected_secret = _get_webhook_secret()
    if not hmac.compare_digest(secret, expected_secret):
        print("[WEBHOOK] Secret validation failed")
        return jsonify({"error": "not_found"}), 404

    header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(header_secret, expected_secret):
        print("[WEBHOOK] Header secret validation failed")
        return jsonify({"error": "unauthorized"}), 401

    if telegram_startup_error:
        return jsonify({"error": "bot_not_ready"}), 503

    if not telegram_ready.wait(timeout=10) or telegram_bot is None:
        return jsonify({"error": "bot_not_ready"}), 503

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"ok": True})

    # Extract diagnostic fields before passing to PTB
    update_id = payload.get("update_id", "unknown")
    message = payload.get("message", {})
    chat = message.get("chat", {})
    user = message.get("from", {})
    chat_id = chat.get("id", "unknown")
    chat_type = chat.get("type", "unknown")
    user_id = user.get("id", "unknown")
    text_preview = message.get("text", "")[:50] if message else ""

    print(
        f"[WEBHOOK] Update received: id={update_id} "
        f"chat={chat_id}({chat_type}) user={user_id} text={text_preview!r}"
    )

    try:
        if telegram_bot.application.bot is None:
            print(f"[WEBHOOK] ERROR: application.bot is None, id={update_id}")
            return jsonify({"error": "bot_not_initialized"}), 500

        update = Update.de_json(payload, telegram_bot.application.bot)
        _run_coro(telegram_bot.application.process_update(update), timeout=25)
        print(f"[WEBHOOK] Update processed successfully: id={update_id}")
        return jsonify({"ok": True})
    except Exception as exc:
        import traceback
        error_details = traceback.format_exc()
        print(f"[WEBHOOK] Update processing FAILED: id={update_id} error={exc}")
        print(f"[WEBHOOK] Traceback: {error_details}")
        return jsonify({"error": "processing_failed", "details": str(exc)}), 500


# ===== Family Budget Module Routes =====

from bot.web.family_budget import (
    api_balance,
    api_debt_pay,
    api_debts_list,
    api_family_create,
    api_family_join,
    api_family_status,
    api_transaction_create,
    api_transaction_delete,
    api_transactions_list,
    family_budget_page,
)

app.route("/family_budget")(family_budget_page)

app.route("/api/budget/family/status")(api_family_status)
app.route("/api/budget/family/create", methods=["POST"])(api_family_create)
app.route("/api/budget/family/join", methods=["POST"])(api_family_join)

app.route("/api/budget/transactions")(api_transactions_list)
app.route("/api/budget/transactions", methods=["POST"])(api_transaction_create)
app.route("/api/budget/transactions/<int:transaction_id>", methods=["DELETE"])(api_transaction_delete)

app.route("/api/budget/debts")(api_debts_list)
app.route("/api/budget/debts/pay", methods=["POST"])(api_debt_pay)

app.route("/api/budget/balance")(api_balance)


def main() -> None:
    """Start HF Flask server and BankBot webhook runtime."""
    threading.Thread(target=_start_telegram_webhook_runtime, daemon=True).start()

    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
