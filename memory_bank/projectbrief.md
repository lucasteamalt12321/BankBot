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

### Phase 1: Core Infrastructure (canonical = 90/100)

Этот раздел является каноническим источником процента выполнения по правилу `AGENTS.md`. Сумма весов ровно `100`; процент считается только по строкам со статусом `completed`.

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
| D10 | ParserRegistry + production E2E парсинг игровых сообщений | completed | 5 |
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
| D23 | Persistent PostgreSQL/Supabase production storage | completed | 9 |
| D24 | HF webhook runtime baseline + production diagnostics | completed | 8 |

**Phase 1 Sum: 95/100 completed** (D18 остаётся `in_progress`).

**Legacy note:** ранняя копия `docs/memory-bank/projectbrief.md` содержала устаревший список с ручным парсингом, SQLite-only runtime и shop/games/D&D как активным scope. Эти сведения не являются каноном. Bridge/VK остаются в репозитории как legacy/compatibility-код, но не учитываются как production deliverables текущего webhook-first BankBot.

### Phase 2: Feature Expansion (новые модули)

#### 🎮 Geometry Dash Module (30%)

| ID | Deliverable | Status | Weight |
|----|-------------|--------|--------|
| GD-01 | Схема и таблицы Supabase (levels, submissions, player_stats, level_completions) | completed | 5 |
| GD-02 | Команда /submit (заявка на прохождение) | completed | 4 |
| GD-03 | Админ-панель /moderate (модерация заявок) | completed | 5 |
| GD-04 | Логика сложности (хардест и топ-100) | completed | 4 |
| GD-05 | Команды статистики (/leaderboard, /my_stats, /player_stats) | completed | 5 |
| GD-06 | Админ-команды (/add_level, /set_level_position) | completed | 4 |
| GD-07 | Интеграция с GD API (gd.py, /gd_user, /gd_level) | completed | 3 |
| GD-TEST | Тестирование GD Module (unit + integration + manual) | pending | 3 |

**GD Module: 30/33 (91%)**

---

#### ♟ Chess Module (20%)

| ID | Deliverable | Status | Weight |
|----|-------------|--------|--------|
| CH-01 | Схема и таблица Supabase (chess_accounts, user_coins) | completed | 2 |
| CH-02 | Команда /chess_link <ник> (привязка Lichess аккаунта) | completed | 3 |
| CH-03 | /chess_rating и /chess_stats (базовые версии) | completed | 4 |
| CH-04 | /puzzle и /chess_puzzle (задача с изображением доски) | completed | 5 |
| CH-05 | Puzzle rewards: награды монетами за решение задач | pending | 3 |
| CH-06 | History: история решённых задач | pending | 2 |
| CH-TEST | Тестирование Chess Module (manual + integration) | pending | 2 |

**Chess Module: 14/21 (67%)**

---

#### 🌟 Universe Module (14%)

| ID | Deliverable | Status | Weight |
|----|-------------|--------|--------|
| UN-01 | Схема и таблицы Supabase (infection_status, daily_prayer_log) | completed | 4 |
| UN-02 | Команды /infect, /tea, /daily_prayer | completed | 4 |
| UN-03 | /generate_prayer — генерация молитв через AI (уже реализовано в AI Module) | completed | 4 |
| UN-TEST | Тестирование Universe Module (manual) | pending | 2 |

**Universe Module: 12/14 (86%)**

---

#### 🤖 AI Module (17%)

| ID | Deliverable | Status | Weight |
|----|-------------|--------|--------|
| AI-01 | AI Manager с поддержкой нескольких провайдеров | completed | 5 |
| AI-02 | /chat <персонаж> <текст> — диалог с олеговирусом/чаем | completed | 3 |
| AI-03 | /generate_prayer — генерация молитв | completed | 3 |
| AI-04 | /ask_canon <вопрос> — вопросы по канону | completed | 2 |
| AI-05 | /ai_model <название> — выбор модели | completed | 2 |
| AI-TEST | Тестирование AI Module (manual) | pending | 2 |

**AI Module: 15/17 (88%)**

---

#### 🧑‍🏫 Mom Module (21%)

