# Project Brief — BankBot (LucasTeam)

## Цели проекта

Telegram-бот-агрегатор для автоматического отслеживания игровой активности и начисления банковских монет. Объединяет несколько игровых платформ в единую экосистему с общей валютой (банковские монеты).

## Рамки проекта

- Поддержка 4 игровых платформ: GD Cards, Shmalala, True Mafia, Bunker RP
- Единый баланс и магазин для всех игр
- Система достижений, социальные функции, мини-игры
- Административная панель с рассылками
- Автоматический и ручной парсинг игровых сообщений

## Репозиторий

https://github.com/lucasteamalt12321/BankBot

## Точка входа

`run_bot.py` → `bot/main.py`

---

## Project Deliverables

| ID | Deliverable | Status | Weight |
|----|-------------|--------|--------|
| D01 | Централизованная конфигурация (Pydantic Settings) | completed | 5 |
| D02 | Вынос конфиденциальных данных в env | completed | 5 |
| D03 | Разделение зависимостей (requirements) | completed | 4 |
| D04 | Исправление импортов | completed | 3 |
| D05 | Слой репозиториев (Repository pattern) | completed | 7 |
| D06 | Service layer (бизнес-логика из handlers) | completed | 5 |
| D07 | Рефакторинг bot.py на модули | completed | 5 |
| D08 | Middleware обработки ошибок | completed | 5 |
| D09 | Graceful shutdown | completed | 4 |
| D10 | ParserRegistry + конфигурация парсинга в БД (инфраструктура) | completed | 5 |
| D11 | Блокировки балансов + Unit of Work | completed | 5 |
| D12 | Connection pooling | completed | 3 |
| D13 | Аудит SQL injection | completed | 5 |
| D16 | Аудит и очистка неиспользуемого кода | completed | 4 |
| D17 | Объединение дублирующихся парсеров | completed | 3 |
| D18 | E2E тесты основных сценариев | completed | 4 |
| D19 | Тесты безопасности (SQL injection, race conditions) | completed | 3 |
| D20 | Coverage 80%+ | completed | 3 |
| D21 | Документация (README, DEPLOYMENT.md, диаграммы) | completed | 3 |
| D22 | Docstrings Google style | completed | 2 |
| D23 | Bridge-модуль: конфигурация + миграция bridge_state | completed | 3 |
| D24 | Bridge-модуль: loop_guard, message_queue, vk_sender | completed | 4 |
| D25 | Bridge-модуль: telegram_forwarder, vk_listener, main_bridge | completed | 4 |
| D26 | Bridge-модуль: media_handler (TG→VK, VK→TG) | completed | 3 |
| D27 | vk_bot/: config, bot, handlers, main | completed | 3 |

**Sum: 5+5+4+3+7+5+5+5+4+5+5+3+5+4+3+4+3+3+3+2+3+4+4+3+3 = 100**

**Процент выполнения:** 100% (D01–D27 completed = 100/100)

**Важное уточнение по парсингу:** таблица D01-D27 отражает завершение базового инфраструктурного roadmap, а не полную готовность production E2E автоматического парсинга. Парсинг игровых сообщений остаётся главной продуктовой целью проекта; текущий completed-статус D10 означает наличие ParserRegistry/конфигурации/ручного контура, но стабилизация автоматического парсинга на реальных игровых сообщениях должна вестись как новый post-release deliverable.

---

## Next Tasks (Post-Review Cleanup)

| ID | Task | Priority | Status |
|----|------|----------|--------|
| T01 | Исправить merge conflict markers в README.md | P0 | completed |
| T02 | Добавить BotApplication в bot/main.py | P0 | completed |
| T03 | Исправить test_user_manager.py — добавить BotApplication | P0 | completed |
| T04 | Исправить merge conflicts в тестах | P1 | completed |
| T05 | Ruff cleanup: 0 errors в продакшн коде | P2 | completed |
| T06 | Удалить лишние папки (examples/, for_programmer/, docs/archive/) | P2 | completed |
| T07 | Удалить test_*.db файлы | P2 | completed |

## Additional Tasks (2026-04-03)

| ID | Task | Priority | Status |
|----|------|----------|--------|
| T08 | BridgeBot: VK Bot публикация в канал | P0 | completed |
| T09 | Тесты BridgeBot + VK Bot (43 tests) | P0 | completed |
| T10 | Unified конфигурация (Pydantic Settings) | P1 | completed |
| T11 | Документация сокращена | P1 | completed |
| T12 | vk_listener.py перенесён в bridge_bot/ | P1 | completed |
| T13 | Рефакторинг bot/bot.py: извлечение команд | P1 | completed |
| T14 | PARSING_ENABLED=true | P2 | completed |
| T15 | Ruff cleanup, ruff.toml создан | P2 | completed |

