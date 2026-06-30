# BankBot - Документация проекта

High-level документация по текущей архитектуре, точкам входа и ключевым модулям проекта. Архитектурная цель BankBot — production-grade парсинг игровой активности с надёжным банковым контуром вокруг него.

## О проекте

Репозиторий содержит основной production-компонент и legacy/dev-интеграции:

- `BankBot` - основной Telegram-бот для целевого парсинга игровой активности, банковой логики, балансов, feedback и администрирования.
- `BridgeBot` и `VK Bot` остаются в репозитории как legacy/dev-интеграции, но исключены из production HF runtime по решению пользователя.

Также в проекте есть общие слои конфигурации, базы данных, сервисов и тестов.

## Продуктовый фокус

Парсинг игровых сообщений — самая важная целевая функция проекта. Однако текущий код и production-эксплуатация показывают, что вокруг парсинга уже построен и стабилизирован базовый банково-админский фундамент:

- persistent PostgreSQL/Supabase storage для пользователей, балансов, feedback и режимов ответа;
- админ-команды для управления пользователями, балансами, рассылками и диагностикой;
- feedback inbox для сбора багов/предложений;
- AI-lite помощник и режимы `/short`, `/long` для UX и стабильности на Hugging Face.

Текущий честный статус: **парсинг остаётся главным продуктовым приоритетом, но не должен описываться как полностью завершённый production E2E контур**. Банк/админка/DB/HF — это фундамент, необходимый для надёжного запуска и контроля парсинга, а стабилизация парсинга по ответам на реальных игровых сообщениях — следующий ключевой этап.

## Текущее состояние

- production HF запуск проекта: `run_bot.py` как Flask + Telegram webhook endpoint
- local/dev polling fallback: `bot/main.py`
- канонический конфиг: `src/config.py`
- основной `.env` файл: `config/.env`
- инициализация схемы БД: `database/schema.py` и `database/initialize_system.py`
- миграции: `database/alembic/`
- smoke-проверки запуска: `tests/smoke/test_startup.py`
- для пользовательской проверки проект клонировать не нужно: актуальный бот тестируется в группе https://t.me/lucasteamgroup
- локальный запуск нужен только разработчикам для отладки и изменения кода

## Точки входа

| Компонент | Точка входа | Назначение |
|-----------|-------------|------------|
| BankBot HF production | `run_bot.py` | Flask endpoints + Telegram webhook, без polling |
| BankBot local/dev | `bot/main.py` | Локальный polling fallback |
| BridgeBot | `bridge_bot/main.py` | Legacy/dev, не запускается в HF production |
| VK Bot | `vk_bot/main.py` | Legacy/dev, не запускается в HF production |

## Архитектура

### 1. Основной бот

Папка `bot/` содержит рабочую точку входа BankBot и orchestration-логику запуска.

Ключевые файлы:

- `bot/main.py` - startup flow, валидация, schema sync, graceful shutdown
- `bot/bot.py` - основной класс Telegram-бота и регистрация функциональности
- `bot/commands/` - модульные обработчики команд
- `bot/response_modes.py` - legacy helper для режимов ответа; production HF scope оставляет только `/short` и `/long`.
- `bot/ai/` - бесплатный локальный AI-lite помощник без платных API; команды `/ai`, `/ask`, `/ai_help`
- `bot/router.py` - маршрутизация и wiring отдельных команд
- `bot/template_coder/` - параметрический диалоговый кодер 10 шаблонов без таблиц пар/троек; хранит состояние в `chat_data`, поддерживает `/coder`, `/reset`, `/done`, `/help`
- `bot/short_mode.py` - краткий режим обычных меню по умолчанию: `/short`/`/long` для одного пользователя и `/short_all`/`/long_all` для всех

#### Командная иерархия и UX

Основные пользовательские точки входа:

- `/start` — регистрация/приветствие; на Hugging Face по умолчанию короткий safe-start;
- `/commands` — меню разделов;
- `/user`, `/admin`, `/config`, `/coder`, `/ai` — прямые разделы;
- `/feedback`, `/suggest`, `/complaint` — предложения и жалобы;
- `/short`, `/long` — личные режимы ответа.

Админские команды включают `/admin_panel`, `/add_points`, `/admin_addcoins`, `/admin_removecoins`, `/broadcast`, `/feedback_list`, `/short_all`, `/long_all`.

В HF webhook production отключены `/shop`, `/games`, `/dnd`, watch/ADB/ntfy realtime diagnostics и связанные shop/game/dnd/background admin handlers. Отключённые команды отвечают явным сообщением, а не молчат.

