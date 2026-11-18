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
- `src/config.py`, `src/startup_validator.py`, `src/process_manager.py` — инфраструктурный startup слой; `src/parsers.py` остаётся compatibility façade над `core.parsers`; `src/webhook_secret.py` — единый вывод webhook-секрета из `BOT_TOKEN` (используют `api/index.py` и `run_bot.py`, отдельный секрет в конфиге не хранится).
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

- webhook регистрируется при старте через `set_webhook(..., secret_token=WEBHOOK_SECRET)`; сам `WEBHOOK_SECRET` не хранится отдельно, а выводится из `BOT_TOKEN` хелпером `src/webhook_secret.py` (в логах секрет и owner-ID редактируются);
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
├── school_project/
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
| `school_project/` | Материалы защиты школьного проекта (паспорт, презентация, речь, демо, чек-лист) |
| `api/index.py` | Vercel serverless entrypoint (вебхуки Telegram + Flask API) |

### Web Accounts & GAL OAuth

Веб-портал LTHub использует собственные аккаунты `web_users` (логин/пароль; токен сессии — `localStorage.web_token`). Для регистрации и входа добавлен OAuth-клиент **GAL** (authorization code + PKCE S256, публичный клиент без `client_secret`).

**Компоненты:**
- `core/gal_oauth.py` — клиент: `state`/PKCE-verifier/`next` в HttpOnly-cookie, обмен кода, чтение `/oauth/userinfo`, поиск/создание `web_users` по `gal_subject`, суффикс при занятом логине, регистрационный бонус новому аккаунту.
- `GET /auth/gal` — старт входа, редирект на GAL `/oauth/authorize`.
- `GET /api/auth/gal/callback` — проверка `state`, обмен кода на токен, импорт `preferred_username` → `login` и `display_name` (только поля, нужные регистрации LTHub), вход/создание аккаунта.
- `GET /auth/gal/done` + `GET /api/auth/gal/session` — одноразовая передача токена из HttpOnly-cookie в `localStorage.web_token` (callback не может писать localStorage напрямую).
- Кнопки «Зарегистрироваться через GAL» на `/register` и «Войти через GAL» на `/login`; параметр `redirect` сохраняется через OAuth. Кнопка регистрации добавляет `intent=register`: если пользователь не залогинен в LTHub, `/oauth/authorize` ведёт его на `/register?redirect=<authorize URL>`, а не на `/login`; после регистрации LTHub возвращает на authorize и выдаёт код. `next` в GAL передаётся через OAuth и восстанавливается после callback (только same-origin путь).
- `web_users`: `gal_subject` (уникальный, привязка identity) и `gal_username` (последний логин GAL). OAuth-only аккаунт получает случайный неиспользуемый хеш пароля; email не импортируется.

**Env:** `GAL_OAUTH_ENABLED` (`true`), `GAL_OAUTH_CLIENT_ID` (`lthub`), `GAL_OAUTH_AUTHORIZE_URL`, `GAL_OAUTH_TOKEN_URL`, `GAL_OAUTH_USERINFO_URL`, `GAL_OAUTH_REDIRECT_URI` (пусто — `request.url_root` + `/api/auth/gal/callback`).

**Тесты:** `tests/unit/test_gal_oauth_client.py`.

### Google OAuth (вход через Google)

Регистрация и вход LTHub через Google — OAuth 2.0 authorization code + PKCE S256, конфиденциальный клиент (`client_secret` используется только server-side). Реализован по образцу GAL-клиента.

