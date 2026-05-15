# Active Context

## Текущий фокус
**Деплой на Hugging Face Spaces завершён.** Бот работает стабильно: polling loop активен, health endpoint отвечает, SSL/DNS проблемы решены через `socket.getaddrinfo` monkey patch.

## Статус проекта: 100% (базовый функционал) + HF Deployment ✅

## Последнее обновление: 2026-05-15

## Выполнено недавно
- ✅ Flask health/metrics/logs сервер на порту `7860` в `run_bot.py`.
- ✅ Dockerfile обновлён до `python:3.12-slim` с health check на `:7860/health`.
- ✅ `bot/main.py` — Alembic-first миграции до инициализации систем.
- ✅ `config_manager` — защита от отсутствующих таблиц БД при первом запуске.
- ✅ HF Network: IP proxy + `Host: tgproxy.me` + `verify=False` + safe `http_client` builder.
- ✅ Обычная среда: `PROXY_URL` через `builder.proxy_url()` + увеличенные таймауты.
- ✅ `docs/DEPLOYMENT.md` — раздел Hugging Face Spaces с operational notes.


## Сводка
| Метрика | Значение |
|---------|----------|
| bot/bot.py | 891 строк (было 3923) |
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

## Текущий checkpoint
- **HF01 — Deployment Phase**: Flask health/metrics/logs сервер на `7860`, Dockerfile на `python:3.12-slim`, IP-based proxy (`195.201.225.248`) с `Host: tgproxy.me` + `verify=False`, safe `builder.http_client()` fallback. Осталась валидация полного цикла в HF среде.
- N02 increment: `NotificationSystem` расширен до multi-transport realtime доставки (`Telegram` + `ntfy` + optional `ADB`).
- N02 fix: команды `/notifications` и `/notifications_clear` теперь корректно мапят `telegram_id -> users.id`.
- N02 API cleanup: прямые вызовы `_send_to_ntfy()` заменены на `send_realtime_notification()`.
- N02 tests: `tests/unit/test_notification_system.py` — realtime fanout, ADB command build, user-id mapping.
- N02 command wiring: `/notify_status` и `/test_adb` подключены в `bot/bot.py`.
- M01: completed — диалоговый кодер текстовых шаблонов с `/coder`, `/help`, `/reset`, TTL 30 минут, 19 unit-тестов.
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
