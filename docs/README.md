# BankBot - Документация проекта

High-level документация по текущей архитектуре, точкам входа и ключевым модулям проекта. Архитектурная цель BankBot — production-grade парсинг игровой активности с надёжным банковым контуром вокруг него.

## О проекте

Репозиторий содержит три основных исполняемых компонента:

- `BankBot` - основной Telegram-бот для целевого парсинга игровой активности, банковой логики, балансов, магазина, достижений, социальных функций и администрирования
- `BridgeBot` - мост Telegram -> VK для пересылки сообщений и медиа
- `VK Bot` - отдельная точка входа для VK Long Poll и публикации в VK-канал

Также в проекте есть общие слои конфигурации, базы данных, сервисов и тестов.

## Продуктовый фокус

Парсинг игровых сообщений — самая важная целевая функция проекта. Однако текущий код и production-эксплуатация показывают, что вокруг парсинга уже построен и стабилизирован базовый банково-админский фундамент:

- persistent PostgreSQL/Supabase storage для пользователей, балансов, feedback и режимов ответа;
- админ-команды для управления пользователями, балансами, рассылками и диагностикой;
- feedback inbox для сбора багов/предложений;
- AI-lite помощник и режимы `/short`, `/long`, `/watch` для UX и стабильности на Hugging Face.

Текущий честный статус: **парсинг остаётся главным продуктовым приоритетом, но не должен описываться как полностью завершённый production E2E контур**. Банк/админка/DB/HF — это фундамент, необходимый для надёжного запуска и контроля парсинга, а стабилизация автоматического парсинга на реальных игровых сообщениях — следующий ключевой этап.

## Текущее состояние

- основной запуск проекта: `run_bot.py`
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
| BankBot | `run_bot.py` -> `bot.main` | Основной Telegram-бот |
| BridgeBot | `bridge_bot/main.py` | Пересылка TG -> VK, loop guard, graceful shutdown |
| VK Bot | `vk_bot/main.py` | Независимый VK Long Poll цикл |

## Архитектура

### 1. Основной бот

Папка `bot/` содержит рабочую точку входа BankBot и orchestration-логику запуска.

Ключевые файлы:

- `bot/main.py` - startup flow, валидация, schema sync, graceful shutdown
- `bot/bot.py` - основной класс Telegram-бота и регистрация функциональности
- `bot/commands/` - модульные обработчики команд
- `bot/response_modes.py` - режимы ответов `/short`, `/long`, `/watch`: личный выбор пользователя применяется к ответам именно этого пользователя; админские `/short_all`, `/long_all`, `/watch_all` меняют общий default для всех, но каждый пользователь может снова выбрать свой режим лично. `/watch` — сверхкороткий режим для часов с quick-reply управлением через 10 шаблонов.
- `bot/ai/` - бесплатный локальный AI-lite помощник без платных API; команды `/ai`, `/ask`, `/ai_help`
- `bot/router.py` - маршрутизация и wiring отдельных команд
- `bot/template_coder/` - параметрический диалоговый кодер 10 шаблонов без таблиц пар/троек; хранит состояние в `chat_data`, поддерживает `/coder`, `/reset`, `/done`, `/help`

#### Командная иерархия и UX

Основные пользовательские точки входа:

- `/start` — регистрация/приветствие; на Hugging Face по умолчанию короткий safe-start;
- `/commands` — меню разделов;
- `/user`, `/shop`, `/games`, `/admin`, `/config`, `/coder`, `/ai` — прямые разделы;
- `/feedback`, `/suggest`, `/complaint` — предложения и жалобы;
- `/short`, `/long`, `/watch` — личные режимы ответа.

Админские команды включают `/admin_panel`, `/add_points`, `/admin_addcoins`, `/admin_removecoins`, `/broadcast`, `/feedback_list`, `/short_all`, `/long_all`, `/watch_all`.

#### Режим часов `/watch`

`/watch` предназначен для управления ботом с часов, где экран помещает только короткий текст, а набор быстрых ответов ограничен шаблонами:

| Ответ часов | Действие |
|-------------|----------|
| `ОК` | профиль |
| `Да` | админ-раздел |
| `Спасибо` | баланс |
| `Спасибо, нет` / `Спасибо нет` | магазин |
| `Великолепно` | игры |
| `Спасибо еще раз` | AI help |
| `Скоро увидимся` | команды |
| `Скоро буду` | уведомления |
| `Я занят(а)` | включить личный watch-режим |
| `Нет` | отмена/подсказка |

В watch-режиме глобальный patch `Message.reply_text` дополнительно сжимает ответы до нескольких строк. Ответ `Я занят(а)` включает watch-режим для конкретного пользователя даже без предварительной команды `/watch`.

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

`run_bot.py` запускает Flask-сервер на порту `7860` и затем основной BankBot.

Runtime endpoints:

- `/health` — health check + проверка БД;
- `/logs` — локальный буфер stdout/stderr для диагностики Space;
- `/metrics` — Prometheus-like метрики;
- `/feedback?limit=N` — защищённый reader последних feedback-записей.

Для HF есть специальные runtime-решения:

- DNS/anyio/httpx workaround для Telegram API;
- webhook-check пропускается на HF, чтобы не блокировать startup;
- polling удерживается guarded-loop, чтобы Space не завершался после transient Telegram timeouts;
- `drop_pending_updates=False` на HF, чтобы команды не терялись при reconnect.

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
| `database/` | Подключение, schema sync, Alembic, bootstrap |
| `config/` | `.env` templates, YAML/JSON конфиги, dev requirements |
| `tests/` | Unit, integration, smoke и вспомогательные тесты |
| `memory_bank/` | Операционный контекст проекта |

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
