# Project Brief — LTHub (LucasTeam Hub)

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
| D18 | E2E тесты основных сценариев парсинга и банка | completed | 5 |
| D19 | Тесты безопасности (SQL injection, race conditions) | completed | 3 |
| D20 | Coverage 80%+ | completed | 3 |
| D21 | Документация (README, DEPLOYMENT.md, диаграммы) | completed | 2 |
| D22 | Docstrings Google style | completed | 2 |
| D23 | Persistent PostgreSQL/Supabase production storage | completed | 9 |
| D24 | HF webhook runtime baseline + production diagnostics | completed | 8 |

**Phase 1 Sum: 100/100 completed** (D18 завершён).

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
| CH-05 | Puzzle rewards: награды монетами за решение задач | completed | 3 |
| CH-06 | History: история решённых задач | completed | 2 |
| CH-TEST | Тестирование Chess Module (manual + integration) | pending | 2 |

**Chess Module: 18/21 (86%)**

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

#### 💬 AI Chat — Reply & Mention Mode (8%)

Новый модуль: AI-ответы на реплаи и @упоминания бота. Заменяет команду `/chat`.

| ID | Deliverable | Status | Weight |
|----|-------------|--------|--------|
| AIC-01 | Кэширование BOT_ID при старте (getMe) | completed | 1 |
| AIC-02 | Характер пользователя в user_preferences (preferred_character) | completed | 1 |
| AIC-03 | Обнаружение реплаев на сообщения бота (reply_to.from.id == BOT_ID) | completed | 1 |
| AIC-04 | Обнаружение @упоминаний бота (entities type=mention) | completed | 1 |
| AIC-05 | AI-роутинг: построение prompt по характеру + call_ai_api() | completed | 1 |
| AIC-06 | Команда /character — выбор характера для пользователя | completed | 1 |
| AIC-07 | Команда /character_all — глобальный характер (только админы) | completed | 1 |
| AIC-08 | Удаление /chat, обновление справки /start | completed | 1 |

**AI Chat Module: 8/8 (100%)**

---

#### 🧑‍🏫 Mom Module (21%)

| ID | Deliverable | Status | Weight |
|----|-------------|--------|--------|
| MOM-01 | Веб-приложение: экран чтения (6 предложений) | completed | 6 |
| MOM-02 | Веб-приложение: экран вопросов (проверка ответов) | completed | 3 |
| MOM-03 | Backend: /reading_generate с HF API и fallback | completed | 5 |
| MOM-04 | UI: регулировка шрифта, печать единым листом | completed | 5 |
| MOM-05 | Дополнительные улучшения (озвучивание, статистика) | completed | 1 |
| MOM-TEST | Тестирование Mom Module (manual + frontend) | pending | 2 |

**Mom Module: 20/22 (91%)**

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

#### 💰 Family Budget Module (BGT)

**PRD:** Домашний бюджет (Family Budget Web App). Версия 1.0, 26 июня 2026, Автор: Лука (LucasTeam), Статус: черновик для реализации.

---

**1. Цели проекта**

Веб-приложение для учёта общих семейных трат, чтобы мама, Юля и Лука могли фиксировать, кто и за кого платил, автоматически рассчитывать долги, погашать их частями с каскадным пересчётом при переплате. Изоляция данных каждой семьи. Ключевая метрика: семья перестаёт ссориться из-за денег.

---

**2. Целевая аудитория**

Первичные: мама, Юля, Лука (семья). Вторичные: другие семьи через BankBot. Технический уровень низкий — крупные кнопки, минимум текста, адаптивный дизайн для телефонов.

---

**3. Функциональные требования**

**3.1. Управление семьёй:**
- Создание семьи → название, генерация 6-значного кода приглашения
- Присоединение по коду
- Просмотр участников (имена, дата присоединения)
- Администратор (создатель) может удалять участников и расформировывать семью

**3.2. Учёт трат:**
- Форма: кто заплатил (select), за кого (select multiple), сумма (int > 0), категория (Еда/Транспорт/Хозяйство/Развлечения/Другое), описание (text, опционально)
- Автосоздание долгов: если payer ≠ for_whom → долг for_whom перед payer. Несколько for_whom — сумма делится поровну

