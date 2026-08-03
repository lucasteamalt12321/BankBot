# Active Context

**Последнее обновление:** 2026-08-03  
**Текущая фаза:** Ребрендинг BankBot → LTHub (LucasTeam Hub)  
**Последнее действие:** Отдельный «Личный кабинет» + раздельные ссылки Войти/Зарегистрироваться

## Текущий фокус

### Личный кабинет, Войти, Зарегистрироваться — раздельные страницы ✅

**Цель:** Разделить вход, регистрацию и личный кабинет на отдельные страницы (была одна кнопка «Войти / Зарегистрироваться», личного кабинета не было).

**Как работает:**
- **`/account`** — новая страница «Личный кабинет»: аватар, имя, @логин, 💎 монеты (из `/api/auth/me`), поля профиля (GD, Telegram, Lichess), статус (админ/пользователь), кнопки «Редактировать профиль» (/settings), «На главную», «Выйти». Если не залогинен → редирект на /login.
- **`/login`** — вход по логину/паролю (существовала)
- **`/register`** — регистрация (существовала)
- **`/api/auth/me`** теперь дополнительно возвращает `coins` (баланс из `user_coins` через `_web_user_id("u<id>")`)
- Хаб `/`: аноним видит две отдельные ссылки «Войти» (/login) и «Зарегистрироваться» (/register); залогиненный — «Личный кабинет» (/account) и «Выйти»

**Проверка на проде:** register (user_id=10) → me возвращает coins=0; /account 200 + «Личный кабинет»; /login и /register 200. ruff 0 errors, py_compile OK.

### Функция «Предложения» (новое) ✅

**Цель:** Пользователь может отправить предложение по улучшению проекта или сообщить о баге.

**Как работает:**
- Таблица `web_feedback` (user_id, login, author_name, category[bug|suggestion], module, message, status[open], created_at)
- Страница `/suggest` — форма: категория (🐛 баг / 💡 предложение), раздел (выпадающий список модулей), текст
- Карточка «Предложения» в бета-блоке хаба
- Плавающая кнопка 🐛 появляется при JS-ошибке (window.onerror / unhandledrejection) на хубе → ведёт на `/suggest?type=bug&module=hub`
- Вкладка «Предложения» в админ-панели настроек (просмотр по типам, удаление)
- Уведомление админу в Telegram через `notify_admin`

**API:** `POST /api/feedback` (подача), `GET /api/admin/feedback?status=`, `DELETE /api/admin/feedback/<id>`

### Пакет исправлений багов (2026-08-03) ✅

Исправлены 5 багов из обращения пользователя:

1. **Шахматы жёсткого off-by-one** (web + telegram): позиция задачи выводилась на `initialPly` полуходов, а не `initialPly + 1`, что давало инверсию цвета («Ход: Белых», но «правильный ход — за чёрных»). Эмпирически подтверждено на 19+ задачах Lichess: `solution[0]` легален именно на `initialPly + 1`. Mirror при ходе чёрных СОХРАНЁН (телеграм-бот не ломался). `turn` теперь считается от `(initialPly + 1) % 2`.

2. **D&D пустая страница**: панели скрывались навсегда, т.к. `refreshStatus()` молча глотал ошибки. Исправлено: `#start-panel` видна по умолчанию, добавлены `xhr.onerror`/`xhr.status !== 200`/`catch`, ошибка показывается в `start-result`; серверный `/api/dnd/status` обёрнут в try/except → `{"active": false}` вместо 500, ошибка логируется в `log_error`.

3. **GD рекорд без GD-ника**: раньше ник из профиля не подтягивался, сохранялась заглушка `web_<hash>`. Исправлено: клиент при пустом поле имени автоматически берёт `gd_nickname` из `/api/auth/me` (если залогинен), сервер добавляе фолбэк через токен (поле `token` в payload) → `_get_session_user(token).gd_nickname`.

4. **Нереалистичные варианты викторины**: в малых группах (rules/tea/ltrs/glossary) фолбэк брал ответы из всей базы («Высокий канон» попадал в вопрос про LTRS). Добавлены ручные поля `distractors` (3 реалистичных варианта) к вопросам групп rules(1-3), tea(16-17), ltrs(19-20), glossary(21-23); генераторы `api_trivia_question()` и telegram `generate_trivia_question()` теперь отут ручные дистракторы.

