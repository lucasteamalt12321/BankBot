# BankBot - Telegram-банк и мост TG -> VK

Репозиторий содержит основной Telegram-бот с банковой логикой, а также bridge-компоненты для пересылки сообщений между Telegram и VK.

## Что есть в проекте

| Компонент | Назначение |
|-----------|------------|
| `BankBot` | Основной Telegram-бот: баланс, магазин, админ-команды, парсинг игровых сообщений |
| `BridgeBot` | Пересылка сообщений и медиа из Telegram в VK |
| `VK Bot` | Отдельная точка входа для VK Long Poll и публикации в VK |

## Точки входа

| Компонент | Запуск |
|-----------|--------|
| BankBot | `py -3.13 run_bot.py` |
| BankBot напрямую | `py -3.13 -m bot.main` |
| BridgeBot | `py -3.13 -m bridge_bot.main` |
| VK Bot | `py -3.13 -m vk_bot.main` |

## Быстрый старт

### 1. Установка зависимостей

```powershell
py -3.13 -m pip install -r requirements.txt
```

### 2. Настройка окружения

```powershell
Copy-Item config/.env.example config/.env
```

Минимально необходимые переменные в `config/.env`:

```env
BOT_TOKEN=your_bot_token_here
ADMIN_TELEGRAM_ID=123456789
DATABASE_URL=sqlite:///data/bot.db
ENV=development
LOG_LEVEL=INFO
```

Для bridge-режима дополнительно:

```env
BRIDGE_ENABLED=false
BOT_TOKEN_BRIDGE=your_bridge_bot_token
TG_CHANNEL_ID=-1001234567890
VK_TOKEN=your_vk_token
VK_PEER_ID=2000000001
```

### 3. Подготовка данных

```powershell
New-Item -ItemType Directory -Force data, logs
py -3.13 database/initialize_system.py
```

### 4. Запуск

```powershell
py -3.13 run_bot.py
```

Подробный локальный сценарий запуска: `RUN.md`

## Проверка

```powershell
py -3.13 -m pytest tests/smoke -v
py -3.13 -m ruff check src/config.py tests/smoke/test_startup.py
```

## Архитектура

### Основные каталоги

| Путь | Назначение |
|------|------------|
| `bot/` | Основной runtime BankBot |
| `bridge_bot/` | TG -> VK bridge |
| `vk_bot/` | Независимый VK runtime |
| `bank_bot/` | Repository/service/middleware слои |
| `src/` | Канонический конфиг и startup-инфраструктура |
| `database/` | Подключение, schema sync, Alembic, bootstrap |
| `tests/` | Unit, integration и smoke-тесты |
| `memory_bank/` | Операционный контекст и прогресс проекта |

### Конфигурация

Канонический источник конфигурации: `src/config.py`.

Ключевые принципы:

- основной env-файл: `config/.env`
- bridge и vk config-модули используют compatibility-обёртки над `src.config`
- схема БД приводится к актуальному состоянию при запуске через `database/schema.py`

## Docker

В проекте есть:

- `Dockerfile`
- `docker-compose.yml`

Базовый запуск:

```powershell
docker-compose up -d
docker-compose logs -f
```

Compose поднимает три сервиса:

- `bank_bot`
- `bridge_bot`
- `vk_bot`

## Документация

| Файл | Назначение |
|------|------------|
| `RUN.md` | Актуальная инструкция по локальному запуску |
| `docs/README.md` | High-level карта проекта |
| `docs/DEPLOYMENT.md` | Развёртывание и Docker/systemd сценарии |
| `docs/ARCHITECTURE.md` | Дополнительные архитектурные заметки |
| `docs/TESTING_GUIDE.md` | Детали по тестированию |

## Примечание

В репозитории ещё есть переходные и legacy-слои. Для актуальной high-level картины следует опираться на:

- `README.md`
- `RUN.md`
- `docs/README.md`
- `memory_bank/`