**3.3. Погашение долгов (каскадный алгоритм):**
1. Найти все активные долги debtor→creditor, старые первыми
2. Списать сумму последовательно с каждого долга
3. Если осталась переплата после закрытия всех долгов этому кредитору → предложить погасить другие долги debtor перед другими кредиторами
4. Если других долгов нет → переплата становится долгом creditor перед debtor (роли меняются)
- История погашений сохраняется в таблицу payments

**3.4. Просмотр состояния:**
- Сводка долгов (главный экран): «Мама → Юле 250 ₽» с кнопкой «Погасить»
- Баланс каждого участника (чистый)
- История транзакций с фильтрацией по дате, категории, участнику
- Статистика (опционально): траты за неделю/месяц по категориям

**3.5. Редактирование/удаление:**
- Удаление: только администратор или автор записи, с пересчётом долгов
- Редактирование — опционально (позже), проще удалить и создать заново

---

**4. Нефункциональные требования**

- Адаптивный дизайн для мобильных (Mobile First)
- Загрузка < 2 с, ответ API < 500 мс
- Изоляция по family_id, авторизация через BankBot
- Хранение в Supabase (уже есть бэкапы)

---

**5. UX/UI — экраны:**
1. **Авторизация:** «Создать семью» / «Присоединиться по коду»
2. **Главный:** сводка долгов, общий баланс, список долгов, плавающая кнопка «+» для новой траты
3. **Добавление траты:** форма с полями, кнопка «Сохранить»
4. **Погашение долга:** предзаполненные должник/кредитор, поле суммы, кнопка «Погасить»
5. **История:** список транзакций с фильтрами

---

**6. API (Flask) — все эндпоинты требуют family_id:**
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/budget/family/status | Инфо о семье пользователя |
| POST | /api/budget/family/create | Создать семью (name, display_name) |
| POST | /api/budget/family/join | Присоединиться по коду (code, display_name) |
| GET | /api/budget/transactions | Список трат (family_id, limit) |
| POST | /api/budget/transactions | Добавить трату (payer_id, amount, category, for_whom_ids) |
| DELETE | /api/budget/transactions/{id} | Удалить трату + пересчёт долгов |
| GET | /api/budget/debts | Список активных долгов |
| POST | /api/budget/debts/pay | Каскадное погашение (debtor_id, creditor_id, amount) |
| GET | /api/budget/balance | Чистый баланс каждого участника |

---

**7. База данных (6 таблиц Supabase):**

**families:** id (PK), name, admin_id, invite_code (6-digit, unique), created_at
**family_members:** id (PK), family_id (FK→families), user_id, display_name, joined_at
**budget_transactions:** id (PK), family_id (FK→families), payer_id, amount (int), category, description, created_at
**transaction_details:** id (PK), transaction_id (FK→budget_transactions), for_whom_id, share (int)
**debts:** id (PK), family_id (FK→families), debtor_id, creditor_id, amount_left (int), created_at, updated_at
**payments:** id (PK), family_id (FK→families), debtor_id, creditor_id, amount (int), paid_at

---

**8. Интеграция с BankBot:**
- `/budget` → ссылка на веб-приложение с `user_id` для автологина
- `/family create <название>` — создать семью, вернуть код
- `/family join <код>` — присоединиться
- `/family info` — информация о семье
- `/family leave` — выход (только не администратор)

---

**9. Критерии приёмки (AC):**
- Создание семьи и присоединение по коду
- При добавлении траты → автодолги
- Погашение уменьшает долг, переплата → следующий долг или смена ролей
- Данные видны только участникам одной семьи
- Работает на телефоне, выглядит аккуратно
- История сохраняется и доступна

---

**10. Этапы реализации (приоритеты):**
1. **MVP:** семья с одним админом, трата (1→1), просмотр долгов, каскадное погашение, ссылка из бота
2. **Итерация 2:** групповые траты (1→N), удаление транзакций, история погашений, статистика
3. **Итерация 3:** PIN-код, экспорт CSV, напоминания через BankBot

---

