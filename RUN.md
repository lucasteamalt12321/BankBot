# Инструкция по запуску BankBot

## Быстрый запуск

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```env
# Telegram Bot Tokens
BOT_TOKEN_BANK=your_bank_bot_token_here
BOT_TOKEN_BRIDGE=your_bridge_bot_token_here

# Telegram Channel
TG_CHANNEL_ID=-1001234567890

# VK Configuration
VK_TOKEN=your_vk_access_token_here
VK_PEER_ID=2000000001
VK_GROUP_ID=123456789

# Database
DATABASE_URL=sqlite:///data/bot.db

# Admin
ADMIN_TELEGRAM_ID=123456789

# Environment
APP_ENV=production
PARSING_ENABLED=true
```

### 3. Запуск ботов

**BankBot (основной):**
```bash
python -m bot.main
# или
python run_bot.py
```

**BridgeBot (опционально, для Telegram → VK):**
```bash
python -m bridge_bot.main
```

**VK Bot (опционально):**
```bash
python -m vk_bot.main
```

## Запуск через Docker

```bash
# Убедитесь что Docker запущен
docker --version

# Сборка и запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

## Проверка работы

```bash
# Запуск тестов
python -m pytest tests/unit/ -v

# Проверка линтера
ruff check bot/ core/ database/ utils/
```

## Возможные проблемы

### "Bot token is required"
Установите переменную окружения `BOT_TOKEN_BANK` или создайте файл `.env`.

### "Database not found"
Убедитесь что директория `data/` существует:
```bash
mkdir -p data
```

### "No module named 'bot'"
Запускайте из корневой директории проекта.

## Структура проекта

```
BankBot/
├── bot/              # BankBot (Telegram)
├── bridge_bot/       # BridgeBot (Telegram → VK)
├── vk_bot/           # VK Bot
├── database/         # База данных
├── utils/           # Утилиты
├── core/            # Ядро приложения
├── tests/           # Тесты
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```
