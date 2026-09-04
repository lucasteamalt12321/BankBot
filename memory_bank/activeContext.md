# Active Context

## 📋 Задачи от пользователя (живой список, сессия 2026-08-31)

> Стоящее указание пользователя: **«все задания, которые я тебе пишу, записывай в mb»**. Каждая новая задача из чата ДОПИСЫВАЕТСЯ сюда. Перед деплоем собрать все незакоммиченные правки и прогнать `ruff` + `pytest`.

### ✅ Выполнено (в этой сессии)
- ✅ [BUG] Admin panel 403 fix — убрана серверная проверка в хендлере `/admin` (браузер не шлёт заголовки при навигации; клиентский auth gate уже работает корректно).
- ✅ Загрузка 10 канонических аудио-треков в Supabase Storage (canon-audio bucket), добавление `audio_url` колонки в `canon_works`, redirect из `/api/canon/work/{id}/audio` на Storage URL. Все 10 треков работают (`has_audio: true`).
- ✅ Перенос Истории и Geometry Dash из бета-секции в основной раздел хаба.
- ✅ **Массовый аудит и фикс бета-модулей (3 раунда, ~29 багов):** (см. progress.md Changelog 2026-08-31)
- ✅ [TASK] Добавлено 7 новых tools для ИИ-куратора: achievements, coins, activity, daily_log, textbooks, history_detail, trivia_stats (12→19 tools).
- ✅ [TASK] Глубокий аудит + 10 фиксов безопасности (2 critical, 8 high): user_id spoofing, room ID brute-force, answer leaks, XSS, error leaks, crashes.
- ✅ [TASK] Архитектурные фиксы: Family SHA-256→bcrypt, Exam in-memory→DB, Admin серверный auth gate, 147 print()→log_error().
  - **Raund 1 (12 багов):** D&D Content-Type, hubTrack, hover кнопки, import re; Trivia тип session, удаление после ответа, pool<3 guard; Family finished=True перед отчётом, каскадное удаление; Verbs type coercion, двойной load; Music temp cleanup.
  - **Raund 2 (10 багов):** D&D input validation (action 2000, name 100, fix 1000, dice 50), generic errors, roll rate limiting; DnD runtime guarded JSON (Gemini/Groq); Exam safe dict cleanup; Suggest rate limiting (5/min); Trivia rate limiting (30/min); AI Chat file upload limit (2MB), _VIRTUAL_PC eviction (max 50), message limits (4000 chars, 20 history).
  - **Raund 3 (7 багов):** SSRF protection browse_web (block private IPs, limit redirects, cap response 50KB); json.loads try/except (2 crash-бага); None guard character.lower(); _pc_extract_reply type handling; Family chat error detection + intent_type sanitization; DnD prompt injection protection.
