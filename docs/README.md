# BankBot - Документация проекта

High-level документация по текущей архитектуре, точкам входа и ключевым модулям проекта.

## О проекте

Репозиторий содержит три основных исполняемых компонента:

- `BankBot` - основной Telegram-бот с банковой логикой, балансами, магазином, достижениями, социальными функциями и парсингом игровых сообщений
- `BridgeBot` - мост Telegram -> VK для пересылки сообщений и медиа
- `VK Bot` - отдельная точка входа для VK Long Poll и публикации в VK-канал

Также в проекте есть общие слои конфигурации, базы данных, сервисов и тестов.

## Текущее состояние

- основной запуск проекта: `run_bot.py`
- канонический конфиг: `src/config.py`
- основной `.env` файл: `config/.env`
- инициализация схемы БД: `database/schema.py` и `database/initialize_system.py`
- миграции: `database/alembic/`
- smoke-проверки запуска: `tests/smoke/test_startup.py`

## Точки входа

| Компонент | Точка входа | Назначение |
|-----------|-------------|------------|
| BankBot | `run_bot.py` -> `bot.main` | Основной Telegram-бот |
| BridgeBot | `bridge_bot/main.py` | Пересылка TG -> VK, loop guard, graceful shutdown |
| VK Bot | `vk_bot/main.py` | Независимый VK Long Poll цикл |

## Архитектура

### 1. Основной бот

Папка `bot/` содержит рабочую точку входа BankBot и orchestration-логику запуска.

Ключевые файлы:

- `bot/main.py` - startup flow, валидация, schema sync, graceful shutdown
- `bot/bot.py` - основной класс Telegram-бота и регистрация функциональности
- `bot/commands/` - модульные обработчики команд
- `bot/router.py` - маршрутизация и wiring отдельных команд

### 2. Bridge и VK интеграция

Папка `bridge_bot/` содержит мост между Telegram и VK.

Ключевые файлы:

- `bridge_bot/main.py` - запуск aiogram-based BridgeBot
- `bridge_bot/handlers.py` - обработчики bridge-событий
- `bridge_bot/queue.py` - очередь отправки и rate limiting
- `bridge_bot/loop_guard.py` - защита от циклов через bot mark
- `bridge_bot/media.py` - работа с медиа
- `bridge_bot/vk_publisher.py` - публикация в VK API
- `bridge_bot/vk_listener.py` - приём сообщений из VK

Папка `vk_bot/` сохраняет отдельную точку входа для VK Long Poll.

### 3. Бизнес-логика и data access

Проект частично разделён на более чистые слои:

- `bank_bot/repositories/` - repository layer
- `bank_bot/services/` - service layer
- `bank_bot/middleware.py` - middleware и обработка ошибок
- `bank_bot/di.py` - wiring зависимостей

При этом в репозитории всё ещё присутствуют legacy и shim-слои в `core/`, `src/` и смежных модулях. Они используются как часть переходной архитектуры и должны рассматриваться как существующий runtime-контур, а не как полностью удалённый legacy.

### 4. Конфигурация

Канонический источник конфигурации - `src/config.py`.

Что важно:

- настройки читаются из `config/.env` и environment variables
- `Settings` и runtime helper `get_settings()` используются как общий контракт конфигурации
- bridge/vk config-модули являются compatibility-обёртками над `src.config`

### 5. База данных

Ключевые файлы:

- `database/connection.py` - подключение и pooling
- `database/database.py` - модели и metadata
- `database/schema.py` - приведение схемы к актуальному состоянию
- `database/initialize_system.py` - bootstrap новой БД
- `database/alembic/` - Alembic migration chain

Текущий подход:

- при запуске используется Alembic-first синхронизация схемы
- если миграционный контур недоступен, предусмотрен fallback на создание таблиц из metadata

## Структура проекта

```text
BankBot/
├── run_bot.py
├── README.md
├── RUN.md
├── bot/
├── bridge_bot/
├── vk_bot/
├── bank_bot/
├── core/
├── src/
├── database/
├── config/
├── tests/
├── docs/
└── memory_bank/
```

### Что где лежит

| Путь | Назначение |
|------|------------|
| `bot/` | Основной Telegram runtime |
| `bridge_bot/` | TG -> VK bridge |
| `vk_bot/` | Отдельный VK entrypoint |
| `bank_bot/` | Repository/service/middleware слои |
| `core/` | Legacy и shared модули, используемые текущим runtime |
| `src/` | Конфигурация, startup validation и часть инфраструктуры |
| `database/` | Подключение, schema sync, Alembic, bootstrap |
| `config/` | `.env` templates, YAML/JSON конфиги, dev requirements |
| `tests/` | Unit, integration, smoke и вспомогательные тесты |
| `memory_bank/` | Операционный контекст проекта |

## Запуск и проверка

Актуальный практический сценарий запуска описан в `RUN.md`.

Коротко:

```powershell
Copy-Item config/.env.example config/.env
py -3.13 -m pip install -r requirements.txt
py -3.13 database/initialize_system.py
py -3.13 run_bot.py
```

Для проверки старта:

```powershell
py -3.13 -m pytest tests/smoke -v
py -3.13 -m ruff check src/config.py tests/smoke/test_startup.py
```

## Документация по разделам

| Файл | Назначение |
|------|------------|
| `README.md` | Общая пользовательская документация проекта |
| `RUN.md` | Актуальная инструкция по запуску |
| `docs/DEPLOYMENT.md` | Деплой и инфраструктура |
| `docs/ARCHITECTURE.md` | Дополнительные архитектурные заметки |
| `docs/API.md` | Внутренние API и интерфейсы |
| `docs/TESTING_GUIDE.md` | Подход к тестированию |

Исторические документы, планы миграции и промежуточные отчёты в `docs/` сохраняются, но не все из них отражают текущее целевое состояние. Для high-level картины следует опираться на этот файл, `README.md`, `RUN.md` и `memory_bank/`.
