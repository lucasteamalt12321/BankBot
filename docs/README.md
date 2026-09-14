# LTHub (LucasTeam Hub) — Документация проекта

High-level документация по текущей архитектуре, точкам входа и ключевым модулям проекта. Архитектурная цель LTHub — production-grade парсинг игровой активности с надёжной экосистемой вокруг него.

## О проекте

Репозиторий содержит основной production-компонент и legacy/dev-интеграции:

- `LTHub` - основной Telegram-бот для целевого парсинга игровой активности, банковой логики, балансов, feedback и администрирования.
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
- единая система тем (светлая/тёмная) и Pico CSS подключаются ко всем HTML-страницам централизованно через `core/theme.py` (`inject_theme` в Flask `after_request`); переключатель темы — на каждой странице, выбор хранится в `localStorage`
- для пользовательской проверки проект клонировать не нужно: актуальный бот тестируется в группе https://t.me/lucasteamgroup
- локальный запуск нужен только разработчикам для отладки и изменения кода

## Точки входа

| Компонент | Точка входа | Назначение |
|-----------|-------------|------------|
| LTHub HF production | `run_bot.py` | Flask endpoints + Telegram webhook, без polling |
| LTHub local/dev | `bot/main.py` | Локальный polling fallback |
| BridgeBot | `bridge_bot/main.py` | Legacy/dev, не запускается в HF production |
| VK Bot | `vk_bot/main.py` | Legacy/dev, не запускается в HF production |

## Архитектура

### 1. Основной бот

Папка `bot/` содержит рабочую точку входа LTHub и orchestration-логику запуска.

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
- `bot/commands/shop_commands.py` — aiogram legacy candidate; текущий runtime использует `shop_commands_ptb.py`.

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

`run_bot.py` запускает Flask-сервер на порту `7860` и основной LTHub через Telegram webhook. Polling в HF production не запускается.

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
LTHub/
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

### Emperors Module (Императоры России)

Тренажёр и шпаргалка для подготовки к игре «сопоставь имена/события с императорами России».

**Компоненты:**
- `core/history/emperors.py` — данные: `EMPERORS` (5 императоров с годами правления), `EVENTS` (48 событий), `PERSONS` (42 личности); у каждого элемента краткое описание. Лёгкий stdlib-пакет (паттерн `core/canon`).
- `api/index.py` — страница `/emperors` (вкладки «📚 Изучить», «🧠 Тренажёр», «📜 Хронология», «Сопоставление»; прогресс-бар выученности — карточка считается выученной после 3 правильных ответов подряд, механика подбора карточек не зависит от этого критерия).
- Карточка «Императоры России» в бета-блоке хаба `/`.

**API эндпоинты:** `/api/emperors/progress` GET/POST/reset — серверная синхронизация SM-2-прогресса карточек для авторизованных пользователей (без токена прогресс живёт в localStorage).

### Music Module (Музыка)

Анализ и трансформация аудио/MIDI: измерение и изменение тональности и темпа (BPM), наложение (микширование) нескольких дорожек.

**Компоненты:**
- `core/music/__init__.py` — публичный API с диспетчеризацией по расширению файла:
  `analyze(path)`, `detect_bpm(path)`, `detect_key(path)`, `change_tempo(path, target_bpm=, factor=, out=)`, `change_key(path, semitones=, target_key=, out=)`, `overlay(paths, out=)`.
- `core/music/midi_utils.py` — работа с MIDI поверх `mido` (чистый Python): темп по `set_tempo`, тональность по `key_signature`, транспозиция нот, смена темпа, объединение дорожек (играют одновременно).
- `core/music/audio_utils.py` — работа с MP3/WAV поверх `librosa` + `soundfile`: BPM через `beat_track`, тональность по хромаграмме (профили Крумхансля–Шмуклера), `time_stretch` (темп без смены высоты) и `pitch_shift` (высота без смены темпа), микширование сигналов.
- MP3 читается/пишется через `soundfile` (libsndfile ≥1.1 с поддержкой MP3) — **без ffmpeg и без `pydub`** (`pydub` несовместим с Python 3.14, модуль `audioop` удалён).

**Зависимости:** `mido`, `librosa`, `soundfile`. `mido` — в основном `requirements.txt` (работает везде); `librosa`+`soundfile` вынесены в `requirements-audio.txt` (опционально, чтобы не раздувать сборку Vercel — обработка MP3/WAV доступна при их установке).

**Веб-интеграция (бета-модуль LTHub):** страница `/music` и API `/api/music/analyze`, `/api/music/change_tempo`, `/api/music/change_key`, `/api/music/overlay` (multipart, лимит 8 МБ, расширения mid/midi/mp3/wav). Карточка-бета в хабе ведёт на `/music`.

**Тесты:** `tests/unit/test_music.py` (MIDI + аудио, все зависимости импортируются лениво).

### Profiles & Friends Module (профили и друзья)

Публичные профили пользователей и двусторонняя дружба через заявки (модель как в VK/Steam) в web portal.

