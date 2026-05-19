# Active Context

## Текущий фокус
**Главный продуктовый фокус — PARSE01: production E2E автоматический парсинг игровых сообщений.** DB01/HF/runtime/UX уже стабилизировались как фундамент для парсинга; AI02 остаётся следующим P1 после прямых багов и PARSE01.

## Приоритет обработки задач
1. Баги, на которые прямо указывает пользователь.
2. Баги из `/feedback`.
3. Текущий фокус разработки.
4. Советы/улучшения из `/feedback`.

## Статус проекта: 90% (канонически по Project Deliverables) + HF Deployment ✅

## Последнее обновление: 2026-05-19

## Выполнено недавно
- ✅ DB01 production activation: Hugging Face `DATABASE_URL` secret установлен на Supabase Session Pooler (`aws-0-eu-west-1.pooler.supabase.com:5432`), `/health` показывает `database=postgresql`.
- ✅ DB01 implementation: env aliases, Alembic URL override, empty PostgreSQL bootstrap, SQLAlchemy-based AdminSystem, DB backend health diagnostics, PostgreSQL connect timeout.
- ✅ DB01 deploy issue resolved: duplicate public/secret `DATABASE_URL` fixed; direct IPv6 URI replaced with Supabase pooler URI.
- ✅ DB01 regressions fixed: `/user`, `/start`, AI help, parsing/admin/shop legacy sqlite call sites migrated or fixed; `/health` stable on PostgreSQL.
- ✅ DB01 final verification: `/health` возвращает `database=postgresql`, external `/feedback?limit=N` возвращает `storage=postgresql`; SQLite fallback больше не используется в production health/feedback path.
- ✅ AI01 implemented/deployed: бесплатный AI-lite помощник для `/ai`, `/ask`, `/ai_help` без обязательных внешних ключей; отвечает по командам BankBot и локальной базе канона Олеговируса/LTL из Google Doc.
- ✅ Earlier `/start`, `/user`, `/ai` direct user-reported regressions have corresponding hotfixes deployed to HF.
- ✅ AI01 canon/UX handled: добавлены `bot/ai/knowledge.py`, глоссарий, статьи высокого канона, short/long ответы; исправлено ранжирование, чтобы `олеговирус` не подтягивал нерелевантные правила/запреты.
- 🔄 Next focus AI02: Никита предложил бесплатный Hugging Face API для более умных ответов. Делать только optional/free, с локальным AI-lite fallback, короткими timeout, лимитами prompt/response и без логирования секретов.
- ✅ HF polling hardening revised: внешний retry-loop вокруг `run_polling()` убран; PTB сам ведёт polling, а на HF `drop_pending_updates=False`, чтобы команды не терялись при сетевой нестабильности.
- ✅ HF `/start` safety: на Hugging Face `/start` по умолчанию отвечает одним коротким сообщением, без длинного welcome и без дополнительного template-coder hint; если пользователь включил `/long`, `/start` уважает режим и отдаёт полный welcome. `drop_pending_updates=False` на HF сохраняет команды при сетевых reconnect.
- ✅ Командная иерархия уточнена: `/commands` — список разделов, `/user` — профиль игрока, `/shop`/`games`/`admin`/`coder` сохраняют старый функционал или разделные подсказки по назначению.
- ✅ D&D command wiring исправлен: `/dnd_create`, `/dnd_join`, `/dnd_roll`, `/dnd_sessions` проходят через wrapper-методы `TelegramBot` с передачей `get_db`.
- ✅ Игровые подсказки `/play`, `/join`, `/startgame`, `/turn` переведены с транслита на русский и стали понятнее для команд без аргументов.
- ✅ FB01: добавлена предложка/жалобы — `/feedback <текст>` (`/suggest`, `/complaint`) сохраняет обращения в SQLite-таблицу `feedback_entries` с JSONL fallback; `/feedback_list [limit]` показывает последние записи администратору.
- ✅ PR10-PR13 закрыты: архитектурный runtime/legacy contract зафиксирован в `docs/README.md`, рискованные shim-слои не удалялись, polling kwargs вынесены в чистый builder, UX/watchlist игровых/D&D/shop команд закрыт безопасными правками.
- ✅ Flask health/metrics/logs сервер на порту `7860` в `run_bot.py`.
- ✅ Dockerfile обновлён до `python:3.12-slim` с health check на `:7860/health`.
- ✅ `bot/main.py` — Alembic-first миграции до инициализации систем.
- ✅ `config_manager` — защита от отсутствующих таблиц БД при первом запуске.
- ✅ HF Network: IP proxy + `Host: tgproxy.me` + `verify=False` + safe `http_client` builder.
- ✅ Обычная среда: `PROXY_URL` через `builder.proxy_url()` + увеличенные таймауты.
- ✅ `docs/DEPLOYMENT.md` — раздел Hugging Face Spaces с operational notes.
- ✅ Global response modes: `bot/response_modes.py` патчит `Message.reply_text`; в `/short` длинные ответы всех разделов автоматически компактятся, в `/long` отправляется полный текст.
- ✅ Response mode scope change: `/short` и `/long` работают как личный выбор пользователя; админские `/short_all` и `/long_all` задают общий default всем, после чего каждый пользователь может снова выбрать личный режим.
- ✅ Watch mode documented/implemented: `/watch` и `/watch_all`, сверхкороткие ответы для часов и управление через 10 шаблонов (`ОК`, `Да`, `Спасибо`, `Спасибо нет`, `Великолепно`, `Спасибо еще раз`, `Скоро увидимся`, `Скоро буду`, `Я занят(а)`, `Нет`); `Я занят(а)` включает watch mode для конкретного пользователя.
- ✅ Documentation refresh: `README.md`, `RUN.md`, `docs/README.md` синхронизированы с текущими BankBot возможностями, HF/PostgreSQL runtime, response modes, feedback, AI-lite и админ-командами.
- 🔄 Product positioning corrected: парсинг игровых сообщений зафиксирован как самая важная цель проекта; текущий банк/админка/PostgreSQL/HF/feedback/watch/AI-lite описаны как фундамент вокруг парсинга, а не замена парсинга. Автоматический production E2E parsing выделен как PARSE01/in_progress.
- ✅ Документация уточнена: для пользовательской проверки проект клонировать не нужно, актуальный bot можно тестировать в https://t.me/lucasteamgroup; локальный запуск нужен только для разработки.
- 🔄 Project Deliverables пересчитаны на 90/100: D10 и D18 оставлены `in_progress`, потому что production E2E parsing ещё не завершён.


