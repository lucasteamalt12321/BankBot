# Active Context

## Текущий фокус
**MAX/P0: новый модуль диалогового кодера текстовых шаблонов.** Пост-релизная стабилизация и pending P2-задачи (`PR10–PR13`) отходят ниже по приоритету до планирования/реализации этого модуля.

## Статус проекта: 100%

## Последнее обновление: 2026-04-17

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
- M01: пользователь предоставил полный список 500 троек `(A,B,C)`; в ТЗ зафиксирован статус данных и правило третьего уровня `{1,2,3,5,10}`.
- M01: пользователь предоставил таблицу 10 одиночных значений; все данные для модуля теперь определены.
- M01 next: перенести 10 одиночных значений, 100 базовых пар и 500 троек из пользовательских списков в JSON/код, затем реализовать диалоговую логику.
- smoke-тесты синхронизированы с текущими экспортами конфигурации и startup flow
- `tests/pytest.ini` дополнен `asyncio_default_fixture_loop_scope = function`
- `src/config.py` синхронизирован: `DynamicSettings` теперь читает feature flags, cache и debug/test поля так же, как основной `Settings`
- `RUN.md` и `config/.env.example` синхронизированы с фактическими именами env-переменных и Windows/PowerShell-командами
- `docs/README.md` переписан как актуальная high-level карта проекта без устаревших метрик, старых путей и неактуальных статусов
- `README.md` и `docs/DEPLOYMENT.md` синхронизированы с текущими entrypoints, Docker-сценариями и конфигурацией
- локальная проверка: `py -3.13 -m pytest tests/smoke -v` -> 9 passed
- локальная проверка: `py -3.13 -m ruff check src/config.py tests/smoke/test_startup.py` -> passed

## PR01 Result
- SQLAlchemy metadata содержит 24 таблицы, ранние Alembic-миграции покрывали только часть схемы
- Исправлен `database/alembic/env.py`: удалён битый импорт `database.models`
- Добавлена миграция `003_create_missing_tables.py` для создания отсутствующих таблиц из текущего metadata
- Добавлен helper `database/schema.py` с Alembic-first обновлением схемы и fallback на `create_tables()`
- `bot/main.py` и `bot/bot.py` переведены на `ensure_schema_up_to_date()`
