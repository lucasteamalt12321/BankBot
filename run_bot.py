#!/usr/bin/env python3
"""Точка входа для запуска ботов проекта BankBot.

Использование:
    python run_bot.py           # запустить BankBot (по умолчанию)
    python run_bot.py bank      # запустить BankBot
    python run_bot.py bridge    # запустить BridgeBot
    python run_bot.py vk        # запустить VK Bot
"""

import sys
import os
import threading
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Микро-сервер для Hugging Face (чтобы Space не засыпал)
app = Flask(__name__)

@app.route('/')
def health_check():
    return "BankBot is running!"

def run_health_server():
    port = int(os.environ.get("PORT", 7860))
    app.run(host='0.0.0.0', port=port)

def check_telegram_connectivity():
    import urllib.request
    import json
    import os
    import time
    from src.config import settings
    
    print(f"[DIAG] Current System Time: {time.ctime()}")
    print(f"[DIAG] Proxy Env: HTTP={os.environ.get('http_proxy')}, HTTPS={os.environ.get('https_proxy')}")
    
    token = settings.BOT_TOKEN
    if not token:
        print("[DIAG] ERROR: BOT_TOKEN is empty!")
        return

    print(f"[DIAG] Testing Telegram API with token: {token[:10]}...")
    
    # 1. Check connectivity with curl (system level)
    print("[DIAG] Testing connection via system curl...")
    import subprocess
    try:
        result = subprocess.run(['curl', '-Is', 'https://api.telegram.org'], capture_output=True, text=True, timeout=15)
        print(f"[NET] Curl Status: {result.returncode}, Output: {result.stdout.strip()}")
    except Exception as e:
        print(f"[NET] Curl failed: {e}")

    # 2. Direct Python connection with extreme timeout
    try:
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        print("[DIAG] Testing direct HTTPS connection (45s timeout)...")
        with opener.open("https://api.telegram.org", timeout=45) as response:
            print(f"[NET] Telegram API status: {response.getcode()}")
    except Exception as e:
        print(f"[NET] Direct connection failed: {e}")

    # 2. Get Me & Webhook Cleanup
    try:
        print("[DIAG] Attempting getMe and Webhook check...")
        with opener.open(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=30) as response:
            data = json.loads(response.read().decode())
            print(f"[DIAG] Webhook Info: {data.get('result')}")
            if data.get('result', {}).get('url'):
                print(f"[DIAG] Deleting webhook...")
                opener.open(f"https://api.telegram.org/bot{token}/deleteWebhook")
    except Exception as e:
        print(f"[DIAG] Webhook check failed: {e}")
    
    # 3. Test send message to Admin
    try:
        admin_id = settings.ADMIN_TELEGRAM_ID or 2091908459
        print(f"[DIAG] Sending startup message to admin {admin_id}...")
        url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={admin_id}&text=🚀+Бот+запущен+на+Hugging+Face+и+готов+к+тестам!"
        with opener.open(url, timeout=30) as response:
            print(f"[DIAG] Startup message sent: {response.getcode()}")
    except Exception as e:
        print(f"[DIAG] Failed to send startup message: {e}")

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
