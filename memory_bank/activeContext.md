# Active Context

**Последнее обновление:** 2026-06-30  
**Текущая фаза:** Universe Module implementation — /infect, /tea, /daily_prayer + auto message modification

## Текущий фокус

### Universe Module (2026-06-30)

**Что сделано:**
- ✅ `/infect` — случайный вирус (олеговирус/LTL-паразит), симптомы, кулдаун 24ч
- ✅ `/tea` — чай для облегчения на 1 час, cooldown проверка
- ✅ `/daily_prayer` — случайная молитва, не чаще раза в день
- ✅ Авто-модификация сообщений заражённых: бот удаляет оригинал и пересылает с подписью (олеговирус: "кхм-кхм" через слова, LTL-паразит: +"☕")
- ✅ Автосоздание таблиц `infection_status` и `daily_prayer_log`
- ✅ Cooldown для `/addexpense` (5 мин)

**Проблемы:**
- Пользователь сообщает, что команды не отвечают
- `/addexpense` спамил документацией каждую минуту (исправлено кулдауном)

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
