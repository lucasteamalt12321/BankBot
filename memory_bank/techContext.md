# Tech Context

## Технологический стек

### Язык и фреймворки
- **Python 3.10+** - основной язык разработки
- **aiogram 3.x** - асинхронный фреймворк для Telegram Bot API
- **SQLAlchemy 2.0+** - ORM для работы с базой данных
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
Конфигурация управляется через файл `.env` (не включается в репозиторий):
- `BOT_TOKEN` — токен Telegram бота
- `DATABASE_URL` — URL подключения к базе данных
- `ADMIN_TELEGRAM_ID` — Telegram ID администратора
- `LOG_LEVEL` — уровень логирования
- `BRIDGE_ENABLED` — включить Bridge TG ↔ VK (bool)
- `BRIDGE_TG_CHAT_ID` — ID Telegram-чата для Bridge
- `VK_TOKEN` — токен VK API (обязателен при BRIDGE_ENABLED=true)
- `VK_PEER_ID` — peer_id VK-чата для Bridge
- `APP_ENV` — окружение: dev / prod / test

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