| ID | Deliverable | Status | Weight |
|----|-------------|--------|--------|
| MOM-01 | Веб-приложение: экран чтения (6 предложений) | completed | 6 |
| MOM-02 | Веб-приложение: экран вопросов (проверка ответов) | completed | 3 |
| MOM-03 | Backend: /reading_generate с HF API и fallback | completed | 5 |
| MOM-04 | UI: регулировка шрифта, печать единым листом | completed | 5 |
| MOM-05 | Дополнительные улучшения (озвучивание, статистика) | pending | 1 |
| MOM-TEST | Тестирование Mom Module (manual + frontend) | pending | 2 |

**Mom Module: 19/22 (86%)**

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

**Phase 1 (Core): 95/100 completed**  
**Phase 2 (Features): 78/100 completed** (GD-01-07: 27%, CH-01-04: 14%, UN-01-03: 14%, AI-01-05: 15%, MOM-01-04: 19%, GD-TEST/CH-TEST/UN-TEST/AI-TEST/MOM-TEST: 0%)  
**Общий прогресс проекта: 95% (Phase 1) + 78% (Phase 2)**

**Важное уточнение:** Phase 1 отражает текущую готовность базовой инфраструктуры (90%). Phase 2 добавляет новые игровые и ИИ-модули. Парсинг (D10, D18) остаётся главной целью и будет завершён параллельно с Phase 2. Миграция 009 успешно применена к Supabase — все таблицы Phase 2 созданы. 

**Завершённые модули:**
- **AI Module (15%):** Полностью реализован — AI Manager, /chat, /generate_prayer, /ask_canon, /ai_model
- **Mom Module (19%):** Полностью реализован — веб-приложение тренажёр чтения, двухэкранный интерфейс, генерация через HF API с fallback, проверка ответов, печать
- **GD Module (27%):** Core функциональность реализована — БД схема, /submit, /moderate, статистика, GD API интеграция
- **Chess Module (14%):** Базовая функциональность — /chess_link, /chess_rating, /chess_stats, /puzzle с изображением доски и inline-кнопкой
- **Universe Module (14%):** Базовая функциональность — /infect, /tea, /daily_prayer, /generate_prayer (через AI Module)

**Осталось:** Manual testing всех модулей (11%), Chess rewards + history (5%), buffer (6%)

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
| CH-02 | Команда /chess_link <ник> (привязка Lichess аккаунта) | completed | 3 |
| CH-03 | /chess_rating и /chess_stats (базовые версии) | completed | 4 |
| CH-04 | /puzzle и /chess_puzzle (задача с изображением доски) | completed | 5 |
| CH-05 | Puzzle rewards: награды монетами за решение задач | pending | 3 |
| CH-06 | History: история решённых задач | pending | 2 |
| UN-03 | /generate_prayer — генерация молитв через AI (уже реализовано в AI Module) | completed | 4 |
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

Каждый модуль Phase 2 должен пройти **ручное тестирование** (manual testing) перед финальным завершением:

1. **Запуск бота** — локально через `py -3.12 bot/main.py` или на HF
2. **Проверка команд** — каждая команда модуля тестируется вручную
3. **Edge cases** — проверка ошибок, пустых данных, некорректного ввода
4. **UI/UX** — корректность отображения, кнопок, форматирования
5. **Database** — проверка сохранения данных в БД через SQL-запросы
6. **Integration** — проверка взаимодействия с другими модулями

### Manual Testing Checklist по модулям

#### 🎮 Geometry Dash Module (GD-TEST)

**Вес:** 3%

**Команды для тестирования:**
- [ ] `/submit` — отправка прохождения (видео/фото)
  - [ ] Ввод названия уровня
  - [ ] Загрузка видео
  - [ ] Загрузка фото
  - [ ] Предпросмотр медиа
  - [ ] Подтверждение отправки
  - [ ] Отмена отправки
  - [ ] Проверка записи в `submissions` таблицу
  - [ ] Проверка обновления `player_stats.total_submissions`
- [ ] `/moderate` (admin) — модерация заявок
  - [ ] Отображение списка pending submissions
  - [ ] Пагинация (⬅️ Назад / ➡️ Вперёд)
  - [ ] Подтверждение заявки (✅)
  - [ ] Отклонение заявки (❌)
  - [ ] Проверка обновления `submissions.status`
  - [ ] Проверка обновления `player_stats.total_approved`
  - [ ] Проверка создания `level_completions` записи
