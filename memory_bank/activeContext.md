# Active Context

## 📋 Задачи от пользователя (живой список, сессия 2026-08-31)

> Стоящее указание пользователя: **«все задания, которые я тебе пишу, записывай в mb»**. Каждая новая задача из чата ДОПИСЫВАЕТСЯ сюда. Перед деплоем собрать все незакоммиченные правки и прогнать `ruff` + `pytest`.

### ✅ Выполнено (в этой сессии)
- ✅ [TASK] **Code Explainer Module** — обьяснялка кода из репозиториев (2026-09-02):
  - POST `/api/code/analyze` → clone + AI-анализ файлов с комментариями
  - GET `/api/code/projects` — список проектов пользователя
  - GET `/api/code/project/<id>` — дерево файлов с AI-сводками
  - GET `/api/code/project/<id>/file?path=...` — содержимое файла + AI/пользовательские комментарии
  - POST `/api/code/project/<id>/comment` — добавить свой комментарий к строкам кода
  - DELETE `/api/code/project/<id>/comment/<cid>` — удалить свой комментарий
  - DELETE `/api/code/project/<id>` — удалить проект
  - GET `/code` — SPA с деревом файлов + подсветкой кода + AI- и пользовательскими комментариями
  - Расширяемый mapping 25+ ЯП (GDScript, Python, JS, TS, C#, Go, Rust и др.)
  - 3 таблицы PostgreSQL: `code_projects`, `code_files`, `code_user_comments`
  - AI-бюджет: батчи по 5 файлов за запрос, max 20 файлов, timeout 60s на Vercel
  - Rate limit: 5 анализов/час, 10 проектов/пользователь
  - Тесты: `tests/unit/test_code_explainer.py` — 7 тестов (analyze flow, comment flow, project delete, auth required, validation, other-user block, AI degraded fallback)
  - `ruff` чисто, `py_compile` чисто, `node --check` JS чисто
  - Карточка добавлена в бета-секцию хаба `/`

### ✅ Выполнено (ранее)
- ✅ [BUG] Admin panel 403 fix — убрана серверная проверка в хендлере `/admin` (браузер не шлёт заголовки при навигации; клиентский auth gate уже работает корректно).
- ✅ Загрузка 10 канонических аудио-треков в Supabase Storage (canon-audio bucket), добавление `audio_url` колонки в `canon_works`, redirect из `/api/canon/work/{id}/audio` на Storage URL. Все 10 треков работают (`has_audio: true`).
- ✅ Перенос Истории и Geometry Dash из бета-секции в основной раздел хаба.
- ✅ **Массовый аудит и фикс бета-модулей (3 раунда, ~29 багов):** (см. progress.md Changelog 2026-08-31)
- ✅ [TASK] Добавлено 7 новых tools для ИИ-куратора: achievements, coins, activity, daily_log, textbooks, history_detail, trivia_stats (12→19 tools).
- ✅ [TASK] Глубокий аудит + 10 фиксов безопасности (2 critical, 8 high): user_id spoofing, room ID brute-force, answer leaks, XSS, error leaks, crashes.
- ✅ [TASK] Архитектурные фиксы: Family SHA-256→bcrypt, Exam in-memory→DB, Admin серверный auth gate, 147 print()→log_error().
- ✅ [AUDIT] Глубокий аудит безопасности + удаление мёртвого кода (4 коммита: `1aa158c`, `bab353c`, `4e606a6`, `292a3be`).
- ✅ [SECURITY] XSS fix family_budget (uid экранирован), Webhook secret hardcoded fallback заменён на `"fallback_not_configured"`, log_error spam fix, DnD UniqueViolation dedup.
- ✅ [TASK] **Phase 6 OGE полностью завершена (100/100):**
  - **OGE-08** Куратор-чат (completed)
  - **OGE-09** Персистентный план дня (completed)
  - **OGE-10** Автопроверка вместо «Знаю/Не знаю» — текстовый ввод + checkAnswer() в study+trainer tabs информатики (commits `c81dff4`)
  - **OGE-11** История: термины-вкладка + фильтр типов (имена/события/термины/все) в панели «Изучить» (commit `6dd7505`)
  - **OGE-12** ИИ-подсказки везде (уже реализовано: `/api/study/hint` + floating banner на 5 страницах)

### 🔲 Осталось (бэклог, по приоритету)
- ✅ [SEC] Family budget user_id spoofing — фикс: `_get_user_id()` теперь проверяет `X-Auth-Token` → web session → `telegram_id`, frontend шлёт `X-Auth-Token` (commit pending).
- ✅ [SEC] AI chat user_id spoofing — фикс: `_get_session_user(token)` из `X-Auth-Token` перед fallback на POST body (commit pending).
- ✅ [ARCH] except Exception audit — 55 блоков найдено: 0 CRITICAL, 2 HIGH + 13/13 MEDIUM исправлены (log_error добавлен), ~40 LOW — acceptable defensive code (commit `930ac41`).
- ✅ [AI-1] `_tool_run_python` RCE sandboxing — regex blocklist + restricted env (commit `f1a2e06`).
- ✅ [AI-2] DnD `build_prompt` prompt injection — `_sanitize_for_prompt()` для user-supplied полей (commit `f1a2e06`).
- ✅ [FIX] In-memory rate limiting — DB-backed `_check_db_rate()` + таблица `rate_limits` для DnD/AI chat (commit `8ab128b`).
- ✅ [DB-3] Dual connection pool — `get_db_engine()` теперь переиспользует shared engine из `database.database` (commit `8ab128b`).

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
