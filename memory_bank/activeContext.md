# Active Context

## Текущий фокус
**Phase 2: Feature Expansion — Новые игровые и ИИ-модули.** Масштабное расширение функциональности BankBot с добавлением 5 новых модулей:
- 🎮 **Geometry Dash** (30%): ✅ **GD-02-03 completed** — команда /submit для отправки прохождений, админ-панель /moderate для модерации, статистика игроков
- ♟ **Chess** (20%): интеграция с Lichess API, задачи с наградами, статистика
- 🌟 **Universe** (15%): олеговирус, LTL-паразит, чайная религия, ИИ-генерация лора
- 🤖 **AI** (15%): ✅ **ЗАВЕРШЁН** — менеджер моделей с автопереключением (HF/OpenRouter/Ollama), диалоги с персонажами, генерация молитв, база знаний канона
- 🧑‍🏫 **Mom Module** (20%): ✅ **ЗАВЕРШЁН** — веб-приложение для детей с умственной отсталостью (1 класс), 6 предложений, 2-3 вопроса, проверка ответов, печать единым листом, генерация через HF API

**Приоритет реализации:** ✅ AI Module (завершён) → ✅ Mom Module (завершён) → ✅ GD-02-03 (completed) → ✅ GD-TEST-1-3 (completed) → GD-04-07 → Chess → Universe Commands.

Детальный план с подзадачами и критериями завершения зафиксирован в `memory_bank/phase2_implementation_plan.md`.

## Active Scope Change — HF Webhook Migration
**Status:** этап 1 completed locally, awaiting user approval to commit/push. Canonical detailed plan: `memory_bank/hf_webhook_migration_plan.md`.

User-approved planning decisions:
- Move HF production BankBot from polling to Telegram webhook to eliminate recurring `getUpdates TimedOut` failures.
- Disable background tasks/periodic loops in HF webhook runtime.
- Keep only `/short` and `/long` from response-mode/watch area; disable `/watch`, ADB and ntfy realtime/watch flows.
- Remove non-working modules from production runtime: `/shop`, `/games`, `/dnd` and related buy/game/dnd handlers.
- Remove BridgeBot and VK Bot from production HF runtime.
- Keep core bank/parsing/admin basics: `/start`, `/user`/`/profile`, `/balance`, `/history`, `/stats`, admin balance tools, feedback if it does not block webhook.
- Keep secure parsing only via real Telegram reply; do not restore unsafe manual text-paste fallback because it enables cheating.
- User approved starting the first implementation stage on 2026-05-20.
- Deployment rule from user: push only to GitHub; do not push/upload to Hugging Face.

### Этап 1 implementation notes
- `run_bot.py` converted into HF Flask + Telegram webhook entrypoint with `POST /telegram/webhook/<secret>`.
- Production HF runtime does not start polling and does not start BridgeBot/VK Bot.
- `TelegramBot` has webhook initialization path (`initialize_for_webhook`/`shutdown_for_webhook`) with background tasks disabled and shop bootstrap skipped.
- HF webhook runtime registers disabled handlers for removed production commands so users get an explicit answer instead of silence.
- Disabled module imports are deferred to local/dev polling runtime only; HF webhook mode never imports shop/games/dnd/watch/background modules.
- `/health` returns `telegram_runtime: webhook` and `webhook_configured: true/false`.
- `RUN.md` updated: HF webhook-first instructions, removed `/watch`, `/shop`, `/games` from examples.
- Smoke tests added for webhook route existence and security (invalid secret/header rejection).

## Статус проекта: 100% (базовый функционал) + HF Deployment Phase

## Последнее обновление: 2026-05-29

