# System Patterns

## Архитектура (слои)

```
Telegram API
    ↓
bot/commands/       — тонкий слой обработчиков команд
    ↓
core/services/      — бизнес-логика (service layer) ✅
    ↓
src/repository/     — доступ к данным (repository pattern) ✅
    ↓
SQLite (data/bot.db / bot.db)
```

## Ключевые паттерны

### Конфигурация ✅
- Единый источник: `src/config.py` (Pydantic Settings)
- Переменные окружения через `config/.env`
- Поддержка окружений: development / test / staging / production
- Запуск: `ENV=production python run_bot.py`

### Repository Pattern ✅
- `src/repository/base.py` — базовый CRUD
- `src/repository/user_repository.py` — пользователи
- `src/repository/unit_of_work.py` — Unit of Work (создан, не интегрирован)
- Все операции с БД только через репозитории

### Service Layer ✅
- `core/services/user_service.py`
- `core/services/transaction_service.py` — с asyncio.Lock для блокировок
- `core/services/shop_service.py`
- `core/services/admin_service.py`
- `core/services/broadcast_service.py`
- `core/services/admin_stats_service.py`

### Dependency Injection ⚠️
- `bot/middleware/dependency_injection.py` — DI middleware (создан, не интегрирован)
- Предоставляет `Services` контейнер с user_service, admin_service, shop_service, transaction_service
- Функции: `build_services()`, `get_services(context)`, `setup_di(application)`
- **Требуется:** интеграция в `bot/main.py`

### Парсинг ⚠️
- `core/parsers/base.py` — базовый класс BaseParser
- `core/parsers/registry.py` — ParserRegistry (создан, не интегрирован)
- Парсеры: gdcards, shmalala, truemafia, bunkerrp
- Идемпотентность через SHA-256 хэш сообщения
- `core/managers/parsing_config_manager.py` — управление правилами в БД
- Таблица `parsing_rules` в БД (database.py:362)
- **Проблема:** `bot/handlers/parsing_handler.py` использует старую систему `src/parsers`
- **Требуется:** рефакторинг ParsingHandler для использования ParserRegistry

### Обработка ошибок ✅
- `bot/middleware/error_handler.py` — централизованный middleware
- Уведомления администратора при критических ошибках

### Фоновые задачи ✅
- `core/managers/scheduler_manager.py` — APScheduler
- `core/managers/background_task_manager.py`
- Задачи: очистка стикеров, бэкапы, проверка VIP

### Graceful Shutdown ✅
- `src/process_manager.py` — PID management + обработка сигналов

### Unit of Work Pattern ⚠️
- `src/repository/unit_of_work.py` — реализован
- Поддерживает context manager для атомарных транзакций
- **Требуется:** интеграция в `core/services/transaction_service.py`

## Соглашения кода

- Type hints во всех публичных методах
- Docstrings в формате Google
- Тесты: unit / integration / property-based (hypothesis)
- Логирование через structlog

## Известные архитектурные проблемы

- **D10 (ParserRegistry):** создан, но не интегрирован в bot handlers
- **D11 (Unit of Work):** создан, но не используется в TransactionService
- **D15 (DI middleware):** создан, но не подключен в bot/main.py
- Дублирующиеся парсеры не объединены (D17 pending)
- Старая система парсинга `src/parsers` всё ещё используется
- Временные тестовые БД создаются в корне проекта (мусор)
