# Project Brief — BankBot (LucasTeam)

## Цели проекта

Telegram-бот-агрегатор для автоматического отслеживания игровой активности и начисления банковских монет. Объединяет несколько игровых платформ в единую экосистему с общей валютой (банковские монеты).

## Рамки проекта

- Главный production focus: безопасный парсинг игровых сообщений и начисление банковских очков.
- Priority platforms for current webhook phase: GD Cards, Shmalala, Гуся Cards; True Mafia/Bunker RP остаются legacy/secondary до отдельного подтверждения.
- Единый баланс, история транзакций и базовая админка для управления начислениями.
- Production HF runtime должен перейти на Telegram webhook вместо polling.
- Shop, games, D&D, BridgeBot, VK Bot, watch/ADB/ntfy realtime flows исключаются из ближайшего production runtime scope по решению пользователя.
- Парсинг должен оставаться защищённым: только по реальному Telegram reply; ручной paste fallback запрещён из-за риска накрутки.

## Репозиторий

https://github.com/lucasteamalt12321/BankBot

## Точка входа

HF production: `run_bot.py` → Flask webhook endpoint → `TelegramBot.initialize_for_webhook()`.

Local/dev polling fallback: `bot/main.py` → `TelegramBot.run()`.

---

## Project Deliverables

### Phase 1: Core Infrastructure (completed = 90/100)

| ID | Deliverable | Status | Weight |
|----|-------------|--------|--------|
| D01 | Централизованная конфигурация (Pydantic Settings) | completed | 5 |
| D02 | Вынос конфиденциальных данных в env | completed | 5 |
| D03 | Разделение зависимостей (requirements) | completed | 4 |
| D04 | Исправление импортов | completed | 3 |
| D05 | Слой репозиториев (Repository pattern) | completed | 7 |
| D06 | Service layer (бизнес-логика из handlers) | completed | 5 |
| D07 | Рефакторинг bot.py на модули | completed | 5 |
| D08 | Middleware обработки ошибок | completed | 5 |
| D09 | Graceful shutdown | completed | 4 |
| D10 | ParserRegistry + production E2E парсинг игровых сообщений | in_progress | 5 |
| D11 | Блокировки балансов + Unit of Work | completed | 5 |
| D12 | Connection pooling | completed | 3 |
| D13 | Аудит SQL injection | completed | 5 |
| D16 | Аудит и очистка неиспользуемого кода | completed | 4 |
| D17 | Объединение дублирующихся парсеров | completed | 3 |
| D18 | E2E тесты основных сценариев парсинга и банка | in_progress | 5 |
| D19 | Тесты безопасности (SQL injection, race conditions) | completed | 3 |
| D20 | Coverage 80%+ | completed | 3 |
| D21 | Документация (README, DEPLOYMENT.md, диаграммы) | completed | 2 |
| D22 | Docstrings Google style | completed | 2 |
| D23 | Bridge-модуль: конфигурация + миграция bridge_state | completed | 3 |
| D24 | Bridge-модуль: loop_guard, message_queue, vk_sender | completed | 4 |
| D25 | Bridge-модуль: telegram_forwarder, vk_listener, main_bridge | completed | 4 |
| D26 | Bridge-модуль: media_handler (TG→VK, VK→TG) | completed | 3 |
| D27 | vk_bot/: config, bot, handlers, main | completed | 3 |

**Phase 1 Sum: 90/100** (D10 и D18 in_progress)

### Phase 2: Feature Expansion (новые модули)

#### 🎮 Geometry Dash Module (30%)

| ID | Deliverable | Status | Weight |
|----|-------------|--------|--------|
| GD-01 | Схема и таблицы Supabase (levels, submissions, player_stats, level_completions) | completed | 5 |
| GD-02 | Команда /submit (заявка на прохождение) | completed | 4 |
| GD-03 | Админ-панель /moderate (модерация заявок) | pending | 5 |
| GD-04 | Логика сложности (хардест и топ-100) | pending | 4 |
| GD-05 | Команды статистики (/leaderboard, /my_stats, /player_stats) | pending | 5 |
| GD-06 | Админ-команды (/add_level, /set_level_position) | pending | 4 |
| GD-07 | Интеграция с GD API (gd.py, /gd_user, /gd_level) | pending | 3 |
| GD-TEST | Тестирование GD Module (unit + integration + total) | pending | 3 |

