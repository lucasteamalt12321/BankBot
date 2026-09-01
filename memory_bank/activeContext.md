# Active Context

## 📋 Задачи от пользователя (живой список, сессия 2026-08-31)

> Стоящее указание пользователя: **«все задания, которые я тебе пишу, записывай в mb»**. Каждая новая задача из чата ДОПИСЫВАЕТСЯ сюда. Перед деплоем собрать все незакоммиченные правки и прогнать `ruff` + `pytest`.

### ✅ Выполнено (в этой сессии)
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
- ✅ [TASK] «Нельзя добавить 2 учебника с одинаковым предметом и описанием»: теперь нельзя. Уникальность по `(subject, title)` (локация игнорируется). Сервер: 409 «Такой учебник уже добавлен» (SELECT перед INSERT в `api_textbooks_create`). Клиент: `m-add` сверяет `subject+title` в массиве и отсекает дубль до отправки запроса; кнопка блокируется на время fetch. Тест `test_duplicate_subject_title_rejected` (9/9 passed, локально bcrypt заглушён — Termux без Rust, на проде/CI bcrypt ставится из requirements.txt). Внимание: при rebase после `git pull` были конфликты в `activeContext.md` — разрешены.

### 🔲 Осталось (бэклог, по приоритету)
- 🔲 [DB-3] Dual connection pool — архитектурный рефакторинг `database/connection.py` + `api/index.py` (объединить два engine в один).
- 🔲 [AI-1] `_tool_run_python` — полный RCE без sandboxing (требует решения по безопасности: seccomp/namespace/WASM).
- 🔲 [AI-2] DnD `build_prompt` — prompt injection через book content (system/user role separation).
- 🔲 [ARCH] 50+ `except Exception: pass` блоков — нужен аудит на критичные скрытые ошибки.

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