5. **Молитвы не по канону**: списки `_PRAYERS` (web + telegram дубль) состояли из IT-юмора. Переписаны по канону чайной религии (многократное «чай» + просьба + финальное «eight-nine»). Telegram теперь использует единый `_PRAYERS` (`random.choice(_PRAYERS)`) без дублирующего кода; убран дубликат `<div class="prayer-amen">eight-nine!</div>` на web-странице.

### Единая регистрация (WEB-11) ✅

**Цель:** Единый пользователь для всех модулей (AI Chat, GD, Chess, Budget, Family, Verbs) без обязательной регистрации.

**Как работает:**
- Анонимный `web_user_id` генерируется в localStorage при первом визите — пользоваться можно без регистрации
- Страница `/register` — регистрация с логином+паролем (обязательно) и опциональными полями: имя, GD nickname, Telegram ID, Lichess nickname
- Зарегистрированный пользователь = `u<user_id>` в localStorage + `web_token` (сессия из таблицы `web_sessions`) → синхронизация между устройствами
- Хаб `/` показывает user-bar: аватар, имя, статус, кнопку «Войти / Зарегистрироваться» или «Выйти» (+ «Настройки»)
- Страницы: `/register`, `/login`, `/settings` (профиль через `/api/auth/me`, обновление через `/api/auth/update`)
- **Поле «Имя» (display_name) предназначено для модулей «Психолог» и «Тренажёр английского»** — в тренажёре глаголов теперь подставляется как имя ученика по умолчанию
- Пароли: PBKDF2-SHA256 (100k итераций), хэш `salt_hex:digest_hex`; сессии: `secrets.token_hex(32)`
- Вспомогательные функции: `_hash_password()`, `_verify_password()`, `_create_session()`, `_get_session_user()`, `_auth_token_from_request()`, `_ensure_web_auth_tables()`
- AI Chat, GD, Chess, Verbs переведены с `ai_user_id` на единый `web_user_id`

**API:** `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/update`, `POST /api/auth/logout`

### Виртуальный компьютер для AI Chat (WEB-09) ✅

**Цель:** AI-персонажи получили «руки» как в Manus: запускают Python, браузят сайты, работают с файлами, редактируют фото. Пользователь видит только текстовый ответ.

**Как работает:**
- `POST /api/ai_chat` — агентный цикл tool-calling через Groq `llama-3.3-70b-versatile` (tools + tool_choice=auto, до 6 итераций)
- Инструменты: `run_python` (реальный subprocess в tempdir), `browse_web` (requests), `list_dir`/`read_file`/`write_file`/`get_cwd`/`set_cwd` (виртуальная ФС в памяти), `edit_image` (Pillow: resize/grayscale/rotate/blur/flip/mirror/thumbnail/invert/contrast)
- Виртуальная ФС: `_VIRTUAL_PC[user_id]` — дерево `{type, children/content/data}`, cwd, uploads
- Загрузка файлов: кнопка 📎 в чате, base64 в `files[]`, сохраняются в `/home/user/uploads/`
- Картинки после edit_image возвращаются как data URI → рендерятся под ответом бота
- Фронтенд теперь шлёт `history` (последние 20 сообщений)

**Файлы:** `api/index.py` (весь бэкенд + inline HTML страницы), `api/requirements.txt` (+Pillow)

### Практика глаголов — новый модуль (WEB-08) ✅

**Цель:** Создать веб-приложение для практики неправильных глаголов английского языка с AI-генерацией заданий.

**Роли:** Учитель (создаёт задания, смотрит результаты) / Ученик (выполняет, получает проверку).

**Как работает:**
- Страница `/irregular_verbs` — роли «Я учитель» / «Я ученик», тёмная тема
- Учитель: создаёт задание (глаголы, кол-во 1-50, режим 2/3 формы, пожелания) → AI генерирует → превью с правильными ответами → подтвердить и получить share-ссылку → «Мои задания» (id, кол-во заданий, учеников) → результаты с ошибками
- Ученик: вводит ID или переходит по share-ссылке → если имя не задано, спрашивает «Как тебя зовут?» (сохраняется в localStorage `verbs_name`) → заполняет пропуски → проверка с подсветкой ✓/✗ и счётом
- Имя ученика по умолчанию подставляется из профиля (display_name) для зарегистрированных пользователей
- Режимы: mode=3 (1 подсказка + 2 пропуска), mode=2 (первые 2 формы видны, пропущен Past Participle)
- Share-ссылка: `/irregular_verbs/exercise/<id>` → 302 на `?exercise=<id>`