## Выполнено недавно
- ✅ Mom Module завершён (MOM-01-04): веб-приложение с двумя экранами, регулировка шрифта (24-72px), HF API генерация с fallback, проверка ответов, печать единым листом
- ✅ GD-02 /submit: команда для отправки прохождений GD с ConversationHandler, предпросмотром, сохранением в БД
- ✅ GD-03 /moderate: админ-панель с пагинацией, approve/reject кнопками, авто-обновлением PlayerStats и LevelCompletion
- ✅ GD-TEST-1: Unit tests для GD Module (10 тестов, ConversationHandler и DB persistence)
- ✅ GD-TEST-2: Unit tests для GD models (15 тестов, Submission, PlayerStats, Level, LevelCompletion)
- ✅ GD-TEST-3: Unit tests для PlayerStats logic (12 тестов, state transitions, calculations, integration)
- ✅ Testing strategy добавлена в projectbrief.md: GD-TEST, CH-TEST, UN-TEST, AI-TEST, MOM-TEST (33 unit + 18 integration + 11 total tests)
- ✅ projectbrief.md обновлён: Phase 2 прогресс 26% → 43%, MOM-01-04, GD-02-03, GD-TEST-1-3 статус completed
- ✅ progress.md обновлён: добавлен changelog за 2026-05-30 (GD-03)
- ✅ activeContext.md обновлён: Mom Module, GD-02-03, GD-TEST-1-3 помечены как завершённые
- 🔄 GD-04-07: следующий приоритет — логика сложности, статистика, GD API интеграция
- ✅ Поддержка прокси в `src/config.py` и `bot/bot.py`.
- ✅ Реализован скрипт `bot/check_proxy.py` для диагностики сетевых соединений.
- ✅ Проверена доступность IP Telegram API (tgproxy.me) из среды Hugging Face (Status 200).
- ✅ Настроен `bot.py` на использование `base_url="https://api.telegram.org/bot/"` с завершающим слэшем для обхода фильтров.
- ✅ Проект успешно пушится на GitHub и Hugging Face одновременно.
- 🔄 HF deploy hardening: текущая попытка убирает нестабильный IP/Host-header hack и переводит Telegram network config на явный `TELEGRAM_BASE_URL` + обычные PTB timeout/proxy настройки.
- 🔄 HF network follow-up: прямой `api.telegram.org` из Space уходит в TLS timeout; добавлен Hugging Face fallback `http://tgproxy.me/bot/` при отсутствии явного `TELEGRAM_BASE_URL`.
- 🔄 HF VPN option: начата интеграция sing-box в Docker runtime; секрет `VPN_SUBSCRIPTION_URL` должен храниться только в Hugging Face Space secrets, локальный proxy — `http://127.0.0.1:1080`.
- 🔄 HF VPN parser: subscription определён как base64-список VLESS URI; добавлена генерация sing-box config из VLESS Reality nodes.
- 🔄 HF VPN parser fix: неподдерживаемый `xhttp` node пропускается; при local proxy Telegram base_url остаётся `api.telegram.org`.


## Сводка
| Метрика | Значение |
|---------|----------|
| bot/bot.py | 1820 строк (было 3923) |
| Удалено | ~2103 строк (54%) |
| ruff errors | 0 (продакшн) |
| Тесты unit | 745 passed, 10 skipped, 37 new (GD-TEST-1-3) |
| Предупреждения pytest | 0 в smoke-проверках |
| Mom Module | ✅ завершён (MOM-01-04, 19%) |
| GD-02 | ✅ завершён (команда /submit) |
| GD-03 | ✅ завершён (админ-панель /moderate) |
| GD-TEST-1 | ✅ завершён (10 unit tests) |
| GD-TEST-2 | ✅ завершён (15 unit tests) |
| GD-TEST-3 | ✅ завершён (12 unit tests) |
| Phase 2 прогресс | 43/100 (GD-01: 5%, GD-02: 4%, GD-03: 5%, GD-TEST-1: 1%, GD-TEST-2: 1%, GD-TEST-3: 1%, CH-01: 2%, UN-01: 4%, UN-02: 4%, AI: 15%, MOM: 19%) |

## Project Deliverables
- D01-D27: 100% (weights sum = 100 ✓)
- MOM-01-04: 100% (weights sum = 19% ✓)
- GD-02: 100% (weights sum = 4% ✓)
- GD-03: 100% (weights sum = 5% ✓)
- GD-TEST-1: 100% (weights sum = 1% ✓)
- GD-TEST-2: 100% (weights sum = 1% ✓)
- GD-TEST-3: 100% (weights sum = 1% ✓)

