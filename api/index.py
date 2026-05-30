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


@app.route("/reading_trainer.html")
def reading_trainer():
    """Serve reading trainer HTML."""
    try:
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        public_dir = os.path.join(base_dir, "public")
        html_path = os.path.join(public_dir, "reading_trainer.html")
        
        # Read and return HTML content directly
        if os.path.exists(html_path):
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
        
        # Fallback to root directory
        html_path_root = os.path.join(base_dir, "reading_trainer.html")
        if os.path.exists(html_path_root):
            with open(html_path_root, 'r', encoding='utf-8') as f:
                html_content = f.read()
            return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
        
        return jsonify({"error": "reading_trainer.html not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