- [ ] `/leaderboard` — топ-100 уровней (pending)
- [ ] `/my_stats` — личная статистика (pending)
- [ ] `/player_stats @user` — статистика игрока (pending)
- [ ] `/add_level` (admin) — добавление уровня (pending)
- [ ] `/set_level_position` (admin) — изменение позиции (pending)
- [ ] `/gd_user <ник>` — статистика из GD API (pending)
- [ ] `/gd_level <id>` — информация об уровне (pending)

**Edge cases:**
- [ ] Отправка текста вместо медиа в `/submit`
- [ ] Отправка `/submit` без названия уровня
- [ ] Модерация несуществующей заявки
- [ ] Доступ к `/moderate` не-админом
- [ ] Пустой список заявок в `/moderate`

**Database checks:**
- [ ] `SELECT * FROM submissions WHERE user_id = <test_user>`
- [ ] `SELECT * FROM player_stats WHERE user_id = <test_user>`
- [ ] `SELECT * FROM level_completions WHERE user_id = <test_user>`

---

#### ♟ Chess Module (CH-TEST)

**Вес:** 2%

**Команды для тестирования:**
- [ ] `/chess link <ник>` — привязка Lichess аккаунта
  - [ ] Проверка существования ника через Lichess API
  - [ ] Сохранение в `chess_accounts`
  - [ ] Обработка несуществующего ника
- [ ] `/chess rating` — рейтинг пользователя
  - [ ] Отображение рейтинга из Lichess
  - [ ] Обработка отсутствия привязки
- [ ] `/chess stats` — статистика пользователя
  - [ ] Отображение статистики из Lichess
- [ ] `/online` — кто онлайн на Lichess
  - [ ] Список онлайн пользователей из команды
  - [ ] Кэширование на 30 секунд
- [ ] `/puzzle` — задача с наградой
  - [ ] Получение случайной задачи из Lichess
  - [ ] Начисление 5 монет в `user_coins`
  - [ ] Ограничение: раз в минуту
- [ ] `/chess club info` — информация о клубе
  - [ ] Отображение информации о LucasTeam клубе
  - [ ] Inline-кнопка с URL

**Edge cases:**
- [ ] Привязка уже привязанного аккаунта
- [ ] Запрос рейтинга без привязки
- [ ] Повторный `/puzzle` раньше минуты
- [ ] Lichess API недоступен

**Database checks:**
- [ ] `SELECT * FROM chess_accounts WHERE user_id = <test_user>`
- [ ] `SELECT * FROM user_coins WHERE user_id = <test_user>`

---

#### 🌟 Universe Module (UN-TEST)

**Вес:** 2%

**Команды для тестирования:**
- [ ] `/infect` — заражение вирусом
  - [ ] Случайный выбор вируса (олеговирус/LTL-паразит)
  - [ ] Сохранение в `infection_status`
  - [ ] Отображение симптомов
- [ ] `/tea` — чай для облегчения
  - [ ] Временное облегчение (1 час)
  - [ ] Обновление `tea_cooldown_until`
  - [ ] Cooldown проверка
- [ ] `/daily_prayer` — ежедневная молитва
  - [ ] Случайная молитва из списка
  - [ ] Проверка: не чаще раза в день
  - [ ] Сохранение в `daily_prayer_log`
- [ ] `/olegovirus_name` — генерация имени через AI (pending)
- [ ] `/lore_event` — генерация события через AI (pending)

**Edge cases:**
- [ ] Повторный `/infect` при активной инфекции
- [ ] `/tea` раньше cooldown
- [ ] Повторный `/daily_prayer` в тот же день
- [ ] AI недоступен для генерации

**Database checks:**
- [ ] `SELECT * FROM infection_status WHERE user_id = <test_user>`
- [ ] `SELECT * FROM daily_prayer_log WHERE user_id = <test_user>`

---

#### 🤖 AI Module (AI-TEST)

**Вес:** 2%

**Команды для тестирования:**
- [ ] `/chat олеговирус <текст>` — диалог с олеговирусом
  - [ ] Персонализированный промпт (кхм-кхм, навязчивый)
  - [ ] Ответ от AI
  - [ ] Fallback при недоступности AI