## Выполнено (F01-F13, G01-G05, Phase 2-3)
- ✅ F01-F13: Roadmap completed
- ✅ G01: 62 → 0 failed tests
- ✅ G02: buy_N + admin commands extracted (164 lines removed)
- ✅ G03-G05: Phase 2 completed
- ✅ H01: Все команды извлечены:
  - D&D: dnd_command, dnd_create, dnd_join, dnd_sessions, dnd_roll
  - Achievements: achievements_command
  - Motivation: daily_bonus, challenges, motivation_stats
  - Notifications: notifications, notifications_clear
  - Social: friends, friend_add, friend_accept, gift, clan, clan_create, clan_join, clan_leave
  - Games: games, play, join, startgame, turn (ранее)
- ✅ MOM-01-04: Mom Module завершён (веб-приложение, HF API, проверка ответов, печать)
- ✅ GD-02: /submit command завершён (ConversationHandler, media upload, DB persistence)
- ✅ GD-03: /moderate admin panel завершён (pagination, approve/reject, auto-update stats)
- ✅ GD-TEST-1: Unit tests завершены (10 тестов, ConversationHandler + DB persistence)
- ✅ GD-TEST-2: Unit tests завершены (15 тестов, Submission, PlayerStats, Level, LevelCompletion models)
- ✅ GD-TEST-3: Unit tests завершены (12 тестов, PlayerStats logic, state transitions, integration)

## Phase 3 Roadmap
- ✅ H01: Извлечь команды — ЗАВЕРШЕНО (891 строк, −77%)
- ✅ H02: Alembic миграции — ЗАВЕРШЕНО
- ✅ H03: Prometheus метрики — ЗАВЕРШЕНО (metrics_server.py)
- ✅ H04: Ruff cleanup — ЗАВЕРШЕНО (F541, F811, E712 автофиксы)
- ✅ H05: BridgeBot тесты — ЗАВЕРШЕНО (test_bridge_loop_guard, test_bridge_queue)
- ✅ H06: Redis кэширование — ЗАВЕРШЕНО (utils/redis_cache.py)

## Post-Release Priorities
- MAX/P0: новый модуль диалогового кодера текстовых шаблонов — planned (`memory_bank/dialog_template_coder_module.md`)
- P0: аудит схемы БД, миграций и runtime-совместимости — выполнен (PR01)
- P0: унификация env-переменных и entrypoint-сценариев — выполнено (PR02-PR03)
- P1: синхронизация `README.md`, `RUN.md`, `docs/README.md` — выполнено (PR04)
- P1: устранение оставшихся `pytest` warnings — выполнено (PR05)
- P1: smoke startup tests для BankBot, BridgeBot, VK Bot — выполнено (PR07)
- P1: ревизия Docker/Compose — выполнено (PR08)
- P1: Release checklist и runbook — выполнено (PR09)
- P2: архитектурная инвентаризация слоёв и сокращение legacy-дублей (PR10-PR13)

## Текущий checkpoint
- MOM-01-04: Веб-приложение «Тренажёр чтения и понимания» полностью реализовано и готово к использованию.
- MOM-01: Статика HTML/CSS/JS с двумя экранами (чтение/вопросы), регулировка шрифта (24-72px), адаптивный дизайн для телефонов/планшетов, крупные кнопки (44x44px+).
- MOM-02: Хостинг в `webapp/reading_trainer/`, `public/reading_trainer.html`, команда `/reading_trainer` в боте.
- MOM-03: Backend `/reading_generate` в `run_bot.py` с HF API (mistralai/Mistral-7B-Instruct-v0.2, таймаут 15 сек) и fallback-наборами (3 набора по 6 предложений + 2-3 вопроса).
- MOM-04: Фронтенд-логика в `app.js`: загрузка через fetch(), проверка ответов (регистронезависимое сравнение), печать единым листом (предложения + вопросы с пустыми строками), регулировка шрифта с localStorage.
- GD-02: Команда `/submit` реализована в `bot/commands/gd_commands_ptb.py`:
  - ConversationHandler с 3 состояниями: ввод уровня → загрузка медиа → подтверждение
  - Поддержка видео и фото
  - Предпросмотр медиа перед отправкой
  - Сохранение в `submissions` таблицу с полями: user_id, level_name, media_file_id, media_type, status
  - Автоматическое обновление `player_stats.total_submissions`
  - Fallback для уровней, ещё не добавленных в БД
