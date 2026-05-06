# System Patterns

## Архитектура

```
Telegram API
    ↓
bot/commands/     — обработчики команд (тонкий слой)
    ↓
core/services/    — бизнес-логика
    ↓
src/repository/   — доступ к данным
    ↓
SQLite (data/bot.db)
```

## Ключевые паттерны

### Конфигурация
- Единый источник: `src/config.py` (Pydantic Settings)
- Переменные окружения через `config/.env`
- Поддержка окружений: development / test / staging / production

### Репозитории
- `src/repository/base.py` — базовый CRUD
- `src/repository/user_repository.py` — пользователи
- Unit of Work для атомарных транзакций

### Парсинг
- `core/parsers/base.py` — базовый класс
- `core/parsers/registry.py` — регистратор парсеров
- Парсеры: gdcards, shmalala, truemafia, bunkerrp
- Идемпотентность через SHA-256 хэш сообщения

### Обработка ошибок
- `bot/middleware/error_handler.py` — централизованный middleware
- Уведомления администратора при критических ошибках

### Фоновые задачи
- `core/managers/scheduler_manager.py` — apscheduler
- `core/managers/background_task_manager.py`

### Диалоговый кодер шаблонов
- `bot/template_coder/service.py` — чистая параметрическая логика кодера без таблиц пар/троек
- `CoderState` хранит `topic`, `time_minutes`, `intensity`, `politeness`, `confidence`, `repeat_flag`, `history`, `steps`, `updated_at`
- `apply(state, template)` мутабельно обновляет состояние, `render(state)` детерминированно генерирует фразу
- Preview следующих вариантов строится через копию состояния + `apply` + `render`, затем сортируется по силе изменения состояния
- `bot/template_coder/dialog.py` хранит состояние в PTB `chat_data` и реализует команды `/coder`, `/reset`, `/done`, `/help`

## Соглашения

- Type hints во всех публичных методах
- Docstrings в формате Google
- Тесты: unit / integration / property-based (hypothesis)
- Логирование через structlog