- [ ] `/chat чай <текст>` — диалог с чаем
  - [ ] Персонализированный промпт (мудрый, eight-nine)
  - [ ] Ответ от AI
- [ ] `/generate_prayer` — генерация молитвы
  - [ ] Генерация через AI с ключевыми словами (чай, eight-nine, настой)
  - [ ] Fallback на предустановленные молитвы
- [ ] `/ask_canon <вопрос>` — вопросы по канону
  - [ ] Поиск в `data/canon_knowledge.txt`
  - [ ] Ответ с релевантной информацией
  - [ ] Fallback при отсутствии совпадений
- [ ] `/ai_model <название>` — выбор модели
  - [ ] Сохранение в `user_preferences`
  - [ ] Применение при следующих вызовах

**Edge cases:**
- [ ] `/chat` без персонажа
- [ ] `/chat` с неизвестным персонажем
- [ ] AI API недоступен (все провайдеры)
- [ ] `/ask_canon` с вопросом вне канона
- [ ] `/ai_model` с несуществующей моделью

**Database checks:**
- [ ] `SELECT * FROM user_preferences WHERE user_id = <test_user>`

---

#### 🧑‍🏫 Mom Module (MOM-TEST)

**Вес:** 2%

**Команды для тестирования:**
- [ ] `/reading_trainer` — ссылка на веб-приложение
  - [ ] Inline-кнопка с URL
  - [ ] Открытие веб-приложения
- [ ] Веб-приложение: экран чтения
  - [ ] Загрузка 6 предложений
  - [ ] Регулировка шрифта (A+ / A-)
  - [ ] Сохранение размера шрифта в localStorage
  - [ ] Кнопка "Дальше →"
  - [ ] Кнопка "Новый текст"
- [ ] Веб-приложение: экран вопросов
  - [ ] Отображение 2-3 вопросов
  - [ ] Ввод ответа
  - [ ] Проверка ответа (регистронезависимое сравнение)
  - [ ] Правильный ответ: ✓ Верно!
  - [ ] Неправильный ответ: ✗ Неверно, попробуй ещё
  - [ ] Переход к следующему вопросу
  - [ ] Кнопка "← Назад к чтению"
- [ ] Веб-приложение: печать
  - [ ] Кнопка "🖨️ Печать"
  - [ ] Печать единым листом (предложения + вопросы с пустыми строками)
  - [ ] Скрытие кнопок и полей ввода при печати
- [ ] Backend: `/reading_generate`
  - [ ] Генерация через HF API (mistralai/Mistral-7B-Instruct-v0.2)
  - [ ] Fallback на predefined sets при ошибке API
  - [ ] Таймаут 15 секунд

**Edge cases:**
- [ ] HF API недоступен (fallback на predefined sets)
- [ ] Ответ с лишними пробелами
- [ ] Печать без загруженного текста
- [ ] Регулировка шрифта за пределы 24-72px

**Frontend checks:**
- [ ] Адаптивный дизайн на телефоне (iPhone SE)
- [ ] Адаптивный дизайн на планшете (iPad)
- [ ] localStorage сохраняет размер шрифта

---

## Testing Progress

| Module | Commands Tested | Edge Cases | DB Checks | Status |
|--------|----------------|------------|-----------|--------|
| GD | 0/9 | 0/5 | 0/3 | 0% |
| CH | 0/6 | 0/4 | 0/2 | 0% |
| UN | 0/5 | 0/4 | 0/2 | 0% |
| AI | 0/5 | 0/5 | 0/1 | 0% |
| MOM | 0/4 | 0/4 | 0/0 | 0% |
| **Total** | **0/29** | **0/22** | **0/8** | **0%** |

---

## Testing Notes

- Тестирование проводится вручную через Telegram клиент
- Для локального тестирования: `py -3.12 bot/main.py`
- Для HF тестирования: через production bot в https://t.me/lucasteamgroup
- Database checks через SQL-запросы к Supabase PostgreSQL
- Все edge cases должны быть покрыты
- UI/UX проверяется на корректность отображения, форматирования, кнопок
- После завершения тестирования модуля — обновить статус в `projectbrief.md`
