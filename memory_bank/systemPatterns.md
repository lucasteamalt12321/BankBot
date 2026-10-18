# System Patterns

## Архитектура проекта

LTHub следует многослойной архитектуре с четким разделением ответственности:

### Слои архитектуры

1. **Presentation Layer (`bot/`)**
   - Основной LTHub runtime на `python-telegram-bot 20.x`
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
- **HF Webhook Runtime (planned)** - Telegram sends updates to Flask webhook endpoint; LTHub calls `Application.process_update(update)`; polling is local/dev fallback only
- **Atomic money mutations** — балансы и покупки меняются только относительным условным `UPDATE` под контролем `rowcount`; `with_for_update()` не считается достаточным (см. раздел ниже)
- **Secrets from env** - webhook-секрет выводится из `BOT_TOKEN`, owner-ID и прочие секреты — только из env (см. раздел ниже)

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

### Переносимый DDL: `_ddl()` / `_ddl_session()` / `_ensure_ddl_column()`

Схема в `api/index.py` создаётся лениво функциями `_ensure_*` при первом обращении, и
одним и тем же кодом должна работать и на PostgreSQL (прод), и на SQLite (тесты и
локальный запуск без `DATABASE_URL`). Отсюда правила:

- **Сырой `conn.execute(text("CREATE/ALTER/DROP ..."))` с диалектными конструкциями
  запрещён.** `SERIAL`, `TIMESTAMPTZ`, `NOW()`, `ADD COLUMN IF NOT EXISTS` и
  много-колоночный `ALTER` SQLite не понимает.
- Весь DDL прогоняется через `_ddl(sql, engine)`, который переписывает конструкции под
  диалекту. Оборачивать в него нужно только DDL — DML идёт как есть.
- `_ddl_session(engine)` — предпочтительная обёртка: нормализует DDL и глотает
  «уже применено» (`duplicate column name` / `already exists`), потому что повторный
  cold start — норма. Остальные ошибки пробрасываются в штатный `log_error`.
- Добавление колонки — только по одной через `_ensure_ddl_column(conn, table, "COL TYPE", engine)`
  (само уже проверяет `information_schema` / `PRAGMA table_info`).
- Грабли, стоившие бага «Новая сессия» (2026-09-30): один непрошенный `ALTER` ронял
  **всю** функцию сразу после `CREATE TABLE`, поэтому таблица создавалась, но без новых
  колонок, и падал уже следующий запрос. Ловить такие бабы можно только тестом на
  **холодной** БД — на прогретой схеме и на Postgres всё работает.

### Денежные операции: атомарные условные `UPDATE` (BUG-05, 2026-10-15)

Балансы и покупки нельзя менять схемой read-modify-write (`obj.balance = obj.balance + delta; commit()`):
на SQLite `with_for_update()` — no-op, а на Postgres блокировка строки без явного перечитывания объекта
всё равно теряет конкурентные начисления. Канон:

- Начисление/списание — **одним относительным** `UPDATE ... SET balance = COALESCE(balance,0) + :delta`
  (или `- :delta`); результат проверяется по `rowcount` (0 = нет строки либо недостаточно средств),
  объект освежается (`populate_existing()`) или перечитывается.
- Проверка «хватает ли денег» — в самом `WHERE` (`WHERE balance >= :amount`), а не отдельным `SELECT`,
  иначе остаётся окно гонки check-then-act.
- Покупка в магазине — списание одним условным `UPDATE`; `rowcount == 0` → `INSUFFICIENT_BALANCE`.
  Под-операции (`_activate_sticker_item`) не коммитят до успеха основной — только `flush()`.
- Списки товаров/сущностей — всегда `ORDER BY <id>`, чтобы нумерация не «плавала» между запросами.
- `with_for_update()` допустим как дополнительная сериализация на Postgres (например, проверка «получал ли
  ежедневный бонус»), но НЕ заменяет атомарный относительный `UPDATE`.
- Регресс: `tests/unit/test_money_races.py` (включая потоковый lost-update тест).

### Секреты и лимиты входа (BUG-06/BUG-07, 2026-10-15)

- Webhook-секрет не хранится отдельной переменной: выводится из `BOT_TOKEN` общим `src/webhook_secret.py`
  (`derive_webhook_secret`); используют `api/index.py` и `run_bot.py`. Owner-ID (`ADMIN_TELEGRAM_ID`)
  берётся только из env, без захардкоженных значений; в логах секреты и owner-ID редактируются.
- Размер тела запроса ограничен `MAX_CONTENT_LENGTH` (по умолчанию 16 МБ, env-переопределяемо) +
  обработчик 413. Werkzeug отсекает тело **до** входа в маршрут, поэтому дружелюбный текст с лимитом
  формируется в обработчике 413, а маршруты (напр. `/api/gd/submit`) сохраняют свои сообщения «лимит. 16 МБ».
- Пользовательские входы-счётчики (напр. `actions` в достижениях, число кубиков `NdM`) жёстко клампятся
  сверху; тяжёлые синхронные циклы по пользовательскому числу недопустимы (вешают event loop).

### Planned runtime removals for webhook migration

- Background periodic loops are disabled in HF webhook runtime.
- Shop/games/D&D handlers are removed from production command registration.
- BridgeBot and VK Bot are removed from production HF entrypoint.
- Manual pasted-message parsing fallback is forbidden; parsing remains reply-only to prevent cheating.