**API:**
- `POST /api/verbs/generate` — AI генерирует задание (Groq llama-3.3-70b), лимит 10 сек между генерациями (`VERB_GEN_LOCK`)
- `GET /api/verbs/exercises` — список заданий учителя (+ student_count)
- `GET /api/verbs/exercise/<id>` — задание с пропусками для ученика
- `POST /api/verbs/submit` — проверка ответов ученика (посимвольно по inf/past/pp)
- `GET /api/verbs/exercise/<id>/results` — результаты по заданию (только учитель, 403 иначе)

**БД:** `verb_exercises` (id, teacher_id, verbs, task_count, mode, wishes, tasks JSON, created_at), `verb_submissions` (exercise_id, user_id, name, score, total, details JSON, timestamp). Хелперы `_save_verb_exercise`/`_load_verb_exercise`/`_load_teacher_exercises`/`_save_verb_submission`/`_load_verb_submissions`.

### Web Portal — все модули бота в браузере

**Цель:** Построить веб-портал, дублирующий большинство функций Telegram-бота в браузере. Все страницы на чистом HTML+JS (без фреймворков), Flask сервит через `api/index.py`.

**Архитектурное решение:** Все веб-страницы — inline HTML в `api/index.py` (как уже сделано с тренажёрами и хабом), API эндпоинты там же. Единая точка входа — хаб на `/`.

## Модули для портирования (утверждено)

| # | Модуль | Статус |
|---|--------|--------|
| 1 | AI / Чат-модуль | ✅ Портирован |
| 2 | Викторина (/trivia) | ✅ Портирован |
| 3 | D&D AI Master | ✅ Портирован (аналог StoryForge) |
| 4 | GD модуль | ✅ Портирован |
| 5 | Практика глаголов | ✅ Портирован |
| 6 | Шахматы | ✅ Портирован |
| 7 | Ежедневная молитва | ⏳ Утверждён |
| 8 | Админ-панель | ⏳ Утверждён |
| 9 | Family Circle (медиация) | ✅ Портирован (объединён с LTHub) |

**Не портируются:** магазин, личный кабинет/профиль, вселенная (infect/tea), парсинг реплаев, основные команды.

**Прогресс Phase 3: 123/123** (WEB-00, WEB-01, WEB-02, WEB-03, WEB-04, WEB-05, WEB-06, WEB-07, WEB-08, WEB-09, WEB-10, WEB-11).

## План архитектуры

### 1. AI / Чат-модуль
- **Страница:** `/ai_chat`
- **API:** `POST /api/ai_chat` — принимает `{message, character}`, возвращает `{reply}`
- **UI:** Поле ввода, история сообщений (лента), выбор персонажа (нейтральный/олеговирус/чай)
- **Данные:** Переиспользует `call_ai_api()` из `api/index.py`

### 2. Викторина (/trivia)
- **Страница:** `/trivia`
- **API:** `GET /api/trivia_question` — вопрос + варианты; `POST /api/trivia_answer` — проверка ответа
- **UI:** Карточка с вопросом, 4 кнопки-варианта, подсветка правильного/неправильного, счёт
- **Данные:** Брать вопросы из `bot/ai/knowledge.py` или новой таблицы

### 3. D&D AI Master (StoryForge-like) ✅ Портирован
- **Страница:** `/dnd` — SPA в стиле GitHub Dark (статус, чат-лог, старт, действие, кубик, исправление, стоп)
- **API:** `GET /api/dnd/status`, `POST /api/dnd/start`, `POST /api/dnd/act`, `POST /api/dnd/roll`, `POST /api/dnd/stop`, `POST /api/dnd/fix`
- **UI:** Лог сессии (лента сообщений user/ai/dice/system), поле ввода действия, бросок кубика (d20 / 2d6+3 + цель), исправление мастера, "новая сессия", остановка
- **Данные:** обёртки над `api/dnd_runtime.py`; `user_id` через `_gd_web_uid()`; ответы в Telegram-HTML → `_dnd_plain()`
- **Схема:** прод-таблица `dnd_sessions` (старый проект) без `paused_at` → `ALTER TABLE ADD COLUMN IF NOT EXISTS` в `_ensure_dnd_tables`

