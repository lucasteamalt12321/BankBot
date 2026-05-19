# System Patterns

## Архитектура проекта

BankBot следует многослойной архитектуре с четким разделением ответственности:

### Слои архитектуры

1. **Presentation Layer (`bot/`)**
   - Основной BankBot runtime на `python-telegram-bot 20.x`
   - `bot/bot.py` регистрирует handlers, mentioned-command fallback и HF polling lifecycle
   - `bot/commands/` содержит модульные PTB command handlers
   - `bot/response_modes.py` глобально патчит `Message.reply_text` для `/short`, `/long`, `/watch`
   - `bot/template_coder/` и watch quick-reply actions обрабатывают шаблонные текстовые ответы
   
2. **Application Layer (`core/`, `bank_bot/`)**
   - Service Layer - бизнес-логика (`core/services`, `bank_bot/services`)
   - Repository Layer - доступ к данным (`bank_bot/repositories`, compatibility shims в `core/repositories`)
   - Managers - управление конфигурацией и состоянием
   - Systems - высокоуровневые подсистемы (магазин, социальные функции, игры, D&D)

3. **Domain Layer (`core/models/`, `database/database.py`)**
   - Модели данных и бизнес-объекты
   - Базовые классы парсеров
   - Интерфейсы репозиториев

4. **Infrastructure Layer**
   - `database/` - SQLAlchemy metadata, pooled engine, Alembic/schema sync
   - `run_bot.py` - Hugging Face Flask endpoints (`/health`, `/logs`, `/metrics`, `/feedback`) и network workarounds
   - `utils/` - админ-совместимость, мониторинг, уведомления, process/startup helpers

### Ключевые паттерны

- **Repository Pattern** - абстракция доступа к данным
- **Service Layer** - инкапсуляция бизнес-логики
- **Unit of Work** - управление транзакциями
- **Parser Registry** - централизованная система парсинга
- **Dependency Injection** - `bot/middleware/dependency_injection.py` создаёт per-request SQLAlchemy session и сервисы
- **Runtime/legacy contract** - активные shim/legacy слои не удаляются без отдельной миграции; канон описан в `docs/README.md`
- **Response Mode Patch** - единый patch `Message.reply_text` сжимает ответы под режим пользователя (`short`, `watch`) и сохраняет режимы в `response_mode_settings`
- **HF Operational Guard** - guarded polling loop удерживает Space живым после transient Telegram/network errors; webhook-check пропускается на HF

### Поток данных

```
Telegram Update → python-telegram-bot Application → bot/bot.py handlers → bot/commands/*
                                                     ↓
                                            core/bank_bot services → SQLAlchemy session → PostgreSQL/SQLite
                                                     ↓
                                         Message.reply_text patch → short/long/watch output
```

### Парсинг игровых сообщений

```
Message → ParserRegistry → BaseParser → ParseResult → BalanceManager → UnitOfWork → Database
```

Это главный целевой поток проекта. На текущем этапе он должен трактоваться как PARSE01/in_progress: инфраструктура, правила и ручной контур существуют, но автоматический production E2E parsing реальных игровых сообщений ещё требует стабилизации, fixtures, diagnostics и мониторинга качества разбора.

### Watch-mode quick replies

```
Text message → parse_all_messages()
             → handle_watch_template_action()
             → template mapping (ОК/Да/Спасибо/...) → existing command handler
```

`Я занят(а)` является особым входом: включает личный `/watch` даже если пользователь ещё не в watch-mode.
