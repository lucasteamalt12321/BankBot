# Tech Context

## Технологический стек

### Язык и фреймворки
- **Python 3.12** - зафиксированный локальный runtime и Docker-образ для BankBot
- **python-telegram-bot 20.x** - асинхронная библиотека для Telegram Bot API
- **aiogram 3.x** - фреймворк для Bridge-модуля
- **SQLAlchemy 2.0+** - ORM для работы с базой данных
- **Flask** - health/metrics/logs сервер для Hugging Face

### Инфраструктура и Деплой
- **Hugging Face Spaces** - основная платформа для хостинга (Docker SDK)
- **GitHub** - основной репозиторий кода
- **Planned HF runtime migration**: production BankBot should move from Telegram polling to webhook (`POST /telegram/webhook/<secret>`) because current HF → Telegram `getUpdates` long-polling repeatedly times out.
- **Network Strategy (HF)**:
  - DNS bypass в `run_bot.py`: monkey patch `socket.getaddrinfo` и `anyio._core._sockets.getaddrinfo`, чтобы `api.telegram.org` резолвился в Telegram IP `149.154.167.220`.
  - HF httpx workaround: `httpx.AsyncClient.__init__` получает `verify=False` по умолчанию, чтобы пережить TLS/IP mismatch в облачной среде.
  - Legacy/current: `bot/bot.py` uses `run_polling()` with increased timeout parameters; this remains unstable on HF and is planned to be replaced by webhook.
  - `drop_pending_updates=False` на HF, чтобы команды не терялись при reconnect/polling instability.
  - HF `/start` использует `safe_start_command`: один короткий ответ без длинного welcome и без дополнительного template-coder hint.
  - Planned: webhook setup becomes the normal HF startup path; manual `getUpdates`/polling is not used in production.
  - Обычная среда: `PROXY_URL` через `builder.proxy_url()` + увеличенные таймауты.
- **Health/Webhook Server**: Flask на порту `7860` — `/health` (с проверкой БД), `/metrics` (Prometheus), `/logs` (захват stdout/stderr), `/feedback` (token-protected reader), planned `POST /telegram/webhook/<secret>`.
- **Structlog** - структурированное логирование

### База данных
- **SQLite** (local/dev fallback) / **PostgreSQL/Supabase** (production/HF)
- `DATABASE_URL`, `POSTGRES_URL`, `SUPABASE_DB_URL` aliases; `postgres://` нормализуется в `postgresql://`
- Supabase Session Pooler используется на HF, direct IPv6 URI был нестабилен
- Миграции через Alembic; HF startup дополнительно применяет idempotent critical schema repairs (`telegram_id BIGINT`, `response_mode_settings`)
- Connection Pooling через SQLAlchemy `QueuePool` + `pool_pre_ping`, PostgreSQL `connect_timeout`
- `users.telegram_id` хранится как `BIGINT`; response modes хранятся в `response_mode_settings`

### Управление зависимостями
- **pip** - основной пакетный менеджер
- **requirements.txt** - зависимости для продакшна
- **requirements-dev.txt** - зависимости для разработки

### Инструменты разработки
- **Ruff** - линтер и форматтер кода
- **pytest** - фреймворк для тестирования
- **hypothesis** - property-based testing
- Markdown (`*.md`) не проверяется через Ruff/Biome

### Архитектурные компоненты
- **Parser Registry** - централизованная система парсинга игровых сообщений
- **Balance Manager** - управление балансами и конвертацией валют
- **Unit of Work** - атомарные транзакции с блокировками
- **DI Container** - `bot/middleware/dependency_injection.py`, per-request SQLAlchemy session/service container
- **Response Modes** - planned production scope keeps `/short` and `/long` only; `/watch`, `/watch_all`, ADB and ntfy realtime/watch flows are to be disabled.
- **AI-lite** - `bot/ai/`, `/ai`, `/ask`, `/ai_help`, `/ai_update_knowledge`; optional AI02 HF Inference пока next focus
- **Feedback** - PostgreSQL-backed `/feedback`, `/suggest`, `/complaint`, `/feedback_list`, external `/feedback?limit=N`
- **Bridge/VK Modules** - planned removal from production HF runtime. Files may remain until cleanup, but `bridge_bot/` and `vk_bot/` should not be active entrypoints after webhook migration.