**Компоненты:**
- `core/google_oauth.py` — клиент: `state`/PKCE-verifier/`next` в HttpOnly-cookie, обмен кода на `oauth2.googleapis.com/token`, профиль с `openidconnect.googleapis.com/v1/userinfo` (scope `openid email profile`), поиск/создание `web_users` по `google_subject`, суффикс при занятом логине, бонус +100 новому аккаунту.
- `GET /auth/google` — старт входа, редирект на `accounts.google.com/o/oauth2/v2/auth` (`prompt=select_account`).
- `GET /api/auth/google/callback` — проверка `state`, обмен кода, чтение userinfo, вход/создание аккаунта. Логин derives из local-part email (или имени); `display_name` — имя профиля Google.
- `GET /auth/google/done` + `GET /api/auth/google/session` — одноразовая передача токена из HttpOnly-cookie в `localStorage.web_token`.
- Кнопки «Войти через Google» на `/login` и «Зарегистрироваться через Google» на `/register` (белый фирменный стиль с логотипом G); параметр `redirect` сохраняется через OAuth. Кнопки рендерятся только если заданы `GOOGLE_CLIENT_ID` и `GOOGLE_CLIENT_SECRET` (флаг `__GOOGLE_OAUTH_ON__` подставляется в страницу); иначе скрыты, а `/auth/google` отдаёт 404.
- `web_users`: `google_subject` (уникальный индекс, привязка identity) и `google_email`. Колонка `web_users.email` не затрагивается; авто-привязки по email нет (email при обычной регистрации не верифицируется — привязка дала бы вектор захвата аккаунта). OAuth-only аккаунт получает случайный неиспользуемый хеш пароля.

**Env:** `GOOGLE_OAUTH_ENABLED` (`true`), `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (обязательны для включения), `GOOGLE_OAUTH_REDIRECT_URI` (пусто — `request.url_root` + `/api/auth/google/callback`), опциональные переопределения `GOOGLE_OAUTH_AUTHORIZE_URL`/`GOOGLE_OAUTH_TOKEN_URL`/`GOOGLE_OAUTH_USERINFO_URL` (тесты/мок).

**Настройка прода:** Google Cloud Console → OAuth consent screen + OAuth client ID (Web application) → authorized redirect URI `https://lthub.vercel.app/api/auth/google/callback` → значения в Vercel env. Миграция `database/migrations/012_google_oauth.sql` (колонки также авто-добавляются `_ensure_web_user_columns`).

**Тесты:** `tests/unit/test_google_oauth_client.py`.

### Personal AI Key (личный API-ключ нейросети)

Зарегистрированный пользователь может сохранить свой API-ключ ИИ-провайдера в личном кабинете `/account` (блок «🔑 Мой AI-ключ»). Ключ **приоритетно** используется для всех веб-запросов этого пользователя к ИИ; при отказе ключа — автоматический fallback на серверную цепочку провайдеров.

**Хранение:** колонки `web_users.ai_provider` (`openrouter`/`gemini`/`groq`), `ai_api_key`, `ai_model` (опционально). Ключ хранится в БД **в открытом виде** (осознанное решение 2026-11-17; шифрование — отдельная будущая задача). Бутстрап колонок — `_ensure_web_user_columns`, миграция `database/migrations/011_user_ai_key.sql`.

**API** (все требуют сессию, `X-Auth-Token`/`Bearer`):
- `GET /api/account/ai-key` — `{has_key, provider, model, key_preview}`; полный ключ наружу не отдаётся, только маскированное превью.
- `POST /api/account/ai-key` — `{provider, api_key, model?}`; валидация провайдера и длин (ключ ≤255, модель ≤128).
- `DELETE /api/account/ai-key` — сброс всех трёх колонок.

**Приоритет в ИИ:** `_ai_chat` (api/index.py) в начале вызывает `_request_user_ai_config()` — резолв сессии из заголовков текущего запроса + чтение ключа из БД (кэш в `flask.g` на время запроса). Если ключ сохранён, `_ai_chat_with_user_key()` пробует провайдера пользователя (модель из профиля или дефолтная; retry 429, reasoning-off для reasoning-моделей) и возвращает успешный ответ. Отказ/пустой ответ → обычная цепочка Gemini → Groq → OpenRouter. Поведение автоматически распространяется на все веб-модули (AI-чат, куратор, Code Explainer, Repo History и др.) без правки call-sites; вне Flask-контекста (бот/скрипты) цепочка не меняется. Гейты «AI недоступен» в `_pc_ai_chat` и `/api/test_ai` учитывают наличие личного ключа.

**Тесты:** `tests/unit/test_user_ai_key.py`.

### School / OGE Module (Школа)

Личный учебный портал для подготовки к ОГЭ — раздел «🎓 Школа» в web-портале. Пять предметов
работают на общем «движке» заданий, поэтому новый предмет добавляется без переписывания
остальных.