**Компоненты:**
- `api/index.py` — таблицы `friend_requests` (pending-заявки) и `web_friends` (две строки на пару) через `_ensure_social_tables()`.
- Страница **`/friends`** — вкладки «Друзья» / «Входящие» / «Поиск» (debounce 300 мс), топ недели среди друзей (SUM действий за 7 дней).
- Страница **`/u/<login>`** — публичный профиль: имя/@логин, монеты, серия, активные дни, активность по модулям, достижения, GD-блок (`/api/gd/user/<nick>`), кнопки по отношению (добавить/принять/отменить/убрать). Без email/telegram/hash.
- Блок «Друзья» в `/account` и ссылка с бейджем входящих заявок в user-bar хаба `/`.

**API эндпоинты:** `GET /api/u/<login>`, `GET /api/users/search?q=`, `GET /api/friends`, `POST /api/friends/request|accept|decline|cancel|remove`, `GET /api/friends/weekly`. Rate-limit заявок `frq:{uid}` 20/час.

**Тесты:** `tests/unit/test_social.py` (публичный профиль без утечек, полный friend-flow, weekly top).

### GD Module (прохождения уровня)
- Страница **`/gd/level/<id>`** — approved-прохождения уровня (дедуп по игроку, последнее медиа) + meta уровня (позиция, сложность). Ленивая загрузка через **GET `/api/gd/level/<id>/completions`**; 404 для неизвестного уровня.
- Имя уровня в лидерборде `/gd` — ссылка на страницу прохождений; для web-игроков у виктора «профиль →» `/u/<login>`.
- Сабмит `/api/gd/submit`: multipart-файл **или** внешняя http(s)-ссылка (`media_url` → `media_type="link"`, хранится в `media_file_id`; валидация `urlparse`, ≤2048 симв., блок `javascript:`/`data:`/`file:`/`vbscript:`; файл+ссылка → 400; файл ≤16 МБ → 413). Переключатель «📎 Файл / 🔗 Ссылка» на странице `/gd`.
- Модерация `/api/gd/moderation`: единый helper `gdMediaHtml` — ссылка «🎬 Открыть медиа» + inline-превью прямых image/video-URL и `data:`-URL (для `link` — бирка «🔗 внешняя ссылка»).
- 🟡 Известный лимит (pre-existing): `/api/gd/leaderboard` может долго отвечать, если у уровня сохранённая сложность `Unknown` (внешний запрос к gdbrowser без таймаута).
- **Нормализованная сложность:** единый 18-тировый ладдер реального Global Demonlist — `easy / normal / hard / harder / insane / easy demon / medium demon / hard demon / insane demon / extreme demon / top 1000 / top 500 / top 200 / top 150 / top 100 / top 50 / top 25 / top 10` (константа `GD_DIFFICULTY_TIERS`, key + label + weight + color). Произвольный текст сложности маппится каноническим ключом (`_gd_norm_difficulty`); если сложность неизвестна — tier авто-выводится из позиции уровня (≤10 → Top 10, …, ≤1000 → Top 1000). Внутренние данные публичной сложности кэшируются (TTL 1 ч, timeout 5 с). Бейджи сложности цветные на лидерборде `/gd`, странице уровня и в топе игроков.
- **Очки и топ игроков:** каждая позиция уровня приносит `points = round(1000 / position)`; `demons_count` считает прохождения сложностей weight≥50. Очки пересчитываются при approve и при смене/удалении уровня. **GET `/api/gd/players`** + страница **`/gd/players`** — топ игроков (ранг, ник, очки, демоны, hardest → карточка).
- **Карточка игрока `/gd/player/<nick>`** + **GET `/api/gd/player/<nick>`**: резолв ника игрока (web `gd_nickname` → tg `first_name/username` → `submissions.username`), очки/демоны/hardest, список пройденных уровней (позиция, цветной бейдж тира, дата) + внешние профильные данные из gdbrowser (stars/demons/creator points) с таймаутом.
- **⚡ Первый виктор:** в `GET /api/gd/level/<id>/completions` каждый виктор получает флаг `is_first` (по `MIN(submitted_at)`); на странице уровня у самого раннего — жёлтый бейдж.
- **Объединение аккаунтов (gd_aliases):** один игрок может быть привязан к нескольким аккаунтам (например, двум TG) — таблица `gd_aliases(user_id, alias)`. Топ игроков, карточка игрока, список викторов и completers в лидерборде считают таких игроков ОДНИМ: очки/демоны суммируются, hardest = самый низкий позишн, прохождения объединяются с дедупом по уровню. Имя — канонический алиас. Первичная миграция (2 TG-аккаунта → `ShadowRaven`) бутстрапится в `_ensure_gd_tables` (idempotent).

## Запуск и проверка

Актуальный практический сценарий запуска описан в `RUN.md`.

Для проверки production-бота без разработки используйте Telegram-группу LucasTeam: https://t.me/lucasteamgroup. Клонирование репозитория для такой проверки не требуется.

Важно: локальный runtime следует фиксировать на **Python 3.12**. Практическая проверка показала, что на Python 3.14 `python-telegram-bot==20.7` может падать при инициализации `Updater`.

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
