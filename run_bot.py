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

def main() -> None:
    # Запускаем сервер в отдельном потоке
    threading.Thread(target=run_health_server, daemon=True).start()
    
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
