# System Patterns

## Архитектура проекта

BankBot следует многослойной архитектуре с четким разделением ответственности:

### Слои архитектуры

1. **Presentation Layer (`bot/`)**
   - Основной BankBot runtime на `python-telegram-bot 20.x`
   - Planned: HF production must use Telegram webhook instead of polling; local/dev may keep polling fallback
   - `bot/bot.py` регистрирует handlers, mentioned-command fallback и должен быть разделён на setup Application vs runtime mode
   - `bot/commands/` содержит модульные PTB command handlers
   - Planned scope: keep only `/short` and `/long`; disable `/watch`, ADB and ntfy realtime/watch flows in production runtime
   - `bot/template_coder/` остаётся отдельным модулем, но не является частью webhook migration scope
   
2. **Application Layer (`core/`, `bank_bot/`)**
   - Service Layer - бизнес-логика (`core/services`, `bank_bot/services`)
   - Repository Layer - доступ к данным (`bank_bot/repositories`, compatibility shims в `core/repositories`)
   - Managers - управление конфигурацией и состоянием
    - Systems - высокоуровневые подсистемы; planned production webhook scope disables non-working shop/games/D&D handlers

3. **Domain Layer (`core/models/`, `database/database.py`)**
   - Модели данных и бизнес-объекты
   - Базовые классы парсеров
   - Интерфейсы репозиториев

4. **Infrastructure Layer**
   - `database/` - SQLAlchemy metadata, pooled engine, Alembic/schema sync
    - `run_bot.py` - Hugging Face Flask endpoints (`/health`, `/logs`, `/metrics`, `/feedback`); planned owner of `POST /telegram/webhook/<secret>`
   - `utils/` - админ-совместимость, мониторинг, уведомления, process/startup helpers

### Ключевые паттерны

- **Repository Pattern** - абстракция доступа к данным
- **Service Layer** - инкапсуляция бизнес-логики
- **Unit of Work** - управление транзакциями
- **Parser Registry** - централизованная система парсинга
- **Dependency Injection** - `bot/middleware/dependency_injection.py` создаёт per-request SQLAlchemy session и сервисы
- **Runtime/legacy contract** - активные shim/legacy слои не удаляются без отдельной миграции; канон описан в `docs/README.md`
- **Response Mode Patch** - planned production scope keeps only `short`/`long`; `watch` is to be disabled from runtime
- **HF Webhook Runtime (planned)** - Telegram sends updates to Flask webhook endpoint; BankBot calls `Application.process_update(update)`; polling is local/dev fallback only

### Поток данных

```text
Production planned:
Telegram → HF Flask /telegram/webhook/<secret> → PTB Application.process_update()
         → bot/bot.py handlers → bot/commands/* / parsing_handler
         → core/bank_bot services → SQLAlchemy session → PostgreSQL
         → safe Telegram send_message/reply_text with short/long output

Local/dev fallback:
Telegram getUpdates polling → PTB Application → same handlers
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

### Planned runtime removals for webhook migration

- Background periodic loops are disabled in HF webhook runtime.
- Shop/games/D&D handlers are removed from production command registration.
- BridgeBot and VK Bot are removed from production HF entrypoint.
- Manual pasted-message parsing fallback is forbidden; parsing remains reply-only to prevent cheating.