| Предмет | Страница | Объём |
|---------|----------|-------|
| Информатика | `/informatics` | 95 задач + режим теста (счёт и таймер) |
| Математика | `/math` | 50 задач, 130 формул, 8 генераторов вариантов |
| Русский язык | `/russian` | 45 заданий, 50 правил |
| Физика | `/physics` | 40 задач, 62 формулы |
| История России | `/emperors` | 100 терминов, интервальное повторение |

**Компоненты:**
- `core/informatics/`, `core/mathematics/`, `core/russian/`, `core/physics/`, `core/history/` — данные и логика предметов (лёгкие stdlib-пакеты).
- `api/index.py` — страницы предметов, общий «движок» заданий и тестов, достижения и монеты.
- Раздел «🎓 Школа» в хабе `/`, ведущий на страницы предметов.

**Доступ:** базовые страницы предметов и общие данные (`/api/study/today`, `GET /api/study/chat`) открыты анонимам; персонализированные подсказки (`POST /api/study/chat`, `/api/study/hint`) и действия куратора — только для авторизованных.

**Мотивация:** геймификация — достижения (всего **325**), «монеты» за активность и ежедневная серия.

**Материалы защиты школьного проекта:** `school_project/` (паспорт, презентация, речь, демо-сценарий, чек-лист).

**Тесты:** `tests/unit/test_informatics_module.py`, `test_russian_module.py`, `test_physics_module.py`, `test_emperors_module.py`, `test_exam_center.py`, `test_study_progress.py`.

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

### Universe Module (Олеговирус / LTL-паразит)

Игровая механика заражения в чатах: сообщение заражённого бот удаляет и публикует заново — от имени автора, с «тиками» вместо нормальной речи; если кто-то спрашивает, что это такое, бот объясняет канон.

**Компоненты:**
- `api/universe_runtime.py` — логика без Telegram: заражение/передача/лечение, тики (`TICKS`: «кхм-кхм» — 60 %, «бум-бум» — 25 %, «тыц-тыц» — 15 %), искажение текста `modify_text()`, формат сообщения `format_infected_message()` («Имя:\n<текст с тиками>»), распознавание вопросов `question_strength()` / `is_virus_question()`, канонический ответ `virus_explainer()`, активность чата `mark_chat_activity()` / `chat_activity()`.
- `api/index.py` — вебхук `/telegram/webhook/<secret>`: автозаражение при упоминании бота, подмена сообщений заражённых, автоответ на вопрос о вирусе и команды `/infect`, `/virus`, `/spread`, `/cure`, `/tea`.
- Таблицы `infection_status` (статус заражения) и `virus_chat_activity` (в каком чате вирус активен). Создаются в `_ensure_universe_tables()` через `CREATE TABLE IF NOT EXISTS` — одинаково работают на PostgreSQL и SQLite, отдельная миграция не нужна.

**Поведение:**
- Сообщение заражённого в группе удаляется, вместо него бот публикует `Имя:\n<текст с тиками>`; в личке удалить чужое сообщение нельзя — бот отвечает на него реплаем.
- Тик выбирается случайно с весами; изредка к сообщению добавляется каноническая реплика («Ты не Олег, ты вирус в зале»).
- Явный вопрос о вирусе («кто такой олеговирус», «что за вирус», «почему кхм-кхм») → канонический ответ бота в любом чате; общее «что это?» → только в чате, где вирус уже активен, либо в реплае на сообщение бота.
- Вопрос проверяется **до** подмены сообщений, иначе вопрос самого заражённого «съедался» бы тиками и бот не смог бы на него ответить.
- `/tea` — облегчение симптомов на час, `/cure` — выздоровление, `/spread` — передача вируса ответом на сообщение.

**Тесты:** `tests/unit/test_universe_runtime.py`.

### Repo History Reader (История репозитория, бета)

Читалка истории репозиториев: пользователь вставляет ссылку на публичный GitHub-репозиторий и выбирает период (7/30/90 дней или свои даты) — ИИ выдаёт сводку «что добавилось за период».

