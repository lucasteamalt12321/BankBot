# Deployment Guide

Актуальное руководство по развёртыванию BankBot, BridgeBot и VK Bot.

## Обзор

В репозитории предусмотрены два практических сценария развёртывания:

1. локальный запуск через `py -3.13`
2. контейнерный запуск через `Dockerfile` и `docker-compose.yml`

Текущие точки входа:

- `run_bot.py` -> основной запуск BankBot
- `bridge_bot/main.py` -> BridgeBot
- `vk_bot/main.py` -> VK Bot

## Требования

### Локально

- Python `3.13` для сценария, который сейчас описан в runbook проекта
- доступ к Telegram Bot API
- для bridge-режима: доступ к VK API

### Для Docker

- Docker
- Docker Compose

Текущий контейнерный образ собирается на `python:3.11-slim`, что отражено в `Dockerfile`.

## Конфигурация

Основной env-файл:

- `config/.env`

Шаблон:

- `config/.env.example`

Канонический код конфигурации:

- `src/config.py`

Минимальный набор обязательных переменных:

```env
BOT_TOKEN=your_bot_token_here
ADMIN_TELEGRAM_ID=123456789
DATABASE_URL=sqlite:///data/bot.db
```

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
py -3.13 -m pip install -r requirements.txt
```

### 2. Подготовка конфигурации

```powershell
Copy-Item config/.env.example config/.env
```

### 3. Подготовка директорий и БД

```powershell
New-Item -ItemType Directory -Force data, logs
py -3.13 database/initialize_system.py
```

### 4. Запуск

BankBot:

```powershell
py -3.13 run_bot.py
```

BridgeBot:

```powershell
py -3.13 -m bridge_bot.main
```

VK Bot:

```powershell
py -3.13 -m vk_bot.main
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

Для новой локальной БД обычно достаточно:

```powershell
py -3.13 database/initialize_system.py
```

## Проверка после деплоя

### Smoke

```powershell
py -3.13 -m pytest tests/smoke -v
```

### Линтер

```powershell
py -3.13 -m ruff check src/config.py tests/smoke/test_startup.py
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

## Что не стоит считать каноническим

В репозитории сохранились старые документы с историческими планами, промежуточными миграциями и ранними архитектурными схемами. Для текущего operational состояния опирайтесь на:

- `README.md`
- `RUN.md`
- `docs/README.md`
- этот файл
- `memory_bank/`