**11. Риски и смягчение:**
- Забывают записывать траты → напоминания, простота UI
- Ошибки ввода → удаление транзакции, пересчёт
- Споры → прозрачная история, общий доступ к балансу

---

**12. Бюджет времени:** ~8-10 часов (БД+API: 1ч, Frontend: 3-4ч, Backend: 2-3ч, Интеграция: 1ч, Тесты: 1-2ч)

---

**Deliverables:**

| ID | Deliverable | Status | Weight |
|----|-------------|--------|--------|
| BGT-01 | Проектирование БД (6 таблиц: families, family_members, budget_transactions, transaction_details, debts, payments) | completed | 5 |
| BGT-02 | Backend API (Flask): создание/присоединение к семье, управление участниками | completed | 10 |
| BGT-03 | Backend API (Flask): CRUD трат, автогенерация долгов (в т.ч. групповые траты 1→N) | completed | 15 |
| BGT-04 | Backend API (Flask): каскадное погашение с переплатой и сменой ролей | completed | 15 |
| BGT-05 | Frontend: экран авторизации (создать/присоединиться), интеграция с API | completed | 10 |
| BGT-06 | Frontend: главный экран (сводка долгов, баланс), форма добавления траты | completed | 15 |
| BGT-07 | Frontend: форма погашения долга, страница истории транзакций с фильтрацией | completed | 10 |
| BGT-08 | Интеграция с BankBot (команды /budget, /family create/join/info/leave) | completed | 5 |
| BGT-09 | Адаптивный Mobile First UI, корректное отображение на телефонах | completed | 8 |
| BGT-10 | Изоляция данных по family_id, проверка членства на каждом запросе | completed | 5 |
| BGT-TEST | Тестирование Family Budget Module (manual + frontend) | pending | 2 |

**BGT Module: 98/100 (98%)**

---

#### 🔗 VK Mini App — Budget UI (替代 Vercel)

**Цель:** Альтернативный UI для бюджет модуля во VK Mini App для пользователей без доступа к Vercel (ограничения мобильного интернета в РФ, белые списки).

**Ключевое решение:** VK аккаунт привязывается к TG аккаунту через 6-значный код. Единая база данных, общие семьи.

**Flux привязки:**
1. Пользователь открывает VK Mini App → видит экран привязки
2. Идёт в Telegram → `/linkvk` → получает 6-значный код (TTL 10 мин)
3. Вводит код в VK Mini App → POST `/api/budget/vk/link`
4. Backend связывает `vk_user_id` → `tg_user_id`
5. Далее VK Mini App работает с `user_id = tg_user_id` — тот же API

**Стек:** React 18 + TypeScript + Vite + @vkontakte/vkui + @vkontakte/vk-bridge

**Деплой:** GitHub Actions → VK Hosting (статика)

**Экраны (7):**
1. LinkPage — привязка VK ↔ TG (ввод кода)
2. CreateFamilyPage — создание семьи
3. JoinFamilyPage — вступление по коду
4. DashboardPage — баланс, долги, участники, FAB "+"
5. AddExpensePage — форма добавления траты
6. PayDebtPage — оплата долга
7. HistoryPage — история транзакций с фильтрами

**Backend изменения:**
- Добавить `flask-cors` для CORS
- Таблица `linked_vk_accounts` (vk_user_id, tg_user_id, link_code, code_expires_at)
- Endpoint `GET /api/budget/vk/status` — проверка привязки
- Endpoint `POST /api/budget/vk/link` — привязка по коду
- Bot command `/linkvk` — генерация кода

**VK Mini App пути:**
- `vk_mini_app/src/pages/LinkPage.tsx`
- `vk_mini_app/src/pages/DashboardPage.tsx`
- `vk_mini_app/src/pages/AddExpensePage.tsx`
- `vk_mini_app/src/pages/PayDebtPage.tsx`
- `vk_mini_app/src/pages/HistoryPage.tsx`
- `vk_mini_app/src/pages/CreateFamilyPage.tsx`
- `vk_mini_app/src/pages/JoinFamilyPage.tsx`
- `vk_mini_app/src/api/budget.ts` — fetch wrapper

