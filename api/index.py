"""Minimal Vercel webhook handler for Telegram bot."""

from __future__ import annotations

import hmac
import os
from flask import Flask, jsonify, request

app = Flask(__name__)

# Webhook secret
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "2f0cada15d8c40d3331d895340329c328494cba48aef25ee8c1461a7fc81d266")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")


@app.route("/")
def index():
    return jsonify({"service": "BankBot", "status": "ok", "platform": "vercel"})


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "platform": "vercel"})


@app.route("/telegram/webhook/<secret>", methods=["POST"])
def telegram_webhook(secret: str):
    """Receive Telegram webhook and forward to processing."""
    
    # Verify secret
    if not hmac.compare_digest(secret, WEBHOOK_SECRET):
        return jsonify({"error": "invalid_secret"}), 404
    
    # Get update
    update = request.get_json()
    if not update:
        return jsonify({"ok": True})
    
    # Process /reading_trainer command
    try:
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        
        if text == "/reading_trainer" and chat_id:
            # Send response with inline button
            import requests
            
            response_text = (
                "🧸 Тренажёр чтения и понимания\n\n"
                "Приложение для тренировки чтения простых текстов.\n\n"
                "📖 Что внутри:\n"
                "• 6 простых предложений (3-4 слова)\n"
                "• 2-3 вопроса по содержанию\n"
                "• Проверка ответов\n"
                "• Возможность вернуться к чтению\n"
                "• Регулировка размера шрифта\n\n"
                "Нажмите кнопку ниже, чтобы открыть в браузере:"
            )
            
            keyboard = {
                "inline_keyboard": [[
                    {
                        "text": "🧸 Открыть тренажёр",
                        "url": "https://bank-bot-ruby.vercel.app/reading_trainer.html"
                    }
                ]]
            }
            
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": response_text,
                    "reply_markup": keyboard
                },
                timeout=5
            )
    except Exception as e:
        print(f"Error processing update: {e}")
    
    return jsonify({"ok": True})


# Vercel handler
handler = app
application = app