---

## Future Improvements (Roadmap)

### Критические (Known Issues)

| ID | Task | Priority | Status |
|----|------|----------|--------|
| F01 | Исправить сломанные unit тесты (sys.path.insert root cause) | P0 | completed |
| F02 | Проверить и удалить merge conflict markers | P0 | completed |

### Высокий приоритет

| ID | Task | Priority | Status |
|----|------|----------|--------|
| F03 | CI/CD pipeline (GitHub Actions) | P1 | completed |
| F04 | Покрытие тестами core логики (balance, shop) | P1 | completed |
| F05 | E2E тесты для бота | P1 | completed |
| F06 | Webhook вместо polling (для прода) | P1 | completed |

### Средний приоритет

| ID | Task | Priority | Status |
|----|------|----------|--------|
| F07 | Документация API | P2 | completed |
| F08 | Мониторинг (метрики, алерты) | P2 | completed |
| F09 | Кэширование (Redis для баланса, профиля) | P2 | completed |
| F10 | Structured logging (JSON) | P2 | completed |

### Низкий приоритет

| ID | Task | Priority | Status |
|----|------|----------|--------|
| F11 | Микросервисы (разделение на сервисы) | P3 | completed |
| F12 | GraphQL API | P3 | completed |
| F13 | Kubernetes (autoscaling) | P3 | completed |

---

## Phase 2 Roadmap (2026-04-03)

### Средний приоритет

| ID | Task | Priority | Status |
|----|------|----------|--------|
| G01 | Исправить 62 сломанных unit тестов | P1 | completed |
| G02 | Рефакторинг bot/bot.py (разбить монолит) | P2 | completed |

### Низкий приоритет

| ID | Task | Priority | Status |
|----|------|----------|--------|
| G03 | Покрытие тестами managers (admin, sticker, background) | P2 | completed |
| G04 | Docker оптимизация (multi-stage build, health checks) | P3 | completed |
| G05 | Безопасность (rate limiting, финальный SQL audit) | P3 | completed |

**Примечание:** G02 выполнен — извлечены buy_N (8) и admin (16) команды. bot/bot.py: 2308 → 2144 строк.

---

## Phase 3 Roadmap (2026-04-05)

### Средний приоритет

| ID | Task | Priority | Status |
|----|------|----------|--------|
| H01 | Извлечь команды из bot/bot.py (games, dnd, motivation, social) | P2 | completed |
| H02 | Alembic миграции БД | P2 | completed |
| H03 | Интеграция Prometheus метрик | P2 | completed |

### Низкий приоритет

| ID | Task | Priority | Status |
|----|------|----------|--------|
| H04 | Ruff full cleanup (исправить F/E/W ошибки) | P3 | completed |
| H05 | Integration тесты BridgeBot (VK forwarding) | P3 | completed |
| H06 | Redis кэширование (кэш баланса) | P3 | completed |

**H01 notes:** bot/bot.py: 3923 → 891 строк (−77%). Созданы модули: dnd_commands_ptb.py, achievements_commands_ptb.py, social_commands_ptb.py, notification_commands_ptb.py, motivation_commands_ptb.py, game_commands_ptb.py

**H06 notes:** Создан Redis бэкенд для кэша (`utils/redis_cache.py`). Redis уже установлен (5.0.1). Добавлен `redis==5.0.1` в requirements.txt. Тесты: `tests/unit/test_redis_cache.py` (19 тестов).

---

## Post-Release Roadmap (2026-04-06)

### Короткий roadmap на 1-2 недели

#### Неделя 1
1. P0: Аудит схемы БД против SQLAlchemy-моделей и Alembic-миграций.
2. P0: Устранение runtime-расхождений схемы, проверка запуска на пустой БД.
3. P0: Унификация env-переменных и entrypoint-сценариев запуска.
4. P1: Синхронизация `README.md`, `RUN.md`, `docs/README.md` с реальным кодом и запуском.

#### Неделя 2
1. P1: Устранение оставшихся предупреждений `pytest`, особенно async/runtime warning в `background_task_manager`.
2. P1: Добавление smoke-проверок запуска BankBot, BridgeBot, VK Bot.
3. P1: Ревизия Docker/Docker Compose пути и health/readiness checks.
4. P2: Архитектурная зачистка legacy-слоёв и дублирующихся сервисов.
5. P2: Формализация release checklist и runbook для локального и production запуска.

## Technical Plan (Files and Modules)