## Сводка
| Метрика | Значение |
|---------|----------|
| Канонический прогресс | 90/100 |
| bot/bot.py | modular runtime, размер меняется по hotfix-итерациям |
| Удалено | ~3032 строк (77%) |
| ruff errors | 0 (продакшн) |
| Тесты unit | 745 passed, 10 skipped |
| Предупреждения pytest | 0 в smoke-проверках |

## Project Deliverables
- D01-D27: 100% (weights sum = 100 ✓)

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
  - ✅ PR10-PR13 completed: documentation-first legacy freeze + safe wiring/runtime cleanup.

## Текущий checkpoint
- **HF01 — Deployment Phase**: Flask health/metrics/logs сервер на `7860`, Dockerfile на `python:3.12-slim`, DNS bypass через `socket.getaddrinfo`/`anyio` monkey patch для `api.telegram.org`, `httpx.AsyncClient(verify=False)` в HF, safe short `/start`; внешний polling retry-loop снят, `drop_pending_updates=False` на HF.
- N02 increment: `NotificationSystem` расширен до multi-transport realtime доставки (`Telegram` + `ntfy` + optional `ADB`).
- N02 fix: команды `/notifications` и `/notifications_clear` теперь корректно мапят `telegram_id -> users.id`.
- N02 API cleanup: прямые вызовы `_send_to_ntfy()` заменены на `send_realtime_notification()`.
- N02 tests: `tests/unit/test_notification_system.py` — realtime fanout, ADB command build, user-id mapping.
- N02 command wiring: `/notify_status` и `/test_adb` подключены в `bot/bot.py`.
- M01: completed — диалоговый кодер текстовых шаблонов с `/coder`, `/help`, `/reset`, TTL 30 минут, 19 unit-тестов.
- FB01: completed — пользовательская предложка и жалобы с SQLite-хранилищем, JSONL fallback, админским просмотром и защищённым external reader `/feedback`.
- AI01: completed/deployed — `bot/ai/service.py`, `bot/ai/knowledge.py`, `bot/commands/ai_commands.py`, команды `/ai`, `/ask`, `/ai_help`, локальная canon KB, global `/short`/`/long`, 19 AI/unit tests без внешних API.
- Startup resilience: `config_manager` проверяет `inspector.has_table("parsing_rules")` до запроса; `bot/main.py` делает `ensure_schema_up_to_date()` первым делом.
- Runtime lesson: локальный BankBot — только `Python 3.12`; `3.14` вызывает crash в `python-telegram-bot==20.7`.
- Env split: `config/.env.shared` (committable) + `config/.env.local` (secrets), fallback на legacy `config/.env`.
- Документация: `README.md`, `RUN.md`, `docs/README.md`, `docs/DEPLOYMENT.md` синхронизированы с текущим кодом и деплоем.

## PR01 Result
- SQLAlchemy metadata содержит 24 таблицы, ранние Alembic-миграции покрывали только часть схемы
- Исправлен `database/alembic/env.py`: удалён битый импорт `database.models`
- Добавлена миграция `003_create_missing_tables.py` для создания отсутствующих таблиц из текущего metadata
- Добавлен helper `database/schema.py` с Alembic-first обновлением схемы и fallback на `create_tables()`
- `bot/main.py` и `bot/bot.py` переведены на `ensure_schema_up_to_date()`
