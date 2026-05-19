# Deployment Guide

Актуальное руководство по развёртыванию BankBot, BridgeBot и VK Bot.

## Обзор

В репозитории предусмотрены два практических сценария развёртывания:

1. локальный запуск через `py -3.12`
2. контейнерный запуск через `Dockerfile` и `docker-compose.yml`

Текущие точки входа:

- `run_bot.py` -> основной запуск BankBot
- `bridge_bot/main.py` -> BridgeBot
- `vk_bot/main.py` -> VK Bot

## Требования

### Локально

- Python `3.12` для локального сценария, описанного в runbook проекта
- Python `3.14` не рекомендуется для основного BankBot: на практике возможен runtime-crash в `python-telegram-bot==20.7` при инициализации `Updater`
- доступ к Telegram Bot API
- для bridge-режима: доступ к VK API

### Для Docker

- Docker
- Docker Compose

Текущий контейнерный образ собирается на `python:3.12-slim`, что отражено в `Dockerfile`.

## Конфигурация

Основные env-файлы:

- `config/.env.shared` — безопасный committable слой
- `config/.env.local` — локальные секреты и приватные значения
- `config/.env` — legacy fallback

Шаблоны:

- `config/.env.shared.example`
- `config/.env.local.example`

Канонический код конфигурации:

- `src/config.py`

Минимальный набор обязательных переменных:

```env
BOT_TOKEN=your_bot_token_here
ADMIN_TELEGRAM_ID=123456789
DATABASE_URL=sqlite:///data/bot.db
```

Для production/Hugging Face `DATABASE_URL` должен быть Secret с PostgreSQL/Supabase URL. Также поддерживаются aliases `POSTGRES_URL` и `SUPABASE_DB_URL`.

Дополнительно для bridge/VK:

```env
BRIDGE_ENABLED=false
BOT_TOKEN_BRIDGE=your_bridge_bot_token
TG_CHANNEL_ID=-1001234567890
VK_TOKEN=your_vk_token
VK_PEER_ID=2000000001
```

Актуальные database pool поля:

```env
DB_POOL_MIN=2
DB_POOL_MAX=10
DB_POOL_TIMEOUT=30
```

## Локальное развёртывание

### 1. Установка зависимостей

```powershell
py -3.12 -m pip install -r requirements.txt
```

### 2. Подготовка конфигурации

```powershell
Copy-Item config/.env.shared.example config/.env.shared
Copy-Item config/.env.local.example config/.env.local
```

### 3. Подготовка директорий и БД

```powershell
New-Item -ItemType Directory -Force data, logs
py -3.12 database/initialize_system.py
```

### 4. Запуск

BankBot:

```powershell
py -3.12 run_bot.py
```

BridgeBot:

```powershell
py -3.12 -m bridge_bot.main
```

VK Bot:

```powershell
py -3.12 -m vk_bot.main
```

## Docker deployment

### Что есть в проекте

- `Dockerfile` - multi-stage сборка
- `docker-compose.yml` - запуск трёх сервисов

### Compose-сервисы

| Сервис | Команда |
|--------|---------|
| `bank_bot` | `python run_bot.py bank` |
| `bridge_bot` | `python run_bot.py bridge` |
| `vk_bot` | `python run_bot.py vk` |

### Запуск

```powershell
docker-compose up -d
docker-compose logs -f
```

### Остановка

```powershell
docker-compose down
```

## База данных и миграции

Ключевые модули:

- `database/schema.py`
- `database/initialize_system.py`
- `database/alembic/`

Текущий runtime-подход:

- при запуске используется Alembic-first синхронизация схемы
- если миграции недоступны, остаётся fallback на создание таблиц из SQLAlchemy metadata
- на Hugging Face применяются короткие idempotent schema repairs для критичных runtime-полей (`telegram_id BIGINT`, `response_mode_settings`), чтобы startup не блокировался долгими/рискованными миграциями

Для новой локальной БД обычно достаточно:

```powershell
py -3.12 database/initialize_system.py
```

## Проверка после деплоя

### Smoke

```powershell
py -3.12 -m pytest tests/smoke -v
```

### Линтер

```powershell
py -3.12 -m ruff check src/config.py tests/smoke/test_startup.py
```

### Docker

```powershell
docker-compose ps
docker-compose logs -f
```

## Operational notes

- `bot/main.py` выполняет startup validation до запуска BankBot
- `database/schema.py` используется для приведения схемы к актуальному состоянию
- `bridge_bot/main.py` и `vk_bot/main.py` поддерживают корректное завершение работы
- `memory_bank/` используется как источник актуального операционного контекста проекта

## Hugging Face Spaces (Docker SDK)

Бот оптимизирован для работы в среде Hugging Face Spaces.

### Особенности настройки:
1. **Network**: Hugging Face может нестабильно работать с Telegram DNS/TLS. `run_bot.py` применяет DNS/anyio/httpx workaround для `api.telegram.org` в среде `SPACE_ID`.
2. **Health Checks**: `run_bot.py` запускает Flask-сервер на порту `7860`, который используется HF для мониторинга состояния.
3. **Variables/Secrets**: необходимы `BOT_TOKEN`, `ADMIN_TELEGRAM_ID`; production DB задаётся через Secret `DATABASE_URL`.
4. **Startup**: webhook diagnostic check на HF пропускается, потому что он может блокировать запуск.
5. **Polling**: BankBot использует guarded polling loop и `drop_pending_updates=False`, чтобы Space оставался живым и команды не терялись при reconnect.

### Просмотр логов:
Логи доступны через:

- веб-интерфейс Hugging Face;
- `GET /logs` на Space host;
- streaming API `https://huggingface.co/api/spaces/LucasTeam/BankBot/logs/run` с `Authorization: Bearer <HF_TOKEN>`.

Не использовать manual `getUpdates` во время live debugging, чтобы не мешать polling.

## Что не стоит считать каноническим

В репозитории сохранились старые документы с историческими планами, промежуточными миграциями и ранними архитектурными схемами. Для текущего operational состояния опирайтесь на:

- `README.md`
- `RUN.md`
- `docs/README.md`
- этот файл
- `memory_bank/`