### 1. БД и миграции
Файлы и модули:
- `database/database.py`
- `database/alembic/env.py`
- `database/alembic/versions/*.py`
- `database/initialize_system.py`
- `database/migrations/*`
- модели в `core/models/*`, `src/models/*`

Что сделать:
- сверить SQLAlchemy-модели с реальной схемой SQLite/Postgres
- проверить полноту Alembic-цепочки на чистой БД
- устранить запросы к отсутствующим колонкам и пропущенные индексы
- проверить bootstrap новой БД без локальных допущений

### 2. Конфигурация и запуск
Файлы и модули:
- `src/config.py`
- `bot/main.py`
- `run_bot.py`
- `bridge_bot/main.py`
- `vk_bot/main.py`
- `README.md`
- `RUN.md`
- `config/.env.example` или актуальный env-template

Что сделать:
- привести env-переменные к одному контракту
- выбрать канонический способ запуска каждого бота
- синхронизировать startup validation, документацию и runtime

### 3. Документация
Файлы:
- `README.md`
- `docs/README.md`
- `RUN.md`
- `docs/guides/*`

Что сделать:
- обновить структуру проекта, статистику и статус модулей
- выровнять install/init/start/test flow
- убрать устаревшие описания старых фаз и legacy-путей

### 4. Тесты и предупреждения
Файлы:
- `tests/pytest.ini`
- `tests/unit/test_background_task_manager.py`
- `tests/unit/test_add_admin_simple.py`
- `tests/unit/test_add_admin_verification.py`
- связанные async-моки в `tests/unit/*`

Что сделать:
- убрать remaining `pytest` warnings
- исправить async mock/await паттерны
- перевести verification-style тесты в строгие assert-based сценарии
- добавить smoke startup tests

### 5. BridgeBot и VK Bot
Файлы и модули:
- `bridge_bot/loop_guard.py`
- `bridge_bot/queue.py`
- `bridge_bot/main.py`
- `bridge_bot/handlers.py`
- `bridge_bot/vk_publisher.py`
- `vk_bot/main.py`
- `vk_bot/handlers.py`

Что сделать:
- проверить startup smoke path
- проверить loop prevention и queue без локальных assumptions
- добавить минимальные integration-checks для стартовых сценариев

### 6. Деплой и эксплуатация
Файлы:
- `docker-compose.yml`
- `Dockerfile`
- `utils/monitoring/*`
- `utils/redis_cache.py`

Что сделать:
- привести Docker/Compose к актуальному рабочему состоянию
- выровнять health/readiness
- проверить единый env-path для Docker и локального запуска

### 7. Архитектурная зачистка
Файлы и пакеты:
- `bot/*`
- `core/*`
- `src/*`
- `utils/*`
- `bank_bot/*`

Что сделать:
- определить канонические слои и legacy-пути
- сократить дубли сервисов и shim-слоёв
- уменьшить связность startup/wiring-кода

## Post-Release Backlog

| ID | Task | Priority | Status |
|----|------|----------|--------|
| M01 | Новый модуль: диалоговый кодер текстовых шаблонов | completed | MAX/P0 |
| PR01-PR09 | Стабилизация и smoke-тесты | completed | P0/P1 |
| N01 | Прокси и исправление HTML-ошибок | completed | P0 |
| N02 | Системные уведомления (ntfy/ADB) | completed | P1 |
| DB01 | Persistent PostgreSQL/Supabase storage для production/HF | completed | P0 |
| HF01 | Деплой на Hugging Face Spaces (Docker, Network Debug) | completed | P1 |
| FB01 | Предложка/жалобы для пользователей бота | completed | P1 |
| AI01 | Бесплатный локальный AI-lite помощник для команд и подсказок | completed | P1 |
| AI02 | Optional бесплатный Hugging Face Inference API для более умных ответов | pending | P1 |
| PARSE01 | Production E2E автоматический парсинг игровых сообщений | in_progress | P0 |

**N02 notes:** multi-transport realtime delivery (`Telegram + ntfy + optional ADB`), env-настройки ntfy/ADB, маппинг `telegram_id -> users.id`, unit-тесты `tests/unit/test_notification_system.py`, команды `/notify_status` и `/test_adb`.

**DB01 notes:** P0 / первая очередь. Проблема: на Hugging Face локальная SQLite/data storage ephemeral, при restart/rebuild база могла обнуляться. Production/HF подключён к persistent Supabase PostgreSQL через HF Secret `DATABASE_URL` с Session Pooler URI; `/health` подтверждает `database=postgresql`, external `/feedback?limit=N` подтверждает `storage=postgresql`. Реализовано: aliases DB URL, нормализация `postgres://` → `postgresql://`, Alembic URL override, bootstrap пустой PostgreSQL БД из SQLAlchemy metadata + Alembic stamp head, SQLAlchemy-based `AdminSystem`, PostgreSQL connect timeout, `/health` с backend diagnostic, dialect-aware feedback DDL. SQLite оставлен local/dev fallback. DB01 completed; мониторить Supabase limits/latency и runtime-команды после deploy.