### 2. Bridge и VK интеграция

Папка `bridge_bot/` содержит мост между Telegram и VK.

Ключевые файлы:

- `bridge_bot/main.py` - запуск aiogram-based BridgeBot
- `bridge_bot/handlers.py` - обработчики bridge-событий
- `bridge_bot/queue.py` - очередь отправки и rate limiting
- `bridge_bot/loop_guard.py` - защита от циклов через bot mark
- `bridge_bot/media.py` - работа с медиа
- `bridge_bot/vk_publisher.py` - публикация в VK API
- `bridge_bot/vk_listener.py` - приём сообщений из VK

Папка `vk_bot/` сохраняет отдельную точку входа для VK Long Poll.

### 3. Бизнес-логика и data access

Проект частично разделён на более чистые слои:

- `bank_bot/repositories/` - repository layer
- `bank_bot/services/` - service layer
- `bank_bot/middleware.py` - middleware и обработка ошибок
- `bank_bot/di.py` - wiring зависимостей

При этом в репозитории всё ещё присутствуют legacy и shim-слои в `core/`, `src/` и смежных модулях. Они используются как часть переходной архитектуры и должны рассматриваться как существующий runtime-контур, а не как полностью удалённый legacy.

#### Runtime/legacy contract

- `bot/` — канонический Telegram runtime на `python-telegram-bot`; новый command wiring добавлять здесь или в `bot/commands/*_ptb.py`.
- `bank_bot/` — публичный repository/service namespace и compatibility entrypoints. Re-export файлы (`bank_bot.bot`, `bank_bot.main`, `bank_bot.di`, `bank_bot.middleware`) являются контрактом для тестов и внешних импортов.
- `core/systems/`, `core/managers/`, `core/parsers/` — активный runtime-контур; не удалять как legacy без отдельной миграции импортов и полного тестового прогона.
- `core/repositories/*` и `core/services/__init__.py` — shim namespace над `bank_bot.*`; новый код предпочтительно писать в согласованный `bank_bot.*` слой или явно используемый runtime-модуль.
- `src/config.py`, `src/startup_validator.py`, `src/process_manager.py` — инфраструктурный startup слой; `src/parsers.py` остаётся compatibility façade над `core.parsers`.
- `utils/simple_db.py`, `utils/admin_system.py`, `utils/compat.py` — frozen deprecated shims: не расширять, не удалять без отдельного migration PR.
- `bot/commands/shop_commands.py` — aiogram legacy candidate; текущий BankBot runtime использует `shop_commands_ptb.py`.

### 4. Конфигурация

Канонический источник конфигурации - `src/config.py`.

Что важно:

- настройки читаются из `config/.env` и environment variables
- `Settings` и runtime helper `get_settings()` используются как общий контракт конфигурации
- bridge/vk config-модули являются compatibility-обёртками над `src.config`
- production/Hugging Face БД должна задаваться через `DATABASE_URL`; также поддерживаются aliases `POSTGRES_URL` и `SUPABASE_DB_URL`. `postgres://` автоматически нормализуется в `postgresql://`. SQLite остаётся local/dev fallback.
- `HF_TOKEN` используется для деплоя/логов Hugging Face; секреты не должны попадать в git.

### 5. База данных

Ключевые файлы:

- `database/connection.py` - подключение и pooling
- `database/database.py` - модели и metadata
- `database/schema.py` - приведение схемы к актуальному состоянию
- `database/initialize_system.py` - bootstrap новой БД
- `database/alembic/` - Alembic migration chain

Текущий подход:

- при запуске используется Alembic-first синхронизация схемы
- если миграционный контур недоступен, предусмотрен fallback на создание таблиц из metadata
- для пустой PostgreSQL/Supabase БД runtime создаёт таблицы из SQLAlchemy metadata и делает Alembic stamp head; это обходит старые SQLite-specific baseline migrations и сохраняет дальнейший Alembic-контур
- `/health` проверяет `SELECT 1` и возвращает активный backend (`sqlite` или `postgresql`)
- production/HF хранит пользователей, балансы, feedback и response mode settings в PostgreSQL; response modes используют таблицу `response_mode_settings`.

### 6. Hugging Face runtime

`run_bot.py` запускает Flask-сервер на порту `7860` и основной BankBot через Telegram webhook. Polling в HF production не запускается.

Runtime endpoints:

- `/health` — health check + проверка БД;
- `/logs` — локальный буфер stdout/stderr для диагностики Space;
- `/metrics` — Prometheus-like метрики;
- `/feedback?limit=N` — защищённый reader последних feedback-записей.
- `POST /telegram/webhook/<secret>` — Telegram webhook endpoint.