**GD Module Sum: 33%** (GD-01-02: 9%, GD-TEST: 3%)  
**Chess Module Sum: 21%** (CH-01: 2%, CH-TEST: 2%)  
**Universe Module Sum: 14%** (UN-01-02: 8%, UN-TEST: 2%)  
**AI Module Sum: 17%** (AI-01-05: 15%, AI-TEST: 2%)  
**Mom Module Sum: 21%** (MOM-01-04: 19%, MOM-TEST: 2%)

**Функциональность:**
- 6 простых предложений (3-4 слова каждое)
- 2-3 вопроса по содержанию с проверкой ответов
- Возврат к чтению без потери прогресса
- Печать одним листом (предложения + вопросы с пустыми строками)
- Регулировка шрифта (36-48px, сохранение в localStorage)
- Генерация через HF Inference API (mistralai/Mistral-7B-Instruct или google/flan-t5-base)
- Резервные наборы при недоступности API
- Адаптивный дизайн для телефонов/планшетов

---

**Phase 1 (Core): 90/100 completed**  
**Phase 2 (Features): 34/100 completed** (GD-01: 5%, GD-02: 4%, CH-01: 2%, UN-01: 4%, UN-02: 4%, AI-01: 5%, AI-02: 3%, AI-03: 3%, AI-04: 2%, AI-05: 2%, MOM-01-04: 19% = 51%, округлено до 34% с учётом тестов)  
**Общий прогресс проекта: 90% (Phase 1) + 30% (Phase 2)**

**Важное уточнение:** Phase 1 отражает текущую готовность базовой инфраструктуры (90%). Phase 2 добавляет новые игровые и ИИ-модули. Парсинг (D10, D18) остаётся главной целью и будет завершён параллельно с Phase 2. Миграция 009 успешно применена к Supabase — все таблицы Phase 2 созданы. AI Module полностью завершён (AI-01 до AI-05): менеджер моделей, команды /chat, /generate_prayer, /ask_canon. Mom Module полностью завершён (MOM-01 до MOM-04): веб-приложение с двумя экранами, регулировка шрифта, генерация через HF API с резервными наборами, проверка ответов, печать единым листом. GD-02 /submit реализован: ConversationHandler, media upload, DB persistence. **Все модули Phase 2 требуют unit + integration + total тестирования перед финальным завершением.**

---

## Next Tasks (Post-Review Cleanup)

| ID | Task | Priority | Status |
|----|------|----------|--------|
| T01 | Исправить merge conflict markers в README.md | P0 | completed |
| T02 | Добавить BotApplication в bot/main.py | P0 | completed |
| T03 | Исправить test_user_manager.py — добавить BotApplication | P0 | completed |
| T04 | Исправить merge conflicts в тестах | P1 | completed |
| T05 | Ruff cleanup: 0 errors в продакшн коде | P2 | completed |
| T06 | Удалить лишние папки (examples/, for_programmer/, docs/archive/) | P2 | completed |
| T07 | Удалить test_*.db файлы | P2 | completed |

## Additional Tasks (2026-04-03)

| ID | Task | Priority | Status |
|----|------|----------|--------|
| PARSE01 | Production E2E парсинг игровых сообщений по ответам | in_progress | P0 |
| TRIVIA01 | Мини-игра: Брейн-Ринг по Канону Олеговируса | in_progress | P0 |
| GD-02 | Команда /submit (заявка на прохождение) | pending | 4 |
| GD-03 | Админ-панель /moderate (модерация заявок) | pending | 5 |
| GD-04 | Логика сложности (хардест и топ-100) | pending | 4 |
| GD-05 | Команды статистики (/leaderboard, /my_stats, /player_stats) | pending | 5 |
| GD-06 | Админ-команды (/add_level, /set_level_position) | pending | 4 |
| GD-07 | Интеграция с GD API (gd.py, /gd_user, /gd_level) | pending | 3 |
| CH-02 | Команда /chess link | pending | 3 |
| CH-03 | /chess rating и /chess stats | pending | 4 |
| CH-04 | /online (кто онлайн на Lichess) | pending | 3 |
| CH-05 | /puzzle с наградой монетами (таблица user_coins) | pending | 5 |
| CH-06 | /chess club info | pending | 2 |
| UN-03 | Генерация через ИИ (/olegovirus_name, /lore_event) | pending | 4 |
| MOM-05 | Дополнительные улучшения (озвучивание, статистика, подсказка) | pending | 1 |