### Статус парсинга

Парсинг — ключевой целевой runtime проекта. Текущий технический статус: infrastructure/manual path есть, production E2E парсинг по ответам ещё in_progress. Для завершения PARSE01 нужны:

- fixtures реальных сообщений GD Cards, Shmalala, True Mafia, Bunker RP;
- проверяемые parsing rules и коэффициенты;
- мониторинг successful/failed parses;
- защита от ложных начислений и дублирования транзакций;
- админские diagnostics для просмотра причин неразбора.

### Тестирование
- Unit tests - покрытие отдельных модулей
- Integration tests - взаимодействие компонентов
- Smoke tests - `python3 -m pytest tests/smoke -v`, обязательны после runtime/code changes
- AI unit tests - `tests/unit/test_ai_lite.py` при изменениях AI-lite

### CI/CD
- Локальная разработка с автоматической проверкой линтером
- Docker контейнеризация (`Dockerfile` на `python:3.12-slim`, `docker-compose.yml`)
- Автоматические миграции БД

## Окружение разработки

### Переменные окружения
Конфигурация управляется через слои env-файлов:
- `config/.env.shared` — безопасные дефолты (committable)
- `config/.env.local` — секреты и локальные переопределения (не коммитится)
- legacy fallback: `config/.env`

Основные переменные:
- `BOT_TOKEN` — токен Telegram бота
- `DATABASE_URL` — URL подключения к базе данных
- `POSTGRES_URL`, `SUPABASE_DB_URL` — aliases для production DB URL
- `ADMIN_TELEGRAM_ID` — Telegram ID администратора
- `HF_TOKEN`, `FEEDBACK_READ_TOKEN` — Hugging Face/API reader токены (секреты, не коммитить)
- `LOG_LEVEL` — уровень логирования
- `PROXY_URL` — HTTP-прокси для обычной среды
- `BRIDGE_ENABLED` — включить Bridge TG ↔ VK (bool)
- `BRIDGE_TG_CHAT_ID` — ID Telegram-чата для Bridge
- `VK_TOKEN` — токен VK API (обязателен при BRIDGE_ENABLED=true)
- `VK_PEER_ID` — peer_id VK-чата для Bridge
- `APP_ENV` — окружение: dev / prod / test
- `NTFY_ENABLED`, `NTFY_BASE_URL`, `NTFY_TAGS`, `NTFY_TIMEOUT_SECONDS` — ntfy уведомления
- `ADB_NOTIFICATIONS_ENABLED`, `ADB_PATH`, `ADB_DEVICE_SERIAL` — ADB уведомления
- Planned webhook env:
  - `TELEGRAM_RUNTIME_MODE=webhook|polling` — explicit runtime selector (recommended)
  - `WEBHOOK_SECRET` — required secret for Telegram webhook path/header
  - `PUBLIC_WEBHOOK_URL` or derived HF URL — public webhook base URL if auto-detection is not reliable

### Структура проекта
```
BankBot/
├── bot/                # BankBot Telegram runtime (python-telegram-bot)
├── bridge_bot/         # BridgeBot Telegram → VK
├── vk_bot/             # VK Long Poll runtime
├── bank_bot/           # Repository/service namespace
├── core/               # Active runtime systems/services + compatibility shims
├── config/             # env templates and config files
├── database/           # Database Layer + миграции
├── src/                # Domain Layer и инфраструктурные компоненты
├── utils/              # Вспомогательные утилиты
├── tests/              # Тесты
├── scripts/            # Вспомогательные скрипты
├── memory_bank/        # Документация и контекст проекта
└── requirements*.txt   # Зависимости
```

## Точки входа
- Planned production: `run_bot.py` Flask app → `/telegram/webhook/<secret>` → BankBot PTB `Application.process_update()`
- Local/dev fallback: `run_bot.py` → `bot/main.py` → polling
- `bridge_bot/main.py` and `vk_bot/main.py` are planned to be removed from production HF runtime.
