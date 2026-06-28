# Active Context

**Последнее обновление:** 2026-06-20  
**Текущая фаза:** Chess Module Testing (прервано)

## Текущий фокус

### Error Logging System (2026-06-20)

**Цель:** Админ-панель для мониторинга ошибок с рекомендациями по исправлению.

**Статус:** В работе.

**Реализация:**
- `_ERROR_LOG` — in-memory кольцевой буфер (последние 50 ошибок)
- `log_error(module, error_type, message, recommendation)` — логирование ошибок
- `notify_admin(text)` — уведомление админа в Telegram при критических ошибках
- `/errors` — админ-команда: последние 10 ошибок с рекомендациями
- `/clear_errors` — админ-команда: очистка лога

**Категории ошибок:**
| Модуль | Тип | Рекомендация |
|--------|-----|--------------|
| DB | table_missing | Миграция из 009_phase2_tables_supabase.sql |
| DB | connection | Проверить DATABASE_URL в Vercel env |
| Chess | lichess_api | Lichess API недоступен |
| Chess | history_query | Таблица chess_games не создана |
| GD | gd_api | GD API недоступен |
| GD | submission_save | Проверить таблицу submissions |
| AI | groq_api | Проверить GROQ_API_KEY |

**Точки входа:** `api/index.py` —addErrorLog ~15 критичных error handlers + 2 admin commands

### GD Module for Vercel (2026-06-07)

**Цель:** Довести парсинг игровых сообщений на Vercel до production E2E — все боты из чата LucasTeam должны парситься через reply "парсинг".

**Статус:** ✅ Завершено. Все GD команды перенесены в `api/index.py` для Vercel.

**Завершено:**
- ✅ Sync GD API клиент (`fetch_gd_user`, `fetch_gd_level`) через `requests`
- ✅ `format_gd_user_stats()`, `format_gd_level_info()` — форматирование ответов
- ✅ 18 raw-SQL helpers для работы с таблицами GD (levels, submissions, player_stats, level_completions)
- ✅ `/gd` — справка по GD командам
- ✅ `/gd_user <ник>` — инфо об игроке в GD
- ✅ `/gd_level <id>` — инфо об уровне GD
- ✅ `/leaderboard` — топ уровней с количеством прохождений
- ✅ `/my_stats` — личная статистика
- ✅ `/player_stats @user` — статистика другого игрока
- ✅ `/submit <название>` — отправка прохождения (2-step: название → медиа)
- ✅ `/moderate` — админ-модерация с пагинацией и inline-кнопками
- ✅ `/add_level <название> <позиция>` — админ: добавить уровень
- ✅ `/set_level_position <id> <позиция>` — админ: изменить позицию
- ✅ Callback handler для `gd_moderate_*` (page/approve/reject)
- ✅ Ruff + py_compile passed

**Технический стек:**
- Command router pattern в `api/index.py`
- Прямые SQL queries через SQLAlchemy + `text()`
- Supabase PostgreSQL через `DATABASE_URL`
- Минимальные зависимости (flask, requests, sqlalchemy, psycopg2-binary)
- Все stateless (без диалогов, ConversationHandler)

### Memory Bank Canon Sync (2026-06-02)

- Канонический Memory Bank: `memory_bank/` в корне репозитория.
- `docs/memory-bank/` больше не является альтернативным источником статусов; это legacy mirror/указатель на `memory_bank/`.
- `memory_bank/projectbrief.md` восстановлен по правилу `AGENTS.md`: раздел `## Project Deliverables` имеет стабильные ID, статусы, веса с суммой ровно `100`; completed-вес = `90`.
- Из старого `docs/memory-bank` исключены как неканоничные: ручной paste-парсинг, SQLite-only production, активный shop/games/D&D scope, Bridge/VK как production runtime.
- Полезная legacy-запись про `bot/template_coder/` перенесена в `memory_bank/dialog_template_coder_module.md`: фактический модуль параметрический, без pair/triple lookup tables, с `/done`.
- В старом `docs/memory-bank/activeContext.md` был обнаружен Telegram bot token. Он удалён из memory mirror; токен следует считать скомпрометированным и перевыпустить через BotFather.