**Компоненты:**
- `api/repo_history.py` — чистые функции: `parse_repo_url()` (только github.com, защита от SSRF), `resolve_period()` (дни или since/until, до года), `fetch_commits()` (GitHub REST API `GET /repos/{owner}/{repo}/commits?since=&until=` — эквивалент `git log`, пагинация до 300 коммитов), `fetch_memory_bank()` (`memory_bank/progress.md` и `projectbrief.md` с raw.githubusercontent.com, 404 → пропуск), `get_context()` (best-effort TTL-кэш коммитов+memory_bank на 10 мин, чтобы уточняющие вопросы и «Короче» не дёргали GitHub повторно), `get_cached_summary()`/`put_cached_summary()` (TTL-кэш готовой AI-сводки на 10 мин, ключ repo+период+brief — повторный analyze не дёргает провайдеров; кэшируется только успешный ответ), `get_cached_fallback()`/`put_cached_fallback()` (negative-кэш fallback на 60 с — во время отказа ИИ повторные запросы отдаются без обращения к провайдерам и без расхода квоты), `build_fallback_summary()` (детерминированная сводка по префиксам коммитов при отказе ИИ), `build_prompt(brief=)` (полная сводка или выжимка 1–3 предложения), `build_ask_prompt()` (ответ на конкретный вопрос), `page_html()`.
- `api/index.py` — `GET /repo_history` (страница), `POST /api/repo_history/analyze` (сводка через `_ai_chat`, флаг `brief` для кнопки «Короче»; при отказе/рейт-лимите ИИ — graceful-fallback: HTTP 200 с `ai:false` и сводкой по коммитам вместо 502) и `POST /api/repo_history/ask` (уточняющий вопрос по истории); бета-карточка в хабе, `HUB_KEY['/repo_history']`.

**Особенности:**
- Git-бинарник и клонирование не используются — всё через HTTP API, укладывается в лимиты Vercel. Только публичные репозитории github.com.
- Опциональный `GITHUB_TOKEN` из env повышает лимит GitHub API (без него 60 запросов/час на IP).
- Rate-limit: analyze — анонимам 3/час на IP (`_check_db_rate`), вошедшим 10/час; ask — анонимам 5/час, вошедшим 20/час. Новых таблиц БД нет; контекст кэшируется в памяти (на холодном старте Vercel перечитывается).
- Кнопка **«⚡ Короче»** — краткая выжимка (1–3 предложения) того, что добавилось; поле **«Спросить у ИИ о конкретном моменте»** — уточняющий вопрос по истории (ответ опирается только на коммиты и memory_bank, до 500 символов вопрос).
- Длинная история обрезается до 300 новейших коммитов (флаг `truncated` в ответе и пометка в промпте); бюджет текста коммитов в промпте — 12 КБ, memory_bank-файлов — по 6 КБ.
- **Устойчивость к отказу ИИ (429/недоступность):** analyze не падает с 502 — отдаёт детерминированную сводку по коммитам (HTTP 200, `ai:false`, пометка «ИИ сейчас недоступен»). OpenRouter повторяет 429 с экспоненциальной паузой (до 3 попыток); готовая успешная сводка кэшируется на 10 мин. Во время отказа ИИ fallback кэшируется на 60 с (negative-кэш) и отдаётся **до** проверки лимитов — повторные одинаковые запросы не дёргают провайдеров и не тратят квоту («уменьшаем частоту запросов» к AI, пока он рейт-лимитит). Сообщения rate-limit называют конкретный лимит и окно (часовой/минутный).
- Ответ ИИ рендерится через marked + DOMPurify (fail-closed в plain text).

