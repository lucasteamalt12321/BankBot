# Active Context

## Текущий фокус
**Интеграция прокси и настройка уведомлений.** Добавлена поддержка HTTP-прокси для обхода блокировок Telegram, исправлены ошибки HTML-разметки в командах, и начата работа над системными уведомлениями через ADB/ntfy.

## Статус проекта: 100% (базовый функционал) + расширения

## Последнее обновление: 2026-05-04

## Выполнено недавно
- ✅ Поддержка прокси в `src/config.py` и `bot/bot.py`.
- ✅ Исправлено экранирование HTML в `WELCOME_TEXT` и обработчике ошибок.
- ✅ `NotificationSystem` переведена на асинхронную работу с отправкой в Telegram.
- ✅ Добавлены команды `/ping` и `/test_notify`.
- ✅ Реализован модуль диалогового кодера (M01).


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
- N02 increment: `NotificationSystem` расширен до multi-transport realtime доставки (`Telegram` + `ntfy` + optional `ADB`).
- N02 fix: команды `/notifications` и `/notifications_clear` теперь корректно мапят `telegram_id -> users.id`, чтобы читать/очищать `user_notifications` для правильного пользователя.
- N02 API cleanup: прямые вызовы приватного `_send_to_ntfy()` в `ping` и template coder заменены на публичный `send_realtime_notification()`.
- N02 config: в `src/config.py` и `config/.env.example` добавлены `NTFY_ENABLED`, `NTFY_BASE_URL`, `NTFY_TAGS`, `NTFY_TIMEOUT_SECONDS`, `ADB_NOTIFICATIONS_ENABLED`, `ADB_PATH`, `ADB_DEVICE_SERIAL`.
- N02 tests: добавлен `tests/unit/test_notification_system.py` для realtime fanout, ADB command build и notification command user-id mapping.
- N02 command wiring: диагностические команды `/notify_status` и `/test_adb` подключены в `bot/bot.py`.
- N02 diagnostics: `notify_status_command` больше не использует заглушку `if True`, статус Telegram realtime определяется по конфигурации `BOT_TOKEN`.
- N02 tests increment: в `tests/unit/test_notification_system.py` добавлены проверки для `notify_status_command` и disabled-сценария `test_adb_command`.
- Локальная валидация в текущей среде: `py -3.12 -m ruff check bot/commands/notification_commands_ptb.py tests/unit/test_notification_system.py bot/bot.py utils/monitoring/notification_system.py` -> passed; `pytest` не запущен, т.к. в доступных Python 3.12/3.14 отсутствует установленный модуль `pytest`.
- Runtime lesson: локальный запуск основного BankBot зафиксирован на `Python 3.12`; на `Python 3.14` воспроизведён crash внутри `python-telegram-bot==20.7` при инициализации `Updater`.
- Runtime docs sync: `README.md`, `RUN.md`, `docs/README.md`, `docs/DEPLOYMENT.md` обновлены и теперь явно требуют `py -3.12` для локального запуска и проверок.
- Runtime verification: `py -3.12 -m pip install -r requirements-dev.txt` -> completed; `py -3.12 run_bot.py` проходит startup, wiring handlers и background tasks, после чего упирается в сетевой `httpx.ConnectError` при polling (внешняя доступность Telegram API/прокси), а не в runtime-ошибки Python/PTB.
- Env split: конфигурация разделена на два слоя — коммитируемый `config/.env.shared` и локальный секретный `config/.env.local`; загрузка реализована в `src/config.py` с fallback на legacy `config/.env`.
- Env templates: `config/.env.example` заменён на `config/.env.shared.example` и `config/.env.local.example`; `.gitignore` обновлён так, чтобы `config/.env.local*` не коммитился, а `config/.env.shared` мог коммититься.
- Env startup validation: `src/startup_validator.py` теперь считает валидными `config/.env.shared` / `config/.env.local`; smoke-запуск с новой схемой проходит.
- M01: пользователь предоставил полный список 500 троек `(A,B,C)`; в ТЗ зафиксирован статус данных и правило третьего уровня `{1,2,3,5,10}`.
- M01: пользователь предоставил таблицу 10 одиночных значений; все данные для модуля теперь определены.
- M01 implementation in progress: добавлены `bot/template_coder/*`, подключение в `bot/bot.py`, unit-тесты `tests/unit/test_template_coder.py`.
- M01 data migration: 10 одиночных значений, 100 пар и все 500 троек перенесены в `bot/template_coder/data.py`; временный fallback генерации троек удалён.
- M01 validation: `validate_data()` проверяет полноту таблиц 10/100/500 при импорте.
- M01 commands: добавлен пользовательский entrypoint `/coder`, `/help` показывает описание модуля и 10 шаблонов, `/reset` сбрасывает состояние.
- M01 `/start`: основной `/start` дополнительно отправляет краткую подсказку по диалоговому кодеру и командам `/coder`, `/reset`, `/help`.
- M01 group command routing: `handle_mentioned_commands` поддерживает `/coder@bot`, `/help@bot`, `/reset@bot` наряду с `/start@bot`.
- M01 `/start` теперь полноценно сбрасывает состояние диалогового кодера перед приветствием, как требует ТЗ.
- M01 TTL: состояние содержит `updated_at`; активная последовательность сбрасывается после 30 минут бездействия.
- M01 adapter tests: покрыты обработка шаблона, игнор обычного текста без активного состояния, auto-reset expired state, `/reset` command.
- M01 status: completed на уровне кода и unit/smoke-проверок.
- Локальная проверка: `python -m pytest tests/unit/test_template_coder.py -q` -> 19 passed; `python -m ruff check bot/template_coder tests/unit/test_template_coder.py bot/bot.py` -> passed.
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