Для HF есть специальные runtime-решения:

- webhook регистрируется при старте через `set_webhook(..., secret_token=WEBHOOK_SECRET)`;
- endpoint проверяет secret path и `X-Telegram-Bot-Api-Secret-Token`;
- фоновые periodic tasks не стартуют в webhook runtime;
- BridgeBot/VK Bot не запускаются из HF production entrypoint;
- локальный polling fallback остаётся в `bot/main.py`.

## Структура проекта

```text
BankBot/
├── run_bot.py
├── README.md
├── RUN.md
├── bot/
├── bridge_bot/
├── vk_bot/
├── bank_bot/
├── core/
├── src/
├── database/
├── config/
├── tests/
├── docs/
└── memory_bank/
```

### Что где лежит

| Путь | Назначение |
|------|------------|
| `bot/` | Основной Telegram runtime |
| `bridge_bot/` | TG -> VK bridge |
| `vk_bot/` | Отдельный VK entrypoint |
| `bank_bot/` | Repository/service/middleware слои |
| `core/` | Legacy и shared модули, используемые текущим runtime |
| `src/` | Конфигурация, startup validation и часть инфраструктуры |
| `bot/web/` | Flask API и SPA для Family Budget Module (Vercel) |
| `bot/budget_parser.py` | Парсер трат Family Budget (без внешних зависимостей) |
| `database/` | Подключение, schema sync, Alembic, bootstrap |
| `config/` | `.env` templates, YAML/JSON конфиги, dev requirements |
| `tests/` | Unit, integration, smoke и вспомогательные тесты |
| `memory_bank/` | Операционный контекст проекта |
| `api/index.py` | Vercel serverless entrypoint (вебхуки Telegram + Flask API) |

### Family Budget Module

Отдельный модуль для учёта семейных трат с авторасчётом долгов и каскадным погашением.

**Компоненты:**
- `bot/web/family_budget.py` — Flask API (9 эндпоинтов) + SPA-фронтенд
- `bot/commands/budget_commands.py` — Telegram-команды `/budget`, `/family`, `/addexpense`
- `bot/budget_parser.py` — Парсер трат из текста (используется и PTB, и Vercel)
- `database/database.py` — SQLAlchemy модели (6 таблиц)
- `api/index.py` — Vercel рантайм (дублирование роутов + вебхуки)

**Команды:**
- `/budget` — ссылка на веб-приложение Family Budget
- `/family create/join/info/leave` — управление семьёй
- `/addexpense` — AI-парсинг трат из текста (формат: `Кредитор Должник Сумма [Категория] [Комментарий]`)

**API эндпоинты:** `/api/budget/family/*`, `/api/budget/transactions`, `/api/budget/debts`, `/api/budget/balance`

**Деплой:** Vercel через `api/index.py`, а также через PTB-рантайм (`run_bot.py`).

## Запуск и проверка

Актуальный практический сценарий запуска описан в `RUN.md`.

Для проверки production-бота без разработки используйте Telegram-группу LucasTeam: https://t.me/lucasteamgroup. Клонирование репозитория для такой проверки не требуется.

Важно: локальный runtime для BankBot следует фиксировать на **Python 3.12**. Практическая проверка показала, что на Python 3.14 `python-telegram-bot==20.7` может падать при инициализации `Updater`.

Коротко:

```powershell
Copy-Item config/.env.example config/.env
py -3.12 -m pip install -r requirements.txt
py -3.12 database/initialize_system.py
py -3.12 run_bot.py
```

Для проверки старта:

```powershell
py -3.12 -m pytest tests/smoke -v
py -3.12 -m ruff check src/config.py tests/smoke/test_startup.py
```

Markdown-файлы не проверяются через `ruff`.

## Документация по разделам

| Файл | Назначение |
|------|------------|
| `README.md` | Общая пользовательская документация проекта |
| `RUN.md` | Актуальная инструкция по запуску |
| `docs/DEPLOYMENT.md` | Деплой и инфраструктура |
| `docs/ARCHITECTURE.md` | Дополнительные архитектурные заметки |
| `docs/API.md` | Внутренние API и интерфейсы |
| `docs/TESTING_GUIDE.md` | Подход к тестированию |

Исторические документы, планы миграции и промежуточные отчёты в `docs/` сохраняются, но не все из них отражают текущее целевое состояние. Для high-level картины следует опираться на этот файл, `README.md`, `RUN.md` и `memory_bank/`.
