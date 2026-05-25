"""Minimal Vercel API for BankBot."""

from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/')
@app.route('/api')
@app.route('/api/index')
def index():
    return jsonify({
        "service": "BankBot",
        "status": "ok",
        "message": "Bot is running on Vercel"
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "platform": "vercel"
    })

@app.route('/telegram/webhook/<secret>', methods=['POST'])
def telegram_webhook(secret):
    """Receive Telegram webhook."""
    # TODO: Add bot logic here
    data = request.get_json()
    return jsonify({"ok": True, "received": True})

# Vercel handler
handler = app