### ✅ Завершено в этой сессии (2026-06-03)

1. **Chess Module (CH-02, CH-03, CH-04) — 12%**
   - ✅ CH-02: Реализована команда `/chess_link <username>` для привязки Lichess аккаунта
   - ✅ CH-03: Реализованы команды `/chess_rating` и `/chess_stats` (базовые версии)
   - ✅ CH-04: Реализована команда `/puzzle` с изображением шахматной доски
   - Синхронный Lichess API клиент (fetch_lichess_user, 8s timeout)
   - Функции работы с таблицей `chess_accounts` (get_chess_account, link_chess_account)
   - Изображение доски через Lichess board export GIF API
   - Inline кнопка "🔗 Решить на Lichess"
   - Защита от привязки одного аккаунта к нескольким пользователям
   - Файлы: `api/index.py` (+341 строка)
   - Коммиты: `fb3819e`, `10266ba`, `8f33214`
   - Таблица `chess_accounts` уже в миграции `009_phase2_tables_supabase.sql`

2. **Chess Module Testing**
   - ✅ Протестированы все базовые команды через webhook
   - ✅ Lichess API работает корректно
   - ✅ Daily puzzle API возвращает данные
   - ✅ Изображение доски отправляется в Telegram
   - ✅ Webhook обрабатывает команды без ошибок

### 🎯 Следующие шаги

1. **Chess Module: Доработка (CH-05, CH-06)** — 8%
   - Система наград за решение задач
   - История решённых задач
   - CH-TEST

2. **GD Module Testing:** 3%
   - Ручное тестирование всех GD команд через webhook

3. **Universe Module (UN-TEST):** 2%
   - Manual testing всех GD команд через webhook
   - Edge cases и UI/UX проверки

## Checkpoint: Phase 2 Progress

**Phase 2: 78/100 (78%)** (+3% GD Module + +1% UN-03)
- ✅ AI Module: 15% (completed)
- ✅ Mom Module: 19% (completed)
- ✅ GD Module: 30% (GD-01 to GD-07 completed + GD for Vercel)
- ✅ Universe Module: 12% (UN-01 to UN-03 completed)
- ⏳ Chess Module: 12% (CH-02, CH-03, CH-04 completed, CH-05, CH-06, CH-TEST remaining: 8%)

**Chess Module Progress: 12/20 (60%)**
- ✅ CH-02: /chess_link command (3%)
- ✅ CH-03: /chess_rating, /chess_stats basic (4%)
- ✅ CH-04: /puzzle with board image (5%)
- ⏳ CH-05: Puzzle rewards system (3%)
- ⏳ CH-06: Bank integration + history (3%)
- ⏳ CH-TEST: Manual testing (2%)

**Remaining:** 26% (Chess: 8%, GD-TEST: 3%, Universe: 4%, buffer: 11%)

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

Нет активных блокеров.

## Следующая сессия

### GD Module Testing
- Проверка всех GD команд через webhook
- Edge cases
- UI/UX

### Приоритет: Chess Module Доработка (CH-05, CH-06)
   - Парсить `perfs` из Lichess API (bullet, blitz, rapid, classical ratings)
   - Показывать количество игр, winrate если доступно
   - Реализовать систему проверки решения puzzle (через callback buttons или текстовый ввод)

3. **Chess Module: Система наград**
   - Интегрировать с таблицей `user_coins`
   - Начислять монеты за правильное решение puzzle
   - Добавить cooldown на получение наград (last_puzzle_at)

4. **Universe Module: /pray команда**
   - Генерация молитв через AI с каноническим форматом
   - Использовать существующий `call_ai_api()` с промптом из projectbrief

## Важные файлы для следующей сессии

- `api/index.py` — основной webhook handler (строки 1500-1650 для chess команд)
- `database/migrations/009_phase2_tables_supabase.sql` — схема chess_accounts и user_coins
- `memory_bank/projectbrief.md` — Project Deliverables для отслеживания прогресса
