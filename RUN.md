# Инструкция по запуску BankBot

## ✅ Чеклист перед запуском

| Шаг | Команда/Действие | Проверка |
|-----|-----------------|----------|
| 1 | `pip install -r requirements.txt` | Зависимости установлены |
| 2 | `Copy-Item config/.env.example config/.env` | Файл `.env` создан |
| 3 | Заполнить `BOT_TOKEN` в `config/.env` | Токен получен от @BotFather |
| 4 | Заполнить `ADMIN_TELEGRAM_ID` | Ваш Telegram ID |
| 5 | `New-Item -ItemType Directory -Force data, logs` | Директории созданы |
| 6 | `python database/initialize_system.py` | БД инициализирована |

## Быстрый запуск

### 1. Установка зависимостей

```bash
py -3.13 -m pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Создайте файл `config/.env`:

```powershell
Copy-Item config/.env.example config/.env
```

Затем заполните его значениями:

```env
# Telegram Bot Token (REQUIRED)
BOT_TOKEN=your_bot_token_here

# Telegram Admin ID (REQUIRED)
ADMIN_TELEGRAM_ID=123456789

# Database URL (REQUIRED)
DATABASE_URL=sqlite:///data/bot.db

# Environment (optional, default: development)
ENV=development
LOG_LEVEL=INFO

# Bridge (optional, для TG → VK)
BRIDGE_ENABLED=false
BOT_TOKEN_BRIDGE=your_bridge_bot_token
TG_CHANNEL_ID=-1001234567890
VK_TOKEN=your_vk_token
VK_PEER_ID=2000000001

# Parsing (optional)
PARSING_ENABLED=false
```

### 3. Запуск ботов

**BankBot (основной):**
```bash
py -3.13 -m bot.main
# или
py -3.13 run_bot.py
```

**BridgeBot (опционально, для Telegram → VK):**
```bash
py -3.13 -m bridge_bot.main
```

**VK Bot (опционально):**
```bash
py -3.13 -m vk_bot.main
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
# Запуск smoke-тестов
python -m pytest tests/smoke/ -v

# Запуск unit-тестов
python -m pytest tests/unit/ -v

# Проверка линтера
ruff check bot/ core/ database/ utils/
```

## Возможные проблемы

### "Bot token is required"
Установите переменную окружения `BOT_TOKEN` в `config/.env`.

### "Database not found"
Убедитесь что директория `data/` существует:
```bash
New-Item -ItemType Directory -Force data
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