- ✅ [NEW MODULE] Трекер учебников (`/textbooks`) — бета-модуль. 3 локации (дом/школа/рюкзак), drag-and-drop (десктоп) + tap-to-move (мобайл), модалка добавления с 15 предметами и цветами. API: GET/POST/PUT/DELETE. Тесты 8/8 passed.
- ✅ [BUG] `textbooks`: «создал 1 учебник → появилось 5; при удалении появляются новые». Диагностика: бэкенд корректен (репро: 5 POST = 5 строк, 1 DELETE = минус 1 строка). Причина — фронтенд: кнопка «Добавить» не блокировалась во время async-запроса (двойной тап/клик → несколько POST) и массив `books` мог копиться без дедупликации. Фикс: (1) `renderBooks()` дедуплицирует `books` по `id`; (2) в обработчике `m-add` — guard `if(btn.disabled)return`, `btn.disabled=true/false` вокруг fetch, и отсев дубликатов по (subject,title,location) с подтверждением «Такой учебник уже добавлен». JS проверен `node --check`, JS `renderBooks`/`m-add` синтаксически валидны.
- ✅ [BUG] `textbooks`: серверная защита от дубликатов — в `api_textbooks_create` перед INSERT выполняется SELECT по `(user_id, subject, title)`; если совпадение найдено → `409 {error: "Такой учебник уже добавлен"}` (защита от обхода клиентской проверки, например добавление с разных устройств).
- ✅ [TASK] «Нельзя добавить 2 учебника с одинаковым предметом и описанием»: теперь нельзя. Уникальность по `(subject, title)` (локация игнорируется). Сервер: 409 «Такой учебник уже добавлен» (SELECT перед INSERT в `api_textbooks_create`). Клиент: `m-add` сверяет `subject+title` в массиве и отсекает дубль до отправки запроса; кнопка блокируется на время fetch. Тест `test_duplicate_subject_title_rejected` (9/9 passed, локально bcrypt заглушён — Termux без Rust, на проде/CI bcrypt ставится из requirements.txt).
- ✅ [BUG] log_error spam fix — `notify_admin()` только при `error_type != "info"`, SEND_MSG не логирует status=200 (commit `ffe5e5f`).
- ✅ [BUG] DnD UniqueViolation spam — дедупликация перед `CREATE UNIQUE INDEX` в `dnd_characters` (commit `be3fba4`).
- ✅ [BUG] Admin panel 403 fix — убрана серверная проверка в хендлере `/admin` (браузер не шлёт заголовки при навигации; клиентский auth gate уже работает корректно).
- ✅ [AUDIT] Глубокий аудит безопасности, ошибок, логики + dnd_runtime (4 субагента). Найдено и исправлено:
  - **[CRITICAL]** Debug endpoints без авторизации → добавлен `_web_admin_session()` guard на все 5 эндпоинтов (`/api/debug_dnd`, `/debug_last_error`, `/debug_db`, `/debug_submissions`, `/debug_addexpense`).
  - **[HIGH]** `int()` без try/except на user input → обёрнуто в 6 локациях (GD admin level update, moderate reject/approve, quiz generate, debug_dnd).
  - **[HIGH]** `request.get_json()` без `silent=True` в Telegram webhook → исправлено (блокирует бота при malformed body).
  - **[MEDIUM]** `gd_moderate_callback` IndexError → `len(parts) < 3` → `< 4` (.parts[3] требует 4 элемента).
  - **[HIGH]** dnd_runtime `_resolve_user_id` — `conn.commit()` на autocommit connection → `engine.begin()` (connection pool corruption).
  - **[HIGH]** `cmd_dnd_stop` останавливает player-сессию вместо master-сессии → теперь ищет master-сессию сначала.
  - **[MEDIUM]** `session_summary`/`build_prompt` — falsy check `if c.get('hit_points')` → `is not None` (HP=0 отображался как "?").
  - **[MEDIUM]** `/dnd_fix` без авторизации → только master может исправлять AI.
  - **[MEDIUM]** `cmd_dnd_start` race condition → INSERT RETURNING id вместо SELECT AFTER INSERT.

### 🔲 Осталось (бэклог, по приоритету)
- 🔲 [BUGHUNT] **Большая охота на баги (2026-09-01)** — запущены N субагентов по модулям: auth/security, OGE study, GD/Chess/DnD/Trivia, Family+VK, Canon/Music/Exam, TG-bot, core ОГЭ-данные, frontend JS, database, AI-curator. Отчёт в процессе.
- ✅ [CHORE] **Удаление мёртвого кода** (коммит `1aa158c`): подтверждено, что файлы нигде не импортируются → удалены `bot/commands/beta_commands.py`, `bot/handlers/message_handler.py`/`callback_handler.py` (aiogram-stubs, никогда не регистрировались), `core/managers/scheduler_manager.py`, `core/school/` (пустой пакет), `core/systems/beta_economy.py`. Ложные срабатывания другого ИИ (НЕ удалять): `core/repositories/` (активно используется через core.di/services), reading_trainer (активная страница), audio_service/ vk_mini_app/ (сервисы), `002_beta_features_schema.sql` (читается мигратором).
- ✅ [CHORE] **Удаление неиспользуемого TG↔VK моста** (коммит `bab353c`): `bridge_bot/` + `vk_bot/` + `bot/bridge/` целиком + связанные тесты (`tests/bridge/`, `tests/vk_bot/`, `tests/unit/test_bridge_*`), выпилены `TestBridgeBotSmoke`/`TestVKBotSmoke` из `tests/smoke/test_startup.py`, обновлены докстринги (`bot/main.py`, `bot/middleware/__init__.py`, `common/__init__.py`). Мост был отключён по умолчанию (`BRIDGE_ENABLED=false`) и не использовался прод-путём (`run_bot.py`/`api/index.py`). Точная картина: **один** основной Telegram-бот (PTB) в `bot/` = `bot/main.py`+`bot/bot.py`+`bot/commands/*`+`core/*`; `bot/bridge/` был вложенным отдельным aiogram-мостом, его код лежал в `bridge_bot/`/`vk_bot/`.
- ✅ [CHORE] **Ревизия проекта + удаление мёртвого кода (раунд 2, коммит `4e606a6`):**
  - Удалены: `database/migrations/apply_beta_migration.py` + `002_beta_features_schema.sql` (SQLite-only, проект на PostgreSQL), `setup_webhook.html`, `reading_trainer.html` в корне, `webapp/reading_trainer/`, `public/reading_trainer/` + `public/reading_trainer.html` (4 дубликата reading_trainer), 20× `test_*.db` (мусор от тестов).
  - Вычищены пустые aiogram stub-роутеры: `game_router`, `system_router`, `admin_router`, `shop_router` удалены из `bot/commands/__init__.py`, `bot/router.py`, `bank_bot/handlers/__init__.py`. `__all__` сокращён.
  - `bot/commands/__init__.py` больше не импортирует `aiogram` (не нужен).
