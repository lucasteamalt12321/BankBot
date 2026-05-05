"""
Webhook support for Telegram bot.
Requires: pip install flask
"""

import os
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, Dispatcher

logger = logging.getLogger(__name__)

app = Flask(__name__)

_webhook_dispatcher: Dispatcher = None


def setup_webhook(app: Application, webhook_path: str, webhook_url: str):
    """
    Setup webhook mode for the bot.

    Args:
        app: Telegram Application instance
        webhook_path: URL path for webhook endpoint (e.g., '/webhook')
        webhook_url: Public URL for webhook (e.g., 'https://yourdomain.com')
    """
    global _webhook_dispatcher

    _webhook_dispatcher = app.dispatcher

    async def webhook_handler():
        """Handle incoming webhook requests."""
        try:
            if request.method == "POST":
                data = request.get_json()
                if data:
                    update = Update.de_json(data, app.bot)
                    await _webhook_dispatcher.process_update(update)
                return jsonify({"status": "ok"})
            return jsonify({"error": "Method not allowed"}), 405
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return jsonify({"error": str(e)}), 500

    app.add_url_rule(webhook_path, "webhook", webhook_handler, methods=["POST"])

    logger.info(f"Setting webhook URL to: {webhook_url}{webhook_path}")
    app.run(host="0.0.0.0", port=int(os.getenv("WEBHOOK_PORT", 8080)))


def run_webhook_mode():
    """Run bot in webhook mode. Requires proper SSL configuration."""
    from telegram import Update
    from telegram.ext import Application
    from src.config import settings

    app = Application.builder().token(settings.BOT_TOKEN).build()

    webhook_url = os.getenv("WEBHOOK_URL")
    webhook_path = os.getenv("WEBHOOK_PATH", "/webhook")

    if not webhook_url:
        raise ValueError(
            "WEBHOOK_URL environment variable is required for webhook mode"
        )

    setup_webhook(app, webhook_path, webhook_url)