### 4. GD модуль ✅ Портирован
- **Страница:** `/gd` — хаб GD с пятью вкладками: Поиск игрока / Топ уровней / Моя статистика / Отправить рекорд / Модерация
- **API:** `GET /api/gd/user/<nick>`, `GET /api/gd/leaderboard`, `GET /api/gd/my_stats?user_id=...`, `GET /api/gd/me`, `POST /api/gd/submit`, `GET /api/gd/moderate`, `POST /api/gd/moderate/reject`, `POST /api/gd/moderate/approve`
- **UI:** Поиск игрока (статистика из GD API), топ уровней (таблица из БД, сложность из GDDL через `get_gd_difficulty_name()`), моя статистика (карточки), отправка рекорда (уровень + имя), модерация (пагинация, ✅/❌, только админ)
- **Тёмная тема:** стиль GitHub Dark
- **Web-user identity:** `_gd_web_uid()` хеширует нечисловой `user_id` в int; числовой = Telegram id. `_gd_web_is_admin()` проверяет по ADMIN_TELEGRAM_ID.

### 5. Шахматы ✅ Портирован
- **Страница:** `/chess` — три вкладки: Моя статистика / Поиск игрока / Пазл
- **API:** `GET /api/chess/stats?user_id=...`, `GET /api/chess/user/<nick>`, `POST /api/chess/link`, `POST /api/chess/puzzle`, `POST /api/chess/puzzle/check`
- **UI:** Статистика привязанного Lichess аккаунта (рейтинги, winrate, история пазлов), поиск игрока, пазл с доской (FEN GIF с lichess1.org), поле ввода UCI хода, +5 монет за верный ход
- **Привязка аккаунта** прямо со страницы (валидация ника через Lichess API)

### 6. Ежедневная молитва
- **Страница:** `/prayer`
- **API:** `GET /api/prayer/today` — молитва дня
- **UI:** Карточка с текстом молитвы, дата, кнопка "обновить"

### 7. Ежедневная молитва
- **Страница:** `/prayer`
- **API:** `GET /api/prayer/today` — молитва дня
- **UI:** Карточка с текстом молитвы, дата, кнопка "обновить"

### 8. Админ-панель (WEB-07) ✅
- **Страница:** `/admin`
- **API:** `GET /api/admin/stats`, `GET /api/admin/users?q=`, `GET /api/admin/users/<id>/coins`, `POST /api/admin/coins/award`, `POST /api/admin/set_admin`, `GET /api/admin/errors`, `POST /api/admin/errors/clear`
- **UI:** 4 вкладки: Статистика / Пользователи / Начисление монет / Ошибки. Тёмная тема GitHub Dark.
- **Авторизация:** по токену профиля — `_web_admin_session()` (is_admin флаг в web_users ИЛИ telegram_id == ADMIN_TELEGRAM_ID). Не-админ → 403. Самим собой управлять нельзя.
- **Назначение админа:** авто-грант при регистрации/обновлении, если telegram_id == ADMIN_TELEGRAM_ID; кнопка «Сделать/снять админа» в списке.
- **Монеты:** `_award_web_coins()` — ключ `_web_user_id("u<web_users.id>")` (согласовано с chess/GD), лог в `web_coin_log`.
- **БД:** `web_users.is_admin` колонка + таблица `web_coin_log` (id, user_id, amount, description, created_at).

### Общий подход
- Каждая страница — отдельный route в `api/index.py` с inline HTML (как hub, reading_trainer, endings_trainer)
- JS-логика inline в том же HTML (или вынесена в `<script>` блок)
- API эндпоинты — `GET/POST /api/<module>/<action>`
- Авторизация: `?user_id=<telegram_id>` (как в budget)
- Все данные через существующие SQLAlchemy engine + get_db_engine()

## Приоритет сборки

1. **AI Chat** — ✅ Портирован
2. **D&D** — ✅ Портирован
3. **Trivia** — ✅ Портирован
4. **Prayer** — ✅ Портирован
5. **Chess** — ✅ Портирован
6. **GD** — ✅ Портирован
7. **Admin** — ✅ Портирован

**Phase 3 (Web Portal) завершён: 123/123.**

## Архитектура (схема)