- ✅ [PROD-BUG] **Study ALTER deadlock в live-логах Telegram** (`[STUDY] alter skipped`): каждый serverless cold start гоняет `_ensure_study_progress_tables`, и параллельные `ALTER TABLE study_progress ADD COLUMN IF NOT EXISTS created_at/last_correct_at` в одной общей транзакции взаимно дедлочатся (`DeadlockDetected`) и «убивают» транзакцию (`InFailedSqlTransaction` → дальнейшие команды aborted). Фикс: миграции вынесены из общей транзакции в автономные `_alter_add_column_if_missing` (свой `engine.begin()` на каждую), перед ALTER — проверка `_column_exists` (pragma_table_info для SQLite / information_schema для PG), retry ×4 на deadlock/serialization/aborted с backoff. Прямые проверки: старая таблица без колонок → мигрируется; свежая → no-op; `_column_exists` корректно определяет наличие. `py_compile`/`ruff` чисто.
- 🔲 [DB-3] Dual connection pool — архитектурный рефакторинг `database/connection.py` + `api/index.py` (объединить два engine в один).
- 🔲 [AI-1] `_tool_run_python` — полный RCE без sandboxing (требует решения по безопасности: seccomp/namespace/WASM).
- 🔲 [AI-2] DnD `build_prompt` — prompt injection через book content (system/user role separation).
- 🔲 [ARCH] 50+ `except Exception: pass` блоков — нужен аудит на критичные скрытые ошибки.
- 🔲 [SEC] Family budget user_id spoofing через query param (`bot/web/family_budget.py:18-23`).
- 🔲 [SEC] Family budget XSS — uid инжектится в HTML/JS без экранирования (`family_budget.py:1066-1075`).
- 🔲 [SEC] Webhook secret hardcoded fallback (`api/index.py:307`) — критично если env не задан.
- 🔲 [SEC] AI chat / Verbs user_id spoofing — нет session verification.
- 🔲 [BUG] In-memory rate limiting неэффективен в serverless (Vercel cold start сбрасывает).

## Previous Context (from earlier sessions)

### ✅ AI через OpenRouter работает на проде (2026-08-25, вечер)
- **Итог цепочки:** Gemini → Groq → **OpenRouter** (ключ добавлен в Vercel env). Gemini так и не получен (AI Studio недоступен из РФ даже с VPN), Groq мёртв — реально отвечает OpenRouter: `nvidia/nemotron-3-super-120b-a12b:free` и др.
- **Прод проверен:** `/api/test_ai` → 200 «Hello» чисто; локально `_ai_chat` на русском → «Париж».
- **Ключевые грабли:** free-модели — reasoning, лечится `reasoning:{enabled:false}`; пулы :free часто 429 → перебор списка моделей из `OPENROUTER_MODEL`.

### ✅ ИИ-алгоритм: куратор выбирает вопрос из БД (2026-08-26, коммит `be76752`)
- **`/api/quiz/ai-generate`**: куратор видит каталог всех вопросов модуля + слабые карточки ученика → выбирает лучший.
- Кнопка "ИИ (генерация)" во всех 5 модулях. Informatics получил algo-selector.
- 53 tests, ruff clean. Deployed ✓ Ready.

### ✅ Максимальная прокачка OGE-системы (2026-08-26)
- **SM-2 стандартный**: ease растёт +0.1 при правильном, −0.2 при ошибке (пол 1.3, потолок 3.0).
- **`/api/study/stats`**: per-module readiness, streak, today summary, forecast 14 дней.
- **`/api/study/due-cards`**: список карточек на повторение.
- **`/api/quiz/generate` + `/api/quiz/check`**: серверный квиз-движок для всех 5 модулей.
- **Тесты**: 53 passed. В проде.