**HF01 notes:** Flask-сервер на `7860` (`/health`, `/metrics`, `/logs`), Dockerfile `python:3.12-slim`, IP-based proxy (`195.201.225.248`) с `Host: tgproxy.me` + `verify=False`, safe `http_client` builder fallback, `SPACE_ID` detection, Alembic-first startup, config manager resilience к отсутствующим таблицам.

**PARSE01 notes:** Это главный продуктовый фокус после стабилизации runtime/DB/UX. Требуется довести автоматический парсинг реальных игровых сообщений до production E2E: fixtures реальных сообщений, правила по поддерживаемым играм, мониторинг successful/failed parses, понятные админские diagnostics и защита от ложных начислений. Текущий ручной/инфраструктурный контур не считать полноценным завершением этого результата.

**FB01 notes:** реализованы команды `/feedback <предложение или жалоба>` с алиасами `/suggest` и `/complaint`; обращения сохраняются в SQLite-таблицу `feedback_entries` с JSONL fallback/debug mirror (`data/feedback.jsonl`): текст, Telegram ID, username, chat ID, chat type и UTC timestamp. Админ может читать последние обращения через `/feedback_list [limit]` (до 20 записей). Для внешнего чтения с HF добавлен защищённый endpoint `GET /feedback?limit=N` с `Authorization: Bearer <FEEDBACK_READ_TOKEN|HF_TOKEN|BOT_TOKEN>`; при сохранении пишется structured log `Feedback saved` с полным текстом обращения.

**AI01 notes:** пользователь попросил добавить ИИ, но обязательно бесплатную реализацию. Реализован локальный AI-lite помощник без платных API, без обязательных внешних ключей и без зависимости от LLM-провайдера. Команды: `/ai <вопрос>`, `/ask <вопрос>`, `/ai_help`. Scope: подсказки по командам BankBot, feedback, магазину, играм, D&D, профилю, админским возможностям и локальной базе канона Олеговируса/LTL из Google Doc (`bot/ai/knowledge.py`: глоссарий, Teaology, candy economy, LTRS, high-canon article links). `/short`/`/long` применяются глобально через `bot/response_modes.py`: long-сообщения автоматически компактятся в short mode, а `/long` сохраняет полный текст. Возможность подключения внешнего free/OpenAI-compatible endpoint допускается только как optional env-настройка позже, не как обязательная зависимость.

**AI02 notes:** Никита предложил использовать бесплатный Hugging Face API, чтобы AI был умнее локального keyword-helper. Требование: только optional/free реализация, без обязательной платной зависимости. Дизайн следующей итерации: env-флаги `AI_PROVIDER=huggingface|local`, `HF_INFERENCE_TOKEN`/`HF_TOKEN`, `HF_INFERENCE_MODEL`, короткие таймауты, лимит prompt/response, safe system prompt про BankBot, fallback на локальный AI-lite при quota/rate-limit/network errors. Нельзя ломать HF runtime и нельзя логировать токены/полный приватный prompt.
| PR10 | Архитектурная инвентаризация слоёв `core/src/utils/bank_bot` | P2 | completed |
| PR11 | Сокращение legacy-дублей и shim-слоёв | P2 | completed |
| PR12 | Упрощение wiring и startup-кода в `bot/bot.py` и entrypoints | P2 | completed |
| PR13 | Ревизия structured logging и эксплуатационных полей | P2 | completed |

**PR10-PR11 notes:** выполнена инвентаризация слоёв и закреплён runtime/legacy contract в `docs/README.md`. Рискованные runtime-зависимости не удалялись; legacy/shim namespaces (`src.parsers`, `core/repositories`, `utils/*` shims, aiogram `shop_commands.py`) зафиксированы как frozen/compatibility, новый код направлен в канонические слои.

**PR12-PR13 notes:** `bot/bot.py` получил чистый `build_polling_kwargs(is_hf)` без изменения HF timeout/retry semantics; structured polling logs сохранены. UX/watchlist закрыт безопасными runtime-правками: `/shop` и `/games` больше не дублируют вывод, `/games_list` показывает активные сессии, `/dnd_*` исправлены на `core.systems.dnd_system`, неизвестные команды получают fallback-ответ.
