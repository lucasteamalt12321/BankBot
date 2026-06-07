# Active Context

**Последнее обновление:** 2026-06-06  
**Текущая фаза:** Vercel Production Fixes + AI Trivia

## Текущий фокус

### Vercel /trivia + AI Fixes (2026-06-06)

**Цель:** Восстановить работу бота на Vercel, добавить AI-генерацию вопросов викторины через Groq.

**Статус:** Бот работает на Vercel, викторина генерируется через Groq AI с контекстом канона.

**Завершено:**
- ✅ Исправлен HF Space import error (`short_mode_command` добавлен обратно в `core_commands.py`)
- ✅ Обновлён `data/canon_knowledge.txt` до v2.9 (12 мая 2026)
- ✅ AI-викторина на Vercel: Groq API + канон, fallback на 23 готовых вопроса
- ✅ Webhook переключён с HF Space на Vercel
- ✅ BOT_TOKEN настроен на Vercel (project-level env var)
- ✅ `api/index.py` больше не зависит от `bot/*` модулей (вся логика inline)

**Коммиты:**
- `0b8980d` — fix: add short_mode_command and long_mode_command back to core_commands
- `9a8a658` — ci: force vercel redeploy

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

1. **GD Module for Vercel** — приоритетное
   - Перенести GD commands в `api/index.py` с префиксом `/gd_`
   - Команды:
     - `/gd_submit` — отправка прохождения
     - `/gd_moderate` — админ-модерация
     - `/gd_leaderboard` — топ уровней
     - `/gd_my_stats` — личная статистика
     - `/gd_player_stats` — статистика игрока
     - `/gd_user <username>` — статистика из GD API
     - `/gd_level <id>` — информация об уровне
     - `/gd` — справка по всем GD командам
   - Файлы: `api/index.py` (добавление GD handlers)
   - Требуется: адаптация ConversationHandler под stateless Vercel

1. **Chess Module: Доработка (CH-05, CH-06)** — 8%
   - Добавить детальные рейтинги в `/chess_rating` (bullet, blitz, rapid, classical)
   - Добавить игровую статистику в `/chess_stats` (games, wins, losses, draws)
   - Реализовать систему проверки решения задач
   - Добавить награды за решение задач (интеграция с user_coins)
   - Добавить историю решённых задач
   - CH-TEST: Manual testing всех команд

2. **Universe Module (UN-03):** 4%
   - UN-03: /pray команда с генерацией молитв через AI
   - UN-TEST: Manual testing

3. **GD Module Testing:** 3%
   - Manual testing всех GD команд
   - Edge cases и UI/UX проверки

## Checkpoint: Phase 2 Progress

**Phase 2: 71/100 (71%)**
- ✅ AI Module: 15% (completed)
- ✅ Mom Module: 19% (completed)
- ✅ GD Module: 56% (GD-01 to GD-07 completed, GD-TEST manual testing remaining: 3%)
- ⏳ Chess Module: 12% (CH-02, CH-03, CH-04 completed, CH-05, CH-06, CH-TEST remaining: 8%)
- ⏳ Universe Module: 10% (UN-01-02 completed, UN-03 pending: 4%)

**Chess Module Progress: 12/20 (60%)**
- ✅ CH-02: /chess_link command (3%)
- ✅ CH-03: /chess_rating, /chess_stats basic (4%)
- ✅ CH-04: /puzzle with board image (5%)
- ⏳ CH-05: Puzzle rewards system (3%)
- ⏳ CH-06: Bank integration + history (3%)
- ⏳ CH-TEST: Manual testing (2%)

**Remaining:** 29% (Chess: 8%, GD-TEST: 3%, Universe: 4%, buffer: 14%)

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

### GD Module Vercel Architecture (новая)
```
api/index.py                  # GD commands handler (Vercel webhook)
├── get_gd_leaderboard()      # Show top levels
├── get_my_stats()            # User personal stats
├── get_player_stats()        # Another player stats
├── /gd_submit                # Submit level completion (legacy - needs state)
├── /gd_moderate              # Admin moderation (legacy - needs state)
├── /gd_leaderboard           # Top 20 levels
├── /gd_my_stats              # Personal statistics
├── /gd_player_stats @user    # Another player stats
├── /gd_user <username>       # GD API user stats
├── /gd_level <id>            # GD API level info
└── /gd                       # GD commands help

database/database.py
├── Level                     # Level definitions
├── Submission                # User submissions
├── PlayerStats               # User statistics
└── LevelCompletion           # Completed levels

database/migrations/
└── 009_phase2_tables_supabase.sql  # GD tables
```

### GD Module Technical Details
- **GD API Base:** `https://gd.api.lucasteam.xyz` (custom)
- **Database:** Supabase PostgreSQL
- **Commands format:** underscore style (`/gd_leaderboard`, `/gd_my_stats`)
- **Vercel limitation:** ConversationHandler не поддерживается, нужна упрощённая реализация
- **Админ-функционал:** требует дополнительной логики для stateless среды

## Блокеры

Нет активных блокеров.

## Следующая сессия

### Приоритет 1: GD Module для Vercel
1. **Перенести GD commands в `api/index.py` с префиксом `/gd_`**
   - `/gd_submit` — отправка прохождения
   - `/gd_moderate` — админ-модерация  
   - `/gd_leaderboard` — топ уровней
   - `/gd_my_stats` — личная статистика
   - `/gd_player_stats` — статистика игрока
   - `/gd_user <username>` — статистика из GD API
   - `/gd_level <id>` — информация об уровне
   - `/gd` — справка по всем GD командам
   - Файлы: `api/index.py` (добавление GD handlers)
   - Требуется: адаптация под stateless Vercel (без ConversationHandler)

2. **GD Module Testing** — после переноса
   - Проверка всех команд
   - Edge cases
   - UI/UX

### Приоритет 2: Chess Module Доработка (CH-05, CH-06)
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