```
api/index.py (Flask)
├── GET  /                     → хаб (карточки сервисов)
├── GET  /ai_chat              → AI Chat SPA
├── POST /api/ai_chat          → call_ai_api()
├── GET  /trivia               → Trivia SPA
├── GET  /api/trivia_question   → вопрос из knowledge.py
├── POST /api/trivia_answer    → проверка + монеты
├── GET  /dnd                  → D&D SPA (старт/логи/действие/кубик/стоп)
├── GET  /api/dnd/status       → find_active_session + лог
├── POST /api/dnd/start        → cmd_dnd_start
├── POST /api/dnd/act          → handle_free_text
├── POST /api/dnd/roll         → cmd_dnd_roll
├── POST /api/dnd/stop         → cmd_dnd_stop
├── POST /api/dnd/fix          → cmd_dnd_fix
├── GET  /gd                   → GD SPA
├── GET  /api/gd/user/<nick>  → fetch_gd_user()
├── GET  /api/gd/leaderboard   → get_gd_leaderboard() + GDDL сложность
├── GET  /api/gd/my_stats      → get_gd_player_stats()
├── GET  /api/gd/me            → is_admin по user_id
├── POST /api/gd/submit        → create_gd_submission(status='pending')
├── GET  /api/gd/moderate      → get_gd_pending_submissions()
├── POST /api/gd/moderate/reject → reject_gd_submission_db()
├── POST /api/gd/moderate/approve → add_gd_level() + approve_gd_submission_db()
├── GET  /chess                → Chess SPA
├── GET  /api/chess/stats      → fetch_lichess_user()
├── GET  /api/chess/user/<nick>→ fetch_lichess_user()
├── POST /api/chess/link       → link_chess_account()
├── POST /api/chess/puzzle     → _fetch_lichess_puzzle()
├── POST /api/chess/puzzle/check → validate UCI move + award coins
├── GET  /prayer               → Prayer SPA
├── GET  /api/prayer/today     → random prayer
├── GET  /admin                → Admin SPA
├── GET  /api/admin/*          → admin endpoints
├── GET  /endings_trainer.html → existing
├── POST /api/endings_process  → existing
├── GET  /reading_trainer.html → existing
├── GET  /family_budget        → existing
├── GET  /family               → Family Circle: создать комнату (медиация)
├── GET  /family/room          → Family Circle: вход + чат
├── GET  /family/result        → Family Circle: финальный отчёт
├── POST /api/family/rooms     → создать/получить/удалить комнату
├── POST /api/family/rooms/join→ присоединение участника
├── GET  /api/family/rooms/<id>→ инфо о комнате
├── DELETE /api/family/rooms/<id>→ удалить комнату
├── POST /api/family/chat/send → диалог с ИИ-медиатором
├── POST /api/family/chat/finish→ завершить диалог участника
├── POST /api/family/report/generate → генерация финального отчёта
└── POST /telegram             → webhook (existing)
```

**Важные файлы:**
- `bot/web/family_budget.py` — Flask API + VK endpoints
- `bot/commands/budget_commands.py` — команда `/linkvk`
- `database/database.py` — модель `LinkedVKAccount`
- `vk_mini_app/` — весь VK Mini App проект
- `config/.env.local` — VK ключи и токены

## Технический контекст

### Chess Module Architecture
```
api/index.py                  # Chess commands handler (Vercel webhook)
├── fetch_lichess_user()      # Sync Lichess API client
├── get_chess_account()       # Get linked account from DB
├── link_chess_account()      # Link/update chess account
├── /chess                    # Show help
├── /chess_link <username>    # Link Lichess account
├── /chess_rating             # Show ratings (basic)
├── /chess_stats              # Show stats (basic)
└── /puzzle                   # Daily puzzle with board image

database/database.py
├── ChessAccount              # user_id, lichess_username, linked_at
└── UserCoins                 # user_id, balance, last_puzzle_at

database/migrations/
└── 009_phase2_tables_supabase.sql  # chess_accounts table
```

### Chess Module Technical Details
- **Lichess API Base:** `https://lichess.org/api`
- **Timeout:** 8 seconds
- **Board images:** `https://lichess1.org/export/fen.gif?fen=<FEN>&theme=brown&piece=cburnett`
- **User endpoint:** `/api/user/{username}` — returns username, title, online, perfs
- **Puzzle endpoint:** `/api/puzzle/daily` — returns puzzle id, rating, themes, FEN, solution
- **Commands format:** underscore style (`/chess_link`, not `/chess link`)
- **Database:** Supabase PostgreSQL, chess_accounts table with unique lichess_username constraint