**Тесты:** `tests/unit/test_repo_history.py` (вкл. brief/ask/кэш и `node --check` inline-JS страницы), `tests/unit/test_repo_history_fallback.py` (graceful-fallback, retry 429, кэш сводки).

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
- **Очки и топ игроков:** каждая позиция уровня приносит `points = round(1000 / position)`; `demons_count` считает прохождения сложностей weight≥50. Очки пересчитываются при approve и при смене/удалении уровня. **GET `/api/gd/players`** + страница **`/gd/players`** — топ игроков (ранг, ник, очки, демоны, hardest → карточка). Имя игрока в топе ведёт на карточку `/gd/player/<nick>` (рядом «профиль →» `/u/<login>` при web-аккаунте).
- **Карточка игрока `/gd/player/<nick>`** + **GET `/api/gd/player/<nick>`**: резолв ника игрока (персона по `submissions.username` → web `gd_nickname` → tg `username/first_name`), очки/демоны/hardest, список пройденных уровней (позиция, цветной бейдж тира, дата) + внешние профильные данные из gdbrowser (stars/demons/creator points) с таймаутом. Карточка также встроена **виджетом в профиль `/u/<login>`** (очки/демоны/уровни, hardest, список пройденных, «Открыть карточку →»), ниже — внешний GD-блок; вкладка **«🃏 Моя карточка» на `/gd`** показывает карточку игрока текущего аккаунта (вместо прежней сводки «Моя статистика»).
- **⚡ Первый виктор:** в `GET /api/gd/level/<id>/completions` каждый виктор получает флаг `is_first` (по `MIN(submitted_at)`); на странице уровня у самого раннего — жёлтый бейдж.
- **🤝 Co-op на двоих (GD-08):** необязательное поле `partner_nick` в сабмите (`/gd`, только веб) — GD-ник второго игрока под тем же общим пруфом. Валидация `_gd_norm_coop_partner`: обрезка, ≤50 симв., запрет управляющих символов и совпадения с собственным ником (регистронезависимо) → иначе 400. Атрибуция напарника **выводится при чтении** (`_gd_persona_lookup` объединяет ветки «своя заявка» + «я указан как `partner_nick`»), поэтому в `level_completions` строка для напарника НЕ пишется: там `UNIQUE(user_id, level_id)`, и два разных напарника на одном уровне сломали бы констрейнт. Следствия: отклонённая заявка не засчитывает никого; каждый уровень считается один раз (соло приоритетнее co-op); очки и демоны начисляются обоим через общий `_gd_completions_stats`. В `GET /api/gd/level/<id>/completions` — флаги `is_coop`/`coop_with` (бейдж + ссылка на напарника), в очереди модерации админ видит, что пруф общий. Для чисто-co-op партнёра (никогда не подававшего заявку) `persona["uid"] = None`, поэтому `_gd_admin_player_uid` падает обратно на резолв аккаунта, а профиль сливает персону с `level_completions` аккаунта.
- **Персона-атрибуция прохождений = ник из заявки:** каждый completion хранит `level_completions.player_name` — GD-ник из approved-`submissions.username` (backfill `_gd_backfill_completion_names`), а НЕ владельца аккаунта. Один аккаунт может иметь несколько персон (пример: аккаунт 1597272920 = персоны «LucasTeam» за Supersonic и «ShadowRaven» за TVOL). Топ игроков, карточка игрока, список викторов и completers в лидерборде группируются ПО НИКУ ИЗ ЗАЯВКИ. Таблица-агрегатор `gd_aliases` УДАЛЕНА (редундантна). Исторические строки без ников дополняются именем аккаунта.
- **Админ-панель игрока (кнопка «＋»):** для `is_admin` на карточке `/gd/player/<nick>` — кнопка «＋ Добавить уровень»: выпадающий список из `GET /api/gd/leaderboard`, поле «Ссылка на медиа» + `file`-инпут (фото/видео ≤16 МБ, data-URI; http(s) или файл — правила как у сабмита), кнопка «✕» у каждого completion. **POST `/api/gd/admin/player/<nick>/completions`** (media обязателен) создаёт approved `submissions` + `level_completions` и пересчитывает статы; **DELETE `/api/gd/admin/player/<nick>/completions?level_id=`** убирает уровень из пройденных; **PUT `/api/gd/admin/player/<nick>/nick`** (`new_nick`, кнопка «✏️ Сменить ник») переименовывает персону (меняет `submissions.username` и `player_name`, сливает статистику). Оба требуют админ-сессию (403 иначе). Признак админа отдаётся СЕРВЕРОМ в карточку (не-админы не получают кнопок), админ-fetch'и шлют `X-Auth-Token`.

### Python Editor Module — удалён (2026-09-28)

Модуль `<Редактор Python>` (`/editor`, CodeMirror 6 + in-process `jedi`) был реализован, задеплоен и прожил в проде один день, после чего удалён по решению владельца: страница, все `/api/pyed/*`, таблица `pyed_documents`, карточка из хаба и `jedi` из `api/requirements.txt` больше не существуют.

