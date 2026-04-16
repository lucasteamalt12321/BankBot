# Active Context

## Текущий фокус
**Пост-релизная стабилизация и прокачка проекта: runtime, БД, документация, тесты и деплой.**

## Статус проекта: 100%

## Последнее обновление: 2026-04-06

## Сводка
| Метрика | Значение |
|---------|----------|
| bot/bot.py | 891 строк (было 3923) |
| Удалено | ~3032 строк (77%) |
| ruff errors | 0 (продакшн) |
| Тесты unit | 745 passed, 10 skipped |
| Предупреждения pytest | 5 (было 9) |

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
- P0: аудит схемы БД, миграций и runtime-совместимости
- P0: унификация env-переменных и entrypoint-сценариев
- P1: синхронизация `README.md`, `RUN.md`, `docs/README.md`
- P1: устранение оставшихся `pytest` warnings и async warning в background tests
- P1: smoke startup tests для BankBot, BridgeBot, VK Bot
- P1: ревизия Docker/Compose и health/readiness checks
- P2: архитектурная инвентаризация слоёв и сокращение legacy-дублей
