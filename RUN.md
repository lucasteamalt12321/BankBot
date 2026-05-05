# Инструкция по запуску BankBot

> Важно: для локального запуска используйте **Python 3.12**. На Python 3.14 основной BankBot может падать при создании `python-telegram-bot` application из-за runtime-несовместимости.

## ✅ Чеклист перед запуском

| Шаг | Команда/Действие | Проверка |
|-----|-----------------|----------|
| 1 | `pip install -r requirements.txt` | Зависимости установлены |
| 2 | `Copy-Item config/.env.shared.example config/.env.shared` | Общий env-слой создан |
| 3 | `Copy-Item config/.env.local.example config/.env.local` | Локальный secret env-слой создан |
| 4 | Заполнить `BOT_TOKEN` в `config/.env.local` | Токен получен от @BotFather |
| 5 | Заполнить `ADMIN_TELEGRAM_ID` | Ваш Telegram ID |
| 6 | `New-Item -ItemType Directory -Force data, logs` | Директории созданы |
| 7 | `python database/initialize_system.py` | БД инициализирована |

## Быстрый запуск

### Самый короткий путь: 3 команды

```powershell
Copy-Item config/.env.shared.example config/.env.shared
Copy-Item config/.env.local.example config/.env.local
py -3.12 run_bot.py
```

Потом обязательно открой `config/.env.local` и укажи:

```env
BOT_TOKEN=your_bot_token_here
ADMIN_TELEGRAM_ID=123456789
```

### 1. Установка зависимостей

```bash
py -3.12 -m pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Создайте два файла:

```powershell
Copy-Item config/.env.shared.example config/.env.shared
Copy-Item config/.env.local.example config/.env.local
```

`config/.env.shared` — коммитируемый safe-слой:

```env
DATABASE_URL=sqlite:///data/bot.db
ENV=development
LOG_LEVEL=INFO

# При системном VPN (например, AmneziaVPN) оставьте пустым
PROXY_URL=
PARSING_ENABLED=false
```

`config/.env.local` — локальный secret-слой:

```env
# Telegram Bot Token (REQUIRED)
BOT_TOKEN=your_bot_token_here

# Telegram Admin ID (REQUIRED)
ADMIN_TELEGRAM_ID=123456789

# Optional local values
BOT_TOKEN_BRIDGE=
BOT_USERNAME=
ADMIN_CHAT_ID=
```

Bridge / VK секреты и локальные значения также храните в `config/.env.local`:

```env
BRIDGE_ENABLED=false
BOT_TOKEN_BRIDGE=your_bridge_bot_token
TG_CHANNEL_ID=-1001234567890
VK_TOKEN=your_vk_token
VK_PEER_ID=2000000001
```

### 3. Запуск ботов

**BankBot (основной):**
```bash
py -3.12 -m bot.main
# или
py -3.12 run_bot.py
```

**BridgeBot (опционально, для Telegram → VK):**
```bash
py -3.12 -m bridge_bot.main
```

**VK Bot (опционально):**
```bash
py -3.12 -m vk_bot.main
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