Что стоит учесть, если модуль вернут:
- **Ловушка CodeMirror, которая стоила дебага:** мета-пакет `codemirror@6.0.1` экспортирует только `EditorView`, `basicSetup` и `minimalSetup`. Обращения вида `cm.EditorState`, `cm.lineNumbers`, `cm.autocompletion` дают `undefined`, `EditorState.create()` бросает TypeError, и страница **молча уходит в `<textarea>`-фолбэк** — снаружи это выглядит как «простой режим», а не как ошибка. Нужны явные импорты `@codemirror/state|view|language|commands|search|autocomplete|lint`, у всех обязательно одинаковый `?deps=codemirror@6.0.1` (иначе esm.sh отдаст два экземпляра `@codemirror/state` и сломается `instanceof` в `Extension`).
- **`node --check` не ловит эту ошибку** — он проверяет только синтаксис. Нужна проверка экспортов в рантайме либо отдельный smoke-тест.
- Backend-часть (`/api/pyed/*`) была полностью проверена unit- и prod-тестами: CRUD с изоляцией по `user_id`, jedi-подсказки, lint, запуск в песочнице с AST-блок-листом, rate-limit, контракт 401.

История модуля и его грабли: `memory_bank/python_editor_module.md` (статус **removed**).

### LTHUB Tunnel — обход блокировки Vercel-домена (2026-10-02)

`scripts/lthub_tunnel/` — локальный прокси из обычной VPN-подписки, чтобы открывать `lthub.vercel.app` и `audioservice.vercel.app` из РФ. **Не часть веб-бэкенда и не часть Telegram-бота**: это отдельный клиентский инструмент на stdlib, у него нет общих импортов с `api/` и `bot/`, и в прод он не деплоится.

Как устроено: `subscriptions.py` скачивает подписки (base64 или «голый» текст со строками `vless://`) с повторами и кешем последнего удачного ответа → `nodes.py` превращает ссылки в outbound sing-box, отбрасывая неподдерживаемое → `probe.py` пингует ноды (TCP + TLS-хендшейк) и оставляет самые быстрые → `sbconfig.py` собирает конфиг (`mixed`-инбаунд `127.0.0.1:2080` + группа `urltest`) → `runner.py` поднимает и гасит прокси → `gui.py` показывает окно с кнопкой «Подключить», а `tunnel.py` остаётся консольным интерфейсом для скриптов и отладки. `clash.py` отдаёт конфиги для телефонов. TUN-драйверы и права администратора не нужны.

Пользователю отдаётся один файл `LthubTunnel.exe` (`build_exe.py`, PyInstaller): внутри код, `sing-box` и подписки, Python не требуется. Подписки зашиты в бинарник **кодом**, а не файлом: PyInstaller распаковывает данные во временную папку `_MEI*`, содержимое которой на машинах с антивирусом не читается (`PermissionError`). Поэтому же в сборке `sources_file()` смотрит только рядом с `.exe` — свой файл подписок имеет приоритет над встроенным.

Выбор ноды двухступенчатый: собственный быстрый пинг отсекает мёртвые адреса и сортирует живые, а окончательный выбор по **сквозной** задержке делает `urltest` внутри sing-box — он же удерживает победителя и уходит на другую ноду, когда текущая умирает. Одного пинга недостаточно: адрес может принимать соединения, а прокси через него — нет.

Главная особенность — **валидация sing-box fail-fast**: одна плохая нода делает невалидным весь конфиг. Поэтому `prune_config()` разбирает индекс `outbound[N]` из вывода `sing-box check`, выкидывает негодную ноду и повторяет проверку. Индекс в ошибке — позиция во всём массиве `outbounds`, где `0` занимает сама группа `urltest`.

Подробности, команды и ограничения: `scripts/lthub_tunnel/README.md`. Список источников — `scripts/lthub_tunnel/sources.local.json`: он в git, потому что внутри публичные VPN-конфиги из интернета, секрета нет (закоммичен, чтобы `.exe` собирался в CI и на любой машине). `bin/` с бинарником sing-box, `dist/` с экспортами и сгенерированный `_bundled.py` в git не попадают.

Готовый `LthubTunnel.exe` раздаётся через **GitHub Releases**: тег `lthub-tunnel-v*` запускает `.github/workflows/release-tunnel.yml`, который скачивает sing-box, собирает бинарник, прогоняет `--selftest` собранного `.exe` и только при успехе публикует ассет. Прямая ссылка на файл: <https://github.com/lucasteamalt12321/BankBot/releases/download/lthub-tunnel-v1/LthubTunnel.exe>

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