### GD Module Vercel Architecture (✅ портирован)
```
api/index.py                  # GD commands handler (Vercel webhook)
├── fetch_gd_user()            # Sync GD API client (user info)
├── fetch_gd_level()           # Sync GD API client (level info)
├── format_gd_user_stats()     # Format user response
├── format_gd_level_info()     # Format level response
├── get_gd_level()             # DB: level by ID
├── get_gd_leaderboard()       # DB: top levels
├── get_gd_completions_count() # DB: completion count per level
├── get_gd_player_stats()      # DB: player stats
├── get_gd_build_player_stats()# DB: create/get player stats
├── get_gd_submission_counts() # DB: submission stats
├── get_gd_user_completions_count() # DB: user completion count
├── get_gd_hardest_level_name()# DB: user's hardest level
├── create_gd_submission()     # DB: create submission
├── get_gd_pending_submissions()# DB: paginated pending
├── approve_gd_submission_db() # DB: approve + update stats
├── reject_gd_submission_db()  # DB: reject
├── add_gd_level()             # DB: add level
├── set_gd_level_position()    # DB: update position
├── gd_moderate_callback()     # Inline button handler
├── _gd_moderate_show_page()   # Pagination handler
├── /gd                        # Help
├── /gd_user <nick>            # GD API user stats
├── /gd_level <id>             # GD API level info
├── /leaderboard               # Top 20 levels
├── /my_stats                  # Personal stats
├── /player_stats @user        # Other player stats
├── /submit <name>             # 2-step submission
├── /moderate                  # Admin moderation
├── /add_level <name> <pos>    # Admin: add level
└── /set_level_position <id> <pos> # Admin: set position

database/migrations/
└── 009_phase2_tables_supabase.sql  # GD tables (already applied)
```

### GD Module Technical Details
- **GD API:** `http://www.boomlings.com/database` (official GD servers)
- **Database:** Supabase PostgreSQL, raw SQL via `get_db_engine()`
- **Commands format:** underscore style (`/gd_user`, `/gd_level`, `/player_stats`)
- **Submit:** 2-step stateless (state in `_GD_SUBMIT_STATE` dict)
- **Moderate:** Pagination with inline approve/reject buttons
- **Callback:** Handled via `gd_moderate_*` prefix in webhook callback routing

## Блокеры

Нет активных блокеров (DATABASE_URL подключена).

## Следующая сессия

### Family Circle — объединён в LTHub (WEB-10)
- Отдельный Vercel-проект `family_circle` (familycircle-nine.vercel.app) удалён; медиация теперь часть LTHub
- Страницы `/family`, `/family/room`, `/family/result`, API `/api/family/*` в `api/index.py` (Flask)
- Таблицы rooms/members/messages/needs/final_reports создаются через `_ensure_family_tables()`
- LLM-вызовы через `call_ai_api()` (Groq llama-3.3), шифрование Fernet (ENCRYPTION_KEY выставлен в Vercel production)
- ⚠️ Существующие таблицы создавал Alembic старого проекта: `created_at`/`status`/`spoke_count`/`finished` — NOT NULL **без** DEFAULT на уровне БД. Поэтому во всех INSERT'ах поля передаются явно (datetime.now(timezone.utc)). При добавлении новых модулей с этими таблицами — тоже передавать явно или менять схему через ALTER.

### GD Module Testing
- Проверка всех GD команд через webhook
- Edge cases
- UI/UX

## План: Debt Payment Fix + Yandex.Disk Export (2026-06-30)

### Часть 1: Погашение конкретного долга
- **JS:** renderDebts() — передавать `d.id` в showPayDebt; showPayDebt — сохранять debt_id; payDebt — отправлять debt_id
- **Python:** api_debt_pay — погашать сначала долг по debt_id, остаток — на остальные debtor→creditor по дате

### Часть 2: Экспорт долгов на Яндекс.Диск
- **scripts/export_debts_yadisk.py** — JOIN debts → transaction_details → budget_transactions → family_members, формирует JSON, загружает на Я.Диск
- **Команда /export_debts** — в api/index.py и bot/bot.py
- **HTML-страница** (debts.html) — хостинг на Яндекс.Диске

## Важные файлы для следующей сессии

- `bot/web/family_budget.py` — Flask API и frontend SPA для Family Budget
- `bot/commands/budget_commands.py` — Telegram команды /budget и /family
- `bot/budget_parser.py` — Парсер трат
- `scripts/export_debts_yadisk.py` — Экспорт на Яндекс.Диск
- `database/database.py` — SQLAlchemy модели (Family Budget в конце файла)
- `database/alembic/versions/010_family_budget_tables.py` — миграция
- `run_bot.py` — регистрация роутов (блок Family Budget)
- `api/index.py` — Vercel-дублирование роутов
- `memory_bank/projectbrief.md` — Project Deliverables для отслеживания прогресса
