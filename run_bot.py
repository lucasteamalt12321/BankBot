#!/usr/bin/env python3
"""Точка входа для запуска ботов проекта BankBot (Hugging Face deployment).

Использование:
    python run_bot.py           # запустить BankBot (по умолчанию)
    python run_bot.py bank      # запустить BankBot
    python run_bot.py bridge    # запустить BridgeBot
    python run_bot.py vk        # запустить VK Bot
"""

import sys
import os
import threading
from flask import Flask, jsonify, Response

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Микро-сервер для Hugging Face и мониторинга
app = Flask(__name__)

# Глобальный буфер для логов
import collections
log_buffer = collections.deque(maxlen=100)

class LogCapture:
    def write(self, data):
        if data.strip():
            log_buffer.append(data.strip())
        sys.__stdout__.write(data)
    def flush(self):
        sys.__stdout__.flush()

sys.stdout = LogCapture()
sys.stderr = LogCapture()

@app.route('/logs')
def get_logs():
    """Endpoint to view recent logs."""
    return Response("<pre>" + "\n".join(log_buffer) + "</pre>", mimetype="text/html")

@app.route('/')
def index():
    return "BankBot System is Active. Check <a href='/logs'>/logs</a> for status."

@app.route('/health')
def health_check():
    """Health check endpoint with DB check."""
    try:
        from database.database import get_db
        db = next(get_db())
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
        return jsonify({"status": "healthy", "service": "BankBot"})
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route("/metrics")
def metrics():
    """Prometheus-compatible metrics endpoint."""
    from database.database import get_db, User, Transaction
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

def run_health_server():
    # Порт 7860 - стандарт для Hugging Face Spaces
    port = int(os.environ.get("PORT", 7860))
    app.run(host='0.0.0.0', port=port)

def check_telegram_connectivity():
    """Быстрая диагностика с минимальными таймаутами для облачной среды"""
    import urllib.request
    import json
    import os
    import time
    
    print(f"[DIAG] Current System Time: {time.ctime()}")
    print(f"[DIAG] Proxy Env: HTTP={os.environ.get('http_proxy')}, HTTPS={os.environ.get('https_proxy')}")
    print(f"[DIAG] Starting quick connectivity check...")
    
    # Проверка общего интернета
    try:
        print("[DIAG] Testing general internet (google.com)...")
        with urllib.request.urlopen("https://www.google.com", timeout=10) as resp:
            print(f"[DIAG] Google status: {resp.getcode()}")
    except Exception as e:
        print(f"[DIAG] General internet check failed: {e}")
    
    try:
        from src.config import settings
        token = settings.BOT_TOKEN
        if not token:
            print("[DIAG] ERROR: BOT_TOKEN is empty!")
            return
        
        # Очищаем токен от возможных пробелов
        token = token.strip()
        print(f"[DIAG] Token loaded (and stripped): {token[:10]}...")
        
        # Проверка Telegram API Proxy по IP (api.telegram-proxy.com)
        try:
            proxy_ip = "104.21.75.145" # Cloudflare edge for api.telegram-proxy.com
            proxy_url = f"https://{proxy_ip}/bot{token}/getMe"
            print(f"[DIAG] Testing Cloudflare Proxy IP ({proxy_ip}) with token...")
            
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            with urllib.request.urlopen(proxy_url, timeout=10, context=ctx) as resp:
                print(f"[DIAG] Cloudflare Proxy status: {resp.getcode()}")
                data = json.loads(resp.read().decode())
                print(f"[DIAG] Bot Me: {data.get('result', {}).get('username')}")
        except Exception as e:
            print(f"[DIAG] Cloudflare Proxy check failed: {e}")
        
        # Быстрая проверка webhook и его удаление
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        
        try:
            print("[DIAG] Checking webhook status...")
            with opener.open(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=10) as response:
                data = json.loads(response.read().decode())
                webhook_url = data.get('result', {}).get('url', '')
                if webhook_url:
                    print(f"[DIAG] Webhook found: {webhook_url}, deleting...")
                    opener.open(f"https://api.telegram.org/bot{token}/deleteWebhook", timeout=10)
                    print("[DIAG] Webhook deleted")
                else:
                    print("[DIAG] No webhook configured")
        except Exception as e:
            print(f"[DIAG] Webhook check failed (non-critical): {e}")
        
        print("[DIAG] Connectivity check completed")
        
    except Exception as e:
        print(f"[DIAG] Diagnostic failed: {e}")
        print("[DIAG] Continuing with bot startup...")

def main() -> None:
    # Запускаем сервер в отдельном потоке
    threading.Thread(target=run_health_server, daemon=True).start()
    
    # Проверка связи и очистка вебхуков
    check_telegram_connectivity()
    
    """Выбрать и запустить нужный бот."""
    bot_type = sys.argv[1] if len(sys.argv) > 1 else "bank"

    if bot_type == "bridge":
        import asyncio
        from bridge_bot.main import main as bridge_main
        asyncio.run(bridge_main())

    elif bot_type == "vk":
        from vk_bot.main import run as vk_run
        vk_run()

    else:
        # bank (default) - основной бот в bot/
        from bot.main import main as bank_main
        bank_main()


if __name__ == "__main__":
    main()
