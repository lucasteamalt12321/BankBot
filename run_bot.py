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
        
        print(f"[DIAG] Token loaded: {token[:10]}...")
        
        # Проверка Telegram API Proxy с токеном
        try:
            proxy_url = f"https://tg.i-c-a.su/bot{token}/getMe"
            print(f"[DIAG] Testing Telegram Proxy (i-c-a) with token: {proxy_url[:45]}...")
            with urllib.request.urlopen(proxy_url, timeout=10) as resp:
                print(f"[DIAG] Proxy status: {resp.getcode()}")
                import json
                data = json.loads(resp.read().decode())
                print(f"[DIAG] Bot Me: {data.get('result', {}).get('username')}")
        except Exception as e:
            print(f"[DIAG] Proxy i-c-a check failed: {e}")
            
        # Попробуем другой вариант прокси (без /bot в начале)
        try:
            proxy_url = f"https://tg.i-c-a.su/{token}/getMe"
            print(f"[DIAG] Testing Telegram Proxy (i-c-a, no /bot) with token: {proxy_url[:45]}...")
            with urllib.request.urlopen(proxy_url, timeout=10) as resp:
                print(f"[DIAG] Proxy (no /bot) status: {resp.getcode()}")
        except Exception as e:
            print(f"[DIAG] Proxy i-c-a (no /bot) check failed: {e}")
        
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