**MOM notes:** Веб-приложение создано (`webapp/reading_trainer/`), backend `/reading_generate` реализован в `run_bot.py` с HF API и fallback-наборами, фронтенд-логика включает два экрана (чтение/вопросы), проверку ответов, печать единым листом, регулировку шрифта (24-72px). Статика размещена в `webapp/reading_trainer/`, `public/reading_trainer.html`, `bot/web/reading_trainer.py`.

**N02 notes:** multi-transport realtime delivery (`Telegram + ntfy + optional ADB`), env-настройки ntfy/ADB, маппинг `telegram_id -> users.id`, unit-тесты `tests/unit/test_notification_system.py`, команды `/notify_status` и `/test_adb`.

**DB01 notes:** P0 / первая очередь. Проблема: на Hugging Face локальная SQLite/data storage ephemeral, при restart/rebuild база могла обнуляться. Production/HF подключён к persistent Supabase PostgreSQL через HF Secret `DATABASE_URL` с Session Pooler URI; `/health` подтверждает `database=postgresql`, external `/feedback?limit=N` подтверждает `storage=postgresql`. Реализовано: aliases DB URL, нормализация `postgres://` → `postgresql://`, Alembic URL override, bootstrap пустой PostgreSQL БД из SQLAlchemy metadata + Alembic stamp head, SQLAlchemy-based `AdminSystem`, PostgreSQL connect timeout, `/health` с backend diagnostic, dialect-aware feedback DDL. SQLite оставлен local/dev fallback. DB01 completed; мониторить Supabase limits/latency и runtime-команды после deploy.

**HF01 notes:** Flask-сервер на `7860` (`/health`, `/metrics`, `/logs`), Dockerfile `python:3.12-slim`, IP-based proxy (`195.201.225.248`) с `Host: tgproxy.me` + `verify=False`, safe `http_client` builder fallback, `SPACE_ID` detection, Alembic-first startup, config manager resilience к отсутствующим таблицам.

**PARSE01 notes:** Это главный продуктовый фокус после стабилизации runtime/DB/UX. Требуется довести парсинг реальных игровых сообщений по ответам до production E2E: fixtures реальных сообщений, правила по поддерживаемым играм, мониторинг successful/failed parses, понятные админские diagnostics и защита от ложных начислений. Текущий инфраструктурный контур не считать полноценным завершением этого результата.

**FB01 notes:** реализованы команды `/feedback <предложение или жалоба>` с алиасами `/suggest` и `/complaint`; обращения сохраняются в SQLite-таблицу `feedback_entries` с JSONL fallback/debug mirror (`data/feedback.jsonl`): текст, Telegram ID, username, chat ID, chat type и UTC timestamp. Админ может читать последние обращения через `/feedback_list [limit]` (до 20 записей). Для внешнего чтения с HF добавлен защищённый endpoint `GET /feedback?limit=N` с `Authorization: Bearer <FEEDBACK_READ_TOKEN|HF_TOKEN|BOT_TOKEN>`; при сохранении пишется structured log `Feedback saved` с полным текстом обращения.

**AI01 notes:** пользователь попросил добавить ИИ, но обязательно бесплатную реализацию. Реализован локальный AI-lite помощник без платных API, без обязательных внешних ключей и без зависимости от LLM-провайдера. Команды: `/ai <вопрос>`, `/ask <вопрос>`, `/ai_help`. Scope: подсказки по командам BankBot, feedback, магазину, играм, D&D, профилю, админским возможностям и локальной базе канона Олеговируса/LTL из Google Doc (`bot/ai/knowledge.py`: глоссарий, Teaology, candy economy, LTRS, high-canon article links). `/short`/`/long` применяются глобально через `bot/response_modes.py`: long-сообщения автоматически компактятся в short mode, а `/long` сохраняет полный текст. Возможность подключения внешнего free/OpenAI-compatible endpoint допускается только как optional env-настройка позже, не как обязательная зависимость.