**Деплой:**
- `.github/workflows/deploy-vk-mini-app.yml`
- Требуется secret: `VK_MINI_APPS_TOKEN`
- Требуется VK App ID (регистрация на dev.vk.com)

**Статус:** в реализации

---

**Phase 1 (Core): 100/100 completed**  
**Phase 2 (Features): 97/100 completed** (GD-01-07: 27%, CH-01-06: 18%, UN-01-03: 14%, AI-01-05: 15%, MOM-01-05: 20%, AIC-01-08: 8%, BGT-01-10: 98%, GD-TEST/CH-TEST/UN-TEST/AI-TEST/MOM-TEST/BGT-TEST: 0%)  
**Общий прогресс проекта: 100% (Phase 1) + 97% (Phase 2)**

**Важное уточнение:** Phase 1 отражает текущую готовность базовой инфраструктуры (90%). Phase 2 добавляет новые игровые и ИИ-модули. Парсинг (D10, D18) остаётся главной целью и будет завершён параллельно с Phase 2. Миграция 009 успешно применена к Supabase — все таблицы Phase 2 созданы. 

**Завершённые модули:**
- **AI Module (15%):** Полностью реализован — AI Manager, /chat, /generate_prayer, /ask_canon, /ai_model
- **AI Chat Module (8%):** Полностью реализован — reply/mention AI, /character, /character_all, память 10 личных + 50 глобальных сообщений
- **Mom Module (20%):** Полностью реализован — веб-приложение тренажёр чтения, двухэкранный интерфейс, генерация через HF API с fallback, проверка ответов, печать
- **GD Module (27%):** Core функциональность реализована — БД схема, /submit, /moderate, статистика, GD API интеграция
- **Chess Module (18%):** Полностью реализована — /chess_link, /chess_rating, /chess_stats, /puzzle с изображением доски и inline-кнопкой, награды 5 монет за решение, история решённых задач
- **Universe Module (14%):** Базовая функциональность — /infect, /tea, /daily_prayer, /generate_prayer (через AI Module)

**Осталось:** Manual testing всех модулей (11%), BGT Module тестирование (2%), buffer (3%)

---

### Phase 3: Web Portal — дублирование функций бота в веб (2026-07-26)

