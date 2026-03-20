# System Patterns

## Архитектура (слои)

```
Telegram API
    ↓
bot/commands/       — тонкий слой обработчиков команд
    ↓
core/services/      — бизнес-логика (service layer)
    ↓
src/repository/     — доступ к данным (repository pattern)
    ↓
SQLite (data/bot.db / bot.db)
```

## Ключевые паттерны

### Конфигурация
- Единый источник: `src/config.py` (Pydantic Settings)
- Переменные окружения через `config/.env`
- Поддержка окружений: development / test / staging / production
- Запуск: `ENV=production python run_bot.py`

### Repository Pattern
- `src/repository/base.py` — базовый CRUD
- `src/repository/user_repository.py` — пользователи
- Все операции с БД только через репозитории

### Service Layer
- `core/services/user_service.py`
- `core/services/transaction_service.py`
- `core/services/shop_service.py`
- `core/services/admin_service.py`
- `core/services/broadcast_service.py`

### Парсинг
- `core/parsers/base.py` — базовый класс BaseParser
- `core/parsers/registry.py` — регистратор парсеров (в работе)
- Парсеры: gdcards, shmalala, truemafia, bunkerrp
- Идемпотентность через SHA-256 хэш сообщения
- Конфигурация парсинга хранится в БД (ParsingConfigManager)

### Обработка ошибок
- `bot/middleware/error_handler.py` — централизованный middleware
- Уведомления администратора при критических ошибках

### Фоновые задачи
- `core/managers/scheduler_manager.py` — APScheduler
- `core/managers/background_task_manager.py`
- Задачи: очистка стикеров, бэкапы, проверка VIP

### Graceful Shutdown
- `src/process_manager.py` — PID management + обработка сигналов

## Соглашения кода

- Type hints во всех публичных методах
- Docstrings в формате Google
- Тесты: unit / integration / property-based (hypothesis)
- Логирование через structlog

## Известные архитектурные проблемы

- Часть handlers всё ещё содержит бизнес-логику (D06 in_progress)
- DI не настроен — зависимости создаются вручную (D15 pending)
- Дублирующиеся парсеры не объединены (D17 pending)
- Unit of Work не реализован (D11 pending)