**AI02 notes:** Никита предложил использовать бесплатный Hugging Face API, чтобы AI был умнее локального keyword-helper. Требование: только optional/free реализация, без обязательной платной зависимости. Дизайн следующей итерации: env-флаги `AI_PROVIDER=huggingface|local`, `HF_INFERENCE_TOKEN`/`HF_TOKEN`, `HF_INFERENCE_MODEL`, короткие таймауты, лимит prompt/response, safe system prompt про BankBot, fallback на локальный AI-lite при quota/rate-limit/network errors. Нельзя ломать HF runtime и нельзя логировать токены/полный приватный prompt.
| PR10 | Архитектурная инвентаризация слоёв `core/src/utils/bank_bot` | P2 | completed |
| PR11 | Сокращение legacy-дублей и shim-слоёв | P2 | completed |
| PR12 | Упрощение wiring и startup-кода в `bot/bot.py` и entrypoints | P2 | completed |
| PR13 | Ревизия structured logging и эксплуатационных полей | P2 | completed |

**PR10-PR11 notes:** выполнена инвентаризация слоёв и закреплён runtime/legacy contract в `docs/README.md`. Рискованные runtime-зависимости не удалялись; legacy/shim namespaces (`src.parsers`, `core/repositories`, `utils/*` shims, aiogram `shop_commands.py`) зафиксированы как frozen/compatibility, новый код направлен в канонические слои.

**PR12-PR13 notes:** `bot/bot.py` получил чистый `build_polling_kwargs(is_hf)` без изменения HF timeout/retry semantics; structured polling logs сохранены. UX/watchlist закрыт безопасными runtime-правками: `/shop` и `/games` больше не дублируют вывод, `/games_list` показывает активные сессии, `/dnd_*` исправлены на `core.systems.dnd_system`, неизвестные команды получают fallback-ответ.

**TRIVIA01 notes:** Мини-игра «Брейн-Ринг по Канону Олеговируса». Команда `/trivia` запускает викторину в чате с вопросом по лору из `bot/ai/knowledge.py`. Использование inline-кнопок позволяет мгновенно фиксировать клики через `CallbackQueryHandler`, определять победителя, начислить ему монеты в Supabase PostgreSQL и предотвращать повторные клики. Включает защиту от спама командами в одном чате.

---

## Testing Strategy — Phase 2 Modules

### Общие принципы тестирования

Каждый модуль Phase 2 должен пройти три уровня тестирования:

1. **Unit Tests** — изолированное тестирование логики без внешних зависимостей
2. **Integration Tests** — тестирование взаимодействия с БД, Telegram API, внешними сервисами
3. **Total (E2E) Tests** — полный сценарий использования от начала до конца

### Тесты по модулям

#### 🎮 Geometry Dash Module (GD-TEST)

| ID | Test Type | Scope | Status |
|----|-----------|-------|--------|
| GD-TEST-1 | Unit | `gd_commands_ptb.py` ConversationHandler states | pending |
| GD-TEST-2 | Unit | `Submission` model validation | pending |
| GD-TEST-3 | Unit | `PlayerStats` update logic | pending |
| GD-TEST-4 | Integration | `/submit` command flow (level → media → confirm) | pending |
| GD-TEST-5 | Integration | DB persistence (submissions table) | pending |
| GD-TEST-6 | Integration | Player stats auto-update | pending |
| GD-TEST-7 | Total | Full user journey: submit → admin review | pending |
| GD-TEST-8 | Total | Error handling: invalid media, duplicate submission | pending |

**GD-TEST Sum: 3%**

#### ♟ Chess Module (CH-TEST)

| ID | Test Type | Scope | Status |
|----|-----------|-------|--------|
| CH-TEST-1 | Unit | Lichess API integration (mocked) | pending |
| CH-TEST-2 | Unit | `ChessAccount` model validation | pending |
| CH-TEST-3 | Unit | Rating/stats parsing logic | pending |
| CH-TEST-4 | Integration | `/chess link` command flow | pending |
| CH-TEST-5 | Integration | `/chess rating` with real Lichess API | pending |
| CH-TEST-6 | Integration | `/puzzle` reward logic (user_coins) | pending |
| CH-TEST-7 | Total | Full chess workflow: link → rating → puzzle | pending |

**CH-TEST Sum: 2%**

#### 🌟 Universe Module (UN-TEST)

| ID | Test Type | Scope | Status |
|----|-----------|-------|--------|
| UN-TEST-1 | Unit | `/infect` random virus selection | pending |
| UN-TEST-2 | Unit | `/tea` cooldown logic | pending |
| UN-TEST-3 | Unit | `/daily_prayer` daily limit check | pending |
| UN-TEST-4 | Integration | `infection_status` table persistence | pending |
| UN-TEST-5 | Integration | `daily_prayer_log` daily check | pending |
| UN-TEST-6 | Total | Full infection/tea cycle | pending |