| ID | Deliverable | Status | Weight |
|----|-------------|--------|--------|
| WEB-00 | Хаб на `/` с карточками всех сервисов | completed | 2 |
| WEB-01 | AI Chat — веб-страница чата с выбором персонажа | completed | 15 |
| WEB-02 | D&D AI Master — StoryForge-like интерфейс | completed | 20 |
| WEB-03 | Trivia — веб-викторина по канону | completed | 12 |
| WEB-04 | Daily Prayer — страница с молитвой дня | completed | 5 |
| WEB-05 | Chess — статистика Lichess + пазлы | completed | 15 |
| WEB-06 | GD Module — профили, топ, статистика | completed | 15 |
| WEB-07 | Admin Panel — управление пользователями, ошибки | completed | 16 |
| WEB-08 | Практика глаголов — AI-генерация заданий, проверка | completed | 10 |
| WEB-09 | AI Chat: виртуальный компьютер (tool-calling: код, браузинг, файлы, фото) | completed | 8 |
| WEB-10 | Family Circle — объединение отдельного Vercel-проекта в LTHub (страницы /family, /family/room, /family/result + API /api/family/*) | completed | 6 |
| WEB-11 | Единая регистрация — страница /register, единый web_user_id, привязка Telegram | completed | 5 |

**Phase 3: 123/123 completed** (WEB-00 + WEB-01 + WEB-02 + WEB-03 + WEB-04 + WEB-05 + WEB-06 + WEB-07 + WEB-08 + WEB-09 + WEB-10 + WEB-11; WEB-07 added +16, WEB-08 added +10, WEB-09 added +8, WEB-10 added +6, WEB-11 added +5)

---

### Phase 4: Canon Module — хранение канона (CANON01)

**Цель:** Единый source of truth канона вселенной Олеговируса и LTL-паразита (Google Doc v2.9) вместо 5+ разошедшихся копий (`data/canon_knowledge.txt`, `api/canon_knowledge.txt`, дубли пулов trivia, `_PRAYERS`). Лёгкий пакет (паттерн `core/rates.py`), переживает cold start (read-only файлы из git).

| ID | Deliverable | Status | Weight |
|----|-------------|--------|--------|
| CN-01 | Пакет `core/canon/`: canon.md (текст v2.9), `__init__.py` (CANON_VERSION, load_canon_text, CanonWork/CanonTerm/CanonEntity, find_canon, render_markdown) | completed | 15 |
| CN-02 | `core/canon/works.py` — перечень произведений (Блок 3.2, уровни 🔵🟡🔴, t.me-ссылки) + `glossary.py` (Блок 4) | completed | 15 |
| CN-03 | `core/canon/questions.py` — единый пул trivia + `prayers.py` — единый `_PRAYERS` | completed | 15 |
| CN-04 | Перевод AI-lite: knowledge.py, knowledge_updater.py, ai_commands_ptb.py на core.canon | completed | 10 |
| CN-05 | Перевод trivia: bot/trivia/questions.py + api/index.py пул → единый core/canon/questions.py | completed | 10 |
| CN-06 | Перевод api/index.py: _load_canon_trivia, _PRAYERS, /ask_canon fallback | completed | 10 |
| CN-07 | Страница `/canon` (3 вкладки: текст/произведения/глоссарий) + API `/api/canon/*` + карточка на хабе | completed | 15 |
| CN-08 | Удаление data/canon_knowledge.txt и api/canon_knowledge.txt (после grep-проверки) | completed | 5 |
| CN-TEST | Тесты test_canon_module.py + /canon в e2e, ruff clean | completed | 5 |

**CANON01: 100/100**

**Факт (2026-08-07):** `core/canon/` — canon.md (оригинальный текст v2.9 с markdown-разметкой), `__init__.py` (stdlib-only: `CANON_VERSION`, `CANON_DOC_URL`, `load_canon_text`, `canon_sections`, `find_canon`, `render_markdown`, `get_glossary`/`get_works`), `works.py` (16 произведений), `glossary.py` (22 термина), `questions.py` (единый пул 24 вопросов), `prayers.py` (15 молитв). Потребители (api/index.py, bot/trivia/questions.py, bot/ai/*) переведены на core.canon; `_match_knowledge` — приоритет dynamic > static > local; удалены `data/canon_knowledge.txt` + `api/canon_knowledge.txt`. Страница `/canon` (📜 Полный текст / 🎵 Произведения / 🧩 Глоссарий) + API `/api/canon/{text,works,glossary,search}`. Тесты: **964 passed / 10 skipped**, ruff clean.

---

### Phase 4.2: Canon Works & Requests (CANON02)

**Цель:** Отображение полных текстов канонических произведений на `/canon`, заявки на канонизацию от зарегистрированных пользователей, админ-модерация заявок и право админа редактировать тексты произведений + основной документ канона (БД-overlay поверх canon.md).

| ID | Deliverable | Status | Weight |
|----|-------------|--------|--------|
| CW-01 | `_ensure_canon_tables` — таблицы canon_works (сид из CANON_WORKS), canon_requests, canon_doc + фолбэк на статику | completed | 15 |
| CW-02 | Публичные API: `/api/canon/works` (approved+content), `/api/canon/work/<id>`, `/api/canon/documents`, `POST /api/canon/request` | completed | 20 |
| CW-03 | Админ API: `/api/admin/canon/requests` (list/approve/reject), `PUT /api/admin/canon/works/<id>`, `GET/PUT/DELETE /api/admin/canon/doc` | completed | 20 |
| CW-04 | Страница `/canon`: кнопка «Читать», «Отправить заявку на канонизацию», админ-кнопки модерации/редактирования | completed | 15 |
| CW-05 | Страницы `/canon/work/<id>`, `/canon/request`, `/admin/canon` | completed | 20 |
| CW-TEST | Тесты test_canon_requests_e2e.py + расширенный _make_engine DDL, ruff clean, существующие тесты не ломаются | completed | 10 |

**CANON02: 100/100**

**Факт (2026-08-08):** всё реализовано в `api/index.py` и задеплоено. БД-слой `_ensure_canon_tables` + автокалибровка из `core.canon.works`; публичные API с фолбэком на статику при недоступности БД; админ-модерация (approve переносит заявку в `canon_works`, reject с заметкой, PUT works, overlay док-та с DELETE-сбросом); страницы `/canon` (+ «📖 Читать»/заявка), `/canon/work/<id>`, `/canon/request`, `/admin/canon` (паттерн доступа как в `/admin`). Тесты: `tests/unit/test_canon_requests_e2e.py` (7), расширен `_make_engine`; полный `tests/unit` **971 passed / 10 skipped**. Прод: все страницы 200, `/api/canon/works` отдаёт 16 си-произведений из БД, admin API 403 без токена.

---

### Phase 4.3: Canon Audio & Article View (CANON-03)

**Цель:** У треков канона появляется аудиозапись (админ загружает в админке, сайт показывает плеер и стримит файл), у статей — читаемый полный текст.

| ID | Deliverable | Status | Weight |
|----|-------------|--------|--------|
| CA-01 | БД: колонки audio_data (BYTEA), audio_name, audio_mime, audio_size в canon_works (CREATE + ALTER для прод-таблицы) | completed | 20 |
| CA-02 | Admin API: POST/DELETE `/api/admin/canon/works/<id>/audio` (multipart, лимит 4 МБ, whitelist mime mp3/ogg/wav/m4a/aac) | completed | 25 |
| CA-03 | Публичный стрим `GET /api/canon/work/<id>/audio` + поля has_audio/audio_* в works/work API | completed | 25 |
| CA-04 | Страницы: аудиоплеер `#audio` на `/canon/work/<id>`, кнопка «🎧 Слушать» на `/canon`, кнопки загрузки/удаления в `/admin/canon` | completed | 20 |
| CA-TEST | Тест test_audio_upload_stream_delete в test_canon_requests_e2e.py, ruff clean, полный tests/unit зелёный | completed | 10 |

**CANON-03: 100/100**

**Факт (2026-08-09):** всё реализовано в `api/index.py`, закоммичено (`75fe269`) и задеплоено на Vercel. Полный `tests/unit` **972 passed / 10 skipped / 0 failed**, ruff clean. Прод: `/admin/canon` 200 + JS uploadAudio, `/api/canon/works` возвращает has_audio, `/canon/work/<id>` содержит audio-card, стрим 404 для трека без аудио (корректно).

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
| PARSE01 | Production E2E парсинг игровых сообщений по ответам | completed | P0 |
| TRIVIA01 | Мини-игра: Брейн-Ринг по Канону Олеговируса | completed | P0 |
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
| MOM-05 | Дополнительные улучшения (озвучивание, статистика, подсказка) | completed | 1 |

**MOM notes:** Веб-приложение создано (`webapp/reading_trainer/`), backend `/reading_generate` реализован в `run_bot.py` с HF API и fallback-наборами, фронтенд-логика включает два экрана (чтение/вопросы), проверку ответов, печать единым листом, регулировку шрифта (24-72px). Статика размещена в `webapp/reading_trainer/`, `public/reading_trainer.html`, `bot/web/reading_trainer.py`.

**N02 notes:** multi-transport realtime delivery (`Telegram + ntfy + optional ADB`), env-настройки ntfy/ADB, маппинг `telegram_id -> users.id`, unit-тесты `tests/unit/test_notification_system.py`, команды `/notify_status` и `/test_adb`.

**DB01 notes:** P0 / первая очередь. Проблема: на Hugging Face локальная SQLite/data storage ephemeral, при restart/rebuild база могла обнуляться. Production/HF подключён к persistent Supabase PostgreSQL через HF Secret `DATABASE_URL` с Session Pooler URI; `/health` подтверждает `database=postgresql`, external `/feedback?limit=N` подтверждает `storage=postgresql`. Реализовано: aliases DB URL, нормализация `postgres://` → `postgresql://`, Alembic URL override, bootstrap пустой PostgreSQL БД из SQLAlchemy metadata + Alembic stamp head, SQLAlchemy-based `AdminSystem`, PostgreSQL connect timeout, `/health` с backend diagnostic, dialect-aware feedback DDL. SQLite оставлен local/dev fallback. DB01 completed; мониторить Supabase limits/latency и runtime-команды после deploy.

**HF01 notes:** Flask-сервер на `7860` (`/health`, `/metrics`, `/logs`), Dockerfile `python:3.12-slim`, IP-based proxy (`195.201.225.248`) с `Host: tgproxy.me` + `verify=False`, safe `http_client` builder fallback, `SPACE_ID` detection, Alembic-first startup, config manager resilience к отсутствующим таблицам.

**PARSE01 notes:** Это главный продуктовый фокус после стабилизации runtime/DB/UX. Требуется довести парсинг реальных игровых сообщений по ответам до production E2E: fixtures реальных сообщений, правила по поддерживаемым играм, мониторинг successful/failed parses, понятные админские diagnostics и защита от ложных начислений. Текущий инфраструктурный контур не считать полноценным завершением этого результата.

**PARSE01 (STATUS: completed, 2026-08-03):** все части закрыты — мониторинг (`parsed_transactions` с status в `_ensure_parsing_tables`, `_log_parsed_transaction`/`_record_parsing_result`, `admin_manager.get_parsing_stats()` считает failed_parses), idempotency (`uq_parsed_transactions_msg` частичный unique-индекс на chat_id/message_id, повторный парсинг блокируется), защита от ложных начислений (reply только на сообщение игрового бота, иначе `not_bot`/failed), единый source of truth курсов (`core/rates.py`, `_sync_conversion_rates` сохраняет админ-правки), E2E PTB-тест `tests/unit/test_manual_parsing_handler_e2e.py` (5 тестов) + фикс бага `balance_repository.add_balance()` (NULL total_earned → TypeError).

**FB01 notes:** реализованы команды `/feedback <предложение или жалоба>` с алиасами `/suggest` и `/complaint`; обращения сохраняются в SQLite-таблицу `feedback_entries` с JSONL fallback/debug mirror (`data/feedback.jsonl`): текст, Telegram ID, username, chat ID, chat type и UTC timestamp. Админ может читать последние обращения через `/feedback_list [limit]` (до 20 записей). Для внешнего чтения с HF добавлен защищённый endpoint `GET /feedback?limit=N` с `Authorization: Bearer <FEEDBACK_READ_TOKEN|HF_TOKEN|BOT_TOKEN>`; при сохранении пишется structured log `Feedback saved` с полным текстом обращения.

**AI01 notes:** пользователь попросил добавить ИИ, но обязательно бесплатную реализацию. Реализован локальный AI-lite помощник без платных API, без обязательных внешних ключей и без зависимости от LLM-провайдера. Команды: `/ai <вопрос>`, `/ask <вопрос>`, `/ai_help`. Scope: подсказки по командам BankBot, feedback, магазину, играм, D&D, профилю, админским возможностям и локальной базе канона Олеговируса/LTL из Google Doc (`bot/ai/knowledge.py`: глоссарий, Teaology, candy economy, LTRS, high-canon article links). `/short`/`/long` применяются глобально через `bot/response_modes.py`: long-сообщения автоматически компактятся в short mode, а `/long` сохраняет полный текст. Возможность подключения внешнего free/OpenAI-compatible endpoint допускается только как optional env-настройка позже, не как обязательная зависимость.

**AI02 notes:** Никита предложил использовать бесплатный Hugging Face API, чтобы AI был умнее локального keyword-helper. Требование: только optional/free реализация, без обязательной платной зависимости. Дизайн следующей итерации: env-флаги `AI_PROVIDER=huggingface|local`, `HF_INFERENCE_TOKEN`/`HF_TOKEN`, `HF_INFERENCE_MODEL`, короткие таймауты, лимит prompt/response, safe system prompt про BankBot, fallback на локальный AI-lite при quota/rate-limit/network errors. Нельзя ломать HF runtime и нельзя логировать токены/полный приватный prompt.
| PR10 | Архитектурная инвентаризация слоёв `core/src/utils/bank_bot` | P2 | completed |
| PR11 | Сокращение legacy-дублей и shim-слоёв | P2 | completed |
| PR12 | Упрощение wiring и startup-кода в `bot/bot.py` и entrypoints | P2 | completed |
| PR13 | Ревизия structured logging и эксплуатационных полей | P2 | completed |

**PR10-PR11 notes:** выполнена инвентаризация слоёв и закреплён runtime/legacy contract в `docs/README.md`. Рискованные runtime-зависимости не удалялись; legacy/shim namespaces (`src.parsers`, `core/repositories`, `utils/*` shims, aiogram `shop_commands.py`) зафиксированы как frozen/compatibility, новый код направлен в канонические слои.

**PR12-PR13 notes:** `bot/bot.py` получил чистый `build_polling_kwargs(is_hf)` без изменения HF timeout/retry semantics; structured polling logs сохранены. UX/watchlist закрыт безопасными runtime-правками: `/shop` и `/games` больше не дублируют вывод, `/games_list` показывает активные сессии, `/dnd_*` исправлены на `core.systems.dnd_system`, неизвестные команды получают fallback-ответ.

**TRIVIA01 notes (STATUS: completed, 2026-08-03):** Мини-игра «Брейн-Ринг по Канону Олеговируса». Команда `/trivia` запускает нативную неанонимную Telegram-викторину (quiz-poll, а не inline-кнопки) с вопросом по лору из канона (`data/canon_knowledge.txt` + пул `bot/trivia/questions.py`). Первый правильный ответ через `PollAnswerHandler` определяет победителя и даёт **10 монет** (константа `TRIVIA_COINS_REWARD`), транзакция `trivia_win` пишется в PostgreSQL. Защита от спама: антиспам-таймаут 60 сек на чат. AI-генерация через `generate_trivia_question()` с fallback на пул из 23 вопросов.**Проверено 2026-08-03: починен async-тест (await), починен Vercel-вебхук `/trivia` (await async-функции через asyncio.run), текст награды приведён к фактическим +10.**

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
| CH | 5/7 | 2/4 | 0/2 | 71% |
| UN | 0/5 | 0/4 | 0/2 | 0% |
| AI | 3/5 | 2/5 | 0/1 | 60% |
| AIC | 0/2 | 0/3 | 0/1 | 0% |
| MOM | 0/4 | 0/4 | 0/0 | 0% |
| Admin | 2/2 | 0/0 | 0/0 | 100% |
| **Total** | **10/34** | **4/25** | **0/9** | **29%** |

### CH tested (2026-06-20):
- ✅ /chess_link LucasTeam — account linked
- ✅ /chess_rating — ratings with blitz/rapid labels
- ✅ /chess_stats — full stats (2525 games, winrate)
- ✅ /puzzle — random puzzle with FEN derivation from PGN
- ✅ /chess_history — works (empty state OK)
- ✅ puzzle answer handler — UCI moves accepted and verified
- ✅ /errors — admin error journal
- ✅ /clear_errors — clears error log

### Bugs found & fixed:
- `text` variable shadowed `sqlalchemy.text()` → renamed to `msg_text`
- Regex broke `response.text` → fixed
- `response.msg_text` → `response.text`
- `if text` → `if msg_text` (4 places)
- Chess labels: "Молния"→"Блиц", "Быстрая"→"Рапид"
- `/puzzle` "задача дня" → "задача" (random now)
- `games.total` mapping from Lichess API `count.all`
- `/puzzle/next` doesn't return FEN → derive from PGN via python-chess
- Solution format: list vs string handled
- `chess_games` auto-table creation on startup

---

## Testing Notes

- Тестирование проводится вручную через Telegram клиент
- Для локального тестирования: `py -3.12 bot/main.py`
- Для HF тестирования: через production bot в https://t.me/lucasteamgroup
- Database checks через SQL-запросы к Supabase PostgreSQL
- Все edge cases должны быть покрыты
- UI/UX проверяется на корректность отображения, форматирования, кнопок
- После завершения тестирования модуля — обновить статус в `projectbrief.md`
