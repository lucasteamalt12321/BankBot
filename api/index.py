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


@app.route("/reading_trainer")
@app.route("/reading_trainer/")
def reading_trainer():
    """Serve reading trainer web app."""
    from flask import Response
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


@app.route("/reading_trainer")
@app.route("/reading_trainer/")
def reading_trainer_index():
    """Serve reading trainer web app."""
    try:
        from bot.web.reading_trainer import HTML_CONTENT
        from flask import Response
        return Response(HTML_CONTENT, mimetype='text/html')
    except ImportError as e:
        return jsonify({"error": "import_failed", "details": str(e), "type": "ImportError"}), 500
    except Exception as e:
        return jsonify({"error": "failed_to_load", "details": str(e), "type": type(e).__name__}), 500


@app.route("/reading_trainer/<path:filename>")
def reading_trainer_static(filename):
    """Serve reading trainer static files."""
    # All content is embedded in HTML, no separate files needed
    return jsonify({"error": "not_found", "filename": filename}), 404


@app.route("/debug/routes")
def debug_routes():
    """Debug endpoint to list all routes."""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            "endpoint": rule.endpoint,
            "methods": list(rule.methods),
            "path": str(rule)
        })
    return jsonify({"routes": routes})


@app.route("/reading_generate", methods=["POST"])
def reading_generate():
    """Generate reading comprehension content for Mom Module using HF API."""
    import json
    import random
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


# Vercel expects 'app' or 'handler'
application = app
handler = app