**UN-TEST Sum: 2%**

#### 🤖 AI Module (AI-TEST)

| ID | Test Type | Scope | Status |
|----|-----------|-------|--------|
| AI-TEST-1 | Unit | `AIModelManager` provider switching | pending |
| AI-TEST-2 | Unit | HF API call with timeout | pending |
| AI-TEST-3 | Unit | Response caching (5 min TTL) | pending |
| AI-TEST-4 | Integration | `/chat` with olegovirus/tea prompts | pending |
| AI-TEST-5 | Integration | `/ask_canon` knowledge base search | pending |
| AI-TEST-6 | Total | Full AI workflow: user question → response | pending |

**AI-TEST Sum: 2%**

#### 🧑‍🏫 Mom Module (MOM-TEST)

| ID | Test Type | Scope | Status |
|----|-----------|-------|--------|
| MOM-TEST-1 | Unit | `/reading_generate` fallback sets | pending |
| MOM-TEST-2 | Unit | Sentence/answer validation | pending |
| MOM-TEST-3 | Integration | Frontend: reading → questions flow | pending |
| MOM-TEST-4 | Integration | Frontend: answer checking (case-insensitive) | pending |
| MOM-TEST-5 | Integration | Frontend: print layout (PDF-ready) | pending |
| MOM-TEST-6 | Total | Full user journey: load → read → answer → print | pending |

**MOM-TEST Sum: 2%**

---

## Testing Progress

| Module | Unit | Integration | Total | Status |
|--------|------|-------------|-------|--------|
| GD | 0/8 | 0/5 | 0/3 | 0% |
| CH | 0/7 | 0/4 | 0/2 | 0% |
| UN | 0/6 | 0/3 | 0/2 | 0% |
| AI | 0/6 | 0/3 | 0/2 | 0% |
| MOM | 0/6 | 0/3 | 0/2 | 0% |
| **Total** | **0/33** | **0/18** | **0/11** | **0%** |

---

## Testing Checklist

- [ ] GD-TEST-1: Unit tests for ConversationHandler states
- [ ] GD-TEST-2: Unit tests for Submission model
- [ ] GD-TEST-3: Unit tests for PlayerStats logic
- [ ] GD-TEST-4: Integration test for /submit flow
- [ ] GD-TEST-5: Integration test for DB persistence
- [ ] GD-TEST-6: Integration test for stats update
- [ ] GD-TEST-7: Total test for full user journey
- [ ] GD-TEST-8: Total test for error handling
- [ ] CH-TEST-1: Unit tests for Lichess API
- [ ] CH-TEST-2: Unit tests for ChessAccount model
- [ ] CH-TEST-3: Unit tests for rating parsing
- [ ] CH-TEST-4: Integration test for /chess link
- [ ] CH-TEST-5: Integration test for /chess rating
- [ ] CH-TEST-6: Integration test for /puzzle reward
- [ ] CH-TEST-7: Total test for chess workflow
- [ ] UN-TEST-1: Unit tests for /infect
- [ ] UN-TEST-2: Unit tests for /tea cooldown
- [ ] UN-TEST-3: Unit tests for /daily_prayer
- [ ] UN-TEST-4: Integration test for infection_status
- [ ] UN-TEST-5: Integration test for daily_prayer_log
- [ ] UN-TEST-6: Total test for infection/tea cycle
- [ ] AI-TEST-1: Unit tests for AIModelManager
- [ ] AI-TEST-2: Unit tests for HF API timeout
- [ ] AI-TEST-3: Unit tests for response caching
- [ ] AI-TEST-4: Integration test for /chat
- [ ] AI-TEST-5: Integration test for /ask_canon
- [ ] AI-TEST-6: Total test for AI workflow
- [ ] MOM-TEST-1: Unit tests for /reading_generate
- [ ] MOM-TEST-2: Unit tests for validation
- [ ] MOM-TEST-3: Integration test for reading flow
- [ ] MOM-TEST-4: Integration test for answer checking
- [ ] MOM-TEST-5: Integration test for print layout
- [ ] MOM-TEST-6: Total test for full journey

---

## Testing Notes

- Unit tests: use `pytest` with mocks for external dependencies
- Integration tests: use test database (SQLite) and real API calls with rate limiting
- Total tests: full user journey with real Telegram updates
- Coverage target: 80%+ for all new code
- Ruff: 0 errors for all test files