- GD handlers подключены в `bot/bot.py`
- GD-TEST-1: Unit tests в `tests/unit/test_gd_commands.py` (10 тестов)
- GD-TEST-2: Unit tests в `tests/unit/test_gd_models.py` (15 тестов)
- GD-TEST-3: Unit tests в `tests/unit/test_gd_player_stats.py` (12 тестов)
- Testing strategy добавлена в `projectbrief.md`: GD-TEST (8 unit + 5 integration + 3 total), CH-TEST, UN-TEST, AI-TEST, MOM-TEST (всего 33 unit + 18 integration + 11 total tests)
- Локальная проверка: `py -3.12 -m ruff check ...` -> passed; `py -3.12 -m py_compile ...` -> passed
- **Phase 2 прогресс: 38/100 (38%)**
- **GD Module: 38% (GD-01: 5%, GD-02: 4%, GD-TEST-1: 1%, GD-TEST-2: 1%, GD-TEST-3: 1%, remaining: 26%)**
- **Следующий приоритет:** GD-TEST-4 (integration tests), GD-03 (админ-панель /moderate)

## PR01 Result
- SQLAlchemy metadata содержит 24 таблицы, ранние Alembic-миграции покрывали только часть схемы
- Исправлен `database/alembic/env.py`: удалён битый импорт `database.models`
- Добавлена миграция `003_create_missing_tables.py` для создания отсутствующих таблиц из текущего metadata
- Добавлен helper `database/schema.py` с Alembic-first обновлением схемы и fallback на `create_tables()`
- `bot/main.py` и `bot/bot.py` переведены на `ensure_schema_up_to_date()`

## Parsing System Implementation Plan (Current)
**Status:** Completed ✅ | **Priority:** P0 (GDcards priority)

### Этап 1: Database Models ✅
- `UserResource` model: tracks internal `n` per user/bot/resource
- `ConversionRate` model: stores coefficient `k` per bot/resource pair
- Migration `005_add_parsing_resources.py` created

### Этап 2: Parsing Service ✅
- `ParsingService` in `bank_bot/services/parsing_service.py`
- Regex patterns for all 3 bots (GDcards priority)
- **NEW:** Shmalala karma patterns (❤️ rating messages)
- **NEW:** GDcards profile patterns (`Орбы: X (#Y)` format)
- **NEW:** `parse_profile_and_accrue()` with delta logic: (current_balance - stored_n) * k
- Logic: detect bot → extract `b` → get `k` → calculate `b*k` → update `n` and balance
- Error handling: unrecognized data, negative values

### Этап 3: Handler Update ✅
- Updated `bot/handlers/parsing_handler.py` with `handle_target_bot_parsing()` method
- **NEW:** Routes both accrual messages (+X) and profile messages (current balance)
- New method uses `ParsingService`, falls back to legacy parser for other games
- Maintains idempotency and existing game support

### Этап 4: Tests ✅
- `tests/unit/test_parsing_service.py` — 29 tests, all passing (was 20)
- GDcards priority coverage: detection, extraction, full accrual flow, multiple accruals
- **NEW:** GDcards profile: detection, extraction, delta accrual, no-change scenario
- **NEW:** Shmalala karma: detection, extraction, accrual with k=0.5
- Gusya Cards and Shmalala money coverage complete
- Error handling tests: unrecognized message, negative amount, user not found, missing rate

### Этап 5: Validation ✅
- ruff: 0 errors across all new files
- Tests: 29/29 passed
- Memory bank updated

### Этап 6: Commit & Push ✅
- GitHub: `3eb7377` feat(parsing): add karma parsing for Shmalala and profile parsing for GDcards
- HF: uploaded
