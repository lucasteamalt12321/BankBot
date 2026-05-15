# Tech Context

## Технологический стек

### Язык и фреймворки
- **Python 3.10+** - основной язык разработки
- **Python 3.12** - зафиксированный локальный runtime и Docker-образ для BankBot
- **python-telegram-bot 20.x** - асинхронная библиотека для Telegram Bot API
- **aiogram 3.x** - фреймворк для Bridge-модуля
- **SQLAlchemy 2.0+** - ORM для работы с базой данных
- **Flask** - health/metrics/logs сервер для Hugging Face

### Инфраструктура и Деплой
- **Hugging Face Spaces** - основная платформа для хостинга (Docker SDK)
- **GitHub** - основной репозиторий кода
- **Network Strategy (HF)**: 
  - IP-based proxy `195.201.225.248` (tgproxy.me) с кастомным `Host` header.
  - SSL verification отключён (`verify=False`) для IP-прокси (сертификат на домен).
  - Safe builder: `builder.http_client(custom_client)` с `try/except AttributeError` fallback.
  - Обычная среда: `PROXY_URL` через `builder.proxy_url()` + увеличенные таймауты.
- **Health Server**: Flask на порту `7860` — `/health` (с проверкой БД), `/metrics` (Prometheus), `/logs` (захват stdout/stderr).
- **Structlog** - структурированное логирование

### База данных
- **SQLite** (разработка) / **PostgreSQL** (продакшн)
- Миграции через Alembic
- Connection Pooling (в разработке)

### Управление зависимостями
- **pip** - основной пакетный менеджер
- **requirements.txt** - зависимости для продакшна
- **requirements-dev.txt** - зависимости для разработки

### Инструменты разработки
- **Ruff** - линтер и форматтер кода
- **Biome** - дополнительная проверка кода
- **pytest** - фреймворк для тестирования
- **hypothesis** - property-based testing

### Архитектурные компоненты
- **Parser Registry** - централизованная система парсинга игровых сообщений
- **Balance Manager** - управление балансами и конвертацией валют
- **Unit of Work** - атомарные транзакции с блокировками
- **DI Container** - внедрение зависимостей (`core/di.py`)
- **Bridge Module** - двусторонняя пересылка TG ↔ VK (`bot/bridge/`)
  - `loop_guard.py` — фильтрация циклов через метку `[BOT]`
  - `message_queue.py` — FIFO очередь с rate limiting и exponential backoff
  - `vk_sender.py` — отправка в VK через vk_api
  - `telegram_forwarder.py` — aiogram handler TG → VK
  - `vk_listener.py` — VKListenerThread (Long Poll)
  - `media_handler.py` — загрузка медиа TG → VK
  - `main_bridge.py` — точка входа aiogram с graceful shutdown

### Тестирование
- Unit tests - покрытие отдельных модулей
- Integration tests - взаимодействие компонентов
- E2E tests - сквозные сценарии (в разработке)
- Security tests - защита от SQL-инъекций и race conditions (в разработке)

### CI/CD
- Локальная разработка с автоматической проверкой линтером
- Docker контейнеризация (в разработке)
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
- `ADMIN_TELEGRAM_ID` — Telegram ID администратора
- `LOG_LEVEL` — уровень логирования
- `PROXY_URL` — HTTP-прокси для обычной среды
- `BRIDGE_ENABLED` — включить Bridge TG ↔ VK (bool)
- `BRIDGE_TG_CHAT_ID` — ID Telegram-чата для Bridge
- `VK_TOKEN` — токен VK API (обязателен при BRIDGE_ENABLED=true)
- `VK_PEER_ID` — peer_id VK-чата для Bridge
- `APP_ENV` — окружение: dev / prod / test
- `NTFY_ENABLED`, `NTFY_BASE_URL`, `NTFY_TAGS`, `NTFY_TIMEOUT_SECONDS` — ntfy уведомления
- `ADB_NOTIFICATIONS_ENABLED`, `ADB_PATH`, `ADB_DEVICE_SERIAL` — ADB уведомления

### Структура проекта
```
BankBot/
├── bot/                # Presentation Layer
│   └── bridge/         # Bridge-модуль TG ↔ VK
├── core/               # Application Layer  
├── config/             # Конфигурация (settings.py)
├── database/           # Database Layer + миграции
├── src/                # Domain Layer и инфраструктурные компоненты
├── utils/              # Вспомогательные утилиты
├── tests/              # Тесты
├── scripts/            # Вспомогательные скрипты
├── memory_bank/        # Документация и контекст проекта
└── requirements*.txt   # Зависимости
```

## Точки входа
- `run_bot.py` → `bot/main.py` — основной бот (python-telegram-bot)
- `python -m bot.bridge.main_bridge` — Bridge-бот (aiogram)
