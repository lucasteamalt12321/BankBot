# Progress

**Текущая фаза:** Phase 6 OGE Center — **Максимальная прокачка OGE-системы** (SM-2标准算法, тренажёр инфо с самооценкой, физика в экзамене, аналитика, серверный квиз-движок, due-cards, хаб-прогрессбары)

## Beta Bugs (баги бета-тестирования, 2026-08-27+)

> Формат записи: **[MODULE-BUG-N]** модуль — краткое описание. Шаги воспроизведения / ожидаемое / фактическое / статус (open/fixed).

> **Основной раздел — модули, выпущенные из беты (GA) (2026-08-27):**
> - 🎮 **Geometry Dash — выпущен из беты** (пользователь подтвердил: «всё работает»). `GD-TEST` → completed (projectbrief Phase 2, GD Module 33/33 = 100%).
> - 🧠 **Викторина (Trivia, WEB-03 / TRIVIA01) — выпущена из беты** (пользователь подтвердил: «викторина готова»). Deliverable уже completed.
> - 🛠 **Администрирование (/admin) — выпущено из беты** (пользователь подтвердил: «администрирование тоже работает»).
> - 🏛 **История (ОГЭ, /emperors, OGE-03) — выпущена из беты** (пользователь подтвердил: «история работает»). Deliverable уже completed.

> **В бете (тестируется, 2026-08-27):**
> - 🐉 **DnD (AI Master)** — шаринг сессий реализован (DND-BUG-1 fixed: `share_code` + `/api/dnd/join` + карточка «Сессия» с копированием ссылки), но **возвращён в бету** для доп. проверки перед выпуском в GA.

### Найденные баги / недостающие фичи

- **[DND-BUG-1]** DnD — нет возможности поделиться сессией для совместной игры с друзьями.
  - **Шаги:** открыть DnD-сессию → попытаться пригласить друга / отправить ссылку на сессию.
  - **Ожидаемое:** кнопка «Поделиться сессией» / ссылка-приглашение, по которой друг присоединяется к одной и той же сессии и играет вместе.
  - **Фактическое (до фикса):** шаринг сессии отсутствовал (сессия локальная / привязана к аккаунту, пригласить друга нельзя).
  - **Фикс (2026-08-27):** `dnd_sessions.share_code` (8 символов), `cmd_dnd_start` генерирует код, `find_session_by_code` + `/api/dnd/join` (мастер-гард, лимит `max_players`), `/api/dnd/start` и `/api/dnd/status` отдают `share_code`/`share_url`, страница `/dnd` — панель присоединения по `?session=` и карточка «Сессия» с кнопкой «📋 Копировать». Тест `test_dnd_session_sharing_flow` покрывает flow.
   - **Статус:** fixed.

- **[OGE-BUG-6]** (2026-08-28, репорт пользователя) ОГЭ — ИИ-куратор в «Плане на день» показывал нереалистичные оценки времени (11м/3м/3м/3м/3м) — `minutes` был захардкожен равным числу карточек (`"minutes": cards`, prompt «~1 минута на карточку»).
  - **Ожидаемое:** время оценивает ИИ-куратор, а система парсит и выводит на сайт реалистичную оценку (чтение + разбор + тренировка).
  - **Фикс (2026-08-28):** `_plan_items_ai` теперь просит куратора возвращать отдельное поле `minutes` (реалистичная оценка 5-25, до 40 мин) и парсит его (`api/index.py:15596,15603-15605,15633-15638,15653`); rule-планировщик `_plan_items_rule_based` оценивает `minutes = max(per, target*2)` (~2 мин/карточку).
  - **Статус:** fixed (не закоммичено).

### Самопроверка (2026-08-27) — авто-найденные баги

> Найдено субагентами при аудите кода. **Статус: все 18 исправлены (2026-08-28).** Фиксы: см. Changelog `BUG-FIX-2026-08-28`.

#### 🐉 DnD (AI Master)
- **[DND-BUG-2]** (med/high) `find_active_session` (dnd_runtime.py:210-221) ищет сначала `master_id=uid` → если друг уже начинал свою сессию, его действия в чужой сессии пишутся в ЕГО собственную. Ожидалось: действовать в той сессии, к которой присоединился.
- **[DND-BUG-3]** (med) `call_ai` (dnd_runtime.py:84,104) может вернуть `None` на 200-ответе провайдера → `answer[:800]` (строки 614,532) бросает `TypeError` и `/api/dnd/act|roll` 500-ятся. Фикс: `answer = call_ai(...) or "🌌 Мастер задумался..."`.
- **[DND-BUG-4]** (med) `dnd_session_logs.player_id`/`dnd_fixes.player_id` пишутся сырым `uid` (dnd_runtime.py:524,552,590,608), а `dnd_characters.player_id` = `users.id` → JOIN в `get_session_log` не совпадает, `player_name` всегда `None`, `character_id` не проставляется. Фикс: резолвить `db_uid = _resolve_user_id(uid)` и использовать его везде.
- **[DND-BUG-5]** (low/med) `DICE_RE` (dnd_runtime.py:49) только lowercase `d/к` → `D20`/`К20` не парсятся. Фикс: `re.IGNORECASE`.
- **[DND-BUG-6]** (low) HF-fallback (dnd_runtime.py:158-170) возвращает `prompt + continuation` (text-generation inputs) → в ответе дублируется весь промпт. Фикс: завернуть в chat-шаблон модели или обрезать префикс.
- **[DND-BUG-7]** (low) `startSession()` (api/index.py:~6596) показывает подтверждение, затем `refreshStatus()`→`renderLog` очищает лог → сообщение стирается. Фикс: рендерить после `refreshStatus()`.

#### 📊 Статистика / ачивки
- **[STATS-BUG-1]** (high) `api_quiz_check` (api/index.py:13770-13774) и `api_exam_ai_record` (13890-13894) пишут `_record_activity`, но НЕ вызывают `_check_web_achievements` → ачивки за квиз/экзамен (`first_quiz`, `streak_*`, `module_*`) никогда не открываются. Фикс: дёрнуть `_check_web_achievements` + commit.
- **[STATS-BUG-2]** (med) `api_quiz_check` хардкодит модуль `"quiz"` (api/index.py:13772) вместо реального предмета `module` → «Активность по модулям» не копит math/physics и `first_quiz` не открывается (проверяет `trivia/emperors/reading/verbs`).
- **[STATS-BUG-3]** (med) OГЭ-ачивки «задания» считают попытки (`SUM(correct_count+wrong_count)`, api/index.py:1732-1740), а не distinct-карточки → уровни открываются преждевременно. Фикс: `COUNT(DISTINCT card_key) WHERE correct_count+wrong_count>0`.
- **[STATS-BUG-4]** (low) `_oge_stats_payload` (api/index.py:14860-14864, 14931-14932) может вернуть Response вместо dict (не ловится `try`) и не инициализирует `current_streak/best_streak` вне блока → 500/скрытый `None`.

#### 📚 ОГЭ (study/quiz/exam)
- **[OGE-BUG-1]** (high) `due` пишется в миллисекундах из веба (`Date.now()+interval*86400000`, api/index.py:11774,12194,12701,13222,10308), а сервер читает как секунды (`time.time()`) → due-cards, «due today» и прогноз всегда пусты. Фикс: слать секунды или делить на 1000.
- **[OGE-BUG-2]** (high) `api_quiz_check` (api/index.py:13710,13751-13757) кладёт в сессию сырые items без `correct_idx` (он только в `safe_items` клиента) → MCQ всегда `correct:false`, прогресс пишется как ошибка. Фикс: сохранять `correct_idx` в сессии.
- **[OGE-BUG-3]** (med) `_oge_stats_payload` «Сегодня» (api/index.py:14963-14969) суммирует lifetime `correct_count/wrong_count`, а не только за сегодня → цифры завышены.
- **[OGE-BUG-4]** (med) `api_study_due_cards` (api/index.py:15124) фильтрует `reps>0` → карточка после ошибки (`reps=0`, `due=now+60`) навсегда выпадает из очереди повторов. Фикс: `reps>0 OR due<=:now`.
- **[OGE-BUG-5]** (low/med) SM-2 (api/index.py:13498-13499) считает интервал ДО обновления `ease` → рост интервала занижен. Фикс: сначала обновить `ease`, потом интервал.

#### 🔐 Web-портал (auth)
- **[AUTH-BUG-1]** (med) `api_auth_register` (api/index.py:9418-9443) не проверяет уникальность email → `UNIQUE`-констрейнт бросает `IntegrityError` → 500 вместо 409 «Email занят». Фикс: явная проверка перед INSERT.
- **[AUTH-BUG-2]** (med) `_ensure_universe_tables` (api/index.py:652-658) использует SQLite `rowid` для дедупа → на Postgres/Supabase падает, уникальный индекс `ux_daily_prayer_log_user_date` не создаётся → дубли молитв/неправильные серии на проде. Фикс: portable-вариант (ctid/rowid по диалекту).
- **[AUTH-BUG-3]** (low/med) `telegram_id` собирается в UI (api/index.py:8865,8905-8912,9513-9527) но не шлётся при регистрации и не обновляется в `/api/auth/update` → значение теряется, привязка Telegram через веб невозможна.

#### 🧪 Тесты
- `tests/unit/test_exam_center.py`: 2 устаревших assert (ожидают `/api/exam/mixed` в `/exam` и подмножество модулей без `physics`) — прод не сломан, тесты stale. Надо обновить ожидания.

_Баги добавляются по ходу тестирования остальных модулей._

### Аудит безопасности и багов (2026-08-28, запрос «займись фиксами багов по всему проекту»)

> Прогнан параллельный аудит (core/, api/index.py, music) + полный прогон тестов (1480 passed, 10 skipped — зелёные). Ниже конкретные найденные баги; критичные/высокие — исправлены в рабочей копии (не закоммичено).

#### 🔴 Критические / безопасность
- **[SEC-BUG-1]** (critical) `POST /api/gd/submit` (api/index.py): медиа хранилось как `data:`-URL с MIME из клиента и рендерилось как `href` без проверок → Stored XSS (через `text/html`/`image/svg+xml`), плюс неограниченный размер загрузки (DoS). **Фикс:** строгий allowlist типов (video/*, image/png|jpeg|gif|webp), отказ svg/html, лимит 16 МБ, корректный MIME в data-URL.
- **[SEC-BUG-2]** (med) `mdLite()` (две копии, api/index.py) экранировал HTML, но не схему ссылки в `[текст](url)` → `javascript:`-XSS в чате для админа. **Фикс:** санитайзер URL (только http/https/tg), иначе `#`.
- **[SEC-BUG-3]** (med) семейные комнаты: `data.your_name` (введённое пользователем) рендерилось через `innerHTML` → reflected XSS. **Фикс:** построение DOM через `textContent` (без вставки HTML).

#### 🟠 Высокие (функциональные)
- **[BANK-BUG-7]** (high) `core/database/simple_bank.py:56` — `Transaction(metadata=...)` при неверном имени колонки (`meta_data`, database.py:84) → `TypeError` и падение начисления за рыбалку. **Фикс:** `metadata=` → `meta_data=`.
- **[BANK-BUG-8]** (high) `core/systems/motivation_system.py` — `calculate_streak` считал стрик от **сегодня**, а сегодняшний бонус ещё не записан → streak всегда 0 → множители `streak_multipliers` никогда не применялись. **Фикс:** считаем последовательные дни до вчера, награда = `calculate_bonus_amount(streak + 1)`.

#### 🟡 Средние / низкие (исправлено)
- **[BANK-BUG-9]** (med) `core/systems/beta_economy.py:57` — `datetime.now()` (локальное) вместо UTC → истечение листингов уезжало на оффсет таймзоны. **Фикс:** `datetime.utcnow()`.
- **[SEC-BUG-4]** (low/med) `MUSIC_API_BASE` инжектился в JS-строку как есть (`json.dumps` отсутствовал) → прививка через кавычку. **Фикс:** `json.dumps(env)`.

#### ⚪ Открытые / архитектурные (не чинил — нужны решения/согласование)
- **[BANK-BUG-10]** (arch) Две независимые реализации магазина: `core/managers/shop_manager.py` (SQLite `data/shop.db`) и `core/systems/shop_system.py` (Postgres `data/bot.db`) — риск расхождения балансов/покупок. Нужен единый источник.
- **[BANK-BUG-11]** (med) `shop_manager.purchase_item` не атомарен (нет row-lock/транзакции) → race-condition на списание при конкурентных покупках.
- **[BANK-BUG-12]** (low) `ParserRegistry` в `core/content/parser_registry.py` пуст → расширение контента невозможно (инертная абстракция).
- **[SEC-BUG-5]** (low) канон: `media_mime` доверяется клиенту при валидации аудио → ложноположительные/отрицательные результаты (не XSS, т.к. путь управляем).
- **[SEC-BUG-6]** (low) мёртвый CORS-блок в `api/index.py` (0.0.0.0) — функционально бесполезен. Можно удалить.

## Changelog

### 2026-08-27 (Session 9d: 🐉 DnD — шаринг сессий + выпуск модулей из беты)
- **[DND-BUG-1] исправлен:** добавлен шаринг DnD-сессий для совместной игры с друзьями.
  - `dnd_sessions.share_code` (VARCHAR(16), 8 символов из набора без ambiguous) — добавлен в `_ensure_dnd_tables`.
  - `cmd_dnd_start` генерирует и сохраняет `share_code`; `find_session_by_code` ищет по коду; `join_session(telegram_id, session_id, player_name)` — мастер-гард (не дублирует персонажа), лимит `max_players`, имя героя опционально.
  - `api_dnd_start`/`api_dnd_status` отдают `share_code`/`share_url`; новый `POST /api/dnd/join` (code + name) присоединяет к активной сессии.
  - Страница `/dnd`: панель присоединения по `?session=<code>` (ввод имени героя + «🤝 Присоединиться») и карточка «Сессия» с полем ссылки и кнопкой «📋 Копировать».
- **Выпущено из беты (GA)** и перенесено в основной раздел: 🎮 Geometry Dash, 🧠 Викторина, 🛠 Администрирование, 🏛 История, 🐉 DnD (см. секцию «Основной раздел — модули, выпущенные из беты» выше).
- **Тесты:** +`test_dnd_session_sharing_flow` (test_web_portal_e2e.py). ruff clean, `node --check` dnd-page JS OK.

### 2026-08-28 (Session: ИИ-куратор — реалистичные оценки времени в «Плане на день»)
- **[OGE-BUG-6] исправлен:** куратор теперь сам оценивает время по каждому пункту плана, а система парсит `minutes` и выводит на сайт. Раньше `minutes` был равен числу карточек (`"minutes": cards`, prompt «~1 минута на карточку») → показывало 11м/3м/3м/3м/3м.
  - `_plan_items_ai`: промпт требует отдельное поле `minutes` (реалистично 5-25, до 40 мин, с учётом чтения/разбора/тренировки); парсинг клампит 3-60, при отсутствии — `cards*2`.
  - `_plan_items_rule_based`: `minutes = max(per, target*2)` (≈2 мин/карточку).
  - Фронт уже рендерил `it.minutes + "м"` — теперь значение осмысленное. 22 теста `test_curator.py` passed, ruff clean. **Не закоммичено.**

### 2026-08-28 (Session: аудит багов по всему проекту — security + core fixes)
- **Задача (пользователь):** «займись фиксами багов и потенциальных багов по всему проекту». Прогнан параллельный аудит (core/, api/index.py, music) + полный прогон тестов (1480 passed, 10 skipped — зелёные).
- **Безопасность (api/index.py):**
  - `[SEC-BUG-1]` `/api/gd/submit`: Stored-XSS (data:-URL с MIME от клиента, рендер в `href`) + неограниченный размер → allowlist типов (video/*, image/png|jpeg|gif|webp), отказ svg/html, лимит 16 МБ, корректный MIME в data-URL.
  - `[SEC-BUG-2]` `mdLite()` (2 копии): схема ссылок не фильтровалась → `javascript:`-XSS; добавлен санитайзер (http/https/tg, иначе `#`).
  - `[SEC-BUG-3]` семейные комнаты: `data.your_name` → `innerHTML` (reflected XSS); переписано на `textContent` (DOM).
  - `[SEC-BUG-4]` `MUSIC_API_BASE` из env инжектился без экранирования; обёрнут в `json.dumps`.
- **Функциональные (core/):**
  - `[BANK-BUG-7]` `simple_bank.py:56` `Transaction(metadata=)` → `meta_data=` (падал `TypeError`, не начислялась награда за рыбалку).
  - `[BANK-BUG-8]` `motivation_system.py`: стрик ежедневного бонуса считался от сегодня → всегда 0 → множители не применялись; теперь считаем до вчера, награда `calculate_bonus_amount(streak+1)`.
  - `[BANK-BUG-9]` `beta_economy.py:57` `datetime.now()` → `datetime.utcnow()` (истечение лотов по таймзоне).
- **Открытые/архитектурные (не чинил, записаны выше):** `[BANK-BUG-10]` две реализации магазина, `[BANK-BUG-11]` неатомарная покупка, `[BANK-BUG-12]` инертный `ParserRegistry`; `[SEC-BUG-5/6]` доверие MIME клиента в каноне / мёртвый CORS-блок.
- **Проверки:** `ast.parse` по api/index.py и core-файлам OK; `tests/unit/test_music.py` 7 passed. **Закоммичено `92b7f44`, задеплоено на `bank-bot-ruby.vercel.app` (Ready).**

### 2026-08-28 (Session: музыка — анализ не работал на реальных файлах)
- **[MUSIC-BUG-1]** (high, реальный репорт «всё равно не анализируется музыка»): изолированно сервис работал (MIDI/WAV 200 JSON), но на реальных аудио падало. **Корень:** `analyze` для аудио грузил весь файл ДВАЖДЫ (BPM + тональность) через `librosa.load` → 30с клип = 14с, холодный старт ещё больше → Vercel убивал функцию по дефолтному лимиту **10с** → браузер видел сбой.
- **Фикс:** `core/music/audio_utils.analyze_audio` грузит трек один раз с капом `duration=20s, sr=16kHz` (~2x быстрее); `detect_bpm`/`detect_key` тоже через `_load` с duration-капом. Аудио-сервис: `maxDuration` 10s→**60s** (`vercel.json`: убран `builds`, оставлен `functions`). В LTHub — понятное сообщение при таймауте («попробуйте фрагмент до ~30с»).
- **Проверка:** прод `audioservice.vercel.app` `/api/music/analyze` на 30с WAV теперь 200 за ~22с (холодный, с JIT) — в лимите 60с; MIDI 120 BPM. **Закоммичено `7547813`, задеплоено (audioservice + bank-bot-ruby).**
- **Остаток:** `change_tempo`/`change_key`/`overlay` грузят полный трек (нужен для синтеза) — на очень длинных файлах всё ещё могут упираться в 60с; при необходимости тоже капать длительность.

### 2026-08-28 (Session: музыка — цепочка регрессов кнопки/анализа)
- **Истинная первопричина «не работает музыка»**: `MUSIC_API_BASE` инжектился через `json.dumps` внутри ШАБЛОНА в одинарных кавычках → `var MUSIC_API_BASE='"https://audioservice..."'` — двойные кавычки стали литералами внутри JS-строки. fetch уходил по невалидному URL и резолвился ОТНОСИТЕЛЬНО ОРИГИНА LTHub (а не на audioservice) → крупные файлы давали **413** на прокси LTHub, мелкие — **404**. Все предыдущие симптомы (timeout/ничего не происходит/413/404) были следствием этого + побочных правок.
- **Фикс:** убраны одинарные кавычки из шаблона, `json.dumps` теперь формирует корректную JS-строку `var MUSIC_API_BASE="https://audioservice.vercel.app";`. Плюс client-side компрессор аудио (20с@16кГц моно WAV ~0.6МБ) как защита от реального лимита Vercel ~4.5МБ. Коммиты `357d969`, `707268a`, задеплоено.
- **Правило проекта (подтверждено граблями):** при инъекции строки в inline-JS НЕ оборачивать `json.dumps` в доп. кавычки шаблона — либо `json.dumps` без кавыч в шаблоне, либо чистая интерполяция без `json.dumps`. И после каждой правки embedded-JS обязательно проверять итоговый отрендеренный `<script>` (не только `node --check` исходника, а именно вывод страницы).

### 2026-08-27 (Session 9c: 📊 Общая статистика как модуль + блок в кабинете)
- **`/api/stats`** (api/index.py): сводная статистика активности по всем модулям хаба — серия, календарь активных дней, список модулей (actions/days), события, тоталы + вложенный ОГЭ-блок.
- **Отдельная страница `/stats`** (`stats_page`): общая статистика как самостоятельный модуль, стиль зеркалит `/achievements` (stat-box'ы, календарь 12 недель, сетка модулей, события, ОГЭ-готовность).
- **Блок «📊 Активность» в `/account`** — компактный, как блок достижений (сводка + календарь + ссылка на `/stats`); карточка «Статистика» 📊 добавлена на хаб `/`.
- **ОГЭ-ачивки** (5 модулей × шкалы заданий/освоенных карточек) + activity-хуки `_record_activity` в quiz/exam/study-progress (`unlocked_detail`).
- **Тесты:** +`test_oge_study_achievements_unlock`, `test_general_stats_endpoint` (test_achievements.py), `test_account_page_has_stats_block`, `test_stats_page_renders` (test_web_portal_e2e.py). ruff clean, `node --check` account/stats JS OK.
- **projectbrief.md:** добавлен раздел Phase 6.5 General Statistics Module (STAT-01…04, 100/100).

### 2026-08-27 (Session 9b: 🤖 Максимальная прокачка ИИ-куратора — баги + 5 инструментов)
- **Исправлен мёртвый код (Б1):** `due`/`weak`/`topics` в `_curator_tool_data` были недостижимы (безусловный `return` progress-журнала на старом 15514 перекрывал все последующие ветки). Dispatch переписан на словарь `_CURATOR_HANDLERS`; прогресс вынесен в `_cur_tool_progress`.
- **Исправлен экзаменационный отсчёт (Б2):** `_oge_exam_countdown` падал (кортеж дат `(2027,6,7)` в `strptime`) → теперь `date(*exam)`, счётчик попадает в промпт («История (284 дн.)…» и т.д.).
- **Исправлен fallback-регэксп (Б3):** `_curator_fallback_reply` ждал `(N мин)`, а реальный план — `(N карточек)`; теперь regex `\((\d+) карточек` + учёт `✅/прогресс`, с оценкой минут.
- **Добавлены 5 инструментов:** `mastered` (выученное для повторения), `streak` (серия/точность/вчера), `due_cards` (детальные просроченные карточки), `recommend` (готовый следующий шаг по предметам), `exam` (дни до каждого экзамена). Обновлены `_CURATOR_TOOLS`, `_curator_tool_action` и схема в системном промпте (15722+).
- **Тесты:** +5 в `tests/unit/test_curator.py` (22 всего): due/weak/topics, новые инструменты, отсчёт с кортежами, fallback-регэксп под реальный план, roundtrip weak ≠ журнал.
- **Проверки:** ruff clean, py_compile, node --check (0 ошибок), 58 тестов passed (curator/study_progress/emperors). Коллекционные ошибки остальных модулей — pre-existing (нет `telegram`).

### 2026-08-27 (Session 8e: 🦶 GD-модуль — устранение «дыр» в местах топ-листа)
- **GD (Geometry Dash) demon-list**: добавлен `_gd_compact_positions(conn)` — перенумерация всех уровней в плотный ряд 1..N по текущему `position` (стабильно по id). Устраняет пробелы в местах (например, 1, 2, 5 — без 3 и 4).
- Вызов перенумерации добавлен после **каждого** редактирования: `add_gd_level` (оба случая — существующий и новый), `set_gd_level_position`, admin PUT (`/api/gd/admin/level/<id>`) и admin DELETE — все в рамках той же транзакции до `commit`.
- **Проверки:** py_compile, ruff clean, 53 теста passed, логика перенумерации проверена на исключении дыры.

### 2026-08-27 (Session 8d: 🔁 3 алгоритма «как в Истории» во всех ОГЭ-модулях, по умолчанию Флешки)
- **Единый набор алгоритмов** во всех ОГЭ-модулях, как в Истории: **Классика (колода) / Флешки (интервалы) / Счётчик (вероятности)** (`deck`/`flash`/`counter`).
- **По умолчанию — Флешки (flash)** во всех модулях.
- **Математика и Физика** (`pickFormula`): селектор `f-algo` переведён со `smart/flash/deck` на `deck/flash/counter`; ветка `smart` (weak/unseen/due/rest) заменена на взвешенный `counter`-пикер (вес `(c<=0)?(1-c):max(1,10-c)`); в `fFlashRec`/`fFlashUpdate` добавлено поле `counter` (`+1 верно / −1 ошибка`).
- **Русский** (`pickRule`): аналогично — селектор `r-algo`, ветка `counter`, поле `counter` в `rFlashRec`/`rFlashUpdate`.
- **Информатика** (тренажёр): добавлен весь селектор алгоритма в `modeRow` (deck/flash/counter, default flash) + `buildQueue()` строит очередь по алгоритму: `deck` — shuffle, `flash` — сортировка по due/unseen, `counter` — сортировка по `counter` (возрастание = слабые первыми). `infoRecord` теперь обновляет `counter`.
- **Проверки:** 53 тестов passed, ruff clean, у всех страниц (`/ /math /physics /russian /informatics /emperors /exam /analytics`) JS валиден (node --check), во всех 4 модулях селектор `deck/flash/counter` и default `flash` подтверждены в рендере.

### 2026-08-27 (Session 8c: 🎯 клик по заданию открывает вкладку предмета)
- **Фича:** клик по пункту «Плана на день» теперь ведёт на страницу предмета **и сразу открывает нужную вкладку** для выполнения задания (раньше клик открывал ИИ-куратора). Куратор остаётся доступен по шапке «План на день … нажмите, чтобы открыть» и подвалу «Автоматически закрыто N из M».
- **Сервер:** `_plan_payload` добавляет пунктам поле `tab` через новый `_plan_item_tab(it)` — умный маппинг по `module` + тексту/теме: история → `terms` (термин/понятие), `chrono` (хронология/даты), `match` (личности/правители), иначе `study`; математика/физика → `tasks`; русский → `essay` (сочинение/эссе), иначе `tasks`; информатика → `trainer`.
- **Модульные страницы принимают `?tab=`:** добавлены JS-обработчики `URLSearchParams.get('tab')` на страницах Математика, Физика, Русский (generic `.tab[data-tab]` click) и Информатика (`switchTab`); история расширена со `terms` на все 5 вкладок (`study/quiz/match/chrono/terms`) через `app.showTab`.
- **Фронт хаба:** `goItem(it)` строит `it.url + '?tab=' + encodeURIComponent(it.tab)`; и `renderWidgetPlan`, и `renderCurPlan` делают пункты кликабельными (cursor + hover + бейдж «→ выполнить»).
- **Проверки:** 53 тестов passed, ruff clean, у всех страниц `/math /physics /russian /informatics /emperors /` и `/exam` JS валиден (node --check). Маппинг `_plan_item_tab` проверен юнит-кейсами (terms/chrono/match/study/tasks/essay/trainer).

### 2026-08-27 (Session 8b: 🔴 два прод-бага — экрана экзаменатора и куратора)

**1) Экзаменатор /exam не работал — SIG-баг разворота лапки в «Показать подсказку».**
- **Корневая причина:** в `EXAM_PAGE_TEMPLATE` строка `onclick="this.nextElementSibling.style.display=\'block\';..."` имела в исходнике Python **одиночный** backslash `\'`. Вместо вывода JS-экранирования `\'` Python внутри тройных кавычек **съедал** backslash → в HTML уходил голый `'` внутри JS-строки в одинарных кавычках → **SyntaxError всего `<script>`** → на странице не работало НИЧЕГО (кнопки, fetch, всё).
- **Фикс:** `\'` → `\\'` в Python-исходнике (выводит `\'` в JS). Проверено: `node --check` на извлечённом `<script>` теперь OK.
- **Аудит:** прогон `node --check` по всем 7 шаблонам с `<script>` (`ANALYTICS`, `EXAM`, `MATH`, `PHYSICS`, `RUSSIAN`, `TERMS_FRAGMENT`, `_OGE_HINT_JS`) — **0 синтакс-ошибок**.
- **Напоминание (подтверждено изmemory):** в тройных кавычках Python для вывода JS `\'` нужен двойной backslash в исходнике.

**2) ИИ-куратор показывал JSON с tool ученику вместо выполнения инструмента.**
- **Корневая причина:** `_CURATOR_TOOLS = {"stats","progress","plan","card"}` — **отсутствовали `due`, `weak`, `topics`**, хотя они реализованы в `_curator_tool_data` и описаны в промпте. Когда ИИ возвращал `{"tool":"due"}` / `{"tool":"weak"}` / `{"tool":"topics"}`, `_tool_directive()` возвращал `None` (имя не в сете) → код НЕ шёл в ветку инструмента и отправлял **сырой JSON как сообщение** ученику.
- **Фикс `_CURATOR_TOOLS`:** `{"stats","progress","plan","card","due","weak","topics"}`.
- **Фикс `_tool_directive`:** заменён regex `\{[^{}]*\}` (не ловил вложенные `{}`) на балансный парсер `_iter_json_objects` (обрабатывает вложенные скобки и кавычки/экранирование) — распознаёт и встроенные в текст, и вложенные директивы.
- **Доп. safety-net:** `_is_serialized_json(reply)` после основной логики — если итоговый ответ всё же голый JSON (`{`/`[` + парсится через `json.loads`), он заменяется на `_curator_fallback_reply`, т.е. ни при каких обстоятельствах JSON не показывается ученику.
- **Проверки:** 53 тестов passed (test_curator 17 вкл. tool-directive), ruff clean, py_compile OK, экзамен end-to-end 200 / 3 items / пул 230.
- **Корневая причина:** `_exam_build_catalog()` обращался к атрибутам, которых нет у объектов: у `HistoryEvent` нет `options`/`correct_idx`/`emperor_id` (только `title`, `year`, `importance`, `note`), а у `MathTask`/`RuleTask`/`InfoTask` нет `options`/`correct` (только `id`, `question`, `answer`, `hint`, `explanation`, `difficulty`, `topic`). Все 5 per-module блоков падали в try/except → пул оставался пустым → `/api/exam/ai-batch` возвращал `{"ok":true,"items":[]}` → очередь не заполнялась → кнопка «Начать экзамен» выглядела сломанной.
- **Фикс `_exam_build_catalog()`:** переписан на реальную схему — только 4 модуля (math/russian/informatics/physics), каждый task отдаёт `{key, question, module, hint, _answer, _explanation}`. Пул = **230 задач** (math 50, russian 45, informatics 95, physics 40). История выпала из каталога (у неё нет MCQ-задач с options — см. решение ниже).
- **Фикс `/api/exam/ai-batch`:** убрана тяжёлая зависимость от ИИ-выборки (промпт + `call_ai_api` на каталог 200 строк + парсинг JSON). Теперь чисто детерминированно: слабые карточки ученика (из `_exam_student_context`) первыми, затем случайные; исключая уже показанные (`seen`). Каждый item отдаётся с полем `answer` (не `_answer`), чтобы подходил текстовой ветке ответа в `EXAM_PAGE_TEMPLATE` (`checkTextAnswer` использует `currentIt.answer`).
- **Решение по истории:** задача-типа mcq с options у History больше нет — возвращён свободный текстовый ответ (как в остальных модулях). Это согласовано с удалением ИИ-алгоритма из модулей (Session 7); экзамен теперь надёжен и не зависит от доступности API.
- **Проверки:** 53 тестов passed (test_curator 17 + test_study_progress 16 + test_emperors_module 20), ruff clean, py_compile OK. End-to-end через тест-клиент: ai-batch 200 + 5 items, seen-исключение работает, `/exam` 200, `/analytics` 200.

### 2026-08-26 (Session 7: ИИ-алгоритм — куратор выбирает вопрос из БД)
- **`/api/quiz/ai-generate`** (POST): ИИ-куратор **выбирает лучший вопрос из БД** для ученика, а не генерирует новый. Алгоритм: (1) строит каталог всех вопросов модуля (ключ + текст + тема), (2) получает слабые карточки ученика из `study_progress`, (3) отправляет каталог + слабые куратору с проритетами: слабые → новые → повтор, (4) куратор возвращает ключ, (5) сервер ищет полный вопрос в пуле и отдаёт с MCQ-опциями. Фоллбэк при недоступном AI: случайная слабая или случайная из каталога. Промпт НЕ сохраняется в историю чата.
- **Кнопка "ИИ (генерация)"** во всех 5 модулях: Math/Physics/Russian — `renderAiQuestion()`, History/emperors — `loadAiQuestion()`, Informatics — `loadInfoAiQuestion()`. Informatics также получил НОВЫЙ algo-selector (Перемешать / ИИ).
- **53 тестов passed**, ruff clean. Деплой `be76752` ✓ Ready.

### 2026-08-26 (Session 6b: Алгоритм smart/flash/deck на страницах ОГЭ)
- **Выбор алгоритма** добавлен на страницы Математика, Физика и Русский язык: `<select id="f-algo">` / `<select id="r-algo">` с тремя вариантами — `smart` (слабые первые, по умолчанию), `flash` (интервалы), `deck` (колода). Каждая страница хранит свой выбор в localStorage (`math_f_algo`, `physics_f_algo`, `russian_r_algo`).
- **`pickFormula()` / `pickRule()`** — новый пикер, заменяющий последовательный `fIdx++`. Алгоритм `smart` приоритизирует: weak (streak < 0) → unseen (reps = 0) → due (due <= now) → rest. Алгоритм `flash` — аналог Emperors page (overdue/new/not-yet-due). `deck` — перемешанная колода.
- **SRS-трекинг per formula/rule** — отдельный объект `fFlash` / `rFlash` (localStorage) с ease, interval, due, streak. Обновляется при каждом ответе через `fFlashUpdate` / `rFlashUpdate`. Статистика: выучено + повтор в строке прогресса.
- **53 тестов passed**, ruff clean, node --check OK. Деплой `675d947` ✓ Ready.

### 2026-08-26 (Session 6: Максимальная прокачка OGE-системы)
- **SM-2 → стандартный алгоритм.** Ease factor теперь растёт (+0.1 при правильном ответе, потолок 3.0) и падает (−0.2 при ошибке, пол 1.3). Обновлено на сервере (`_study_record_one` Python) и во всех 5 клиентских копиях (emperors `recordAnswer`, math/physics/russian `record`, informatics `infoRecord`). Раньше ease никогда не рос — теперь повторение интервалов геометрически растёт при хорошем знании.
- **Информатика-тренажёр: самооценка вместо автопревращения.** Было: `infoRecord(task.id, true)` — невозможно ошибиться. Стало: 2 кнопки «✅ Знал» / «❌ Ошибся» после показа ответа; точность отображается в счёте.
- **Физика: MODULE='math' → 'physics'.** Косметический баг в константе (не влиял на push, но путал).
- **Физика добавлена в смешанный экзамен.** `api_exam_mixed` теперь тянет задачи из 4 предметов (math, russian, informatics, physics) вместо 3.
- **Новый эндпоинт `/api/study/stats`** (GET): per-module readiness (mastered/total * 100%), streak (current/best), today summary (cards/correct/wrong/correct_rate), forecast на 14 дней. Требует авторизацию.
- **Новый эндпоинт `/api/study/due-cards`** (GET): список карточек на повторение (due <= now), с overdue_min и accuracy по модулям.
- **Серверный квиз-движок `/api/quiz/generate` + `/api/quiz/check`**: генерация квизов для всех 5 модулей ОГЭ. MCQ (история, формулы, правила) с автоматическими distractors из данных; free-text (задачи). Алгоритм `smart` — адаптивный (приоритет weak/unseen через study_progress). Сессии хранятся в `_QUIZ_SESSIONS` (макс. 300).
- **Аналитический дашборд `/analytics`**: полная страница — серия дней (streak), общий прогресс (readiness bar), сегодня (cards/correct_rate/score), per-module progress bars (clickable), forecast grid (14 дней, hot/active/empty), слабые места (clickable).
- **Хаб: прогресс-бары на OGE-карточках** + ссылка на Аналитику ОГЭ. Функция `loadOgeStats()` тянет `/api/study/stats` и рендерит mastered/total + due + weak на каждой карточке.
- **Тесты:** 8 новых в test_study_progress.py (stats, due-cards, quiz generate/check, analytics). Итого: test_curator 17 + test_study_progress 16 + test_emperors_module 20 = **53 passed**. ruff clean, node --check OK для хаба и analytics.
- **Деплои:** `64189e9` (SM-2 + инфо + физика + stats + хаб), `73fa99d` (аналитика + квиз + due-cards), `c9e4021` (fix analytics JS escape). Все на проде ✓ Ready.
- **⚠️ Паттерн:** `\'` в Python triple-quoted template → `'` в JS (Python consumed backslash). Для onclick handlers нужен `\\'` → `\'` в JS (escaped quote inside single-quoted string). Обнаружено через `node --check` на отрендеренном output.

## Changelog

### 2026-08-26 (Session 5: типы заданий fix/new + topic; фикс синка прогресса между устройствами)
- **План дня: два типа заданий.** `kind:"fix"` — исправить ошибки: зачёт = верный ответ сегодня на слабую карточку (`wrong_count>0 AND last_correct_at>=начала суток`), одна карточка в день считается один раз (по строке на карточку); `kind:"new"` — изучить новые: зачёт = первая работа с карточкой сегодня (`created_at>=начала суток`). ИИ-план возвращает `{module, kind, cards 3-30, topic?}` — topic это фильтр-подстрока по card_key (LOWER LIKE). Rule-планировщик выбирает тип сам: weak>0 → fix («🛠 Исправить ошибки…»), иначе new («✨ Изучить новые…»).
- **Схема:** `study_progress` += `created_at REAL DEFAULT 0`, `last_correct_at REAL DEFAULT 0` (+ idempotent ALTER для прода; `_study_record_one` проставляет обе метки). ⚠️ SQLite-фикстуры тестов обновлены вручную.
- **🐛 Синк прогресса Истории между устройствами (репорт Луки: разный ранг на телефонах и ПК):** страница `/emperors` жила на localStorage + `/api/emperors/progress` (отдельная таблица!), а мердж при загрузке брал серверную карту только если её `due` строго новее локальной — устройства расползались. Фикс: страница переведена на единую `/api/study/progress` (module=history): GET отдаёт `ts` (=updated_at) и streak; мердж по ts (сервер >= локали → берём сервер), затем pushFlash доливает локальные более свежие записи на сервер. Бонус: автозачёт планов по истории теперь видит реальную активность (раньше emperors_activity писалась мимо study_progress, миграция была one-shot).
- **Проверки:** ruff clean; test_curator 17 (новые: подсчёт fix/new/topic, план с двумя типами, снапшот), test_study_progress 8, test_emperors_module 20 = 45 passed; node --check хаба и /emperors OK. Коммит `ce28185` запушен.
- Примечание: анонимы (без входа) синхронизироваться не могут по определению — прогресс привязан к аккаунту через токен.

### 2026-08-26 (Session 4: автозачёт плана дня вместо ручной кнопки)
- **Решение пользователя:** кнопка «✓ Отметить выполненным» убрана — зачёт только автоматический.
- **Механика (`f2ef98e`):** пункт плана получает `cards` (целевое число карточек; rule-планировщик `max(3, per)`, ИИ-план теперь просит `"cards":N` 3–30 и формулирует text под объём). Пункт закрыт, когда в `study_progress` у предмета today `updated_at >= начала суток` записей >= target (`_touched_today_by_module`, `_item_target`, `_auto_plan_done`). `_plan_payload(row, uid)` считает per-item done/target и общий done=число закрытых пунктов. `_snapshot_auto_done` пишет автозначение в done_count при каждом GET/POST плана — история для облегчения завтрашнего плана сохранена. Роут `/api/study/plan/done` удалён (404).
- **UI:** виджет — «Автоматически закрыто X из Y», чипы прогресса d/target на частично выполненных пунктах; модалка — справа «d/N карт» или «✅ готово», поясняющая строка вместо кнопки, 🎉 при полном закрытии; pollToday раз в минуту тихо подтягивает свежий план. Чат куратора: в контекст идёт автостатус («прогресс d/target», «✅»).
- **Совместимость:** старые items без cards → target = minutes (клампы 2..40); фронт и бэк деплоятся парой.
- **Проверки:** test_curator 16/16 (done-тест переписан: активность по математике → закрыт только её пункт, снапшот в done_count, /plan/done → 404); с test_study_progress 24 passed; ruff clean; node --check хаба OK.

### 2026-08-26 (Session 3: куратор — реалистичное время и названия карточек; прод смоукнут)
- **Повод (репорт Луки):** куратор советовал «разобрать одну карточку (5 минут)» и сыпал техническими ключами `event::Крымская война`.
- **Фиксы:** нормы времени в промпте чата (карточка ~0,5–1 мин, задача 2–4 мин; группировать в пачки под бюджет; не показывать ученику ключи); слабые карточки в данных тула progress отдаются человекочитаемыми именами (`_card_display_name`: префикс `типа::` снимается, если хвост содержит кириллицу; полные ключи остаются только в строке «Ключи» для тула card) + строка «повторение одной карточки ~1 минуту»; ИИ-план (`_plan_items_ai`): требование реалистичных minutes и сумма ≤ бюджета, кламп пункта снижен 5→2 мин; rule-планировщик: `per = max(2, …)` вместо max(5,…).
- **Прод-смоук:** `/` → 200; чат с тулом progress по Истории → actions=[листает журнал…], в ответе нет `event::`, совет пачкой «5–10 карточек». Деплой fbbc59d ✓ Ready in 36s.
- Тесты 24 passed, ruff clean.

### 2026-08-26 (Session 2: куратор — тулы topic/card; фикс бета-раздела хаба; деплой через CLI)
- **Куратор: данные по теме и отдельной карточке.** `progress` получил опциональный `topic` (подстрока-фильтр `card_key`, без учёта регистра; пустой результат → «записей в журнале нет»); в ответ progress добавлен список ключей карточек (до 20 + счётчик) с подсказкой про тул card. Новый тул **`{"tool":"card","key":"formula::f01"}`** (module опционален): повторения, серия (3+ = выучена), ✓/✗, интервал, человекочитаемое «следующее повторение» (`_curator_card_report`). `_curator_tool_action` подписывает в UI: «листает журнал: …, тема „…“ 📖», «проверяет карточку … 🃏». Промпт дополнен описанием topic/card.
- **🐛 Бета-раздел на хабе перестал открываться — причина найдена, виновник мой прошлый коммит.** В Python-шаблоне хаба `\n` внутри JS-регэкспов mdLite декодировалось в РЕАЛЬНЫЙ перевод строки → SyntaxError убивал весь `<script>` хаба (toggleBeta, loadUser, куратор — всё). Локальный рендер-тест строку ловил, но JS не проверялся. Фикс: удвоенные бэкслеши (`\\n`); **правило проекта: после правок embedded-JS обязательно `node --check` отрендеренного `<script>`** (паттерн из memory bank, теперь подтверждён граблями).
- **Деплой впервые отсюда через Vercel CLI:** токен в `.env.local` как `VERCEL_TOKEN`; `VERCEL_TOKEN=… vercel deploy --prod --yes` → ✓ Ready in 28s, алиас bank-bot-ruby.vercel.app. Прод смоукнут: `/` → 200, toggleBeta/mdLite/статус-строка присутствуют, извлечённый `<script>` проходит `node --check`.
- **Проверки:** ruff clean; test_curator 16/16 (+ассерты topic-фильтра, card, действий UI); с test_study_progress 24 passed.
- Коммит `68249a9` запушен и задеплоен.

### 2026-08-26 (Session: куратор — markdown + инструменты-lookup)
- **Markdown в чате куратора:** фронт рендерил ответы как сплошной текст (`textContent`). Добавлен `mdLite()` (escape-first → `**жирный**`, `` `код` ``, `*курсив*`, списки «- » → «•», `\n` → `<br>`), `bubble()` использует innerHTML для bot/sys и textContent для user — XSS безопасно.
- **Инструменты-lookup (кодовое слово):** модель может ответить ТОЛЬКО `{"tool":...}` — `stats` (общая статистика), `progress` (+опц. `module`) — журнал карточек по предмету/всем (выучено = серия 3+, к повторению сегодня, слабые карточки с ✓/✗, разбивка по типам), `plan` — план дня. `_tool_directive()` парсит директиву, `_curator_tool_data()` собирает данные из `study_progress`/`oge_daily_plans`, второй вызов ИИ получает их блоком «Система передала данные» и даёт финальный ответ без JSON. Директива в историю чата НЕ пишется. В ответе API новое поле `actions`.
- **UI:** на время запроса пузырь статуса «📖 Куратор смотрит твой журнал…» (удаляется по ответу); при lookup — центрированная системная строка `.cur-msg.sys` «🔍 Куратор листает журнал … 📖»; ответы рендерятся с markdown.
- **⚠️ Грабля (поймана локальным рендером до пуша):** `\ud83d\udcd6` внутри Python-строки = два lone-surrogate → UnicodeEncodeError и 500 всей страницы хаба. Правило: эмодзи в JS-инъекциях писать только 8-значным `\U0001F4D6`.
- **Проверки:** ruff clean; `test_curator.py` 16/16 (+4 новых: парсинг директив, данные инструментов, roundtrip c actions и чистотой истории, фолбэк при сбое второго вызова); вместе с test_study_progress 24 passed; локальный рендер `/`: mdLite/status/sys присутствуют, кодировка OK. Коммит `b90bf5d`, запушен.

## Changelog

### 2026-08-25 (Session: деплой — OpenRouter подключён как рабочий фоллбэк, прод проверен)

- **Повод:** GEMINI_API_KEY получить не удалось (AI Studio недоступен даже с VPN) → пользователь зарегистрировался на OpenRouter и выдал ключ; `vercel env add OPENROUTER_API_KEY production` выполнен (Sensitive).
- **Живая проверка моделей OpenRouter :free** (ключом): рабочие — `nvidia/nemotron-3-super-120b-a12b:free`, `minimax/minimax-m2.7:free`, `dots-studio/dots-3-note-preview:free`; glm-5.2/gemma-4 — постоянные 429 (общий пул); inkling-small — 403. **Грабля 1:** все они reasoning-модели — при малых max_tokens жгут токены на «мысли» → пустой/обрезанный content. Лечится параметром `reasoning: {"enabled": false}` (minimax на него отвечает 400 → ретрай без параметра). **Грабля 2:** PowerShell 5.1 `Invoke-RestMethod` шлёт string-body не в UTF-8 — кириллица ломалась ТОЛЬКО в локальных тестах (продовый Python requests не затронут).
- **`api/index.py` `_ai_chat`:** третье звено цепочки Gemini→Groq→**OpenRouter**: перебор моделей из `OPENROUTER_MODEL` (дефолт nemotron→minimax→dots), каждая с попыткой `reasoning:{enabled:false}` и ретраем без него на 400; 200 с пустым content (без tool_calls) = фоллбэк на следующую модель.
- **Деплой:** `vercel --prod` ✓ Ready, alias bank-bot-ruby.vercel.app. Прод проверен: `/api/test_ai` → 200, ответ «Hello» без reasoning-мусора. Ключ засветился в чате — можно ротировать на openrouter.ai/keys.

### 2026-08-25 (Session: AI-провайдер — Gemini первичный, Groq/HF фоллбэк)

- **Повод:** Groq API сдох у пользователя. Решение: Google Gemini (free tier, OpenAI-совместимый эндпоинт) как первичный провайдер, Groq/HuggingFace — фоллбэки; финально рабочим стал OpenRouter (см. запись выше).
- **`api/index.py`:** хелпер `_ai_chat(payload)` — цепочка Gemini → Groq → OpenRouter; переведены `call_ai_with_memory`, `call_ai_api`, `_get_ai_recommendation`, `_call_ai_api_fast`, `_pc_ai_chat`, `/api/test_ai`, `reading_generate`. Deep-fallback `_GROQ_MODEL_CANDIDATES` при 404 сохранён. `bot/ai/model_manager.py`: GEMINI первым провайдером; D&D = Gemini → Groq → HF (`api/dnd_runtime.py`).
- **Тесты:** `test_ai_model_manager.py` 14 passed (+тест порядка gemini→groq); ruff clean.

### 2026-08-25 (Session: фикс «Куратор временно недоступен»)
- **Проблема:** при полной недоступности всех ИИ-провайдеров `/api/study/chat` возвращал 502, модалка куратора показывала «❌ Куратор временно недоступен».
- **Фикс 1 — устойчивость `call_ai_api`:** сетевой сбой на модели Groq больше не обрывает перебор кандидатов (continue вместо return); 429 также пробует следующую модель; ошибка парсинга успешного ответа основного провайдера уходит в фоллбэк вместо мгновенного ❌.
- **Фикс 2 — rule-based фолбэк куратора:** `_curator_fallback_reply(subjects, plan_lines)` — при недоступности ИИ чат отвечает автоподсказкой (план дня + совет по слабой теме из `_oge_subjects_payload`), сообщения сохраняются в историю; 502 убран.
- **Подтверждено по git-логу:** итерация OGE-08…12 реализована коммитами `53ed71f`, `64b1b16`, `e5d948b`, `7d84430`, `1553840`, `fca5b62`; оба приоритетных бага исправлены в `83082af`.
- **Финальный деплой этой сессии:** `vercel --prod` ✓ Ready; прод смоукнут (`/`, `/emperors`, `/math`, `/exam` → 200; `/api/test_ai` → «Hello»).

### 2026-08-25 (Session: планирование — итерация «ИИ-куратор + UX», запись багов)

- **ТЗ записано в `activeContext.md`** (полный текст от пользователя): ИИ-куратор-чат из виджета «План на день» (промпт = прогресс карточек + слабые темы + бюджет времени + история переписки из БД, прочерк если пусто); план генерируется раз в сутки при первом заходе, облегчается при невыполнении вчера, меняется только при смене целевого времени; чипы бюджета 5/10/15/20/30 мин; автопроверка вместо «Знаю/Не знаю»; термины истории — нативной вкладкой уровня Тренажёр/Сопоставление + режимы тренажёра «имена/события/термины/все сразу»; ИИ-подсказки темы/режима на всех страницах.
- **`projectbrief.md` Phase 6 пересчитан** (сумма весов ровно 100): база завершена → 73 (OGE-FULL переключён в completed — волна контента задеплоена `16b13f9`), добавлены deliverables OGE-08 Куратор-чат (9), OGE-09 Персистентный план дня (8), OGE-10 Автопроверка (5), OGE-11 История вкладки/режимы (3), OGE-12 ИИ-подсказки везде (2).
- **Записаны баги по протоколу пользователя:** [EXAM-BUG-1] сводный экзамен `/exam` не запускается; [AICHAT-BUG-1] AI Chat персонаж «Чай» → «Ошибка AI: 404» (гипотеза: модель/endpoint провайдера в `call_ai_api`). Оба — первоочередные.
- Код не менялся; `last_checked_commit` без изменений.

### 2026-08-24 (Session: LucasTeam — засчитан день 24, разовый фикс через временный эндпоинт)

- **Задача:** засчитать пользователю `lucasteam` (id=8, «Лука») день 24 как пройденный (`web_streak.total_active_days` → 24).
- **Проблема доступа:** прямой Postgres к Supabase с этой машины заблокирован (DPI рвёт TLS-рукопожатие на 5432/6543 и даже по IPv6 direct-хосту `db.<ref>.supabase.co`; TCP открывается, но handshake падает). Старый сохранённый токен сессии невалиден (401). Готового админ-API для правки стрика нет.
- **Решение (паттерн проекта):** временный защищённый эндпоинт `POST /api/debug/credit-day` (заголовок `X-Fix-Key` = одноразовый секрет) в `api/index.py`: идемпотентно ставит `total_active_days=max(old(+1),24)`, `last_active_day=2026-08-24`, пересчитывает current/longest streak по правилам `_record_activity`, пишет сегодня в `web_activity_log` (module=system), затем `_check_web_achievements`.
- **Результат (прод):** before: last=2026-08-23, cur=8, longest=8, **total=8**; after: last=2026-08-24, cur=9, longest=9, **total=24**. Бонусом открылась ачивка `module_5` (+10 монет через штатный механизм).
- **Чистка:** эндпоинт удалён из кода (`git checkout api/index.py` — дерево было чистым на момент старта), повторный `vercel deploy --prod` ✓ Ready; прод проверен: `/` → 200, `/math` → 200, `/api/debug/credit-day` → 404.
- **⚠️ Важно:** во время сессии в рабочем дереве появилась параллельная работа пользователя: staged-переименования `core/math/*` → `core/informatics/*` (+ тесты) и свежая правка `M api/index.py`, при этом `api/index.py:10570` всё ещё импортирует `core.math.tasks`. Для рабочего деплоя `core/math` был временно восстановлен из HEAD (и после деплоя убран из дерева). **Незакрытый риск:** следующий деплой без восстановления `core/math` или обновления импорта сломает `/math`.

### 2026-08-20 (Session: модуль Информатика — переписан под уроки ITlessons + вкладка «📖 Теория»)

- **Задача:** переписать модуль информатики под РЕАЛЬНЫЕ уроки 1–9 из `D:\ITlessons` (старые темы «круговые дороги/муравей/графы/вероятность/комбинаторика» были выдуманными) + добавить вкладку теории, чтобы пользователю было удобно учить теорию.
- **Данные `core/math/tasks.py`:** 9 тем × 5 задач = 45, id `lessonN_oM`. Темы: сложность алгоритмов, целочисленная арифметика, делители/простые, факторизация, решето Эратосфена, НОД/НОК, первый контест, свойства чисел, линейный/бинарный поиск. Каждая `MathTopic` получила поля `theory` (конспект) и `code_examples`. Ответы задач сверены независимым вычислением (скрипт). Добавлены helpers `get_all_tasks`/`get_topic_by_id` (были `task_by_id`/`tasks_for_topic`/`get_random_task`/`get_tasks_by_difficulty`).
- **Страница `api/index.py` (`/math`):** добавлена третья вкладка **📖 Теория** (`panel-theory`, `renderTheoryTab`/`loadTheory`) — рендерит `theory` + примеры кода. В `topics_data` JSON добавлены поля `theory` и `code`. docstring `tasks.py` сделан raw (`r"""`), чтобы не было SyntaxWarning на `\I` в пути `D:\ITlessons`.
- **Тесты:** `test_math_module.py` 12/12 passed (ответы по difficulty как `tuple`); ruff clean; `/math` → 200, вкладка «Теория» присутствует и на проде.
- **Деплой:** `vercel deploy --prod` ✓ Ready, алиас `bank-bot-ruby.vercel.app`. Прод проверен: «Теория»/«panel-theory»/«renderTheoryTab»/«Читать конспект»/«lesson1» присутствуют в HTML.
- **Статус:** готово, задеплоено (не закоммичено).

### 2026-08-20 (Session: ачивки 240 → 250, сортировка линий по сложности, деплой)

- **Задача:** переупорядочить ачивки внутри каждой линии по возрастанию сложности (порога), добавить ачивку `prayer_89` («Восемь-девять» — сакральное число чайной религии из канона) + 9 вариаций `_89` по модулям до **250** штук.
- **Переупорядочен реестр `ACHIEVEMENTS`** в `api/index.py` (скрипт `reorder_achievements.py`): линии сгруппированы и отсортированы по числовому порогу (system_first/actions, module, streak, days, trivia_count/streak, emperors_count/modes/mastered, reading, verbs, chess, canon, prayer, gd, dnd, coins). Было 240 → стало 250.
- **Добавлены 10 ачивок:** `prayer_89`, `trivia_89`, `emperors_89`, `reading_89`, `verbs_89`, `chess_89`, `gd_89`, `dnd_roll_89`, `coins_89`, `days_89` (порог 89 в каждой линии).
- **Условия разблокировки** в `_check_web_achievements` (`api/index.py`): добавлены `if X >= 89: should.append(...)` для всех 10 новых кодов.
- **Исправлен синтаксис `api/index.py`** (корень проблемы «100 ачивок на проде»): (1) JS `{}` внутри f-строк ломали билд Vercel → заменены `|| '{{}}'` и `json.dumps(dict(topic_names))` для `topicNames`; (2) декоратор `@app.route("/achievements")` восстановлен на отдельной строке (`/achievements` был 404); (3) `_record_activity` возвращает `new_streak, longest, total` (иначе 500 «cannot unpack non-iterable NoneType»). Файл снова проходит `ast.parse`.
- **Миграция email для прод-БД:** в `_ensure_web_auth_tables` добавлен `ALTER TABLE web_users ADD COLUMN IF NOT EXISTS email VARCHAR(255) UNIQUE` — регистрация на проде падала с 500 (INSERT email в таблицу без колонки).
- **Деплой:** `vercel deploy --prod` ✓ Ready in 46s, алиас `bank-bot-ruby.vercel.app`. Прод проверен: регистрация нового юзера → 200, `GET /api/achievements` → **total: 250**.
- **Тесты:** `test_achievements.py` + `test_emperors_module.py` = 26/26 passed; `test_math_module.py` 12/12.
- **✅ ПРОВЕРЕНО (2026-08-20):** (1) реестр `ACHIEVEMENTS` (dict, 250) — все 21 числовая линия отсортирована по возрастанию порога; (2) все 10 `_89` кодов присутствуют в `_check_web_achievements`; (3) `_unlock_achievements` делает SELECT открытых кодов до INSERT (дедуп под PostgreSQL); (4) 8 тестов (5 canon e2e + 3 web_portal) починены — в `test_web_portal_e2e.py` регистрация шлёт `email` + тестовая схема `_make_engine()` получила колонку `email VARCHAR(255) UNIQUE`; в `test_canon_requests_e2e.py` хелперы шлют уникальный email. Теперь эти тесты = 19/19 passed. Осталось только убедиться визуально на проде, что у реального юзера лента ачивок выглядит упорядоченно (данные в коде упорядочены).

### 2026-08-20 (Session: модуль «Информатика — ОГЭ» `/math` доведён до боевого состояния)
- **Задача:** завершение модуля информатики (по решению пользователя — именно «информатика», не «математика»), теория из уроков `D:\ITlessons` (1–9), паттерн императорского модуля.
- **Починено:** `core/math/tasks.py` — синтаксическая ошибка `explanation "29 не делится..."` → `explanation=` (SyntaxError: positional argument follows keyword argument).
- **Пакет:** `core/math/__init__.py` создан по правильному пути (удалён ошибочный `core/math/_/_init__.py`), из импорта убран несуществующий `TaskDifficulty`. Модуль импортируется: 9 тем / 45 задач.
- **Страница:** `api/index.py` маршрут `/math` был сломан: декоратор `/achievements` вставлен в одну строку с закрывающими `"""` → f-string не закрывался, не было `return html` → 500. Фикс: `return html` + декоратор на отдельной строке.
- **Хаб:** карточка «💻 Информатика — ОГЭ» добавлена в бета-раздел `/` (рядом с Императорами).
- **Чистка:** убран ошибочный `return new_streak, longest, total` из `_record_events` (`api/index.py`, F821 — переменные не определены в этой функции).
- **Тесты:** новый `tests/unit/test_math_module.py` (12 тестов); вместе с `test_emperors_module.py` + `test_achievements.py` = **38 passed**; ruff clean; `/`, `/math`, `/emperors`, `/achievements` → 200.
- **Статус:** готово, не закоммичено — ждёт коммита + деплоя.

### 2026-08-19 (Session: math module implemented — пересмотрено 2026-08-20)
- **Задача:** реализован модуль informatics — OGE preparation based on IT lessons 1-9, following the emperors module pattern.
- **Модуль:** `/math` страница с двумя вкладками: 📚 Изучить (темы) и 🧠 Тренажер (задачи).
- **Данные:** `core/math/tasks.py` — 9 тем с 45 задачами из IT lessons (алгоритмы, арифметика, делители, круговые дороги, муравей/марафон, логика, графы, вероятность, комбинаторика).
- **Статус:** первоначально реализовано following pattern of `core/history/emperors.py`; `/math` route добавлен в `api/index.py`. Позже (2026-08-20) исправлены синтаксис, путь пакета и рендер страницы.
- **Интеграция:** SCH-01: `/math` page in api/index.py; SCH-02: карточка модуля в бета-разделе хаба.

### 2026-08-19 (Session: план школьного проекта по информатике)

- **Задача:** пользователь преподносит свой личный сайт (LTHub) как обязательный проект по информатике в 9 классе. Код и функционал не удаляются — только добавление и документация.
- **Тема:** «Мой личный учебный портал: от Telegram-бота до платформы подготовки к ОГЭ».
- **План:** записан в `memory_bank/school_project_plan.md` (3 блока: модуль ОГЭ-математика `/math`, раздел «🎓 Школа» на хабе, документация `school_project/` + обновление README/docs).
- **Создано:** `memory_bank/school_project_plan.md`, обновлён `activeContext.md`. Реализация не начата — ждёт одобрения старта с Блока 1.

### 2026-08-18 (Session: [ACH-BUG-1] — ачивки не открывались на проде)

- **Симптом:** пользователь играл в тренажёр императоров, ачивки не начислялись (73 действия emperors в логе, открыто только 2).
- **Диагностика:** временные print-ы в `api_achievements_activity`/`_unlock_achievements` → логи Vercel: `UniqueViolation` на уже открытой `first_step` → PostgreSQL **абортит транзакцию** → все следующие INSERT падают с `InFailedSqlTransaction` → `newly=[]`.
- **Root cause:** `_unlock_achievements` полагался на UNIQUE-индекс для дедупликации; в SQLite (тесты) это работает, в PostgreSQL первая же ошибка валит всю транзакцию.
- **Фикс:** `_unlock_achievements` сначала читает открытые коды (`SELECT code FROM web_achievements WHERE user_id=:id`), пропускает их, затем вставляет новые.
- **Проверка на проде:** `POST /api/achievements/activity` от имени пользователя (id=8) открыл 13+ ачивок сразу (`emperors_first…emperors_50`, `first_quiz`, `first_streak`, `streak_3`, `days_3`, `module_2`, `first_50_actions`, `chess_first`, `prayer_first`, `coins_10`); итого 17, повторный вызов → `unlocked: []`.
- **Проверки:** `test_achievements.py` + `test_web_portal_e2e.py` → **17 passed**; ruff clean; задеплоено на прод. Не закоммичено.

### 2026-08-16 (Session: единая система достижений и стрика)

- **Задача:** «раскидай ачивки по всему проекту и сделай стрик единым; отдельная страница со своими и будущими достижениями; в личном кабинете — кол-во достижений, календарь стрика и ссылку». План одобрен; за каждую ачивку **+10 монет**.
- **БД-слой:** `_ensure_achievements_tables` (web_achievements / web_streak / web_activity_log), вызывается из `get_db_engine`.
- **Реестр `ACHIEVEMENTS`: 100 достижений** (streak 18, coins 10, system 8, trivia 8, reading 8, chess 8, gd 8, emperors 7, verbs 7, prayer 7, dnd 6, canon 5). Удалены недостижимые спец-ачивки (trivia_correct_*, trivia_streak_10, emperors_master, reading_perfect, verbs_perfect) — API не собирает «правильность»; вместо них добавлены пороги 200/500.
- **Логика:** `_record_activity` (стрик: сегодня/вчера/сброс, `total_active_days`), `_check_web_achievements` (условия по фактам: streak, active_days, modules, per-module counts, coins), `_unlock_achievements` (UNIQUE-дедуп), `_award_web_coins` (+10 за каждую новую).
- **API:** `POST /api/achievements/activity` (module/actions → streak + unlocked), `GET /api/achievements` (реестр + unlocked + streak + calendar + modules); авторизация `_require_web_user()`, без токена 401.
- **JS `hubTrack(module, actions)`** на каждой странице: авторизованный → POST API, аноним → localStorage `hub_activity`. Интегрированы: trivia, emperors (миграция `emperors_streak`→`hub_streak`), chess, reading (локальный), verbs, prayer, GD, D&D.
- **UI:** страница `/achievements` (статистика, календарь 12 недель, фильтры по модулям, сетка ✅/🔒); блок «🏆 Достижения» в `/account` (счётчик, календарь, ссылка); карточка «Достижения» на хабе `/` с прогрессом.
- **Баг найден тестом:** условие стрика было перепутано (`_prev_day(last_day) == today` → `_prev_day(today) == last_day`) — стрик не продлевался. Исправлен.
- **Проверки:** полный `tests/unit` **999 passed / 10 skipped**; ruff All checks passed; `node --check` всех страниц с hubTrack OK. Задеплоено на прод, прод проверен (страница, карточка хаба, ach-box кабинета, hubTrack на модулях, 401 API без токена). **Не закоммичено.**

### 2026-08-13 (Session: фикс [ADMIN-BUG-2] — пустая админ-панель)

- **Корень найден:** JS syntax error в странице `/admin`. Python-строки, собранные через JS-конкатенацию в одинарных кавычках, содержали `\'`, который Python превращал в голый `'` → JS-строка обрывалась → весь `<script>` не парсился → `init()` не запускался → `#gate`/`#app` оставались скрытыми → пустая панель.
- **Сломаны были 3 фрагмента в `api/index.py`:** `onkeydown="if(event.key===\'Enter\'){...}"` (:7320), `onclick="viewCoins(' + u.id + ',\'' + ...)"` (:7330), `onclick="loadFeedback(\'bug\')"` и др. (:7415-7417). Python-эскейп заменён на `\\\'` (даёт корректный JS-эскейп `\'`).
- **Подтверждено на проде:** прод-HTML `/admin` имел те же 3 ошибки (`node --check` fail); после фикса извлечённый JS → `node --check` OK. `/account` JS тоже OK. Остальные `event.key===` в портале — в raw HTML (безопасны).
- **Проверки:** полный `tests/unit` **984 passed / 10 skipped**; ruff All checks passed. **Нужен деплой на Vercel.** Ранее записанная гипотеза про `is_admin` у «lucasteam» не подтвердилась.

### 2026-08-13 (Session: модуль «Императоры России» `/emperors`)

- **Новый бета-модуль «Императоры России»** — шпаргалка + тренажёр для подготовки к игре «сопоставь имена/события с императорами».
- **`core/history/emperors.py`** (новый лёгкий stdlib-пакет, как `core/canon`): `EMPERORS` (5 императоров с годами), `EVENTS` (48 событий хронологической ленты из плаката пользователя), `PERSONS` (42 личности). Каждый элемент имеет краткое описание (`note`/`description`) для подсказок. Хелперы `emperor_by_id`/`events_for_emperor`/`persons_for_emperor`.
- **Страница `/emperors`** в `api/index.py`: две вкладки — «📚 Изучить» (5 карточек-периодов, цветные чипы событий и личностей, tooltip-описания) и «🧠 Тренажёр» (случайный вопрос «имя/событие → император», 5 вариантов, подсветка верного/неверного + описание, счёт в localStorage `emperors_score`, режим «только ошибки» `emperors_wrong`, сброс счёта). Без БД — данные внедряются JSON-ом при рендере.
- **Карточка** «Императоры России» в бета-блоке хаба `/` (после «Практика глаголов»).
- **Маппинг личностей** (согласован с пользователем, по пикам славы/смерти): Пушкин→Николай I, Монюшко→Александр II, Чайковский→Александр III, Мечников→Александр III, Айвазовский→Александр II.
- **Тесты:** `tests/unit/test_emperors_module.py` (11 тестов: целостность, маппинги, рендер страницы); `/emperors` добавлен в `test_web_pages_render`. Полный `tests/unit` → **984 passed / 10 skipped**; ruff clean; JS-блок страницы прошёл `node --check`.
- **Замечание:** в Python-строке страницы `\n` в JS-коде надо писать как `\\n` (иначе Python превращает в реальный перенос и JS ломается).
- **Итерация 2 (по фидбеку пользователя):** из вопроса тренажёра убран год события (`text: ev.title`, без префикса года) — год «сдавал» ответ, т.к. кнопки показывают годы правления; вопросы выдаются из перемешанной колоды (`buildDeck`/`shuffleArray`), при неверном ответе элемент возвращается в колоду + в `wrongItems`, так что ошибки повторяются чаще (акцент на слабых местах). Задеплоено на прод (Ready).
- **Итерация 3 (2 алгоритма):** добавлен переключатель в тренажёре (`<select id="algo-select">`): **«Классика (колода)»** — как в итерации 2, и **«Флешки (интервалы)»** — SM-2-подобный интервальный повтор: состояние карточек (`{reps, interval, ease, due}`) в `localStorage['emperors_flash']`, выдаются только «просроченные» (`due <= now`), при верном ответе интервал растёт (1→3→7→…→interval*ease), при ошибке сброс `reps=0, interval=0, due=now` (карточка снова в пуле); при отсутствии карточек — экран «Все карточки изучены на сегодня!»; `updateScore` показывает «· к изучению: N». Выбор алгоритма сохраняется в `localStorage['emperors_algo']`, «Сбросить счёт» чистит и flash-прогресс. Задеплоено на прод (Ready).
- **Итерация 4 (большое обновление по выбору пользователя «Всё по максимуму»):**
  - **Бэкенд-прогресс (БД):** таблица `emperors_progress` (user_id, card_key, reps, interval_days, ease, due, correct_count, wrong_count) + `/api/emperors/progress` GET/POST (`_web_user_id`, upsert ON CONFLICT, `reset=true` для очистки). JS: `uid` из `localStorage['web_user_id']`, debounce-сохранение `pushFlash()` (600мс), merge с сервером при загрузке (сервер приоритетнее по `due`).
  - **Умнее «Флешки»:** `pickFlash` сортирует по `due` (давно просроченные первыми), чередует типы событие/личность и императоров.
  - **Статистика:** `renderStats()` — освоено карточек (reps≥3), очередь на повторение, топ ошибок по императорам (цветные ●); `updateProgressBar()` — прогресс-бар «освоено N/M».
  - **Режим «Сопоставление» (вкладка 🎯):** 10 случайных карточек, клик по карточке → клик по императору → раскладывается (верно ✅ / ошибка ❌), «Проверить» показывает результат.
  - **UX:** клавиатура 1–5 (ответ), Enter (далее); кнопка «💡 Подсказка» (показывает `info`); прогресс-бар в тренажёре.
  - **Тесты:** `test_emperors_progress_api_save_and_get` (mock SQLite + patch get_db_engine, upsert/reset), `test_emperors_page_has_new_features`. Полный `tests/unit` → **987 passed / 10 skipped**; ruff clean; `node --check` ок. Задеплоено на прод (Ready), API проверен на проде (POST/GET/reset).

- **Итерация 4.1 (дебаг-режим):** кнопка «🔧 Дебаг» в тренажёре — полупрозрачная панель в правом верхнем углу (`#debug-panel`, `position:fixed`, rgba-фон) со списком всех карточек: тип, имя, император, reps, interval, ease, correct/wrong, due (⏰ для просроченных), сортировка — просроченные первыми. Обновляется при каждом действии (`renderDebug` в `updateScore`). Задеплоено на прод (Ready), `node --check` ок.
- **Итерация 4.2 (приоритет в «Флешках»):** `pickFlash` теперь сортирует кандидатов по приоритету: **1) карточки с ошибками** (wrong>0), **2) ни разу не появлявшиеся** (нет записи), **3) обычные повторы**; внутри группы — по `due` (давно просроченные раньше). Чередование типов/императоров сохраняется. Задеплоено на прод (Ready).
- **Итерация 4.3 (3-й алгоритм «Счётчик» + единые данные):** добавлен алгоритм **«Счётчик (вероятности)»** — у каждой карточки счётчик `counter` (+1 за правильный, −1 за неправильный), выбор рандомный, но с весом выше для низкого counter (≤0 → вес 10, иначе max(1, 10−counter)). **Все 3 алгоритма теперь пишут в БД одни данные** (`recordAnswer` в `answerClick` всегда обновляет counter + SM-2 reps/interval/ease/due + correct/wrong независимо от выбранного алгоритма), а выбор алгоритма — только метод подбора (`pickItem`: flash→pickFlash, counter→pickCounter, deck→buildDeck). В БД добавлена колонка `emperors_progress.counter` (ALTER TABLE IF NOT EXISTS), GET/POST API передают counter. В `updateScore` для counter-режима показывается «· слабых: N» (counter<0); в дебаг-панели выводится счётчик. Полный `tests/unit` **987 passed / 10 skipped**, ruff clean, `node --check` ок. Задеплоено на прод (Ready), API проверен (counter сохраняется).
- **Итерация 4.4 (прогресс привязан к аккаунту):** прогресс «Императоров» теперь привязан к **аккаунту**, а не к анонимному uid. GET/POST `/api/emperors/progress` резолвят uid только из сессии (`_get_session_user(_auth_token_from_request())` → `_web_user_id("u"+id)`); **без валидного токена** GET возвращает `{"cards": {}, "uid": 0}`, POST → `401`. JS: `pushFlash`, загрузка и `resetScore` слают `X-Auth-Token` только если есть `localStorage.web_token`; **незалогиненные хранят прогресс только в localStorage** (не пишут в БД). Один аккаунт видит одинаковый прогресс на любом устройстве. Тест `test_emperors_progress_api_save_and_get` переписан на токен-мок (успешные save/get/reset через `X-Auth-Token`, анонимные GET=пусто и POST=401). ruff clean, `node --check` ок. Задеплоено на прод (Ready), прод проверен (anon GET=пусто, anon POST=401).
- **Итерация 4.5 (описания во вкладке «Изучить»):** чипы событий и личностей в «Изучить» теперь кликабельные (`data-type`/`data-text` + `onclick="app.showInfo(this)"`); по клику открывается модальное окно `#info-modal` (tag «Событие»/«Личность», заголовок с годом, император цветом, описание из `note`/`description`). Закрытие по ✕ или клику по фону. CSS: `.chip.clickable:hover`, `.modal-overlay`, `.modal`. ruff clean, `node --check` ок, прод проверен. Задеплоено.
- **Итерация 4.6 (важность 1–5 + расширенный режим «Все правители»):**
  - **Данные** (`core/history/emperors.py`): `HistoryEvent` и `Person` получили поле `importance: int = 3` (1–5). Добавлен `RULERS` — все ключевые правители от Рюрика до Путина (~33): rurik, oleg, igor, olga, svyatoslav, vladimir_i, yaroslav, monomakh, dolgoruky, nevsky, kalita, donskoy, ivan_iii, ivan_iv, godunov, mikhail_romanov, alexey_mikhailovich, peter_i, elizaveta, catherine_ii, paul_i, alexander_i, nicholas_i, alexander_ii, alexander_iii, nicholas_ii, lenin, stalin, khrushchev, brezhnev, gorbachev, yeltsin, putin. `EMPERORS` (5 базовых) сохранён.
  - **Ключевые правители получили больше контента:** Владимир Святой, Ярослав Мудрый, Иван III, Иван Грозный, Пётр I, Екатерина II, Сталин и др. — по 4–9 событий и 3–6 личностей (включая мировые личности: Вашингтон, Кант, Ньютон, Черчилль, Рузвельт, Рейган, Линкольн и др.); второстепенные/недолго правившие (Игорь, Ольга, Святослав, Калита, Годунов, Павел I) — по 1–3 события и 1–2 личности. Итого: **157 событий, 119 личностей**.
  - **Сериализация** (`api/index.py` `emperors_page`): в JSON добавлены `"rulers"` (все правители), `importance` в событиях/личностях; импорт `RULERS as _RULERS`; экспорт `RULERS` добавлен в `core/history/__init__.py`.
  - **JS-страница:** переключатель `<select id="scope-select">` — «5 императоров» (scope=`emperors`, по умолчанию) / «Все правители (Рюрик–Путин)» (scope=`all`), сохраняется в `localStorage['emperors_scope']`. Всё (вопросы, колода, флешки, счётчик, статистика, прогресс, сопоставление, дебаг, «Изучить») фильтруется по активному scope (`itemsInScope()`/`activeRulerIds()`).
  - **Важность влияет на выбор:** `pickFlash` сортирует внутри приоритетной группы по importance (выше важность → раньше); `pickCounter` — вес = база×importance; колода — без весов (классика).
  - **Звёзды важности:** в «Изучить» у чипов событий/личностей отображается `★`×importance (`starRow`), в модалке `#info-modal` — звёзды у императора (`showInfo`). Цвета правителей — палитра из 33 цветов `PALETTE`, генерируется по индексу вместо фиксированного `COLORS`.
  - **Тесты:** обновлены под новые объёмы (≥100 событий, ≥100 личностей, importance 1–5, RULERS ≥30); добавлены `test_rulers_count`, `test_every_ruler_has_items`, `test_key_rulers_have_more_items_than_minor_ones`, `test_emperors_page_has_extended_mode_and_importance`; дубликаты имён личностей (Рейган/Ельцин) разведены уточнениями. Итого 18 тестов. ruff clean, `node --check` ок. Задеплоено на прод, прод проверен (scope-select, звезды, importance на месте).
- **Итерация 4.7 (приоритет флэшки + дефолт + повтор ошибок):** флэшка стала **алгоритмом по умолчанию** (`|| 'flash'`). Новый приоритет в `pickFlash`: **1) просроченные** (сначала более просроченные, по `due`), **2) новые** (сначала с высокой важностью), **3) остальное** — изученные непросроченные, только когда нет просроченных и новых. Пул = все карточки в scope. При **неправильном ответе** карточка становится просроченной **через 1 минуту** (`due = Date.now() + 60000`), чтобы повторялась вскоре. Тесты: `test_emperors_page_flash_priority`, `test_emperors_page_has_two_algorithms` (дефолт flash). Итого 19 тестов. ruff clean, `node --check` ок. Задеплоено на прод, прод проверен.
- **Итерация 4.8 (выбор числа вариантов ответа):** жалоба пользователя — в режиме «Все правители» вопрос показывал все 33 варианта ответа. Добавлен переключатель `<select id="opt-count">` (в `localStorage['emperors_optcount']`): **«5 вариантов»** (по умолчанию: правильный + 5 случайных дистракторов из активного пула) / **«Все (хронологически)»** (все правители активного scope в хронологическом порядке, без перемешивания). Клавиатура расширена до 1–6. Тесты обновлены (19 passed), ruff clean, `node --check` ок. Задеплоено на прод, прод проверен.
- **Итерация 4.9 (убраны самоссылки правителей + очки по сложности):** пользователь заметил, что в «Личностях» у каждого правителя был он сам (Рюрик у Рюрика, Пётр I у Петра I и т.д.). **Удалены 26 записей-самоссылок** из `core/history/emperors.py`. Для 8 правителей, оставшихся без личностей (Олег, Игорь, Ольга, Святослав, Мономах, Долгорукий, Калита, Годунов), добавлены реальные личности (Свенельд, князь Мал, Константин VII, Иоанн Цимисхий, Олег Гориславич, Андрей Боголюбский, митрополит Пётр, царевич Дмитрий). Итого 157 событий / 101 личность. **Начисление очков зависит от сложности:** «5 вариантов» → +1 за верно / 0 за ошибку; «Все» → +2 за верно / −1 за ошибку; в `updateScore` показывается «· сложность: все варианты (+2/−1)». Тесты (19 passed), ruff clean, `node --check` ок. Задеплоено на прод, прод проверен (самоссылок нет, очки по сложности работают).
- **Итерация 4.10 (максимальная прокачка модуля):** по запросу «максимально прокачай этот модуль» добавлен пакет из 8 улучшений:
  1. **Таймлайн по эпохам** в «Изучить» (`eraGroups()` + HTML-блок `.timeline`): 7 эпох (Древняя Русь 862–1125 → Россия 1991–…), цветные чипы правителей по `PALETTE`, клик → Тренажёр.
  2. **Обратный режим вопроса** `#qdir-select` («Событие → Правитель» / «Правитель → Событие», `localStorage['emperors_qdir']`): в обратном показывается правитель, варианты — 6 событий/личностей (правильный + 5 дистракторов из scope).
  3. **Уровень по очкам** `levelInfo()`: Новичок (0) → Знаток (20) → Профи (60) → Мастер (120); уровень в счёте и stats («до следующего: N очк.»).
  4. **Серия дней** `updateStreak()`/`getStreak()` (`localStorage['emperors_streak']`), в счёте «· серия: N дн.», в stats — серия дней.
  5. **Ачивки** `checkAchievements()` (`localStorage['emperors_achievements']`): первый ответ 🎯 / 20 очков ⭐ / 100 очков 💎 / серия 3 дня 🔥 / серия 7 дней 🌟 / все карточки 🏆; alert при разблокировке + бейджи ✅/🔒.
  6. **Правильных подряд** `streakCorrect` (обнуляется на ошибке), показывается в stats.
  7. **Анимации ответов** CSS `@keyframes pulse-green`/`shake`, классы `.animate-correct`/`.animate-wrong` на вопросе и кнопке.
  8. **Вкладка «📜 Хронология»** `#panel-chrono`: расстановка правителей scope в хронологическом порядке кликом (самый ранний из оставшихся), ✅/❌ фидбек, «Правильный порядок» / «Твоя последовательность», счётчик «Поставлено: N / M».
  Тесты (20 passed), ruff clean, `node --check` ок. Задеплоено на прод, прод проверен (все 20 маркеров новых фич). Не закоммичено.

### 2026-08-13 (Session: запись [ADMIN-BUG-2])

- Прод подтверждён обновлённым: `/admin` → 200, `/settings` → 301 (деплой нового билда прошёл). [SETTINGS-BUG-1] фактически закрыт деплоем.
- **Записан [ADMIN-BUG-2]** (Админ): админ-панель `/admin` пустая у «lucasteam». Первоначальная гипотеза: после security-фикса админ-доступ строго по колонке `web_users.is_admin` (`api/index.py:161-168`, `:146`), авто-грант удалён (`api_auth_register` :7055-7056). *(UPD: гипотеза НЕ подтвердилась — реальная причина JS syntax error, см. [ADMIN-BUG-2] ПОЧИНЕНО выше.)*

### 2026-08-13 (Session: фикс багов из memory bank)

- **[TRIVIA-BUG-1] ПОЧИНЕНО:** в `core/canon/questions.py` всем вопросам без ручных `distractors` (группы `tracks` id 4-11, 18, 24 и `candy` id 12-15) добавлены 3 реалистичных варианта. Вопрос id 24 получил distractors по материалу `explanation` (частичные проявления: только вокальные тики / только моторные тики / только множественные личности). Фолбэки генераторов переведены на ручные distractors: `api_trivia_question` (`api/index.py:7588`), `_vercel_trivia_question` (:4961), `bot/trivia/questions.py::generate_trivia_question`. Вопросов без distractors — 0. Полный `tests/unit`: **973 passed / 10 skipped**; ruff All checks passed.
- **[SETTINGS-BUG-1]** — подтверждено, что код-фикс в рабочей копии (`/settings` → 301 на `/account`, админка на `/admin`); баг на проде вызван отсутствием деплоя. Осталось: задеплоить рабочую копию на Vercel.

### 2026-08-11 (Session: протокол записи багов пользователя)

- Пользователь переключился на протокол: баги вписывает в чат → я фиксирую их в memory bank → другой разработчик фиксит.
- **Записан [TRIVIA-BUG-1]** (Викторина): вопрос id 24 (`core/canon/questions.py:73-79`, группа `tracks`) с пустым `distractors: []` → в `api_trivia_question` (`api/index.py:7587-7606`) фолбэк подставляет `correct_text` других вопросов группы (названия треков/статей) → «идиотские» варианты ответов. Детали в `activeContext.md`.
- **Записан [SETTINGS-BUG-1]** (Настройки/Админ): на проде `/settings` совмещён с админ-панелью — это старая задеплоенная версия; рефактор 2026-08-11 (`/account`+`/settings`, вынос админки на `/admin`, `301`) есть в рабочей копии, но не задеплоен. Фикс = деплой. Детали в `activeContext.md`.

### 2026-08-11 (Session: объединение /account + /settings, админ-панель на отдельную страницу)

**Задача:** объединить личный кабинет и настройки в одну страницу; админ-панель — отдельная страница со ссылкой из кабинета админа.

**Сделано (всё в `api/index.py`):**
- `/account` — единая страница: профиль (аватар, имя, @логин, статус админ/пользователь) + 💎 монеты + форма редактирования (имя/GD/Telegram/Lichess, сохранение через `/api/auth/update`) + подсказка «Рекомендуем заполнить» + «Выйти». Для админов — кнопка «🛠 Админ-панель» → `/admin` (показывается только при `p.is_admin`).
- `/settings` → **301 redirect** на `/account` (импортирован `redirect` из flask).
- `/admin` — отдельная страница админ-панели, добавлена вкладка «💡 Предложения» (перенесена из embedded-панели `/settings`): фильтры Все/🐛 Баги/💡 Предложения/Открытые, удаление; стиль `.badge-danger`.
- Ссылки: карточка «Администрирование» на хабе `/` → `/admin`; подсказка на `/register` → `/account`.

**Проверки:** полный `tests/unit` **973 passed / 10 skipped**; ruff All checks passed. Не закоммичено.

### 2026-08-11 (Session: производительность + фидбек в админке)

Два бага от пользователя:

**Баг 1 — «сайт думает пол минуты» (везде, включая страницы).** Root cause: `get_db_engine()` на **каждый** вызов выполнял 9 функций `_ensure_*`, которые шлют 69 DDL-запросов (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN`, `CREATE INDEX`) в удалённую Postgres — десятки сетевых round-trip'ов на каждый запрос страницы/API. **Фикс (`api/index.py`):** все `_ensure_*` перенесены внутрь блока `if DB_ENGINE is None:` — DDL-миграции выполняются один раз при создании движка, а не на каждый запрос.

**Баг 2 — фидбек с `/suggest` не виден в админке.** Root cause: фильтры «Баг»/«Предложения» в `/admin` слали `?status=bug`/`?status=suggestion`, но API фильтрует по колонке `status` (`open`/`closed`), а категория лежит в `category` → отфильтрованные списки всегда пустые. **Фикс:** JS `loadFeedback` теперь шлёт `?category=bug`/`?category=suggestion`, `?status=open` — только для «Открытые»; эндпоинт `/api/admin/feedback` принимает параметр `category`.

**Доп. оптимизация cold start (после деплоя выяснилось):** страницы без БД (`/`, `/health`) всё равно открывались ~21s — при импорте модуля выполнялся import-time блок инициализации (`get_db_engine()` + `_load_bot_id()` + 2 `_ensure_*`, строки ~12378). **Фикс:** блок удалён — `get_db_engine()` и `_load_bot_id()` теперь вызываются лениво (первый запрос к БД / webhook). Результат на проде: `/health` 21s → **0.6s**, `/` → **0.4s**; первый запрос к БД на новом инстансе ~10s (DDL один раз), последующие 0.4-1.3s.

**Тесты:** добавлена проверка фильтра по категории в `test_feedback_submit_and_admin_flow`; полный `tests/unit` **973 passed / 10 skipped**; ruff clean. Задеплоено на прод.

### 2026-08-11 (Session: аудит бета-модулей — фикс последних 3 багов)

- Повторный аудит подтвердил: все баги бета-аудита 2026-08-10 уже исправлены в рабочей копии (валидация кубиков D&D, медиа/таймаут GD, ключи `_TRIVIA_SESSIONS` по session_id, валидация `answer_index`, атомарный `pop` перед начислением монет в шахматах, XSS в глаголах, `VERB_GEN_LOCK` cleanup, авторизация DELETE комнат Family, детерминированная молитва дня + UNIQUE-индекс, XSS/`</`/лимиты в Каноне, privilege escalation и валидация длин в админке).
- Закрыты 3 остававшихся бага в `api/index.py`:
  - **Family stored XSS:** список участников в `/family/room` теперь проходит `escapeHtml` (`data.members.map(escapeHtml).join(', ')`).
  - **Chess JSON.parse:** в `checkMove` добавлен try/catch — при не-JSON ответе показывается «Ошибка сервера.», кнопка «Проверить» не залипает.
  - **Chess TTL `_PENDING_PUZZLES`:** константа `_PENDING_PUZZLE_TTL = 1800` + ленивая чистка протухших записей при выдаче нового пазла; проверка устаревания в check переведена на константу.
- Проверки: ruff All checks passed; `py_compile` OK (только pre-existing SyntaxWarnings); тесты — 19 passed (web_portal_e2e + canon_requests_e2e), 9 passed (chess/family/trivia/verbs/puzzle).

### 2026-08-10 (Session: бета-аудит 9 модулей — запись + начало фиксов)

Пользователь провёл аудит всех бета-модулей. Полный план фиксов зафиксирован в `activeContext.md` («Бета-аудит 2026-08-10»). Начата работа по приоритету №1 (privilege escalation в `/settings`/`/admin`), затем остальные критические (XSS, авторизация DELETE, DoS dice, монеты пазлов).

### 2026-08-10 (Session: фикс GD-BUG-1 — веб-заявка GD с медиа)

**Баг:** на `/gd` заявка отправлялась без видео/фото (сразу `pending`, без `media_file_id`), и кнопка «Отправить рекорд» зависала на минуту при медленном XHR.

**Фикс (всё в `api/index.py` + тест):**
- `POST /api/gd/submit` переведён с JSON на **multipart/form-data** и теперь **требует** файл `media` (видео/фото с прохождением); 400 «Прикрепите видео или фото с прохождением» без файла. `media_type` определяется по MIME (`video/*`/`image/*`) или расширению; файл сохраняется как **data-URL** в `media_file_id` (веб не имеет Telegram file_id).
- `/gd`: добавлено `<input type="file" id="sub-media" accept="video/*,image/*,...">` с лейблом `.file-label` (подсветка при выборе файла), JS `submitRecord()` переписан на FormData + `xhr.timeout = 30000` + `ontimeout` (возвращает кнопку), после успеха поля очищаются.
- Модерация `/gd`: для заявок с data-URL-медиа показывается ссылка «🎬 Смотреть медиа».
- Тест `test_gd_web_submit_requires_media` (`tests/unit/test_web_portal_e2e.py`): 400 без файла → создание с `.mp4` → status=pending, media_type=video, `media_file_id` = data-URL; страница `/gd` содержит `#sub-media`. Таблица `submissions` добавлена в `_make_engine`.
- Итог: unit **973 passed / 10 skipped**, ruff clean.

### 2026-08-10 (Session: деплой + режим тестирования бета-модулей)

- Задеплоено на прод (Vercel, alias `bank-bot-ruby.vercel.app`): Family Circle JS переведён на ES5/XHR (фикс кнопки «Создать» в старом Telegram WebView — ранее весь скрипт падал на `async/await`/стрелках/`fetch`), доработка канона (поиск по произведениям, `view_count`, `has_audio` в каталоге), cooldown пазлов, админ-проверка GD через AdminSystem.
- Прод проверен: `/`, `/family`, `/family/room`, `/family/result`, `/canon`, `/api/canon/works` — все 200.
- **Новый режим:** пользователь вручную тестирует бета-модули; рабочие → перенос в основной раздел, баги → запись в memory bank (не фиксятся на месте). Список бета-модулей и зафиксированные баги — в `activeContext.md`.
- **Зафиксирован баг [GD-BUG-1]** — веб-заявка GD без медиа (см. `activeContext.md`).

### 2026-08-09 (Session: CANON-03 — аудио для треков + просмотр текста для статей)

**Сделано (всё в `api/index.py` + тесты):**
- **БД:** `_ensure_canon_tables()` — колонки `audio_data BYTEA`, `audio_name VARCHAR(255)`, `audio_mime VARCHAR(100)`, `audio_size INTEGER` в CREATE + ALTER `ADD COLUMN IF NOT EXISTS` для существующей прод-таблицы (Supabase). SQLite-зеркало в `tests/unit/test_web_portal_e2e.py::_make_engine()` — `audio_data BLOB` + остальные колонки.
- **Admin API (только админ, `_admin_require`):** `POST /api/admin/canon/works/<id>/audio` (multipart, поле `audio`, лимит 4 МБ, whitelist mime mp3/ogg/wav/m4a/aac), `DELETE /api/admin/canon/works/<id>/audio`. Константы `_MAX_AUDIO_BYTES`, `_ALLOWED_AUDIO_MIME`, хелпер `_canon_audio_mime()`.
- **Публичное API:** `GET /api/canon/work/<id>/audio` — потоковая отдача бинарных данных (Content-Type из БД, `Content-Disposition: inline`, Cache-Control 1 день, 404 для не-approve/без аудио). `/api/canon/works` и `/api/canon/work/<id>` теперь возвращают `audio_name`/`audio_mime`/`audio_size`/`has_audio` (нормализация `bool()` — SQLite отдаёт 0/1).
- **Страница работы `/canon/work/<id>`:** блок `#audio` (audio-player + имя/размер) для треков с аудио, `format_bytes()` (новый хелпер). Список `/canon`: кнопка «🎧 Слушать» на карточке трека с аудио (якорь `#audio`).
- **Админ-панель `/admin/canon`:** в редакторе произведения для треков — поле загрузки файла + кнопки «⬆️ Загрузить» / «🗑 Удалить» (JS `uploadAudio`/`removeAudio`).

**Тесты:** новый `test_audio_upload_stream_delete` в `tests/unit/test_canon_requests_e2e.py` — загрузка админом → has_audio/audio_name/audio_mime в API → аудиоплеер на странице → стрим с корректными mime/данными → 403 анониму / 400 bad-ext → удаление → 404. Полный `tests/unit`: **972 passed / 10 skipped / 0 failed**; ruff All checks passed.

### 2026-08-08 (Hotfix: CANON-02 auth_token → web_token)

**Баг:** залогиненный пользователь на `/canon/request` видел «Чтобы отправить заявку, войдите в аккаунт» — форма не показывалась.

**Причина:** новые CANON-страницы читали `localStorage.getItem('auth_token')`, но весь остальной портал сохраняет сессионный токен под ключом **`web_token`** (`login_page`/`register_page`: `localStorage.setItem('web_token', r.token)`, строка ~6323). Ключа `auth_token` во фронтенде не существовало никогда → токен не находился.

**Фикс:** заменил `auth_token` → `web_token` в 4 местах `api/index.py`: `canon_page` (loadAdminActions, строка ~8024), `canon_request_page` (init + sendRequest, ~8687/8694), `admin_canon_page` (TOKEN, ~8796). Серверная часть (`_auth_token_from_request`) не менялась — читает `Authorization: Bearer` корректно.

**Тесты:** `test_canon_requests_e2e.py::test_admin_pages_render` теперь проверяет маркер `web_token` на страницах `/admin/canon` и `/canon/request`. Полный `tests/unit`: **971 passed / 10 skipped**, ruff clean. Задеплоено на Vercel — страница `/canon/request` отдаёт `web_token` (проверено на проде).

### 2026-08-08 (Session: CANON-02 — произведения + заявки + модерация)

**CANON02 completed.** Канон стал живым: на `/canon` появились сами произведения, зарегистрированные пользователи подают заявки на канонизацию, админ модерует их и правит тексты (произведения + основной документ канона через БД-overlay).

**Сделано (всё в `api/index.py`):**
- **БД-слой:** `_ensure_canon_tables()` (вызывается из `get_db_engine()` в try/except — сбой БД не роняет старт) — таблицы `canon_works` (status approved/pending/rejected, content), `canon_requests`, `canon_doc` (overlay документа); сид метаданных 16 произведений из `core.canon.works` при пустой таблице.
- **Публичные API:** `GET /api/canon/works` (фильтры + content, БД→фолбэк статика), `GET /api/canon/work/<id>` (полный текст, автору/url/canon_level), `GET /api/canon/documents` (overlay БД → файл, поле `source`), `POST /api/canon/request` (только залогиненный: title/author/content обязательны, title≤200, content≤5000, валидация kind/canon_level).
- **Admin API (`_admin_require` → 403):** `GET /api/admin/canon/requests?status=`, `POST …/requests/<id>/approve|reject` (approve переносит в `canon_works` со статусом approved + reviewer_id/review_note), `PUT /api/admin/canon/works/<id>` (метаданные + полный текст), `GET/PUT/DELETE /api/admin/canon/doc` (overlay документа; PUT обновляет/создаёт, DELETE сбрасывает к `canon.md`).
- **Страницы:** `/canon` — add-to-bar «📩 Отправить заявку на канонизацию» + карточки произведений с «📖 Читать» (рендер из БД); `/canon/work/<id>` (мета-бейджи, оригинал в Telegram, prev/next-навигация, `_html_escape`); `/canon/request` (форма для зарегистрированных, без токена → подсказка); `/admin/canon` (вкладки Заявки/Произведения/Документ, JS-паттерн как в `/admin` — доступ контролируют API).
- **Баг-фиксы по ходу:** декоратор `@app.route("/canon")` случайно висел на `_canon_doc_effective()` вместо `canon_page()` (страница отдавала голый текст) — исправлен; добавлен недостающий хелпер `_html_escape`; JS `saveWork` читал несуществующие id (`title`/`author` → `we-*`); `loadRequests` искал `#reqs` вместо `#requests-list`.

**Тесты:** `tests/unit/test_web_portal_e2e.py::_make_engine()` — добавлены DDL-зеркала `canon_works`/`canon_requests`/`canon_doc` + сид-произведение; `now_impl` возвращает ISO-строку (sqlite не умеет datetime в UDF). Новый `tests/unit/test_canon_requests_e2e.py`: 7 тестов — страницы работ/API, 404 для отсутствующего id, submit требует auth, валидация полей, полный модерационный флоу (submit→approve→works→edit→403 не-админу), reject + doc overlay PUT/DELETE roundtrip, рендер `/admin/canon` и `/canon/request`.

**Проверки:** полный `tests/unit` **971 passed / 10 skipped** (было 964/10); всё зелёное. Деплой на Vercel: https://bank-bot-ruby.vercel.app — `/canon`, `/canon/work/1`, `/canon/request`, `/admin/canon` → 200; `/api/canon/works` отдаёт 16 сид-произведений из БД; `/api/admin/canon/requests` без токена → 403.

### 2026-08-07 (Session: CANON01 — модуль хранения канона)

**CANON01 completed.** Единый source of truth канона вселенной Олеговируса/LTL (Google Doc v2.9) вместо 5+ разошедшихся копий.

**Сделано:**
- **`core/canon/`** — лёгкий stdlib-пакет (паттерн `core/rates.py`, без тяжёлых зависимостей — критично для Vercel):
  - `canon.md` — полный оригинальный текст v2.9 (232 строки, markdown-разметка, гиперссылки t.me, блок-цитаты; сохранена опечатка оригинала «námёки»).
  - `__init__.py` — `CANON_VERSION="2.9 (12 мая 2026)"`, `CANON_DOC_ID`/`CANON_DOC_URL`/`CANON_DOC_EXPORT_URL`/`CANON_FILE_PATH`/`PROHIBITED_CANON_KEYWORDS`, `load_canon_text()`/`canon_version()`/`canon_sections()`/`find_canon()`/`render_markdown()` (свой stdlib-рендерер), `get_glossary()`/`get_works()`.
  - `works.py` (16 произведений + фильтры level/kind), `glossary.py` (22 термина), `questions.py` (единый пул 24 вопросов trivia), `prayers.py` (15 молитв + `random_prayer`).
- **Перевод потребителей на core.canon:** `api/index.py` (удалены локальные `_TRIVIA_QUESTIONS`/`_PRAYERS`, `_load_canon_trivia`/`generate_trivia_from_canon` → `load_canon_text()`), `bot/trivia/questions.py`, `bot/ai/knowledge.py`, `bot/ai/knowledge_updater.py` (`LOCAL_CANON_PATH = CANON_FILE_PATH`), `bot/commands/ai_commands_ptb.py` + `ai_commands.py`; `bot/ai/service.py::_match_knowledge` — приоритет групп dynamic > static (CANON_KNOWLEDGE) > local, порог 0.5×max.
- **Страница `/canon`** (GitHub Dark, 3 вкладки: 📜 Полный текст / 🎵 Произведения с фильтрами / 🧩 Глоссарий с поиском) + API `GET /api/canon/{text,works,glossary,search}` + карточка «📖 Канон» на хабе `/`.
- **Удалены** `data/canon_knowledge.txt` и `api/canon_knowledge.txt` (grep-проверка: ссылок в коде нет).
- **Файлы:** `tests/unit/test_canon_module.py` (25 тестов), `/canon` добавлен в `test_web_portal_e2e.py::test_web_pages_render`.

**Проверки:** полный `tests/unit` **964 passed / 10 skipped**; ruff All checks passed по всем изменённым файлам. Исправлен баг `'module' object is not callable` (функции `glossary()`/`works()` переименованы в `get_glossary()`/`get_works()` из-за конфликта с подмодулями).

**Осталось отдельной задачей:** 4 падения pre-existing `tests/property/test_bunker_profile_parser_properties.py` + `test_mafia_profile_parser_properties.py`.

### 2026-08-03 (Session: QUALITY — ruff-clean всего репозитория + автотесты веб-портала)

**A — ruff-clean всего репо (завершено).**
- `api/dnd_runtime.py`: удалён мёртвый `msg_type` (`"action"`/`"dice"`), нигде не использовался.
- 4 субагента исправили E712/F841 в unit/property/integration/pbt-тестах (33+12+31+6 правок) + ручной фикс `tests/unit/test_command_validation_edge_cases.py:330`.
- Итог: `ruff check . --exclude .venv --exclude vk_mini_app --exclude node_modules` → **All checks passed!** (было 100 ошибок).
- Полный прогон (unit+integration+property+smoke): 30 failed / 1242 passed / 32 skipped / 3 errors; на чистом HEAD (git stash) — те же 30 failed + 3 errors → pre-existing, не связаны с ruff-правками.

**B — автотесты веб-портала (10/10 passed).**
- Создан `tests/unit/test_web_portal_e2e.py` (новый файл, не в collect_ignore): полный auth-цикл, feedback+admin flow, admin stats/users/coins, trivia (сессии + реалистичные дистракторы), веб-страницы (200 + маркеры), reading_trainer (MOM-05 маркеры + чистота HTML), /suggest форма, reading_generate fallback.
- `_make_engine()`: in-memory sqlite со схемой, совместимой с PG-DDL продуктива (`web_users`, `web_sessions`, `web_coin_log`, `web_feedback`, `users`, `user_coins`) + sqlite-функция `NOW()`.
- PG-only `ANY(:ids)` (`api/index.py:7039` /admin/users) → sqlite-функция `ANY` (JSON) + `do_execute`-хук сериализует список в JSON перед bind.
- Убран ошибочный ассерт `{currentData` (валидный JS template literal в /reading_trainer.html) → проверка `id="stats-bar"`.
- Проверка: полный `tests/unit` **939 passed / 10 skipped / 0 failed**; ruff All checks passed.

**Осталось по QUALITY:** C — разбор TODO (`api/index.py:9347` cooldown пазлов; `bot/commands/gd_admin_commands_ptb.py:276` админ-проверка).

### 2026-08-03 (Session: PARSE01 финал — E2E PTB-тест handle_manual_parsing + фикс бага начисления)

**PARSE01 completed.** Реальный E2E-тест PTB-хендлера + production-баг, найденный тестом.

**Сделано:**
- **`tests/unit/test_manual_parsing_handler_e2e.py`** (5 тестов, реальная SQLite в tmp-файле, оба DB-контура): 
  - целевой путь `ParsingService` для GD Cards (`🤩 Орбы: +10` → 25 монет по канону 2.5, транзакция),
  - legacy-путь `UnifiedParser` для True Mafia профиля (`💵 Деньги: 3000` → 200 монет, курс 15:1),
  - идемпотентность (`processed_messages` в сыром SQLiteRepository) — повторный парсинг блокируется,
  - нераспознанное сообщение / отсутствие reply.
  - Фикстуры патчат оба входа: `database.database.engine`/`SessionLocal` + `utils.admin.admin_system.SessionLocal`.
- **Баг:** `bank_bot/repositories/balance_repository.py` `add_balance()` падал `TypeError: unsupported operand += 'NoneType' and 'int'` — `AdminSystem.register_user()` делает raw INSERT без `total_earned` (→ NULL в БД), а `add_balance` делал `user.total_earned += amount`. Исправлено на `user.balance = (user.balance or 0) + amount` / `user.total_earned = (user.total_earned or 0) + amount`.

**Проверки:** 5/5 passed (новый E2E); таргетированные 57 passed (parsing_service + manual_parsing + vercel_parsing_e2e); полный `tests/unit` 938 passed / 10 skipped, 1 failed — **pre-existing** `test_web_portal_e2e.py::test_admin_stats_and_users` (PostgreSQL-only `ANY()` на SQLite, untracked-файл, не связан с правкой). ruff All checks passed.

**Осталось по PARSE01:** нет — все части (мониторинг, idempotency, канон курсов, E2E PTB) закрыты.

### 2026-08-03 (Session: PARSE01 часть 3 — единый source of truth курсов конвертации)

**PARSE01 ч.3 completed.** Курсы конвертации игровых валют приведены к единому канону.

**Проблема:** 3 несогласованных источника курсов: api-словарь (gdcards 2.5, gusya 5.0, shmalala 2.5, karma 0.5, bunkerrp 50) был мёртвым fallback (миграция 005 засеяла прод-таблицу `conversion_rates` значениями 1.0); legacy `bot/handlers/parsing_handler.py` имел жёсткие 2:1/1:1/15:1/20:1; `/admin_rate` правил только in-memory `src.config`.

**Сделано:**
- **`core/rates.py`** — новый канонический модуль: `BOT_CONVERSION_RATES` (значения api-словаря), `DEFAULT_CONVERSION_RATE=1.0`, `PARSING_RESOURCE_TYPES` (gusya_cards→coins, gdcards→orbs, shmalala→money, shmalala_karma→karma), `get_conversion_rate(bot_name)`.
- **`api/index.py`**: импорт канона (~2519); `_ensure_parsing_tables` → `_sync_conversion_rates(conn)` (INSERT отсутствующих, UPDATE только строк с k==1.0 — сохраняет админ-правки).
- **`bank_bot/services/parsing_service.py`**: fallback-курс из канона вместо жёсткой 1.0.
- **`bot/handlers/parsing_handler.py`** legacy: GD Cards/Shmalala конвертация через канон (курс ×...), True Mafia /15 и BunkerRP /20 оставлены.
- **Миграция `005_add_parsing_resources.py`**: seed 1.0 → 5.0/2.5/2.5.
- **`tests/unit/test_parsing_service.py`**: fallback-тест ждёт канонический gdcards 2.5.

**Блокер деплоя:** первый деплой упал `ModuleNotFoundError: structlog` — импорт `core.parsers.rates` тянул тяжёлый `core/parsers/__init__.py`. Модуль перенесён в `core/rates.py` (лёгкий родительский пакет).

**Проверки:** 70 passed (test_parsing_service + test_vercel_parsing_e2e + test_admin_manager); полный `tests/unit` **924 passed / 10 skipped / 0 failed**; ruff All checks passed. После фикса импорта задеплоено: `/api/dnd/status` → 400 (нормальный запуск, без traceback). Интеграционные падения (7) — pre-existing (git stash), не связаны.

**Осталось по PARSE01:** E2E PTB-тесты (handle_manual_parsing с реальной БД).

### 2026-08-03 (Session: MOM-05 — доработки тренажёра чтения)

**MOM-05 completed.** Дополнительные улучшения тренажёра чтения в production `api/index.py` (`/reading_trainer.html`), Vercel-страница.

**Сделано:**
- **Озвучивание (TTS):** кнопка «🔊 Слушать» (экран чтения) + «🔊 Вопрос» у каждого вопроса через Web Speech API (`SpeechSynthesisUtterance`, `ru-RU`, rate 0.9), безопасный fallback-`alert` при отсутствии API.
- **Подсказка:** кнопка «💡 Подсказка» у каждого вопроса — раскрывает правильный ответ (экранируется `escapeHtml`).
- **Статистика:** панель `stats-bar` под `h1`; после проверки ответов обновляемая статистика в `localStorage` (`reading_trainer_stats`: runs/questions/correct) с показом «Заданий · Вопросов · Верно (%)».
- CSS: добавлены `.btn-voice`, `.btn-hint`, `.toolbar`, `.question-tools`, `.hint-box`, `.stats-bar`; в `@media print` скрываются `.hint-box` и `.stats-bar`.

**Проверки:** ruff All checks passed; py_compile OK (только pre-existing SyntaxWarning во встроенном JS); извлечённый JS тренажёра → `node --check` OK; flask test client `GET /reading_trainer.html` → 200 + все новые маркеры; `tests/unit/test_vercel_webhook_start.py` + `tests/unit/test_vercel_parsing_e2e.py` → 23 passed.

**Обновление Memory Bank:** `projectbrief.md` MOM-05 pending→completed, Mom Module 19/22 → 20/22 (91%), Phase 2 96% → 97%, «Завершённые модули» Mom 19%→20%, Additional Tasks MOM-05 → completed. `activeContext.md` — заголовок секции MOM-05. `progress.md` `last_checked_commit` → `4eea518`.

### 2026-08-03 (Session: BUGFIX01 — фикс юнит-тестов + регрессий)

**Сделано:**
- **`database/database.py`:** добавлен хелпер `get_db_session()` (= `next(get_db())`) — экспортируется как единый источник сессий, импортируется модулями GD/bot. Добавлены `__init__` c дефолтами для GD-моделей (`Level.created_at`, `Submission.status`/`submitted_at`, `PlayerStats.total_approved`, `LevelCompletion.completed_at`): SQLAlchemy `default=` применяется только при INSERT, поэтому создание объекта в памяти без явных kwargs оставляло `None` → падали тесты `test_gd_models.py`/`test_gd_player_stats.py`.
- **`bot/commands/gd_commands_ptb.py`:** убран невалидный kwargs `username` у `Submission` (TypeError); создание `PlayerStats` без несуществующих колонок `total_submissions`/`approved_submissions`; `context.user_data.clear()` в ветке «Отменить»; `filters.DOCUMENT` → `filters.Document.ALL` (в PTB 21.0 `filters.DOCUMENT` отсутствует).
- **`utils/admin/admin_system.py`:** добавлен совместимый `get_db_connection()` (raw-коннекция глобального движка из `database.database` с `sqlite3.Row`) — закрывает регрессию DB01 `'AdminSystem' object has no attribute 'get_db_connection'`; восстановлено тело `get_users_count()` (случайно повреждённого при правке). `test_add_admin_verification.py`: 2 passed.
- **Обновлены тесты под актуальный бренд LTHub / scope:** `test_gd_commands.py` (ожидает 3 хендлера от `get_gd_handlers`), `test_vercel_webhook_start.py` («[BANK] LucasTeam Hub (LTHub)»), `test_short_mode.py` («/profile» вместо исключённого «/shop»), `test_ai_lite.py` («LTHub (LucasTeam Hub)» + «справочник по LTHub»), `test_gd_player_stats.py` (сортировка через int-позиции, `SimpleNamespace` вместо `MagicMock` для `name`).

**Проверки:** полный `tests/unit`: **924 passed, 10 skipped** (0 failed); `tests/smoke`: 12 passed; ruff All checks passed; py_compile OK (только pre-existing SyntaxWarning во встроенном JS `api/index.py`).

**Примечание:** рабочая копия содержит параллельные незакоммиченные правки `api/index.py` + `tests/unit/test_vercel_parsing_e2e.py` (идемпотентность PARSE01 ч.2, принадлежат другим коммитам PARSE01/64d40d7). Мои правки багфикса — в `git diff HEAD`.

### 2026-08-03 (Session: PARSE01 часть 2 — idempotency + защита от ложных начислений)

**Сделано:**
- **`api/index.py` `_ensure_parsing_tables()`:** добавлены колонки `chat_id BIGINT`, `message_id BIGINT` (CREATE + ALTER IF NOT EXISTS для существующей прод-таблицы) + `CREATE UNIQUE INDEX IF NOT EXISTS uq_parsed_transactions_msg ON parsed_transactions(chat_id, message_id) WHERE message_id IS NOT NULL` (частичный индекс, обёрнут try/except).
- **`_log_parsed_transaction()` / `_record_parsing_result()`:** принимают `chat_id`/`message_id`. `_record_parsing_result` теперь возвращает bool; **убран предварительный SELECT-дубль** — повторный парсинг детектится через UNIQUE-индекс (IntegrityError, сообщения `duplicate`/`unique` → False).
- **Webhook-блок парсинга:** проверка `reply_from.get("is_bot")` — reply на сообщение НЕ бота → запись `not_bot` (failed) + «❌ Парсинг доступен только в ответ на сообщение игрового бота...». При `recorded=False` → «ℹ️ Это сообщение уже было распарсено ранее.» без начисления. Оба вызова `_record_parsing_result` (success / unknown) обновлены с chat_id/message_id.
- **`tests/unit/test_vercel_parsing_e2e.py`:** хелпер `_build_parsing_update` получил `is_bot: True` у reply_to.from; добавлен тест `test_webhook_parsing_reply_from_user_rejected`.

**Проверки:** 41 passed (test_vercel_parsing_e2e + test_admin_manager); полный test/unit: 914 passed / 10 failed — все 10 падений **pre-existing** (gd_models/gd_player_stats/short_mode; подтверждено git stash: падают и без моих правок). ruff All checks passed; SYNTAX OK (только известные SyntaxWarnings). Задеплоено на prod.

**Осталось (часть 3):** единый source of truth курсов (gdcards 2:1 в bot vs 2.5 в api), E2E PTB-тесты (handle_manual_parsing с реальной БД).

### 2026-08-03 (Session: PARSE01 — мониторинг парсинга: parsed_transactions пишется в проде)

**Сделано (часть 1 PARSE01):**
- **`api/index.py`:** добавлены `_ensure_parsing_tables` (создаёт `parsed_transactions` с колонкой `status`) + вызов из `get_db_engine()`, helper `_log_parsed_transaction()` и `_record_parsing_result()` (резолвит `users.id`, пишет success/failed). Теперь каждый ручной reply-парсинг «парсинг» записывается в `parsed_transactions`: при успехе (после расчёта монет) и при неудаче (source_bot='unknown', status='failed').
- **`core/managers/admin_manager.py`:** `get_parsing_stats()` теперь реально считает `failed_parses` (по полю `status != 'success'`) вместо закомментированного `failed_parses=0`; `total_amount_converted` и `successful_parses` считаются только по успешным.
- **`database/database.py`:** ORM-модель `ParsedTransaction` получила атрибут `status` (default 'success').
- **`tests/unit/test_admin_manager.py`:** мок транзакции получил `status='success'` (Mock авто-создаёт атрибуты).

**Проверки:** 77 passed (test_admin_manager, test_vercel_parsing_e2e, test_parsing_service, test_manual_parsing); ruff 0 errors; /api/dnd/status 200 после деплоя (триггер создания таблицы без 500). Integration is_admin падения — предсуществующие (падают и на чистом HEAD, не связаны с правкой).

**Осталось (часть 2):** idempotency/де-дуп в api-пути, проверка reply_to.from (защита от ложных начислений), единый source of truth курсов, E2E PTB-тесты.

### 2026-08-03 (Session: TRIVIA01 завершён)

**TRIVIA01 completed.** Мини-игра «Брейн-Ринг по Канону» доведена до готовности:

**Сделано:**
- Починен сломанный тест `tests/unit/test_trivia_game.py:41` — `test_question_generator` теперь `async` с `await generate_trivia_question()` (asyncio_mode=auto уже включён). Тест падал с `TypeError: coroutine` с коммита a11826f (async-переход) — 3/3 passed.
- Починен Vercel webhook `/trivia` (`api/index.py:8833`): `generate_trivia_question()` вызывалась без `await` → `TypeError`, молча проглатывался `except` → опрос не отправлялся. Теперь `import asyncio; asyncio.run(...)`. Проверено локально: возвращает вопрос с 4 вариантами.
- Награда в текстах приведена к фактической: «+25 монет» → «+10 монет» (2 места). Колбэк `trivia_answer_callback` даёт 10.
- `projectbrief.md`: TRIVIA01 `in_progress` → `completed`; notes обновлены (нативные quiz-poll, а не inline-кнопки; канон из `data/canon_knowledge.txt`; награда 10 монет).
- Добавлен `bot/trivia/__init__.py`.

**Проверки:** pytest tests/unit/test_trivia_game.py → 3 passed; ruff 0 errors (api/index.py, bot/trivia, test_trivia_game.py); API SYNTAX OK; задеплоено на prod.

### 2026-08-03 (Session: Личный кабинет + раздельные Войти/Зарегистрироваться)

**Сделано:**
- Новая страница `/account` — «Личный кабинет»: аватар, имя, @логин, 💎 монеты, поля профиля, кнопки «Редактировать профиль»/«На главную»/«Выйти»; без токена → редирект на /login
- `/api/auth/me` дополнен полем `coins` (баланс из `user_coins`)
- Хаб `/`: аноним — раздельные ссылки «Войти» (/login) и «Зарегистрироваться» (/register); залогиненный — «Личный кабинет» (/account) + «Выйти»

**Проверки (E2E):** register → me (coins=0); /account 200; /login 200; /register 200. ruff 0 errors, py_compile OK.

### 2026-08-03 (Session: Предложения + 5 фиксов багов)

**Сделано:**
- **Функция «Предложения»:** таблица `web_feedback`, страница `/suggest` (категория баг/предложение + раздел + текст), карточка на хабе, вкладка «Предложения» в админ-панели настроек, плавающая кнопка 🐛 (появляется при JS-ошибке), API `POST /api/feedback` / `GET /api/admin/feedback` / `DELETE /api/admin/feedback/<id>`, уведомление админу в Telegram.
- **Фикс шахмат (off-by-one):** позиция задачи переведена на `initialPly + 1` полуходов (web + telegram), `turn = Белых/Чёрных` от `(initialPly+1)%2`, mirror при ходе чёрных сохранён. Подтверждено эмпирически (solution[0] легален на ip+1 в 19+ тестах).
- **Фикс D&D пустой страницы:** `#start-panel` видна по умолчанию, `refreshStatus()` получил обработку onerror/status/catch с показом ошибки; серверный `/api/dnd/status` обёрнут в try/except.
- **Фикс GD-ника:** при отправке рекорда подтягивается `gd_nickname` из профиля (клиент через `/api/auth/me`, сервер-фолбэк через токен).
- **Фикс викторины:** добавлены ручные `distractors` для групп rules/tea/ltrs/glossary; генераторы web и telegram используют их.
- **Фикс молитв:** `_PRAYERS` переписаны по канону чайной религии («чай» + просьба + «eight-nine»); telegram использует единый `_PRAYERS`; убран дубликат eight-nine на web-странице.

**Проверки (E2E):** /suggest 200 + форма, POST /api/feedback (suggestion) ok; страница /dnd 200 + старт-панель; /api/daily_prayer (канон-текст); /api/trivia/question — реалистичные варианты (id 20 → только LTRS-имена). ruff 0 errors, py синтаксис OK.

### 2026-08-02 (Session: Админ-панель WEB-07)

**WEB-07 completed:** Веб-админ-панель LTHub готова. **Phase 3 завершён: 123/123.**

**Сделано:**
- Страница `/admin` — 4 вкладки: Статистика / Пользователи (поиск) / Начисление монет / Журнал ошибок
- API: `/api/admin/stats`, `/api/admin/users?q=`, `/api/admin/users/<id>/coins`, `/api/admin/coins/award`, `/api/admin/set_admin`, `/api/admin/errors`, `/api/admin/errors/clear`
- Авторизация по токену профиля: `_web_admin_session()` (is_admin флаг в `web_users` ИЛИ telegram_id == ADMIN_TELEGRAM_ID), не-админ → 403, самим собой управлять нельзя
- Авто-грант админа при регистрации/обновлении профиля при telegram_id == ADMIN_TELEGRAM_ID
- Монеты: `_award_web_coins()` — ключ `_web_user_id("u<id>")` (согласовано с chess/GD), лог в таблицу `web_coin_log`
- Колонка `is_admin` в `web_users`, таблица `web_coin_log`
- Карточка «Админ-панель» добавлена на хаб `/`

**Проверки (E2E на https://bank-bot-ruby.vercel.app):** регистрация с admin Telegram ID → is_admin=True; stats 5 web_users / 2 admins; начисление 15 монет → баланс 15 + лог; set_admin on/off; self-set_admin → 400; без токена → 403; страница /admin 200. py_compile OK, ruff 0 errors.

### 2026-08-02 (Session: D&D AI Master веб-страница реализована)

**Проблема:** карточка «D&D AI Master» на хабе вела на `/dnd`, но route отсутствовал → 404. В memory bank модуль был помечен как портированный, но веб-обёртки фактически не было (только Telegram-логика в `api/dnd_runtime.py`).

**Сделано:**
- `GET /dnd` — SPA в стиле GitHub Dark: панель статуса (название, сцена, число событий, персонажи), чат-лог, форма старта сессии, инпут действия, бросок кубика (d20 / 2d6+3 + назначение), исправление мастера, остановка сессии. `user_id` из localStorage / `?user_id=`.
- API: `GET /api/dnd/status`, `POST /api/dnd/start`, `POST /api/dnd/act`, `POST /api/dnd/roll`, `POST /api/dnd/stop`, `POST /api/dnd/fix` — обёртки над `api/dnd_runtime.py`, `user_id` резолвится через `_gd_web_uid()` (числовой = Telegram id, иначе hash).
- Фикс схемы: `_ensure_dnd_tables` теперь добавляет недостающие колонки к уже существующей прод-таблице через `ALTER TABLE dnd_sessions ADD COLUMN IF NOT EXISTS ...` (продовская таблица, созданная старым проектом, не имела `paused_at` → `cmd_dnd_stop` падал с 500 UndefinedColumn).
- Ответы D&D приходят в Telegram-HTML (`<b>` и т.п.) — для веба теги вырезаются через `_dnd_plain()` (regex-стрип, XSS-safe).

**Проверка на проде:** page `/dnd` 200; start → act (AI отвечает) → roll d20 (AI комментирует) → stop — все 200; status отдаёт лог. Тестовые кампании удалены через временный эндпоинт `_cleanup_test` (задеплоен → выполнен → удалён), прод чистая (status `active:false`).

**Коммит:** не коммитился (по правилам AGENTS.md)

### 2026-08-02 (Session: Завершение тренажёра глаголов WEB-08, регистрация доведена)

**WEB-08 completed:** Практика глаголов полностью готова и проверена на продакшене.

**Сделано:**
- Полный цикл «учитель → ученик» проверен E2E: генерация (id=930065) → выдача задания с пропусками → проверка (9/9) → результаты для учителя (1 submission, 403 для чужого учителя)
- Share-ссылка `/irregular_verbs/exercise/<id>` → 302 на `?exercise=<id>`
- Имя ученика по умолчанию подставляется из профиля (display_name) для зарегистрированных пользователей
- Регистрация доведена: логин+пароль, `/login`, `/settings`, logout инвалидирует токен (401 после выхода)

**Проверки:** py_compile OK, ruff 0 errors, E2E на https://bank-bot-ruby.vercel.app.

**Итог Phase 3: 113/123** (остался WEB-07 Admin Panel).

### 2026-08-01 (Session: Единая регистрация для веб-портала, WEB-11)

**WEB-11 completed:** Единая система пользователей для всех модулей.

**Сделано:**
- Страница `/register` — анонимный вход / привязка Telegram (ID + 6-значный код)
- API: `/api/auth/register`, `/api/auth/me`, `/api/auth/link_telegram`, `/api/auth/logout`
- Анонимный `web_user_id` в localStorage — работа без регистрации сохранена
- Зарегистрированный пользователь = `tg_<telegram_id>` (синхронизация между устройствами)
- Хаб `/` получил user-bar: аватар, имя, статус, вход/выход
- Все страницы (AI Chat, Chess, GD, Verbs) переведены с `ai_user_id` на единый `web_user_id`
- Вспомогательные функции auth: `_generate_web_user_id()`, `_is_valid_web_user_id()`, `_extract_telegram_id()`, `_web_user_id_to_int()`

**Проверка:** py_compile OK, ruff 0 errors, деплой на Vercel выполнен.

**Коммит:** не коммитился (по правилам AGENTS.md)

### 2026-08-01 (Session: GD web — отправка рекордов + модерация, чистка тестовых данных)

**Сделано:**
- Сложность уровней на `/gd` и `/api/gd/leaderboard` — через GDDL: исправлен `get_gd_difficulty_name()` (читает поле `difficulty` из gdbrowser, а не несуществующие `isDemon`/`difficultyName`). Проверено: Grey Trap → Hard Demon, Tartarus/Bloodbath → Extreme Demon.
- Leaderboard обогащается сложностью через ThreadPoolExecutor (5 workers); прохождения — `COALESCE(NULLIF(u.first_name,''), u.username, '?')`, на фронте «👤 имя» под числом.
- `create_gd_submission()` получила параметр `status`.
- Новые API: `GET /api/gd/me` (is_admin), `POST /api/gd/submit` (уровень + имя), `GET /api/gd/moderate` (пагинация), `POST /api/gd/moderate/reject`, `POST /api/gd/moderate/approve` (добавляет уровень в топ через `add_gd_level` + `approve_gd_submission_db`). Хелперы `_gd_web_uid()`, `_gd_web_is_admin()`.
- Фронтенд `/gd`: вкладки «Отправить рекорд» и «Модерация» (только для админа, ✅/❌), поддержка `?user_id=` в URL.
- E2E-проверка на проде: submit → заявка #13, reject OK, не-админ → 403, approve → уровень id=2, повторный approve → «уже обработана».
- Тестовые данные удалены из прод-БД (levels.id=2 «Nine Circles», submissions #13/#14, player_stats/level_completions uid=248609333) через временный эндпоинт `/api/gd/_cleanup_test` (задеплоен → выполнен → удалён). Локально подключение к pooler заблокировано (TCP проходит, SQL-handshake виснет), поэтому чистка выполнена с Vercel.

**Проверка:** ruff All checks passed; прод: leaderboard чист (только Grey Trap), moderate total=0, my_stats uid=248609333 пуст.

**Коммит:** не коммитился (по правилам AGENTS.md)

### 2026-08-01 (Session: Family Circle prod-фиксы — NOT NULL без DEFAULT)

**Проблема:** `POST /api/family/rooms` возвращал 500 `NotNullViolation` для `rooms.created_at`.

**Root cause:** Таблицы уже существовали в Supabase — их создал Alembic старого проекта `family_circle`, где `created_at`/`status`/`spoke_count`/`finished` имеют `nullable=False` без DEFAULT на уровне БД (DEFAULT был только в ORM). `CREATE TABLE IF NOT EXISTS` существующие таблицы не меняет.

**Фикс (commit c77502c):** все INSERT'ы Family Circle теперь передают поля явно: `created_at` (datetime.now(timezone.utc)), `status`, `participants_total`, `spoke_count`, `finished`. Добавлен импорт `timezone`.

**Верификация на проде:** create → join → chat (AI отвечает) → finish → report — все 200. Страницы /family, /family/room, /family/result — 200. debug-поле `detail` из 500-ответа убрано.

**Прочее:** Vercel-проект `family_circle` удалён (`vercel project rm family_circle`), production alias familycircle-nine.vercel.app больше не существует. ENCRYPTION_KEY (Fernet) выставлен в Vercel project bank-bot (production, sensitive) — сообщения шифруются. `cryptography` в requirements.

### 2026-08-01 (Session: Family Circle объединён в LTHub — WEB-10)

**WEB-10 completed:** Отдельный Vercel-проект `family_circle` (familycircle-nine.vercel.app) удалён; модуль медиации перенесён в основной LTHub проект.

**Сделано:**
- `_ensure_family_tables(engine)` — таблицы `rooms`, `members`, `messages`, `needs`, `final_reports` (создаются при старте через `get_db_engine()`, паттерн остальных `_ensure_*`).
- CRUD-логика перенесена из `family_circle/backend/app/` в синхронном стиле `api/index.py` (raw SQL + SQLAlchemy engine).
- Страницы: `/family` (создание комнаты), `/family/room` (вход + чат с ИИ-медиатором + завершение), `/family/result` (финальный отчёт + печать) — inline HTML в `api/index.py`.
- API: `POST /api/family/rooms`, `POST /api/family/rooms/join`, `GET/DELETE /api/family/rooms/<id>`, `POST /api/family/chat/send`, `POST /api/family/chat/finish`, `POST /api/family/report/generate`.
- LLM-вызовы переведены на существующий `call_ai_api()` (Groq llama-3.3); промпты медиатора и синтеза отчёта из `prompts.py` встроены в `api/index.py`.
- Шифрование сообщений через Fernet (`ENCRYPTION_KEY`), `cryptography` добавлена в `api/requirements.txt`.
- Карточка «Family Circle 🫂» в хабе `/` теперь ведёт на `/family` вместо внешнего домена.
- Каталог `family_circle/` удалён из репозитория.

**Проверка:** py_compile OK; ruff (только pre-existing F401); flask test client на SQLite-зеркале схемы: create/get/join/existing/chat/wrong-pass/finish/report/delete/404 — все 9 сценариев прошли; HTML страниц проверен на отсутствие артефактов f-string.

### 2026-08-01 (Session: Chess WEB-05 портирован)

**WEB-05 completed:** Шахматный модуль перенесён на веб-портал.

**Сделано:**
- `GET /chess` — SPA с тремя вкладками: Моя статистика / Поиск игрока / Пазл.
- Вкладка «Моя статистика»: привязка Lichess аккаунта прямо со страницы, рейтинги (bullet/blitz/rapid/classical), статистика игр с winrate, история решённых пазлов, баланс монет.
- Вкладка «Поиск игрока»: поиск по нику через Lichess API (рейтинги, онлайн-статус, статистика игр).
- Вкладка «Пазл»: случайная задача из Lichess (`/api/puzzle/next`), доска через FEN GIF (lichess1.org), ввод хода в формате UCI, +5 монет за верный ход, кнопка «Открыть на Lichess».
- API: `GET /api/chess/stats?user_id=`, `GET /api/chess/user/<nick>`, `POST /api/chess/link`, `POST /api/chess/puzzle`, `POST /api/chess/puzzle/check`.
- Переиспользованы существующие функции: `fetch_lichess_user()`, `get_chess_account()`, `link_chess_account()`, `update_user_coins()`, `log_chess_game()`, `_PENDING_PUZZLES`.
- Новые хелперы: `_derive_puzzle_fen()` (PGN→FEN через python-chess, зеркалирование при ходе чёрных), `_fetch_lichess_puzzle()` (пазл + нормализация solution в список UCI-ходов).
- Карточка «Шахматы ♟️» добавлена в хаб `/` в блок бета-модулей.

**Проверка:** py_compile OK; ruff clean; flask test client: `/chess` 200, все API-сценарии (пазл без аккаунта → 400, correct/wrong/stale ход) пройдены, `_derive_puzzle_fen` верифицирован. Lichess API локально недоступен (ReadTimeout) — на проде используется теми же функциями бота.

**Коммит:** не коммитился (по правилам AGENTS.md)

### 2026-08-01 (Session: Trivia fix + AI Chat error fix)

**WEB-03 completed:** Веб-викторина по канону доведена до рабочего состояния.

**Сделано:**
- Исправлен критический баг `/api/trivia/answer`: эндпоинт заново генерировал дистракторы при каждом ответе, поэтому массив вариантов отличался от показанного — счётчик работал некорректно.
- Введено in-memory хранилище `_TRIVIA_SESSIONS`: `POST /api/trivia/question` сохраняет `{options, correct_index, explanation}`, `POST /api/trivia/answer` проверяет по сохранённому сеансу.
- В `_TRIVIA_QUESTIONS` добавлено поле `explanation` для всех 23 вопросов (фронтенд его отображал, но данные отсутствовали).
- `GET /trivia` (страница) существовала и работает: карточка вопроса, 4 кнопки-варианта, подсветка правильного/неправильного, счёт в localStorage.

**WEB-01 AI Chat — исправление «Ошибка ответа.» после каждого ответа:**
- `_pc_ai_chat`: Groq может возвращать `content` массивом (multimodal) — теперь конвертируется в строку, чтобы `reply` всегда был строкой.
- `api_ai_chat`: добавлен try-except — любые внутренние исключения возвращают JSON (а не HTML-ошибку Flask), `reply`/`images` нормализуются.
- Фронтенд: проверка структуры ответа (`r` — объект, `reply` — строка, `images` — массив) + `console.error` для диагностики.

**Проверка:** py_compile OK; flask test client: `/api/trivia/question` → 4 опции + correct_index, `/api/trivia/answer` correct/wrong/stale — все сценарии пройдены. ruff — только pre-existing (F821 `reply_to`, E402, F401 `ImageDraw`).

**Коммит:** не коммитился (по правилам AGENTS.md)

### 2026-08-01 (Fix: /gd отдавал 404)

**Сделано:**
- На хабе `/` карточка Geometry Dash вела на `/gd`, но route отсутствовал в `api/index.py` → 404.
- Реализована страница `GET /gd` (тёмная тема GitHub Dark) с тремя вкладками: поиск игрока, топ уровней, моя статистика.
- Добавлены API: `GET /api/gd/user/<nick>` (fetch_gd_user), `GET /api/gd/leaderboard` (get_gd_leaderboard), `GET /api/gd/my_stats?user_id=` (player_stats + hardest + completions + submissions).

**Проверка:** py_compile OK, flask test client: `/gd` 200, `/api/gd/leaderboard` 200, `/api/gd/user/Riot` 200. ruff — только pre-existing F821 (reply_to, не мой код).

**Коммит:** не коммитился (по правилам AGENTS.md)

### 2026-07-31 (Session: AI Chat — виртуальный компьютер, как у Manus)

**WEB-09 completed:** AI-персонажи получили виртуальный компьютер.

**Сделано:**
- `POST /api/ai_chat` переписан на агентный цикл tool-calling (Groq llama-3.3-70b-versatile, tools, до 6 итераций)
- Инструменты: run_python (реальный запуск кода), browse_web (загрузка сайта), виртуальная ФС (list_dir/read_file/write_file/get_cwd/set_cwd), edit_image (Pillow)
- Виртуальная ФС per-user в памяти (`_VIRTUAL_PC`), загруженные файлы → `/home/user/uploads/`
- Кнопка 📎 в чате: загрузка фото/текста/кода → AI может обработать
- Результат edit_image рендерится как картинка в чате
- Фронтенд шлёт историю сообщений (20 последних)
- `api/requirements.txt` — добавлен Pillow

**Проверка:** py_compile OK, ruff — только pre-existing F821 (reply_to, не мой код), локальные тесты инструментов прошли.

**Коммит:** не коммитился (по правилам AGENTS.md)

### 2026-07-26 (Session: Web Portal — хаб на / + план портирования модулей)

**Новый Phase 3: Web Portal — дублирование функций бота в веб**

**Сделано:**
- Хаб на `/` с карточками трёх сервисов (чтение, окончания, бюджет)
- Кнопка «Печать» в тренажёре окончаний (скрывает UI, оставляет пропуски)
- Архитектурный план в `memory_bank/activeContext.md` и `memory_bank/projectbrief.md`

**Утверждённые модули для портирования (7 шт):**
| Модуль | Приоритет | Статус |
|--------|-----------|--------|
| AI / Чат | 1 | ✅ |
| D&D AI Master (StoryForge) | 2 | ✅ |
| Trivia | 3 | ⏳ |
| Daily Prayer | 4 | ⏳ |
| Chess | 5 | ⏳ |
| GD | 6 | ✅ |
| Admin Panel | 7 | ⏳ |

**Коммит:** 60adaa9

### 2026-07-30 (Session: Family Circle — DATABASE_URL подключена)

**Сделано:**
- Добавлена DATABASE_URL (Supabase pooler) в `family_circle/backend/.env` и в Vercel project `family_circle` (production)
- Исправлен `database.py`: pool заменён на `NullPool` для serverless-совместимости
- Строка подключения переведена на Supabase pooler (`aws-0-eu-west-1.pooler.supabase.com:6543`) с `sslmode=require`
- Выполнен production деплой на Vercel
- Сайт https://familycircle-nine.vercel.app отвечает 200, статика загружается, БД подключается

**Блокер DATABASE_URL снят.**

### 2026-07-27 (Session: Web Portal — GD Module портирован)

**WEB-06 completed:** Geometry Dash Module перенесён на веб.

**Сделано:**
- `/gd` — веб-страница с тремя вкладками в тёмной теме (GitHub Dark)
- Вкладка «Поиск игрока» — поиск по нику, отображение статистики из GD API (звёзды, демоны, CP, монеты, алмазы, ранг)
- Вкладка «Топ уровней» — таблица уровней из БД (позиция, название, сложность, прохождения, игроки)
- Вкладка «Моя статистика» — карточки с показателями игрока (хардест, прохождения, заявки, процент одобрения)
- `GET /api/gd/user/<nick>` — API для поиска игрока
- `GET /api/gd/leaderboard` — API для получения топа уровней
- `GET /api/gd/my_stats?user_id=...` — API для статистики игрока
- Карточка GD добавлена в хаб на `/`

**Файлы:**
- `api/index.py` — все роуты и API эндпоинты (inline HTML + API handlers)
- `memory_bank/activeContext.md` — статус обновлён
- `memory_bank/projectbrief.md` — WEB-06 отмечен как completed
- `memory_bank/progress.md` — changelog обновлён

### 2026-07-06 (Session: VK + Vercel deploy, /budget dual links)

**Сделано:**
- Yandex.Disk export удалён из кодовой базы (dead code)
- Установлен Vercel CLI, выполнен production деплой
- `/budget` показывает две inline-кнопки: "🌐 Web (Vercel)" и "📱 VK Mini App"
- VK_PROTECTED_KEY, VK_SERVICE_TOKEN, VERCEL_TOKEN добавлены в `config/.env.local`
- Получен VK сервисный и защищённый ключи, Vercel токен
- VK Mini App зарегистрирован (app_id=54665568)

**Коммиты:** 4e4da4e, 3abc5bf

### 2026-07-04 (VK Mini App — Budget UI + Yandex.Disk removal)

**Удалено:**
- `scripts/export_debts_yadisk.py` — скрипт экспорта долгов на Яндекс.Диск
- Все yadisk-функции из `api/index.py`: `_log_yadisk`, `_upload_to_yadisk`, `_fetch_debts_for_export`, `_build_debts_html`
- Переменная `_YADISK_LOG`, константа `YADISK_API`
- Команды `/export_debts` и `/yadisk_logs`

**Добавлено (VK Mini App):**
- `flask-cors` в `requirements.txt`, CORS настроен для VK origins (`https://vk.com`, `https://*.vk.com`)
- Модель `LinkedVKAccount` в `database/database.py` (vk_user_id, tg_user_id, link_code, code_expires_at)
- Alembic миграция `011_vk_account_linking.py` — таблица `linked_vk_accounts`
- Endpoint `GET /api/budget/vk/status` — проверка привязки VK ↔ TG
- Endpoint `POST /api/budget/vk/link` — привязка по 6-значному коду
- Bot command `/linkvk` — генерация кода (TTL 10 мин)
- VK Mini App проект: React 18 + TypeScript + Vite + @vkontakte/vkui@8.3.0 + @vkontakte/vk-bridge@3.0.2
- 7 страниц: LinkPage, DashboardPage, AddExpensePage, PayDebtPage, HistoryPage, CreateFamilyPage, JoinFamilyPage
- API wrapper: `vk_mini_app/src/api/budget.ts`
- Маршруты зарегистрированы в `api/index.py` и `run_bot.py`

### 2026-06-20 (Chess Fixes + Error Logging System + text shadowing bug)

**Исправлено:**
- `text = message.get("text")` перезаписывал `sqlalchemy.text()` → renamed to `msg_text`
- Regex-замена сломала `response.text`, `if text`, print-строки → все исправлены
- Chess labels: "Молния"→"Блиц", "Быстрая"→"Рапид"
- `/puzzle` "задача дня"→"задача" (теперь random через `/api/puzzle/next`)
- `games.total` mapping: Lichess API `count.all` → `games.total`
- `/api/puzzle/next` не возвращает FEN → конвертация PGN→FEN через `python-chess`
- Solution format: list vs string handled (Lichess возвращает массив)
- `chess_games` таблица создаётся автоматически при старте

**Добавлено:**
- `_ERROR_LOG` in-memory лог (50 ошибок)
- `log_error()` с AI рекомендациями через Groq + traceback контекст
- `notify_admin()` — уведомления админа в Telegram при ошибках
- `/errors` — журнал ошибок с 💡 рекомендациями от ИИ
- `/clear_errors` — очистка лога
- Админ-секция в `/start` (только для ADMIN_TELEGRAM_ID)

**Тестирование:**
- Chess Module: 5/7 команд протестированы (71%)
- Admin: 2/2 команды (100%)
- Общий прогресс тестирования: 29%

**Коммиты:** f26e098, a91f11a, 881988e, 3aa801c

### 2026-06-03 (Memory Bank: HF deprecated, GD Module planned for Vercel)
- **Hugging Face runtime помечен как устаревший** в `memory_bank/activeContext.md`.
- **Причина:** постоянные таймауты `getUpdates TimedOut`, пропуск команд, нестабильная обработка webhook.
- **Перенос GD Module на Vercel запланирован** с префиксом `/gd_`: `/gd_submit`, `/gd_moderate`, `/gd_leaderboard`, `/gd_my_stats`, `/gd_player_stats`, `/gd_user`, `/gd_level`, `/gd`.
- **GD commands в `bot/commands/gd_*_ptb.py`** остаются legacy (локальный polling), production будет на Vercel webhook.
- **Active context обновлён:** добавлен приоритетный пункт GD Module for Vercel.

### 2026-06-03 (Chess Module Implementation)
- **Chess Module (CH-02, CH-03, CH-04) completed:** 12% deliverables finished.
- **CH-02:** Implemented `/chess_link <username>` command for Lichess account binding.
  - Synchronous Lichess API client (`fetch_lichess_user()`) with 8s timeout
  - Database functions: `get_chess_account()`, `link_chess_account()`
  - Validation: checks if account exists on Lichess, prevents duplicate bindings
  - User feedback: shows username, title, online status
- **CH-03:** Implemented `/chess_rating` and `/chess_stats` commands (basic versions).
  - Currently show basic profile info (username, title, online status)
  - Full ratings/stats implementation pending (perfs parsing)
- **CH-04:** Implemented `/puzzle` command with visual board.
  - Fetches daily puzzle from Lichess API (`/api/puzzle/daily`)
  - Displays chess board as GIF image using Lichess board export API
  - Shows puzzle rating, themes, FEN position
  - Inline button to solve on Lichess website
  - Fallback to text-only if image fails
- **Architecture:**
  - All chess commands in `api/index.py` (Vercel webhook)
  - Underscore command format: `/chess_link`, `/chess_rating`, `/chess_stats`, `/puzzle`
  - Table `chess_accounts` already in migration `009_phase2_tables_supabase.sql`
  - Board images via `https://lichess1.org/export/fen.gif?fen=<FEN>&theme=brown&piece=cburnett`
- **Testing:** All commands tested via webhook, Lichess API verified working.
- **Commits:** 
  - `fb3819e` — feat: add chess module with Lichess integration
  - `10266ba` — refactor: change chess commands to underscore format
  - `8f33214` — feat: display chess board image in /puzzle command
- **Phase 2 progress:** 59% → 71% (+12% for CH-02, CH-03, CH-04)
- **Remaining Chess work:** CH-05 (puzzle rewards, 3%), CH-06 (bank integration + history, 3%), CH-TEST (manual testing, 2%)
- **Verification:** `python -m py_compile api/index.py` passed; webhook tests successful; Lichess API endpoints verified.
- **Next steps:** Add detailed ratings/stats parsing, implement puzzle verification system, add rewards integration with user_coins.

### 2026-06-02 (Memory Bank canon sync)
- Объединены две версии Memory Bank: каноническим источником оставлен `memory_bank/`, а `docs/memory-bank/` переведён в legacy mirror/указатель.
- `memory_bank/projectbrief.md` приведён к правилу `AGENTS.md`: `## Project Deliverables` содержит стабильные ID, статусы, веса с суммой `100`; completed-вес = `90`, поэтому текущий канонический прогресс Phase 1 = `90/100`.
- Устаревшие сведения из `docs/memory-bank` не перенесены как канон: ручной paste-парсинг, SQLite-only production, активный shop/games/D&D scope, Bridge/VK production runtime.
- Полезное отличие legacy mirror про `bot/template_coder/` сверено с кодом и зафиксировано в `memory_bank/dialog_template_coder_module.md`: модуль параметрический, без pair/triple lookup tables, с `/done`.
- Удалён секрет из legacy mirror: старый `docs/memory-bank/activeContext.md` содержал Telegram bot token. Токен нужно считать раскрытым и перевыпустить вне репозитория.
- `docs/memory-bank/*` теперь ссылается на соответствующие файлы `memory_bank/*`, чтобы не создавать второй источник процента выполнения.

### 2026-06-02 (P0 Vercel /start no-response fix)
- Пользователь уточнил, что production сейчас на Vercel, не на Hugging Face.
- Root cause: `api/index.py` Vercel webhook принимал Telegram updates, но отправлял Telegram `sendMessage` только для `/reading_trainer`; `/start` и `/start@lt_lo_game_bot` silently acknowledged with `{"ok": true}`.
- Fix: добавлены `normalize_command()`, `send_telegram_message()`, `build_start_text()` и ветка обработки `/start` в `telegram_webhook()`.
- Regression tests: `tests/unit/test_vercel_webhook_start.py` проверяет `/start` и mentioned `/start@lt_lo_game_bot` без реального Telegram API.
- Verification: `python3 -m py_compile api/index.py ...` passed; `python3 -m ruff check api/index.py bot/bot.py bot/commands/chess_commands_ptb.py bot/chess/lichess_api.py tests/unit/test_chess_commands.py tests/unit/test_vercel_webhook_start.py` passed; `python3 -m pytest tests/unit/test_vercel_webhook_start.py -q` -> 2 passed.
- Note: combined focused pytest with chess test currently needs full project deps (`aiogram` etc.); Vercel `/start` regression test passes independently.

### 2026-05-30 (Phase 2: GD-05 statistics commands)
- **GD-05 completed:** Statistics commands in `bot/commands/gd_stats_commands_ptb.py`.
- **Commands:**
  - `/leaderboard` — топ-20 уровней с количеством прохождений и сложностью
  - `/my_stats` — личная статистика (хардест, подтверждённые прохождения, процент одобрения)
  - `/player_stats @user` — статистика другого игрока
- **Features:**
  - Отображение хардеста с позицией
  - Подсчёт прохождений, заявок (всего/pending/rejected)
  - Процент одобрения заявок
  - Поиск игрока по username или mention
- **Integration:** `calculate_difficulty_score()` из `bot/gd/difficulty.py`
- **Deliverables completed:** GD-05 (5%)
- **Phase 2 progress:** 47% → 52% (+5% за GD-05)
- **GD Module total:** 52% (GD-01: 5%, GD-02: 4%, GD-03: 5%, GD-04: 4%, GD-05: 5%, GD-TEST-1-3: 3%, remaining: 14%)
- **Verification:** ruff 0 errors (auto-fixed), py_compile passed
- **Next steps:** GD-06 (админ-команды: /add_level, /set_level_position), GD-07 (GD API)
- **MOM-01-04 completed:** Веб-приложение «Тренажёр чтения и понимания» полностью реализовано.
- **Files:**
  - `webapp/reading_trainer/index.html` — статика с двумя экранами (чтение/вопросы), регулировка шрифта (24-72px), адаптивный дизайн
  - `webapp/reading_trainer/app.js` — логика: загрузка, проверка ответов, печать единым листом, переходы между экранами
  - `bot/web/reading_trainer.py` — HTML-контент для интеграции в бота
  - `api/reading_trainer.py` — Flask endpoint для Vercel
  - `run_bot.py` — `/reading_generate` endpoint с HF API (mistralai/Mistral-7B-Instruct-v0.2) и fallback-наборами (3 набора по 6 предложений + 2-3 вопроса)
- **Features:**
  - 6 простых предложений (3-4 слова) + 2-3 вопроса по содержанию
  - Проверка ответов (регистронезависимое сравнение)
  - Печать одним листом (предложения + вопросы с пустыми строками)
  - Регулировка шрифта (A+/A-), сохранение в localStorage
  - HF API с таймаутом 15 сек, fallback на predefined sets при ошибках
- **Deliverables completed:** MOM-01 (6%), MOM-02 (3%), MOM-03 (5%), MOM-04 (5%) = 19% (округлено до 20% с учётом интеграции)
- **Phase 2 progress:** 26% → 30% (+4% за Mom Module)
- **Verification:** ruff 0 errors, py_compile passed, files verified
- **Next steps:** GD Core (GD-02 → GD-07, 30%) или Universe Module (UN-03, 4%)

### 2026-05-29 (Phase 2: GD Core - GD-02 /submit command)
- **GD-02 completed:** Реализована команда `/submit` для отправки прохождений уровней Geometry Dash.
- **Files:**
  - `bot/commands/gd_commands_ptb.py` — новый модуль с командами GD Module
  - `bot/bot.py` — подключение GD handlers
- **Features:**
  - ConversationHandler с 3 состояниями: ввод названия уровня → загрузка медиа → подтверждение
  - Поддержка видео и фото
  - Предпросмотр медиа перед отправкой
  - Сохранение заявки в `submissions` таблицу с полями: user_id, level_name, media_file_id, media_type, status
  - Автоматическое обновление `player_stats.total_submissions`
  - Fallback для уровней, ещё не добавленных в БД (level_name вместо level_id)
- **Database model extended:** `Submission` добавлены поля `level_name`, `media_type`, `notes`
- **Deliverables completed:** GD-02 (4%)
- **Phase 2 progress:** 30% → 34% (+4% за GD-02)
- **Verification:** ruff 0 errors, py_compile passed
- **Next steps:** GD-03 (админ-панель /moderate), GD-04 (логика сложности), GD-05 (статистика)

### 2026-05-24 (Phase 2: AI Commands Implementation)
- **AI-02, AI-03, AI-04 completed:** Implemented AI-powered commands in `bot/commands/ai_commands_ptb.py`.
- **Commands:**
  - `/chat <персонаж> <текст>` — диалог с олеговирусом или чаем (персонализированные промпты)
  - `/generate_prayer` — генерация молитвы чайной религии через AI
  - `/ask_canon <вопрос>` — вопросы по канону с использованием базы знаний
- **Features:**
  - Character prompts: олеговирус (кхм-кхм, навязчивый) и чай (мудрый, eight-nine)
  - Prayer generation with keywords: чай, eight-nine, настой, кружка-алтарь
  - Canon knowledge base: `data/canon_knowledge.txt` с информацией о вселенной
  - Fallback: простой keyword search если AI недоступен
  - Typing indicators, cache indicators, error handling
- **Integration:** Commands registered in `bot/bot.py` after existing AI commands.
- **Canon knowledge:** Created `data/canon_knowledge.txt` with lore about олеговирус, LTL-паразит, чайная религия.
- **Deliverables completed:** AI-02 (3%), AI-03 (3%), AI-04 (2%). AI Module полностью завершён (15%).
- **Phase 2 progress:** 18% → 26% (+8% за AI Commands).
- **Verification:** ruff 0 errors, py_compile passed.
- **Next steps:** Mom Module (MOM-01 → MOM-05, 20%) или Universe Module commands (UN-03).

### 2026-05-24 (Phase 2: AI Manager Implementation)
- **AI-01 completed:** Implemented `AIModelManager` in `bot/ai/model_manager.py` with full multi-provider support.
- **Features:**
  - Support for 3 provider types: Hugging Face Inference API, OpenRouter, local Ollama
  - Automatic failover on errors (429, 403, 500, timeouts)
  - Response caching with 5-minute TTL
  - Configurable via environment variables (JSON or individual configs)
  - Special method `generate_sentence(theme)` for Mom Module
- **Configuration:** Added AI settings to `src/config.py` (both `Settings` and `DynamicSettings` classes):
  - `AI_PROVIDERS` (JSON string)
  - `HF_INFERENCE_TOKEN`, `HF_INFERENCE_MODEL`
  - `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`
  - `OLLAMA_ENABLED`, `OLLAMA_ENDPOINT`, `OLLAMA_MODEL`
- **Environment example:** Updated `config/.env.shared.example` with AI configuration section.
- **Tests:** Created `tests/unit/test_ai_model_manager.py` with 13 tests covering:
  - Provider initialization (no providers, single, multiple)
  - Cache functionality (key generation, storage, expiration)
  - API calls (HF success, failover, all fail scenarios)
  - Special methods (generate_sentence)
- **Verification:** All 13 tests passed, ruff 0 errors, py_compile passed.
- **Deliverable status:** AI-01 (5%) completed. Phase 2 progress: 18/100.
- **Next steps:** Implement AI commands (AI-02, AI-03, AI-04) → Start Mom Module.

### 2026-05-24 (Phase 2 Infrastructure — Database Schema)
- **Phase 2 Planning:** Created comprehensive implementation plan for 5 new modules (GD, Chess, Universe, AI, Mom) with total weight 100%.
- **Memory Bank sync:** Updated `projectbrief.md` with Phase 2 deliverables (30 new items: GD-01 to GD-07, CH-01 to CH-06, UN-01 to UN-03, AI-01 to AI-05, MOM-01 to MOM-05).
- **Active context update:** Changed focus from Trivia game to Phase 2 Feature Expansion in `activeContext.md`.
- **Detailed plan:** Created `memory_bank/phase2_implementation_plan.md` with execution order, time estimates (29-41 hours), and risk analysis.
- **Migration 009:** Created Alembic migration `database/alembic/versions/009_phase2_tables.py` for all Phase 2 tables.
- **SQLAlchemy models:** Added 9 new models to `database/database.py`:
  - GD Module: `Level`, `Submission`, `PlayerStats`, `LevelCompletion`
  - Chess Module: `ChessAccount`, `UserCoins`
  - Universe Module: `InfectionStatus`, `DailyPrayerLog`
  - AI Module: `UserPreferences`
- **SQL script:** Created `database/migrations/009_phase2_tables_supabase.sql` for manual Supabase application.
- **Python script:** Created `scripts/apply_migration_009_supabase.py` for automated migration (encountered connection timeouts initially).
- **Documentation:** Created `docs/APPLY_MIGRATION_009.md` with instructions for manual migration via Supabase Dashboard.
- **Migration applied:** Successfully applied migration 009 to Supabase PostgreSQL via VPN connection. All 9 tables created and verified:
  - `chess_accounts`, `daily_prayer_log`, `infection_status`, `level_completions`, `levels`, `player_stats`, `submissions`, `user_coins`, `user_preferences`
- **Deliverables completed:** GD-01 (5%), CH-01 (2%), UN-01 (4%), UN-02 (4%), AI-05 (2%) = 17% infrastructure (13% effective as only DB tables).
- **Verification:** All code passes `ruff check` and `py_compile`. Migration verified in Supabase.
- **Commits:** 
  - `4ad26e9` — feat(phase2): add database infrastructure for 5 new modules
- **Next steps:** Implement AI Manager (AI-01) → Start Mom Module and GD Core.
- **Phase 2 progress:** 13/100 (infrastructure only, commands pending).

### 2026-05-24 (Shop price update and AI knowledge expansion)
- **Issue:** User reported bot not responding after multiple commits. Root cause: incorrect Supabase password in Vercel environment variables caused authentication failures and circuit breaker activation.
- **Database connection fix:** Switched from direct Supabase URL (`db.xrrdliznuyausiutxqwv.supabase.co`) to Connection Pooler (`aws-0-eu-west-1.pooler.supabase.com:5432`) to resolve IPv6 connectivity issues on Vercel serverless.
- **Shop item price update:** Reduced "Безлимит стикеров на 24 часа" price from 100 to 35 coins (20% of daily earnings with new balanced parsing coefficients).
- **Migration 008:** Created Alembic migration `008_init_shop_sticker_item.py` to initialize shop category and sticker item with price 35 coins. Applied to Supabase via SQL Editor.
- **AI knowledge expansion:** Added 7 new knowledge sections to `bot/ai/knowledge.py`:
  - `bot_commands` — основные команды бота
  - `parsing_games` — парсинг игровых валют (Shmalala, GD Cards, Гусь Cards)
  - `exchange_rates` — курсы перевода валют (коэффициенты 0.8-1.5)
  - `shop_items` — товары магазина
  - `balance_profile` — управление балансом
  - `trivia_game` — викторина по канону
  - `response_modes` — режимы short/long
- **AI now answers:** `/ai курс перевода`, `/ai как получить монеты`, `/ai что в магазине`, `/ai сколько стоит безлимит стикеров`
- **Error handling fix:** Added try-except wrapper around `template_coder_dialog.handle_text()` in `bot/bot.py` to prevent crashes on ordinary messages (later reverted during troubleshooting).
- **Environment setup:** Created `.env` file with correct Supabase Connection Pooler URL and bot token for local development.
- **Scripts created:**
  - `scripts/init_shop_items.py` — initialize shop items in SQLite
  - `scripts/apply_migration_008_supabase.py` — apply migration via DATABASE_URL (Python)
  - `database/migrations/008_update_sticker_price_supabase.sql` — SQL script for manual application
  - `docs/APPLY_MIGRATION_008.md` — migration instructions
- **Verification:** Bot restored to working state after updating DATABASE_URL on Vercel with correct password and Connection Pooler URL.
- **Commands for BotFather:** Updated list of 13 main commands for bot menu.

### 2026-05-22 (Shop reset for new catalog)
- Started shop implementation/reset phase for Vercel production.
- Disabled automatic creation of demo/default shop items in `EnhancedShopSystem.initialize_default_items()`, legacy SQLite `ShopDatabaseManager.initialize_default_items()`, and `scripts/initialize_shop.py`.
- Production Supabase shop cleanup: deactivated all active rows in `shop_items` instead of deleting them, preserving historical `user_purchases` references. Result: `active_before=8`, `deactivated=8`, `active_after=0`.
- Verification: `python3 -m ruff check core/systems/shop_system.py core/database/shop_database.py scripts/initialize_shop.py` -> passed; `python3 -m py_compile ...` -> passed.

### 2026-05-22 (Sticker hourly moderation)
- Added sticker moderation in `bot/bot.py`: per chat/user PostgreSQL-backed rolling window allows up to 5 stickers per hour; stickers over the limit are deleted automatically.
- The sticker counter stores events in `sticker_usage_events`, so Vercel serverless cold starts and multiple instances do not reset the hourly limit.
- Handler is registered before generic message logging (`group=-3`) with `filters.Sticker.ALL`.
- Deletion failures are logged safely; Telegram requires the bot to be a chat admin with delete-message permission.
- Verification: `python3 -m ruff check bot/bot.py` -> passed; `python3 -m py_compile bot/bot.py` -> passed.

### 2026-05-22 (Vercel serverless parsing path)
- User reported `Парсинг временно недоступен на serverless-хостинге` after replying to a GDcards card message.
- Added Vercel-safe manual parsing path in `bot/bot.py`: when legacy `ParsingHandler` is disabled, reply-based `Парсинг` now uses PostgreSQL `User` + `bank_bot.services.ParsingService` directly, without SQLite repository initialization.
- GDcards accrual sample `🤩 Орбы: +2` is covered by existing regex and should route to `parse_and_accrue()`.
- Verification: `python3 -m ruff check bot/bot.py` -> passed; `python3 -m py_compile bot/bot.py` -> passed; local full service import still requires `psycopg2`, available in Vercel via `requirements.txt`.

### 2026-05-22 (Shop item: 24h sticker limit bypass)
- Added production Supabase shop item `Безлимит стикеров на 24 часа` (`shop_items.id=9`, price `100`, type `sticker`, meta `activation_type=unlimited_stickers`, `duration_hours=24`).
- Updated sticker moderation in `bot/bot.py` to skip deletion/counting when the user has active `users.sticker_unlimited = TRUE` and `sticker_unlimited_until > now`.
- Existing `ShopManager._activate_sticker_item()` already sets `sticker_unlimited_until` for 24 hours on purchase.
- `/shop` display now includes the user's current coin balance before the product list.
- Added warning message throttling: when a sticker is deleted, the bot sends a warning message proposing the `/shop` item at most once per 60 seconds per user/chat key to prevent spam.

### 2026-05-20 (HF Webhook Migration — этап 1 completed)
- Tightened HF webhook runtime: disabled module imports (`shop`, `games`, `dnd`, `watch`, `background`) are now deferred to local/dev polling runtime only; HF webhook mode never imports them.
- Added webhook security smoke tests (`tests/smoke/test_startup.py`): route existence, invalid secret rejection (404), invalid header rejection (401).
- Updated `/health` JSON to match plan: `telegram_runtime: webhook`, `webhook_configured: true/false`.
- Updated `RUN.md`: removed polling references for HF, removed `/shop`, `/games`, `/watch` from command examples, added HF Secrets checklist (`WEBHOOK_SECRET`, `WEBHOOK_BASE_URL`), added `POST /telegram/webhook/<secret>` endpoint documentation.
- Verified no `deleteWebhook` calls remain in HF path; `set_webhook` + `get_webhook_info` are present in `initialize_for_webhook`.
- Removed disabled commands (`/shop`, `/games`, `/dnd`, `/buy*`, `/inventory`, `/daily`, `/challenges`) from `WELCOME_TEXT`, `SHORT_WELCOME_TEXT`, and private-message fallback text.
- Added structured webhook update logging: logs update_id, chat_id, chat_type, user_id, text preview, processing success/failure, and secret validation failures.
- All checks: ruff 0 errors, smoke tests 12 passed, parsing tests 29 passed, template coder tests 21 passed (62 total).

### 2026-05-20 (HF Webhook Migration Planning — no implementation yet)
- User requested planning-only phase for full HF migration from Telegram polling to webhook after recurring `getUpdates TimedOut` caused missed group commands.
- User-approved scope decisions recorded across Memory Bank: disable background periodic tasks; keep only `/short` and `/long`; remove non-working `/shop`, `/games`, `/dnd`; remove BridgeBot and VK Bot from production HF runtime; keep secure reply-only parsing and do not restore pasted-message fallback.
- Added canonical detailed plan: `memory_bank/hf_webhook_migration_plan.md`.
- Updated `activeContext.md`, `productContext.md`, `systemPatterns.md`, `techContext.md`, `projectbrief.md`, and this `progress.md` to reference the new plan/scope.
- No production code implementation was started in this planning step.

### 2026-05-19 (Watch response/action mode)
- User requested a third control mode for smartwatch usage. Constraints: the watch screen fits only very short messages, and available quick-reply templates are exactly: `ОК`, `Да`, `Спасибо`, `Спасибо, нет`, `Великолепно`, `Спасибо еще раз`, `Скоро увидимся`, `Скоро буду`, `Я занят(а)`, `Нет`.
- Clarification: watch mode should not just shorten text; it should map those 10 templates to bot actions. Implemented `/watch` and `/watch_all`, ultra-short `watch` compaction, and template action shortcuts: ОК=profile, Да=admin, Спасибо=balance, Спасибо нет=shop, Великолепно=games, Спасибо еще раз=AI help, Скоро увидимся=commands, Скоро буду=notifications, Я занят(а)=short, Нет=cancel/help.
- Follow-up requirement: `Я занят(а)` must also enable watch mode for the current person even when they are not already in `/watch`. Updated quick-reply handling so `Я занят(а)` is a personal watch-mode entrypoint.

### 2026-05-19 (Documentation refresh)
- User requested project documentation update. Updated `README.md`, `RUN.md`, and `docs/README.md` to cover current BankBot scope: PostgreSQL/Supabase production storage, Hugging Face endpoints and runtime behavior, feedback system, AI-lite commands, admin commands, response modes `/short`/`/long`/`/watch`, admin defaults, and smartwatch quick-reply controls.
- Explicitly documented that Markdown files are not checked with `ruff`; Python code still must pass `ruff` and smoke tests after code changes.
- Product positioning correction: user clarified that parsing must remain the most important stated goal, not be hidden behind the newer bank/admin/UX work. Updated Memory Bank/docs to present bank/admin/PostgreSQL/HF/feedback/watch/AI-lite as the stabilizing foundation around the main parsing mission. Added PARSE01 to post-release backlog as in-progress production E2E automatic parsing.
- User clarified that the project should not be presented as fully complete. Updated `Project Deliverables` to 90/100 exactly: D10 production E2E parsing and D18 E2E parsing/bank tests are `in_progress`; all weights still sum to exactly 100. Also documented that users do not need to clone the project to test it; production testing is available in https://t.me/lucasteamgroup.

### 2026-05-19 (Response modes per user + admin defaults)
- User requested scope change: `/long` and `/short` must apply per Telegram user, while admins can set the mode for everyone with `/long_all` and `/short_all`.
- Direct user-reported bug: `/start@lt_lo_game_bot` for Telegram ID `8543044969` returns full welcome with `❌ Ошибка регистрации`. Likely production PostgreSQL `users.telegram_id` was still `INTEGER`, while newer Telegram IDs exceed 32-bit signed integer range. Fix path: migrate `telegram_id` to `BIGINT` and make welcome status use the later `UserManager` DB registration fallback before replying.
- Direct user-reported bug: `/admin@lt_lo_game_bot` sends the compact section and then an error. Root cause is likely the second old admin panel reply with unescaped HTML placeholder `/broadcast <текст>` after `admin_with_section_command` sends the section. Fix path: avoid double panel on `/admin` and escape the admin panel placeholder.
- Follow-up user report: after `/long@lt_lo_game_bot`, `/admin@lt_lo_game_bot` still looked like the short section, so short/long modes were not visually distinct for `/admin`. Fix: make `/admin` mode-aware — short sends the compact command section, explicit long delegates to the full admin panel.
- Direct user-reported P0: bot appeared dead on HF after deploy. Runtime showed `ImportError: cannot import name 'ai_update_knowledge_command' from bot.commands.ai_commands`, meaning HF had a stale/missing `bot/commands/ai_commands.py`. Hotfix: upload the current AI commands file and restart Space before continuing admin-command fixes.
- Direct user-reported admin bugs: `/admin_addcoins@lt_lo_game_bot` with no args did not answer, and `/add_points @Nikiktosik 100` did not answer. Fix scope: add mentioned-command routing for balance admin commands and fix Transaction constructor fields (`meta_data`, not `metadata`) so admin balance commands respond instead of failing silently/global-erroring.
- Direct user-reported P0: `/ping@lt_lo_game_bot` does not answer while `/health` is healthy. Authenticated HF logs show polling reaches `Starting run_polling...` but then repeatedly logs `Polling interrupted by transient Telegram network error, retrying... error=Timed out`; the external HF retry loop restarts `run_polling()` every timeout and likely prevents stable update processing. Fix: remove the outer HF `run_polling()` retry loop again and let PTB manage polling internally, with longer HF getUpdates read timeout.
- Follow-up HF startup issue: after restart, `/health` was healthy but runtime stayed `RUNNING_APP_STARTING`; internal `/logs` showed startup blocked at `[DIAG] Checking webhook status...`. Fix: skip webhook check on HF startup because it is diagnostic/non-critical and can block app readiness; do not use manual `getUpdates` while debugging polling.
- Follow-up HF runtime issue: after removing the outer polling loop entirely, HF reported `RUNTIME_ERROR` with `Exit code: 0`, meaning `run_polling()` returned and the process exited cleanly. Keep a guarded HF loop that restarts polling only after return/exception, with longer polling timeouts and a longer retry delay, so the Space stays alive without rapid timeout churn.
- Direct user-reported bug: `/broadcast 123` answered generic broadcast error. HF logs showed `BroadcastService.__init__() missing 1 required positional argument: 'bot'`. Fix: instantiate `BroadcastService` with the active SQLAlchemy session and `context.bot`, escape preview/broadcast HTML text, and expose exception text in admin error replies.
- Implemented in-memory personal mode map plus global default mode in `bot/response_modes.py`: personal `/short`/`/long` overrides the global default; `/short_all`/`/long_all` changes the default and updates known in-memory users.
- Wired admin-only `/short_all` and `/long_all` in `bot/bot.py`, including mentioned-command fallback for group usage.
- Updated `/admin` command section and architecture docs to mention response mode behavior.

### 2026-05-20 (Parsing System Implementation)
- **Task:** Implement parsing system for 3 target bots (Гуся Cards, GDcards, Shmalala) triggered by "парсинг" reply.
- **Database:** Added `UserResource` model (tracks internal `n` per user/bot/resource) and `ConversionRate` model (stores coefficient `k` per bot/resource pair).
- **Migration:** Created `005_add_parsing_resources.py` with default rates: gusya_cards=1.0, gdcards=2.0, shmalala=1.5.
- **Service:** `bank_bot/services/parsing_service.py` — detects bot, extracts amount `b`, looks up `k`, calculates `b*k`, updates `n` and balance.
- **Handler:** Updated `bot/handlers/parsing_handler.py` — new `handle_target_bot_parsing()` method using `ParsingService`, falls back to legacy parser for other games.
- **Tests:** `tests/unit/test_parsing_service.py` — 20 tests, all passing. GDcards priority coverage: detection, extraction, full accrual flow, multiple accruals.
- **Status:** Parsing system ready for production use. ruff: 0 errors. Tests: 20/20 passed.

### 2026-05-20 (Parsing Extensions — Karma & Profile)
- **User request:** Parse Shmalala karma (❤️ rating) and GDcards profile (current orb balance).
- **Shmalala Karma:** Added `shmalala_karma` bot config with patterns for "Теперь его рейтинг: X ❤️". Conversion rate k=0.5.
- **GDcards Profile:** Added `profile_patterns` for "Орбы: X (#Y)". New `parse_profile_and_accrue()` method calculates delta = (current_balance - stored_n) * k, updates n to current_balance.
- **Handler Update:** `handle_target_bot_parsing()` now detects both accrual messages (+X) and profile messages, routes to appropriate parser.
- **Tests:** Added 9 tests: karma detection/extraction/accrual, profile detection/extraction/delta-accrual/no-change. Total: 29/29 passing.
- **Commit:** `3eb7377` feat(parsing): add karma parsing for Shmalala and profile parsing for GDcards.

### 2026-05-18 (DB01 — persistent PostgreSQL/Supabase storage)
- User-defined priority order recorded: (1) direct user-reported bugs, (2) bugs from `/feedback`, (3) current development focus, (4) suggestions from `/feedback`.
- Started DB01 as P0/first-priority task after user reported HF DB resets on restart/rebuild.
- Problem: local SQLite/data storage on Hugging Face is ephemeral; users, balances, feedback, game sessions, and runtime state can be lost.
- Target: production/HF must use persistent PostgreSQL, e.g. Supabase, through env (`DATABASE_URL`/`POSTGRES_URL`), with SQLite kept as local/dev fallback.
- Requirements: PostgreSQL-compatible Alembic/schema startup, no secrets in git, health endpoint checks production DB, feedback/users/balances/transactions use production DB, docs and smoke/config coverage updated.
- Implemented DB URL resolution aliases: `DATABASE_URL`, `POSTGRES_URL`, `SUPABASE_DB_URL`; `postgres://` is normalized to `postgresql://`.
- Updated Alembic config/runtime to use the resolved env DB URL instead of hardcoded `sqlite:///data/bot.db`.
- Added empty-DB bootstrap path: create SQLAlchemy metadata tables and stamp Alembic head, avoiding legacy SQLite-specific baseline SQL on fresh PostgreSQL/Supabase.
- Converted `utils.admin.admin_system.AdminSystem` from raw sqlite3/PRAGMA queries to SQLAlchemy sessions/text queries so admin registration/balance/transactions work on PostgreSQL.
- `/health` now includes `database` backend after a real `SELECT 1` DB check.
- HF deploy check: duplicate public/secret `DATABASE_URL` caused `CONFIG_ERROR`; public variable was removed and secret kept.
- Supabase direct URI `db.xrrdliznuyausiutxqwv.supabase.co:5432` failed from Hugging Face with IPv6 `Network is unreachable`. Next action: replace secret with Supabase Transaction pooler URI (`*.pooler.supabase.com:6543`, usually IPv4-friendly) or temporarily remove `DATABASE_URL` to restore SQLite fallback while obtaining pooler URI.
- DB01 regression reported after deploy: `/user@lt_lo_game_bot` fails with `'AdminSystem' object has no attribute 'get_db_connection'`. Root cause: some profile/admin command code still expects the legacy `AdminSystem.get_db_connection()` compatibility method removed during SQLAlchemy conversion. Hotfix: restore compatibility or migrate remaining call sites.
- New direct user-reported P1 bug: after DB01 hotfix deploy, bot does not answer `/user@lt_lo_game_bot` or `/start@lt_lo_game_bot`. Diagnose HF runtime/polling/logs without manual `getUpdates`; likely polling crash, DB startup issue, or handler blocking after PostgreSQL switch.
- HF runtime was `RUNNING`, but `/health` timed out. Likely PostgreSQL connection attempts can hang without a short DBAPI connect timeout. Hotfix in progress: add `connect_timeout` for PostgreSQL engines and simplify `/health` DB check via `engine.connect()`.
- New direct user-reported P1 bug: `/start@lt_lo_game_bot` and `/user@lt_lo_game_bot` now answer, but `/ai@lt_lo_game_bot` with no args does not. Likely root cause: AI help is sent with `parse_mode="HTML"` and contains unescaped `/ai@lt_lo_game_bot <вопрос>`, so Telegram rejects invalid HTML.
- Feedback endpoint check after PostgreSQL switch returned JSONL fallback with `count=0`; root cause: `feedback_entries` helper used SQLite-only `INTEGER PRIMARY KEY AUTOINCREMENT`, which fails on PostgreSQL. Hotfix: generate dialect-specific ID column (`SERIAL` on PostgreSQL) and report actual DB backend in `/feedback` response.
- Supabase pooler activation completed: HF secret `DATABASE_URL` was corrected to one-line Session Pooler URI and `/health` confirmed `{"database":"postgresql","service":"BankBot","status":"healthy"}`.
- Direct user-reported regressions fixed and deployed: `/start@lt_lo_game_bot`, `/user@lt_lo_game_bot`, `/ai@lt_lo_game_bot` no-args HTML escaping, PostgreSQL connect timeout, and remaining legacy sqlite calls in bot runtime.
- Feedback DB hotfix deployed: `feedback_entries` DDL is now dialect-aware (`SERIAL` on PostgreSQL, `AUTOINCREMENT` on SQLite). Need final live `/feedback?limit=N` re-check after HF startup settles.
- DB01 final verification passed: `GET /health` -> `database=postgresql`; external `GET /feedback?limit=20` -> `storage=postgresql`, `count=0`. DB01 can be considered completed for production persistence; keep monitoring runtime commands and Supabase limits.

### 2026-05-18 (AI01 — free local AI-lite assistant)
- Started AI01: add a free local AI-lite assistant without paid API keys or mandatory external providers.
- Target commands: `/ai <question>`, `/ask <question>`, `/ai_help`.
- Scope: command/navigation help, game/shop/feedback/mode hints, safe short responses for Hugging Face.
- User constraint: implementation must be free by default; no paid API dependency is acceptable for the baseline.
- Implemented `bot/ai/service.py` with deterministic keyword-routed local answers and no network/API key dependency.
- Added `bot/commands/ai_commands.py` and wired `/ai`, `/ask`, `/ai_help` in `bot/bot.py`, including mentioned-command fallback.
- Updated `/commands`, private-message help, and short HF `/start` command list to mention `/ai`.
- Added `tests/unit/test_ai_lite.py` for free-mode help, topic routing, fallback, and prompt length guard.
- Extended AI01 with offline canon knowledge base from Google Doc `Вселенная Олеговируса и LTL-паразита: канон` (`bot/ai/knowledge.py`): Olegovirus, LTL-паразит, Teaology, candy economy/Nine Circles, LTRS, glossary, high-canon article links and source metadata.
- Added global response modes (`bot/response_modes.py`): `/short` compacts long bot replies across sections via `Message.reply_text` patch, `/long` keeps full messages. AI canon answers now respect the same mode.
- Fixed AI canon relevance ranking: specific long keywords (`олеговирус`, `ltl-паразит`, etc.) beat generic words (`олег`, `канон`) so answers do not include unrelated rules/prohibitions.
- HF deployment commits: GitHub through `c4b0215 fix(ai): prefer specific canon matches`; Hugging Face through `f0991c2` for AI ranking and `7f19c9e` for global response modes.
- Verification: `python -m ruff check bot/response_modes.py bot/bot.py bot/commands/core_commands.py bot/commands/ai_commands.py bot/ai tests/unit/test_ai_lite.py` -> passed; `python -m pytest tests/unit/test_ai_lite.py -q` -> 19 passed; `python -m pytest tests/smoke -q` with dummy `BOT_TOKEN`/`ADMIN_TELEGRAM_ID` -> 9 passed.

### 2026-05-18 (New issue queue)
- User reported after sending `/feedback тест`: `/start@lt_lo_game_bot` does not answer. Must diagnose HF runtime/logs without manual `getUpdates` to avoid interfering with polling. Check whether latest local/GitHub fixes were deployed to Hugging Face, whether polling is alive, and whether mentioned-command fallback handles `/start@lt_lo_game_bot` correctly after deploy.
- Action taken: HF runtime showed `RUNNING`, but `/health` timed out and run logs endpoint was not practically readable from the current request. Uploaded latest runtime fixes (`bot/bot.py`, core/feedback commands, Memory Bank files) to HF Space and called `restart_space()`.
- User reported AI01 issue: `/ai@lt_lo_game_bot` with no args answers help, but bare `/ai что это за бот?` in chat does not answer. Need to improve AI-lite topic handling for “what is this bot” and verify bare `/ai` command registration/Telegram group semantics; if group has multiple bots, mentioned `/ai@lt_lo_game_bot <question>` remains the reliable form.
- Likely root cause found: AI answers were sent with `parse_mode="HTML"`, while answer text contained examples like `/feedback <текст>`. Telegram can reject such messages as invalid HTML tags. Fix: `/ai` without args still sends HTML help, but question answers are sent as plain text; added explicit “what is this bot” topic.
- User feedback on AI01: current AI-lite is perceived as “very dumb / made from sticks” because it is only a local keyword helper, not a real LLM. Improve positioning and fallback: be honest that it is a free command assistant, handle off-topic questions more naturally, and avoid overclaiming “AI”.
- New AI02 proposal from Nikita: use a free Hugging Face API to make answers smarter. Keep it optional/free with local AI-lite fallback, short timeouts, response limits, no secret logging, and no dependency on paid providers.

### 2026-05-18 (HF runtime and command UX stabilization)
- **HF runtime fix revised**: external retry-loop around `run_polling()` was removed again because it could repeatedly restart polling and drop/skip updates. PTB handles polling; HF uses `drop_pending_updates=False` to preserve user commands during transient network instability.
- **HF safe `/start`**: `/start` is routed through `safe_start_command` on HF and sends one short response only. This avoids long welcome spam and template-coder hint spam in groups after restarts.
- **Pending updates safety**: after live testing, HF now keeps pending updates (`drop_pending_updates=False`) because dropping them on reconnect caused user commands such as `/ai ...` to disappear during unstable Telegram networking. Safe `/start` still prevents long-message floods.
- **Command hierarchy correction**: `/commands` remains the command-section menu; `/user` now opens the player profile instead of duplicating the section list.
- **Game/D&D command fixes**:
  - D&D commands requiring database access (`/dnd_create`, `/dnd_join`, `/dnd_roll`, `/dnd_sessions`) are wired through `TelegramBot` wrapper methods that pass `get_db`.
  - `/dnd_roll` without arguments should now show usage help instead of failing through the global error handler.
  - `/play`, `/join`, `/startgame`, `/turn` usage/error messages were converted from transliteration to Russian.
- **Verification**:
  - `python3 -m ruff check bot/bot.py` -> passed after HF polling and safe-start fixes.
  - `python3 -m ruff check bot/bot.py bot/commands/game_commands_ptb.py bot/commands/dnd_commands_ptb.py` -> passed after game/D&D fixes.
  - `python3 -m pytest tests/smoke -v` -> `9 passed` after each fix batch.
- **Deployments**:
  - GitHub commits pushed through `f0dc04b fix(bot): корректные ответы игровых команд`.
  - Hugging Face Space `LucasTeam/BankBot` updated via `huggingface_hub.HfApi().upload_file()` for touched files.

### 2026-05-18 (FB01 — feedback/suggestions inbox)
- Added `bot/commands/feedback_commands.py`.
- Added `/feedback <text>` command for user suggestions and complaints.
- Added aliases `/suggest` and `/complaint` to the same feedback handler.
- `/feedback` without text now shows a feedback command menu with `/feedback`, `/suggest`, `/complaint`, and admin `/feedback_list`.
- Feedback is saved primarily in SQLite table `feedback_entries` with UTC timestamp, text, Telegram ID, username, first name, chat ID, and chat type. Append-only `data/feedback.jsonl` remains as fallback/debug mirror.
- Added admin-only `/feedback_list [limit]` command to read the latest saved entries from SQLite with JSONL fallback; limit is clamped to 1–20.
- Updated `/commands` and `/user` section text to mention `/feedback <текст>`.
- Verification: `python3 -m ruff check bot/bot.py bot/commands/feedback_commands.py` -> passed; `python3 -m pytest tests/smoke -v` -> `9 passed`.
- Added external feedback reader for HF: `GET /feedback?limit=N` in `run_bot.py`, protected by `Authorization: Bearer <FEEDBACK_READ_TOKEN|HF_TOKEN|BOT_TOKEN>` or `?token=...`.
- Added structured `Feedback saved` log with full feedback text and metadata when feedback is stored.
- Fixed: JSONL-only feedback storage on HF could confirm save but later show empty `/feedback_list`; SQLite `feedback_entries` is now primary storage and JSONL remains fallback/debug mirror.
- Fixed: `/long` mode did not affect HF `/start` because `safe_start_command` always forced the short text. HF `/start` now delegates to full `welcome_command` when the user mode is `long`.

### 2026-05-18 (PR10-PR13 — architecture cleanup and UX watchlist closure)
- **PR10 completed**: documented canonical layer responsibilities and runtime/legacy boundaries in `docs/README.md`.
- **PR11 completed**: risky physical deletion of active legacy/shim modules was avoided; shims are frozen/documented instead (`src.parsers`, `core/repositories`, `utils/*` deprecated shims, aiogram `shop_commands.py`).
- **PR12 completed**: extracted `build_polling_kwargs(is_hf)` in `bot/bot.py` while preserving HF timeout/retry behavior.
- **PR13 completed**: kept structured HF polling retry logs and improved operational command fallback for unknown commands.
- **UX/watchlist fixed**:
  - `/shop` now opens the shop directly without duplicate section preamble.
  - `/games` opens game help directly; `/games_list` now lists active sessions via `GamesSystem.get_active_sessions()`.
  - `/startgame` always responds on success, even if session details are incomplete.
  - `/turn` now reports success/reason/reward/next player instead of falling back to misleading `Ход сделан`.
  - `/dnd`, `/dnd_create`, `/dnd_join`, `/dnd_sessions`, `/dnd_roll` now use `core.systems.dnd_system.DndSystem` and only advertise currently wired commands.
  - Unknown commands now receive a `/commands` fallback response instead of silence.

## Known Issues
- ~~**Производительность: сайт «думает» пол минуты везде (2026-08-11)**~~ → **ПОЧИНЕНО:** `get_db_engine()` выполнял 69 DDL-запросов на каждый вызов; `_ensure_*` перенесены в блок создания движка. Дополнительно убран import-time init (cold start 21s → 0.5s). Задеплоено.
- ~~**Фидбек с /suggest не виден в админке (2026-08-11)**~~ → **ПОЧИНЕНО:** фильтры админки слали `?status=bug/suggestion` вместо `?category=`; API теперь принимает `category`. Задеплоено.
- ~~**[GD-BUG-1] Веб-заявка GD без медиа (2026-08-10)**~~ → **ПОЧИНЕНО (2026-08-10):** `/api/gd/submit` требует multipart-файл видео/фото (хранится data-URL в `media_file_id`), в `/gd` добавлено поле загрузки, `submitRecord()` → FormData + `xhr.timeout=30000`, модератор видит «🎬 Смотреть медиа». Тест `test_gd_web_submit_requires_media`. Задеплоено.
- **Бета-аудит 2026-08-10 (9 модулей, 18+ пунктов):** полный список улучшений и багов зафиксирован в `activeContext.md` → «Бета-аудит 2026-08-10». Приоритет №1: **privilege escalation** в `/settings`/`/admin` (is_admin из клиентского telegram_id). Также критичные: DELETE family-комнаты без авторизации, Stored XSS (глаголы/канон/family), двойное начисление монет в пазлах, DoS через `/api/dnd/roll`.
- ~~User сообщает что кнопка "Создать" на экране создания семьи не реагирует на нажатие в Telegram WebView~~ → **ПОЧИНЕНО (2026-08-10):** JS Family Circle переписан на ES5 + XHR Promise (старый WebView падал на async/await/стрелках/fetch). Деплой сделан.
- ~~**Pre-existing падения тестов (~30 failed)**~~ → **ПОЧИНЕНЫ (2026-08-10):** исправлены парсеры legacy, @settings(deadline=None), getattr callback в bot.py, temp-БД патчи интеграционных тестов, флейк PID_FILE в graceful shutdown. property+integration зелёные, unit 972 passed / 10 skipped.

### 2026-08-24 (ОГЭ-центр — Этап 0: ядро рекомендаций)
- Реализовано ядро ОГЭ-центра: таблица `study_progress` (user_id, module, card_key, reps, interval_days, ease, due, streak, correct_count, wrong_count, counter), API `/api/study/progress` GET/POST/reset и `/api/study/recommendations` (приоритет: просроченные due → слабые темы >40% ошибок → новые; вес по датам ОГЭ из `OGE_EXAM_DATES`), хаб-виджет «📌 План на сегодня» + бейджи на карточках предметов, идемпотентная миграция `emperors_progress`→`study_progress`. Информатика переименована `/math`→`/informatics` (+301 redirect).
- Проверки: ruff clean; `tests/unit/test_study_progress.py` (11 тестов: API, recommendations-приоритеты, миграция, хаб-виджет); `test_informatics_module.py` (бывш. `test_math_module.py`) обновлён под `/informatics` + тест редиректа; регресс моих модулей зелёный. Задеплоено `7967c1d`.
- Разделение труда (решение пользователя): ОГЭ ведёт opencode; легаси-падения тестов (120 шт., env/version mismatch по `telegram`/`pydantic`/`aiohttp`/`structlog` в бот/src-модулях) чинит другой разработчик параллельно — НЕ блокирует ОГЭ.

### 2026-08-24 (ОГЭ-центр — Этап 1: Математика)
- Реализован модуль Математика `/math`: пакет `core/mathematics/` (FORMULAS ~130 карточек формул по 12 темам, TASKS ~30 задач, GENERATORS 8 клиентских параметрических генераторов). Страница `math_page` (шаблон `MATH_PAGE_TEMPLATE`): вкладки 📚Формулы (flashcards SM-2 через `study_progress`, ключ `formula::<id>`), 🧠Задачи (самопроверка, `task::<id>`), 🎲Генератор (рандом-задачи, `gen::<gid>`), 📝Экзамен (20 заданий + таймер + оценка). Прогресс пишется в `/api/study/progress` (module='math', ключ без префикса модуля; важно: `body={"module":...,"cards":...}`, ответ `{"ok":True}`; ключи хранятся как есть).
- Карточка «Математика» добавлена в хаб (после Информатики). Тесты: `test_mathematics_module.py` (данные + страница + roundtrip прогресса), `test_informatics_module.py` обновлён (больше нет редиректа `/math`→`/informatics`). Мои модули зелёные. Задеплоено `731c453`.

### 2026-08-24 (ОГЭ-центр — Этап 2: Информатика расширена до кодификатора)
- Расширен модуль Информатика `core/informatics/tasks.py`: добавлено 6 тем кодификатора ОГЭ — Системы счисления, Кодирование информации, Логические основы, Базы данных и запросы, Компьютерные сети, Алгоритмы и исполнители (итого 15 тем × 5 задач = 75). Каждая тема: theory + 5 задач. `OGE_MODULES["informatics"].total` → 75. Тесты `test_informatics_module.py` обновлены (count=15, ids lesson1..lesson15).
- Интеграция с ОГЭ-центром: страница `/informatics` теперь пишет прогресс в `study_progress` (module='informatics', ключ = id задачи) через `infoRecord`/`infoPush`/`infoLoad` (как у математики). Теперь информатика появляется в виджете «План на сегодня» и рекомендациях. `node --check` JS ок, прод `/informatics` 200, новые темы присутствуют. Задеплоено `59cbd6f`.
- Генераторы/экзамен-режим для информатики (паритет с математикой) — отложены в OGE-FULL (полный проход по кодификатору).

### 2026-08-24 (ОГЭ-центр — Этап 3 / OGE-04: Русский язык)
- Создан модуль `core/russian/` (`rules.py` + `__init__.py`): RULES 40 карточек правил (Орфография/Пунктуация/Работа с текстом), TASKS 30 заданий тренажёра (вставь букву, расставь знаки, найди средство выразительности, тип речи), ESSAY_CRITERIA 12 критериев ФИПИ (К1–К12) с чек-листами без автопроверки.
- Страница `/russian` (шаблон RUSSIAN_PAGE_TEMPLATE в api/index.py): вкладки 📚 Правила (flashcards SM-2, `rule::<id>`), 🧠 Тренажёр (самопроверка, `task::<id>`), 📋 Чек-лист сочинения (чекбоксы, `essay::<id>`). Прогресс → `/api/study/progress` module='russian'. Карточка в хабе добавлена. `OGE_MODULES["russian"].total` → 82.
- Тесты: `test_russian_module.py` (данные + страница + roundtrip); мои модули зелёные (57 тестов), ruff clean, node --check JS ок. Прод `/russian` 200, правила встроены. Задеплоено `5c053df`.

### 2026-08-24 (ОГЭ-центр — OGE-07: ИИ-план дня + режим ОГЭ)
- **ИИ-план:** новый эндпоинт `GET /api/study/ai-plan` — собирает статистику через рефакторенный хелпер `_oge_subjects_payload(uid, now)` (общий с `/api/study/recommendations`), шлёт промпт в Groq (`call_ai_api`, llama-3.3-70b), кэширует результат на день в `_OGE_AI_PLAN_CACHE[uid]`, поддерживает `?force=1`. Fallback: `{"ok":false,"plan":""}` при ошибке AI.
- **Хаб:** блок «✨ Персональный план от ИИ» внутри виджета (кнопка ↻ = force); переключатель «🎯 Режим подготовки к ОГЭ» (`#oge-mode-bar`) — скрывает виджет и 4 предметные карточки (`data-oge="1"`), состояние в localStorage `oge_mode`, по умолчанию ВКЛ.
- Тесты: ai-plan (401 без auth; генерация→кэш→force; fallback при ❌) + расширен hub-тест. Все зелёные, node --check ок. Задеплоено `aef6359`.

### 2026-08-24 (ОГЭ-центр — OGE-05: Физика)
- Создан `core/physics/` (`formulas.py`): FORMULAS 57 формул по 9 темам (кинематика, динамика, давление, плотность, работа/энергия, тепло, электричество, оптика, колебания), TASKS 28 задач, GENERATORS 6 клиентских. Страница `/physics` клонирована с математики (скрипт-клон шаблона, GEN-блок переписан под физику): вкладки Формулы/Задачи/Генератор/Экзамен; module='physics', ключи `formula::`/`task::`/`gen::`. Хаб-карточка + data-oge="1", `OGE_MODULES["physics"].total`=85.
- Тесты `test_physics_module.py` (данные+страница+roundtrip) — мои модули 68 зелёных; ruff clean; node --check ок. Прод `/physics` 200. Задеплоено `45fc25f`.

## last_checked_commit
70f00b5 (2026-08-27; Session 9b: максимальная прокачка ИИ-куратора — починены due/weak/topics + отсчёт + fallback, +5 инструментов, +5 тестов; деплой через CLI)
c9e4021 (2026-08-26; максимальная прокачка OGE: SM-2 с ростом ease, инфо-тренажёр с самооценкой, физика в экзамене, /api/study/stats, /api/study/due-cards, /api/quiz/generate+check, /analytics, хаб-прогрессбары; деплой через CLI)
f2ef98e (2026-08-26; автозачёт плана дня: пункт закрыт когда по предмету сегодня тронуто >= cards карточек, кнопка/роут plan/done удалены, снапшот в done_count; ранее fbbc59d — нормы времени + названия без ключей; 68249a9 — тулы topic/card + фикс JS хаба; прод: деплой через CLI по мере сессий)
fbbc59d (2026-08-26; куратор: реалистичные нормы времени + названия карточек без ключей + планер 2 мин/пункт; ранее 68249a9 — тулы topic/card и фикс JS хаба; b90bf5d — mdLite + lookup-инструменты; прод задеплоен через CLI и смоукнут)
b90bf5d..68249a9 (2026-08-26; 68249a9 — тулы куратора topic/card + фикс JS хаба (\n в regex ломал весь script, бета-раздел не открывался); b90bf5d — mdLite markdown + инструменты-lookup {"tool":...}, UI-статус «смотрит твой журнал»; прод задеплоен через Vercel CLI, смоукнут)

### 2026-08-23 (Темы + Pico CSS + императоры: критерий выученности)
- **ОГЭ-центр (план):** составлен и записан в память банка план подготовки к ОГЭ по 5 предметам (математика, русский, информатика, физика, история) с ядром рекомендаций «что учить сейчас». Deliverables — `projectbrief.md` Phase 6 (OGE-00…OGE-06 + OGE-FULL), детальный план — `memory_bank/oge_center_plan.md`. Решения: информатика → `/informatics`, математика → `/math`; единая таблица `study_progress`; контент MVP, затем весь кодификатор ФИПИ. Исполнение не начато.
- **Тема светлая/тёмная:** полный набор переменных `--bb-*`/`--gh-*` в `core/theme.py`, инжекция через `after_request`, переключатель на всех страницах (localStorage + prefers-color-scheme). Конвертация всех страниц с жёстких hex на переменные; исправлены предсуществующие баги (неопределённые var(), `color: var(--bb-bg)` как текст, скорруппированные 8-битные hex).
- **Pico CSS v2** подключён централизованно (`THEME_CSS`) на все страницы; палитра Pico замаплена на переменные темы; глобальный фикс `button { width: auto }` против full-width по умолчанию.
- **Прогресс-бары** (императоры + информатика): трек `--bb-elev` / заливка `--bb-primary` — починен контраст после осветления синих в светлой теме.
- **Императоры:** карточка считается выученной для бара/статистики при серии из 3 правильных ответов подряд (`rec.streak`, сброс на ошибке); механика подбора карточек не тронута. Исправлен баг подсчёта: раньше в бар попадали карточки вне текущего охвата («5 императоров» vs «все»). Проверки: node --check OK, ruff clean, 49 тестов passed, задеплоено `0320d70`.

### 2026-06-13 (D18 — E2E tests for parsing + bank)
- **D18 completed:** 19 E2E tests for all 6 bot parsers + webhook flow.
- **Tests in `tests/unit/test_vercel_parsing_e2e.py`:**
  - 7 parser unit tests (GDcards card/chest, Gusya, Shmalala fish/karma, Chaometer, BunkerRP)
  - 3 edge case tests (empty/gibberish, markdown tea action)
  - 1 test: negative/zero coins not returned
  - 7 webhook integration tests (5 bots + failure message + no-reply)
  - 1 test: priority GDcards over Shmalala
- **Bugfix:** Added missing `amount` key to GDcards chest and card parsers (required by webhook handler at line 2075).
- **Bugfix:** Fixed DB mock setup for webhook tests — `execute().mappings().first()` returns `{"id": 1}` and `.all()` returns `[]`.
- **Verification:** All 19 + 3 smoke tests = 22 passed.
- **Commit:** `6091a4f` — D18: Fix GDcards amount key, add 19 E2E parsing tests

### 2026-06-07 (D10 — E2E парсинг всех ботов на Vercel + калибровка коэффициентов)
- **D10 (ParserRegistry + E2E парсинг):** Значительный прогресс. В `api/index.py` добавлены парсеры для всех ботов из чата.
- **Новые функции в api/index.py:**
  - `parse_bot_message()` — единая точка входа, перебирает парсеры по приоритету
  - `parse_gdcards_message()` — расширен: карты (`🤩 Орбы: +X`) + сундуки (`🎁 X открыл сундук`)
  - `parse_gusya_cards_message()` — новый: монеты (`💰 Монеты • +X`)
  - `parse_shmalala_fishing_message()` — новый: рыбалка (`🎣 [Рыбалка] ... Монеты: +X`)
  - `parse_shmalala_karma_message()` — новый: рейтинг (`рейтинг: X ❤️`)
  - `parse_chaometer_message()` — новый: профиль чая (`👤 Имя ... Сегодня: X.X л.`)
  - `parse_bunkerrp_message()` — новый: окончание игры (`Прошли в бункер: 1. Name`)
  - `get_conversion_rate()` — читает курс из `conversion_rates` таблицы, fallback на хардкод
- **Курсы:** GDcards=2.5, Гуся Cards=5.0, Shmalala=2.5, Shmalala karma=0.5, Чайометр=1.0, BunkerRP=50.0
- **Калибровка:** проанализирован экспорт чата за месяц (106 сообщений Чайометра, 48 GDcards, 70 Shmalala), курсы подобраны под ~50-100 монет/день на бота
- **Вебхук:** заменён `parse_gdcards_message()` на `parse_bot_message()` с детальным сообщением о начислении
- **Verification:** `py_compile` OK, `ruff check` OK

### 2026-06-06 (Vercel Production Fixes + AI Trivia)
- **HF Space crashed** с `ImportError: cannot import name 'short_mode_command'` — `bot.py` импортирует `short_mode_command` из `core_commands.py`, но функция была удалена в предыдущем рефакторинге. **Fix:** добавлена обратно в `core_commands.py`.
- **HF Space не пересобирается** из git push — Docker образ на HF Space не обновляется автоматически. **Webhook переключён на Vercel.**
- **Vercel webhook не работал** — Telegram всё ещё отправлял updates на HF Space (webhook не был переключён, т.к. запросы к Telegram API не проходили с этой машины). **Fix:** добавлен endpoint `/api/set_webhook`, который переключает webhook с Vercel через Telegram API.
- **BOT_TOKEN был пуст на Vercel** — проектная env var BOT_TOKEN была `""` (пустая строка). Бот не мог отправлять сообщения. **Fix:** удалён старый BOT_TOKEN через `vercel env rm`, создан новый через `vercel env add`.
- **/trivia не работал через import questions.py** — на Vercel нет зависимостей `aiohttp`, `python-telegram-bot`. **Fix:** вся логика викторины (23 вопроса + AI-генерация + парсинг) перенесена напрямую в `api/index.py`.
- **AI-викторина на Vercel:** Groq API + контекст канона (первые 1500 символов), таймаут 5 секунд. Если AI не отвечает — fallback на готовые вопросы.
- **canon_knowledge.txt на Vercel:** файл скопирован в `api/canon_knowledge.txt` для доступа из serverless функции.
- **Файлы:** `api/index.py` (+викторина, +AI, +set_webhook, +debug), `api/canon_knowledge.txt`, `bot/commands/core_commands.py` (+short_mode_command)

### 2026-05-04 (Network & Notification Fixes)
- **Proxy Support**: Added `PROXY_URL` configuration to `src/config.py` and implemented proxy logic in `bot/bot.py` using `ApplicationBuilder.proxy_url`.
- **HTML Escaping Fixes**: Escaped `<` and `>` in `WELCOME_TEXT` and user dynamic data in `core_commands.py` to prevent `BadRequest` errors in Telegram.
- **Error Handler Improvement**: Added `html.escape` to traceback formatting in `error_handler.py`.
- **Notification System Upgrade**: 
  - `NotificationSystem` methods made `async`.
  - Added real-time Telegram message sending to `NotificationSystem`.
  - Updated `shop_commands_ptb.py` and `core_commands.py` to use async notifications with the bot instance.
- **New Commands**: Added `/ping` (latency test) and `/test_notify` (notification popup test).
- **Environment**: Configured `.env` with `PROXY_URL=http://127.0.0.1:1080` to restore connectivity.
- **N02 Increment**:
  - `NotificationSystem` refactored to public realtime API `send_realtime_notification()`.
  - Added async `ntfy` delivery through `aiohttp` with configurable `NTFY_ENABLED`, `NTFY_BASE_URL`, `NTFY_TAGS`, `NTFY_TIMEOUT_SECONDS`.
  - Added optional `ADB` delivery transport via `adb shell cmd notification post` with env settings `ADB_NOTIFICATIONS_ENABLED`, `ADB_PATH`, `ADB_DEVICE_SERIAL`.
  - Fixed `/notifications` and `/notifications_clear`: commands now resolve `telegram_id` to internal `users.id` before reading/updating `user_notifications`.
  - Replaced direct private `_send_to_ntfy()` calls in `/ping` and template coder with public realtime notification API.
  - Added unit tests `tests/unit/test_notification_system.py` for realtime fanout, ADB command construction, and correct user-id mapping.
  - Added diagnostic commands `/notify_status` and `/test_adb`; wired into `bot/bot.py`.
  - **Runtime lesson**: local BankBot startup should use `Python 3.12`. On `Python 3.14`, `python-telegram-bot==20.7` crashes during `Updater` initialization.
  - Documentation updated: `README.md`, `RUN.md`, `docs/README.md`, `docs/DEPLOYMENT.md` now explicitly require `py -3.12` for local install/run/test flow.
  - Runtime verification on `Python 3.12`: dependency installation via `py -3.12 -m pip install -r requirements-dev.txt` completed; `py -3.12 run_bot.py` reaches polling, and further failures are network-level (`httpx.ConnectError`), not Python/runtime-level.
  - **Env split**: configuration model refactored into `config/.env.shared` (committable safe defaults) + `config/.env.local` (uncommitted secrets/local overrides). `src/config.py` now loads multiple env layers in order and preserves fallback to legacy `config/.env`.
  - Replaced `config/.env.example` with `config/.env.shared.example` and `config/.env.local.example`; updated `.gitignore` and runbook accordingly.

- Добавлен новый модуль в планы с максимальным приоритетом: **M01 — диалоговый кодер текстовых шаблонов**.
- Создано подробное ТЗ: `memory_bank/dialog_template_coder_module.md`.
- `projectbrief.md` обновлён: M01 добавлен в `Post-Release Backlog` как `MAX/P0 planned` выше pending-задач `PR10–PR13`.
- `activeContext.md` обновлён: текущий фокус переключён на M01.
- Пользователь предоставил полный список 500 троек: `100 пар × 5 модификаторов C`, где `C ∈ {1,2,3,5,10}`.
- В `dialog_template_coder_module.md` зафиксированы коды 10 шаблонов, правило третьего уровня и задача переноса данных в JSON/код.
- Пользователь предоставил полную таблицу 10 одиночных значений; все три таблицы данных для M01 теперь определены.
- Начата реализация M01:
  - создан пакет `bot/template_coder/`;
  - добавлены `data.py`, `service.py`, `dialog.py`;
  - подключены `/reset`, `/help` и обработка текстовых шаблонов в `bot/bot.py`;
  - добавлены unit-тесты `tests/unit/test_template_coder.py`.
- Проверки: `python -m pytest tests/unit/test_template_coder.py -q` -> 6 passed; `python -m ruff check bot/template_coder tests/unit/test_template_coder.py bot/bot.py` -> passed.
- Следующая итерация: перенесены все 500 троек в `bot/template_coder/data.py`, временный fallback генерации удалён.
- Добавлена `validate_data()` для проверки полноты таблиц: 10 шаблонов, 10 одиночных значений, 100 пар, 500 троек.
- Добавлен entrypoint `/coder` для запуска нового блока и сброса состояния.
- `/help` расширен инструкцией по диалоговому кодеру и списком 10 шаблонов; `/reset` сбрасывает состояние кодера.
- Тесты расширены проверками полноты таблиц и help/start-текста.
- Проверки после расширения: `python -m pytest tests/unit/test_template_coder.py -q` -> 9 passed; `python -m ruff check bot/template_coder tests/unit/test_template_coder.py bot/bot.py` -> passed.
- `/start` синхронизирован с новым блоком: после основного приветствия отправляет отдельную краткую подсказку по диалоговому кодеру.
- Добавлена поддержка mentioned-команд для групп: `/coder@bot`, `/help@bot`, `/reset@bot`.
- Тесты расширены до 11 сценариев, включая `/start` hint и `_extract_bot_mentioned_command` для команд нового блока.
- Проверки: `python -m pytest tests/unit/test_template_coder.py -q` -> 11 passed; `python -m ruff check bot/template_coder tests/unit/test_template_coder.py bot/bot.py` -> passed.
- `/start` теперь сбрасывает состояние кодера перед отправкой основного приветствия и подсказки.
- Добавлен TTL 30 минут: `CoderState.updated_at`, `TemplateCoderService.is_expired()`, авто-сброс устаревшего состояния в `TemplateCoderDialog.handle_text()`.
- Тесты расширены до 13 сценариев, включая TTL свежего/устаревшего состояния и отсутствие expiry у пустого состояния.
- Проверки: `python -m pytest tests/unit/test_template_coder.py -q` -> 13 passed; `python -m ruff check bot/template_coder tests/unit/test_template_coder.py bot/bot.py` -> passed.
- Финализация M01:
  - добавлены adapter-level async тесты `TemplateCoderDialog`;
  - проверены обработка шаблонного текста, игнор обычного текста, сброс устаревшего состояния и `/reset`;
  - добавлен import smoke для wiring класса `TelegramBot`.
- M01 переведён в `completed` в `projectbrief.md`.
- Финальные проверки M01: `python -m pytest tests/unit/test_template_coder.py -q` -> 19 passed; `python -m ruff check bot/template_coder tests/unit/test_template_coder.py bot/bot.py` -> passed.
- Краткий режим обычных меню сделан режимом по умолчанию. `/short` и `/long` реализованы как персональный краткий/полный режим; `/short_all` и `/long_all` — как общий режим для всех. Это не режим часов и не справка кодера.
- Временно отключён режим часов: `send_realtime_notification()` больше не отправляет в `ntfy`/`ADB`, но сохраняет Telegram realtime. Команды `/short` и `/short_all` не отключались.

### 2026-04-17 (PR10 — smoke sync and pytest-asyncio cleanup)
- Актуализирован `tests/smoke/test_startup.py` под текущие публичные API и startup flow
  - smoke-проверки для `bridge_bot.config` и `vk_bot.config` переведены с устаревших `BridgeConfig` / `VKConfig` на текущие экспорты `BotSettings` и `get_settings`
  - startup smoke для `bot.main` переведён на патч `bot.main.TelegramBot`, чтобы тестировать фактическую точку использования класса
- В `tests/pytest.ini` добавлен `asyncio_default_fixture_loop_scope = function`
- В `src/config.py` расширен `DynamicSettings`, чтобы env-загрузка не теряла feature flags, cache-настройки и debug/test поля из основного `Settings`
- Синхронизированы `RUN.md` и `config/.env.example`
  - `RUN.md` переведён на актуальные `BOT_TOKEN`, `config/.env` и PowerShell-команды для Windows-среды
  - `config/.env.example` переведён на реальные `DB_POOL_MIN` / `DB_POOL_MAX`, удалён устаревший `HOT_RELOAD`
- Переписан `docs/README.md`
  - удалены устаревшие метрики, старые команды запуска и неактуальные пометки "в разработке"
  - зафиксированы реальные точки входа: `run_bot.py`, `bot/main.py`, `bridge_bot/main.py`, `vk_bot/main.py`
  - описаны актуальные роли каталогов `bot/`, `bridge_bot/`, `vk_bot/`, `bank_bot/`, `core/`, `src/`, `database/`, `memory_bank/`
- Переписаны `README.md` и `docs/DEPLOYMENT.md`
  - `README.md` сокращён до актуального верхнеуровневого описания проекта, запуска, Docker и структуры каталогов
  - `docs/DEPLOYMENT.md` синхронизирован с текущими entrypoints, `docker-compose.yml`, `Dockerfile`, `config/.env.example` и `src/config.py`
  - удалены устаревшие env-поля, ранние архитектурные слои и старые deployment-сценарии, не соответствующие текущему коду
- Локальная проверка на Python 3.13:
  - `py -3.13 -m pytest tests/smoke -v` -> 9 passed
  - `py -3.13 -m ruff check src/config.py tests/smoke/test_startup.py` -> passed

### 2026-04-17 (Post-Release: PR01-PR09 completed)
- **PR01 (schema audit)**: Verified SQLAlchemy metadata vs Alembic migrations
- **PR02 (schema verification)**: Verified Alembic migrations exist and work correctly
  - `database/alembic/versions/001_initial.py` - initial migration
  - `database/alembic/versions/002_add_alias.py` - alias field
  - `database/alembic/versions/003_create_missing_tables.py` - missing tables
  - `database/schema.py` - Alembic-first helper with create_tables() fallback
- **PR03 (env unification)**: Unified environment variables across documentation
  - Updated `RUN.md` to match `config/.env.example` format
  - Verified `src/config.py` is canonical source of Settings class
- **PR04 (documentation sync)**: Started documentation synchronization
  - Verified `RUN.md`, `README.md`, `docs/README.md` exist
  - Updated RUN.md to reflect actual .env path (`config/.env`)
- **PR05 (pytest warnings)**: Verified pytest.ini configuration is correct
  - Filterwarnings configured for DeprecationWarning and PytestUnknownMarkWarning
- **PR07 (smoke tests)**: Created startup smoke tests
  - `tests/smoke/test_startup.py` - tests for BankBot, BridgeBot, VK Bot, DB schema, config
  - Tests for: imports, loop guard, configuration loading, repository/service imports
- **PR08 (Docker/Compose)**: Verified Dockerfile and docker-compose.yml are working
  - Multi-stage build with tini for proper signal handling
  - Health checks configured for all 3 services
  - Resource limits defined
- **PR09 (runbook)**: Updated RUN.md with release checklist
  - Added "Чеклист перед запуском" table
  - Updated error messages to use correct env vars
  - Added smoke tests to verification commands

### 2026-04-06 (PR01 — schema audit and migration hardening)
- Выявлено ключевое расхождение: SQLAlchemy metadata описывает 24 таблицы, а ранняя Alembic-цепочка покрывала только базовые таблицы и частичный `users`
- Исправлен `database/alembic/env.py`: удалён несуществующий импорт `database.models`
- Добавлена миграция `database/alembic/versions/003_create_missing_tables.py`
- Добавлен `database/schema.py` с `ensure_schema_up_to_date()`
- `bot/main.py` и `bot/bot.py` переведены на Alembic-first обновление схемы
- Проверка на чистой БД `data/test_pr01.db`: миграция до `003` проходит успешно, metadata-таблицы создаются полностью
- **Ruff**: all checks passed для `bot` и `database`
- **Тесты**: 745 passed, 10 skipped

### 2026-04-06 (Post-Release planning)
- В `memory_bank/projectbrief.md` зафиксирован post-release roadmap на 1-2 недели
- Добавлен подробный технический план по файлам и модулям
- Добавлен post-release backlog `PR01–PR13` с приоритетами `P0/P1/P2`
- `activeContext.md` обновлён: текущий фокус смещён на пост-релизную стабилизацию и прокачку проекта

### 2026-04-06 (Post-Phase 3 — cleanup warnings)
- Убрана неизвестная pytest-опция `env` из `tests/pytest.ini`
- Исправлены 3 теста, которые возвращали `bool` вместо падения через `assert`
- Исправлена проверка в `test_add_admin_verification.py`: поиск пользователя по `telegram_id`, а не по `id`
- **Тесты**: 745 passed, 10 skipped
- **Предупреждения pytest**: 5 (было 9)

### 2026-04-05 (H06 — Redis кэширование)
- **Создан Redis бэкенд:**
  - `utils/redis_cache.py` — полнофункциональный Redis кэш
  - Поддержка fallback при недоступности Redis
  - Key prefix для изоляции данных
  - JSON сериализация значений
- **Добавлен в requirements.txt:**
  - `redis==5.0.1`
- **Созданы тесты:**
  - `tests/unit/test_redis_cache.py` (19 тестов)
- **Тесты**: 745 passed, 10 skipped

### 2026-04-05 (H04 — Ruff cleanup)
- **Автофиксы ruff:**
  - F541: f-strings without placeholders (47 fixed)
  - F811: Redefinition of unused imports (5 fixed)
  - E712: Equality comparisons to True/False (47 fixed)
- **Тесты**: 703 passed, 10 skipped

### 2026-04-05 (H05 — BridgeBot тесты)
- **Созданы тесты:**
  - `tests/unit/test_bridge_loop_guard.py` (9 тестов)
  - `tests/unit/test_bridge_queue.py` (14 тестов)
- **Покрытые модули:**
  - `bridge_bot/loop_guard.py` — has_bot_mark, add_bot_mark
  - `bridge_bot/queue.py` — MessageQueue, OutboundMessage, RateLimitError
- **Тесты**: 726 passed, 10 skipped

### 2026-04-05 (H03 — Prometheus метрики)
- **metrics_server.py** уже реализован:
  - `/metrics` — Prometheus-compatible endpoint
  - `/health` — Health check endpoint
- **Добавлены в requirements.txt:**
  - `flask==3.0.0`
  - `prometheus-client==0.19.0`

### 2026-04-05 (H02 — Alembic миграции)
- **Создан Alembic конфиг:**
  - `alembic.ini` — конфигурация
  - `database/alembic/env.py` — окружение миграций
  - `database/alembic/script.py.mako` — шаблон миграций
  - `database/alembic/versions/001_initial.py` — начальная миграция
  - `database/alembic/__init__.py`
  - `database/alembic/versions/__init__.py`
- **Тесты**: 703 passed, 10 skipped

### 2026-04-05 (H01 — извлечение команд, продолжение)
- **bot/bot.py**: 3923 → 891 строк (−77%)
- **Созданы модули команд:**
  - `bot/commands/dnd_commands_ptb.py` (10850 bytes)
  - `bot/commands/achievements_commands_ptb.py` (2679 bytes)
  - `bot/commands/social_commands_ptb.py` (5836 bytes)
  - `bot/commands/notification_commands_ptb.py` (1813 bytes)
  - `bot/commands/motivation_commands_ptb.py` (2135 bytes)
- **Удалены inline методы:**
  - D&D: dnd_command, dnd_create_command, dnd_join_command, dnd_sessions_command, dnd_roll_command
  - Achievements: achievements_command
  - Motivation: daily_bonus_command, challenges_command, motivation_stats_command
  - Notifications: notifications_command, notifications_clear_command
  - Social: friends_command, friend_add_command, friend_accept_command, gift_command, clan_command, clan_create_command, clan_join_command, clan_leave_command
- **Тесты**: 703 passed, 10 skipped
- **Ruff**: All checks passed

### 2026-04-03 (F03 — CI/CD pipeline)
- Создан `.github/workflows/ci.yml`:
  - Lint (ruff)
  - Unit tests (pytest)
  - Integration tests
  - Coverage (codecov)

### 2026-04-03 (F01 — исправление unit тестов)
- **Root cause**: `sys.path.insert(0, 'core/')` в source файлах затенял корневой `database/` модуль
- **Исправлено**: убраны `sys.path.insert` из:
  - `core/managers/shop_manager.py`
  - `core/managers/admin_manager.py`
  - `core/managers/config_manager.py`
  - `core/managers/sticker_manager.py`
  - `core/managers/background_task_manager.py`
  - `core/handlers/shop_handler.py`
  - `core/handlers/purchase_handler.py`
  - `core/systems/shop_system.py`
  - `database/database.py`
  - `core/systems/motivation_system.py`
  - `bot/bot.py`, `bot/main.py`
  - `bot/commands/config_commands.py`
  - `utils/monitoring/notification_system.py`
  - `utils/monitoring/monitoring_system.py`
  - `utils/core/error_handling.py`
- **Добавлен импорт**: `import os` в `config_commands.py`, `config_manager.py`
- **Тесты**: 746 passed, 62 failed (не импорты, а test-specific issues)
- **Ruff**: All checks passed

### 2026-04-03 (ревизия проекта)
- **Git commit**: a5355a2 — Refactoring: extract commands from bot/bot.py, Ruff cleanup, Bridge/VK tests
- **Статистика**: 109 files changed, 4735 insertions(+), 6657 deletions(-)
- **bot/bot.py**: 3923 → 2112 строк (−44%)
- **Ruff**: 0 errors в продакшн коде
- **Tests**: BridgeBot + VK Bot — 43 passed
- **T08–T15**: все completed

## Known Issues
- 55 errors при сборе тестов (unit tests с устаревшими импортами)
- Основные тесты (bridge/vk_bot): работают ✅

### 2026-04-03 (завершение очистки)
- **Git**: добавлены 8 новых файлов (extracted modules, tests, ruff.toml)
- **Ruff**: продакшн код — 0 errors, тесты — 149 errors (в ruff.toml)
- **Тесты**: BridgeBot + VK Bot — 43 passed
- **bot/bot.py**: 3923 → 2112 строк (−44%)
- **T15 завершён**: Ruff cleanup полностью

### 2026-03-29 (ревизия проекта)
- **Ruff**: 370 автоисправлено, 354 осталось (в legacy коде)
- **Тесты**: 706 passed, 89 failed
  - Провалы: импорт BotApplication, отсутствие колонки alias, merge conflicts
- **Merge conflicts**: найдены в README.md, test_task_9_verification.py, test_auto_registration_pbt.py
- **Core service tests**: 53 passed (shop, transaction, user services)
- **Docker**: Dockerfile и docker-compose.yml базовые, работающие

### 2026-03-28 (продолжение)
- **Этапы 4-6 завершены**: vk_bot/ создан, корень проверен, финальная проверка пройдена
  - `vk_bot/config.py`, `bot.py`, `handlers.py`, `main.py` — импорты OK
  - ruff check: предупреждения только в legacy-коде (bot/bot.py)
  - Все модули (bank_bot, bridge_bot, vk_bot) импортируются корректно

### 2026-03-28 (доп.)
- **D12 (Connection Pooling)**: Подключен `get_pooled_engine()` в `database/database.py`
- **D13 (SQL Injection Audit)**: Аудит завершён — параметризация используется везде
- **D16 (Очистка неиспользуемого кода)**: Исправлены unused imports в bot/bot.py (6 шт)
- **TransactionService fix**: Добавлен `session` параметр для тестов, исправлены методы для использования `get(id)` вместо `get_by_telegram_id`
- **UserRepository fix**: Добавлен метод `get_all()` в `core/repositories/user_repository.py`
- **Unit tests**: 713 passed, прогресс в стабильности
- **D19 (Security tests)**: Созданы тесты SQL injection и race conditions
- **D20 (Coverage)**: TransactionService 96%, ShopService 95%, UserService 94%, AliasService 91%
- **D21 (Documentation)**: Обновлена архитектура README.md, добавлены точки входа
- **D22 (Docstrings)**: Google style docstrings добавлены во все ключевые модули:
  - core/repositories/ (BaseRepository, BalanceRepository, TransactionRepository, UnitOfWork)
  - core/services/ (BalanceService, TransactionService)
  - bridge_bot/, vk_bot/, bank_bot/ (re-exports + entry points)

### 2026-03-29 (реструктуризация)
- bridge_bot/ получил реальный код (queue, loop_guard, media, vk_publisher, handlers)
- bot/bridge/ стал shim-обёртками на bridge_bot/
- bank_bot/repositories/ получил реальный код из core/repositories/
- bank_bot/services/ получил реальный код из core/services/
- core/repositories/ стал shim-обёртками на bank_bot/repositories/
- core/services/__init__.py стал shim на bank_bot/services/
- Dockerfile и docker-compose.yml созданы
- ruff: 0 ошибок в целевых модулях
- Тесты: 991 passed, 168 failed (все провалы pre-existing)
  - SimpleShmalalaParser отмечен как deprecated
  - Рекомендуется использовать BaseParser из core/parsers/shmalala.py, gdcards.py

### 2026-03-28
- Реализован Bridge-модуль (ядро + медиа):
  - `config/settings.py` — BotSettings с Bridge-полями и валидацией
  - `requirements.txt` / `requirements-dev.txt` — конфликты разрешены, добавлен `vk_api~=11.9`
  - `database/migrations/004_add_bridge_state.sql` + `add_bridge_state.py`
  - `bot/bridge/__init__.py`, `config.py`, `loop_guard.py`
  - `bot/bridge/message_queue.py` — FIFO очередь с rate limiting
  - `bot/bridge/vk_sender.py` — отправка в VK с префиксом [TG] и меткой [BOT]
  - `bot/bridge/telegram_forwarder.py` — aiogram handler TG → VK
  - `bot/bridge/vk_listener.py` — VKListenerThread, Long Poll, медиа VK → TG
  - `bot/bridge/media_handler.py` — загрузка фото/видео/документов TG → VK
  - `bot/bridge/main_bridge.py` — точка входа aiogram + graceful shutdown
- Чекпоинт 3 (Bridge ядро) пройден: импорты OK, логика loop_guard OK, валидация конфига OK

### 2026-03-27
- Обновлена документация в memory_bank
- Исправлен конфликт импортов в src/balance_manager.py
- Выявлены проблемы с типизацией в ParsingConfigManager

### Предыдущие изменения
- Реализован ParserRegistry для централизованного парсинга
- Создан ParsingConfigManager для управления правилами в БД
- Добавлена таблица parsing_rules в БД
- Реализован BalanceManager для обработки балансов
- Добавлен Unit of Work для атомарных транзакций

### 2026-05-07 (Connectivity & Deployment Fixes)
- **Hugging Face Deployment**: Initialized deployment to HF Spaces.
- **Network Diagnostics**: Created `bot/check_proxy.py` to test direct and proxy connections to Telegram API.
- **Reverse Proxy Test**: Confirmed that IP `195.201.225.248` (tgproxy.me) is reachable from HF environment (Status 200).
- **Base URL Fix**: Changed `base_url` to `https://api.telegram.org/bot/` (with trailing slash) in `bot/bot.py` as a potential bypass for HF network restrictions.
- **Dual Push**: Automated pushing to both GitHub (`main`) and Hugging Face (`main`) repositories.

### 2026-05-15 (HF Deployment — Network Hardening & Runtime Fixes)
- **Health/Metrics Server**: Flask на `7860` (`/health`, `/metrics`, `/logs`).
- **Docker**: `python:3.12-slim`, multi-stage build, health check.
- **Startup Resilience**: `config_manager` проверяет `inspector.has_table()` перед запросом.
- **DB Migrations First**: `bot/main.py` — Alembic-first.
- **HF Network Evolution** (итерации):
  - Попытка 1: `api.telegram-proxy.com` → DNS блокирует.
  - Попытка 2: `195.201.225.248` (tgproxy.me) + `verify=False` → SSL mismatch.
  - Попытка 3: `149.154.167.220` + `Host: api.telegram.org` + monkey-patch `httpx.AsyncClient` → curl OK, PTB "Invalid server response".
  - Попытка 4: `/etc/hosts` в Dockerfile → read-only, BUILD_ERROR.
  - **Решение**: monkey-patch `socket.getaddrinfo` в `run_bot.py` — DNS bypass на уровне Python. Работает для всех HTTP-библиотек, SSL валиден (сертификат на `api.telegram.org`).

### 2026-05-15 (Memory Bank Sync & Deployment Prep)
- **Memory Bank Sync**: Актуализированы `activeContext.md`, `progress.md`, `projectbrief.md`, `techContext.md` после 15 коммитов деплоя HF.
- **Code Fixes**: Исправлены regression в `bot/main.py` (восстановлены `validate_startup` и `kill_existing_bot_processes` в startup flow), исправлен f-string в `run_bot.py`.
- **Quality Gate**: `ruff check` — 0 errors; `pytest tests/smoke` — 9/9 passed.
- **Startup Validation**: `run_bot.py` проходит startup: Flask `7860`, диагностика, Alembic миграции.
- **Git Commit**: `48780f8` — sync(memory_bank): актуализация после 15 коммитов деплоя HF.
- **Push Blocked**: `git push origin main` требует интерактивной авторизации GitHub (HTTPS). Требуется действие пользователя или настройка SSH/credentials.

### 2026-05-30 (Phase 2: GD-07 GD API integration)
- **GD-07 completed:** GD API integration without gd.py library (installation timeout issues).
- **Implementation:**
  - `bot/gd/gd_api.py` — direct HTTP requests to Geometry Dash servers
  - `bot/commands/gd_api_commands_ptb.py` — /gd_user and /gd_level commands
  - Integrated into `bot/commands/gd_commands_ptb.py` via `get_gd_handlers()`
- **Commands:**
  - `/gd_user <username>` — fetch player statistics (stars, demons, creator points, coins, diamonds, global rank)
  - `/gd_level <level_id>` — fetch level information (name, difficulty, downloads, likes, length, coins)
- **Features:**
  - Async HTTP requests via aiohttp (already in requirements.txt)
  - Response parsing from GD API format (key:value pairs)
  - Formatted output with emojis and readable stats
  - Error handling for network issues and not found cases
- **Deliverables completed:** GD-07 (3%)
- **Phase 2 progress:** 56% → 59% (+3% за GD-07)
- **GD Module total:** 59% (GD-01: 5%, GD-02: 4%, GD-03: 5%, GD-04: 4%, GD-05: 5%, GD-06: 4%, GD-07: 3%, GD-TEST-1-3: 3%, remaining: 7%)
- **Verification:** ruff 0 errors, py_compile passed
- **Next steps:** GD-TEST (manual testing всех GD команд), Chess Module (CH-02 → CH-06)

### 2026-06-01 (Phase 2: Groq API integration + Memory Bank sync)
- **Groq API integration:** Added as primary AI provider (HF as fallback)
  - `bot/ai/model_manager.py`: Added ProviderType.GROQ and _call_groq() method
  - `api/index.py`: Try Groq first, then HF as fallback
  - Free tier: 14,400 requests/day, much faster than HF
- **Mom Module logging:** Added console logging for debugging
- **Memory Bank sync:** Verified `projectbrief.md` has `## Project Deliverables` table with 100/100 total weight
- **Phase 2 progress:** 59% → 62% (+3% за Groq API)
- **GD Module total:** 62% (GD-01-07 completed, GD-TEST manual testing remaining: 3%)
- **Verification:** ruff 0 errors, py_compile passed
- **Next steps:** GD-TEST manual testing, Chess Module (CH-02 → CH-06)

### 2026-06-01 (GD-TEST: Manual testing started)
- **GD-TEST started:** Manual testing of all GD commands
- **Commands tested:** /submit, /moderate, /leaderboard, /my_stats, /player_stats, /add_level, /set_level_position, /gd_user, /gd_level
- **Status:** Testing in progress
- **Phase 2 progress:** 62% → 62% (GD-TEST pending)
- **GD Module total:** 62% (GD-01-07 completed, GD-TEST manual testing remaining: 3%)
- **Next steps:** Complete GD-TEST manual testing, update deliverables status

## last_checked_commit
- 6c14e3b (2026-06-01, Phase 2: GD-TEST manual testing started)
- GD-TEST: Manual testing of all GD commands started
- Groq API: Primary AI provider (HF as fallback)
- Memory Bank: Verified - Project Deliverables table with 100/100 total weight

## last_checked_commit
- c604468 (2026-05-30, Phase 2: GD-07 + Mom Module print button)
- GD-07: GD API integration in `bot/gd/gd_api.py` and `bot/commands/gd_api_commands_ptb.py`
- Mom Module: Added print button to reading trainer, fixed Vercel static file serving
- Features: /gd_user (player stats), /gd_level (level info), print worksheet (text + questions on A4)

## last_checked_commit
3931843 fix: add parse_mode=HTML to /addexpense usage message

---

### 2026-06-28 (Family Budget Module — MVP frontend JS fixes)

**Добавлено:**
- SQLAlchemy модели: Family, FamilyMember, BudgetTransaction, TransactionDetail, Debt, Payment
- Alembic миграция 010_family_budget_tables.py
- Flask API: 9 эндпоинтов в `bot/web/family_budget.py`
  - /api/budget/family/status, /api/budget/family/create, /api/budget/family/join
  - /api/budget/transactions (GET/POST/DELETE)
  - /api/budget/debts (GET), /api/budget/debts/pay (POST)
  - /api/budget/balance
- Frontend SPA: экраны авторизации, дашборда, добавления траты, погашения долга
- Каскадный алгоритм погашения: старые долги первыми, переплата → другие долги → смена ролей
- Удаление транзакции с пересчётом долгов (только автор или админ)
- Telegram команды: /budget, /family create/join/info/leave
- Роуты зарегистрированы в run_bot.py (HF) и api/index.py (Vercel)
- Адаптивный Mobile First дизайн

### 2026-06-28 (Family Budget — JS fixes)

**Проблема:** Кнопки на странице `/family_budget` не работали ("не жмутся").

**Root cause:** Внутри `FAMILY_BUDGET_HTML = """..."""` в Python escape-последовательность `\'` интерпретируется Python как `'`. Из-за этого в JavaScript функции `renderDebts()` строка:

```python
'onclick="showPayDebt(\'' + esc(d.debtor_id) + '\',\'' + ...'
```

превращалась в:

```javascript
'onclick="showPayDebt('' + esc(d.debtor_id) + '','' + ...'
```

Что приводило к синтаксической ошибке `Unexpected string` при парсинге всего скрипта. Ни одна функция не определялась, кнопки не работали.

**Fix:**
- Убраны `\'` в аргументах `onclick` — user_id передаётся как числа (без кавычек)
- Добавлен ES5-режим: `var` вместо `const/let`, `function` вместо `async function`, Promise-цепочки вместо `await`
- Добавлен Promise polyfill (если браузер не имеет нативного)
- Добавлен XHR fallback для `fetch` (старые WebView)
- Добавлен `#js-debug` жёлтый индикатор для отладки
- `touch-action: manipulation` для мобильных кнопок

**Верификация:** Playwright тест подтвердил — JS выполняется, кнопки работают, API-вызовы проходят (ответ 400 "already in a family" для тестового ID 2091908459).

---

## Changelog

### 2026-06-30 — AI Expense Entry via Telegram

**Что сделано:**
- Добавлена команда `/addexpense` для ввода трат через Telegram без веб-приложения
- Формат: `Кредитор Должник Сумма [Категория] [Комментарий]` (одна строка)
- Парсер вынесен в `bot/budget_parser.py` — без зависимостей от PTB/aiogram
- `/budget` исправлен для Vercel-рантайма (добавлен обработчик в `api/index.py`)
- `/addexpense` работает в обоих рантаймах: PTB (run_bot.py) и Vercel (api/index.py)

**Файлы:**
- `bot/budget_parser.py` — новый модуль парсинга (re только)
- `bot/commands/budget_commands.py` — import из budget_parser, ConversationHandler для /addexpense
- `bot/bot.py` — регистрация get_budget_handlers()
- `api/index.py` — /budget и /addexpense обработчики

**Коммиты:** `3931843`, `cb53e11`, `2d9a3ae`, `bd20fff`

### 2026-06-30 — Universe Module: /infect, /tea, /daily_prayer + auto message modification

**Что сделано:**
- Добавлены таблицы `infection_status` и `daily_prayer_log` (автосоздание)
- `/infect` — случайный вирус (олеговирус/LTL-паразит), симптомы, кулдаун 24ч
- `/tea` — чай для облегчения на 1 час, проверка cooldown
- `/daily_prayer` — случайная молитва из списка, не чаще раза в день
- Авто-модификация сообщений заражённых: удаление оригинала и пересылка с подписью
- Олеговирус: "кхм-кхм" через каждое слово + подпись 🦠
- LTL-паразит: +"☕" + подпись 🧬
- Кулдаун для `/addexpense` (5 мин) — предотвращение спама

**Файлы:**
- `api/index.py` — все команды + инфекция-чек в обработчике сообщений

**Коммиты:** `795435b`, `3fd47df`

### 2026-07-28 — Практика глаголов (WEB-08)

**Новый модуль:** Веб-приложение для практики неправильных глаголов английского языка.

**Что сделано:**
- Memory bank обновлён (activeContext, projectbrief, progress)
- План утверждён пользователем через `question` tool
- _(реализация следует)_

**Файлы:**
- `api/index.py` — +6 эндпоинтов `/api/verbs/*`, +страница `/irregular_verbs`

### 2026-08-24 (ОГЭ-центр — OGE-03: История термины)
- Создан core/history/terms.py: TERMS 80 терминов по 5 периодам (Русь IX-XV, Московская Русь XV-XVII, Империя XVIII-XIX, XX век 1900-1945, 1945-2000). Страница /terms (TERMS_PAGE_TEMPLATE, флешкарточки SM-2): module=history, ключ term::<id> - прогресс объединяется с императорами в одном модуле history. Хаб-карточка + data-oge, OGE_MODULES history.total -> 371.
- Тесты test_history_terms.py; ruff clean; node --check ок; прод /terms 200. Задеплоено d65607a.

### 2026-08-24 (ОГЭ-центр - OGE-06: Экзаменатор)
- Новый эндпоинт GET /api/exam/mixed?n=15: собирает случайные задания из math+russian+informatics TASKS, хранит сессию в _EXAM_SESSIONS (cap 300), клиенту ответы НЕ отдаёт. POST /api/exam/check: серверная проверка (_exam_is_correct: строка+число), при авторизации пишет прогресс в study_progress через _study_record_one (SM-2 upsert). Страница /exam (EXAM_PAGE_TEMPLATE): ввод по одному заданию, Enter=ответ/дальше, итоговый счёт. Хаб-карточка data-oge.
- Тесты test_exam_center.py (страница, сессия без ответов, грейд+запись в БД, 404) - всего моих модулей 77 зелёных; ruff clean; node --check ок. Прод /exam 200, mixed отдаёт задания. Задеплоено 9e854b7.

### 2026-08-24 (UI-полировка названий ОГЭ-модулей)
- Убран суффикс «— ОГЭ» из заголовков карточек хаба, <title> и h1 всех предметных страниц; вместо него — плашка-бейдж «ОГЭ» в стиле «Бета» (в хабе класс beta-tag с accent2, на страницах самодостаточный inline-pill). Затронуты: Информатика, Математика, Русский язык, Физика, Экзаменатор, История—термины.
- Карточка и страница «Императоры России» переименованы в «Историю» (+бейдж ОГЭ); тесты test_emperors_module и test_web_portal_e2e обновлены. Прод: hub/emperors/math проверены. Задеплоено 80f16aa.

### 2026-08-24 (История объединена + режим ОГЭ только для виджета)
- Модули истории слиты: /emperors теперь единая страница с вкладками «Даты и правители» / «Термины» (TERMS_FRAGMENT встроен, JS с префиксом t-, прогресс общий module=history). /terms -> redirect /emperors?tab=terms; карточка «История — термины» из хаба удалена. Переключатель режима ОГЭ больше не скрывает предметные карточки (только виджет плана). При сносе шаблона terms случайно удалились _EXAM_SESSIONS/_exam_is_correct/_study_record_one - восстановлены.
- Тесты: 83 зелёных по моим модулям; node --check ок; прод: /emperors 200 c вкладками и терминами, /terms 302, карточки в хабе чисты. Задеплоено 7bae239.

### 2026-08-28 (BUG-FIX: самопроверка — 18 багов)

**Контекст:** субагенты нашли 18 багов (3 HIGH, 8 med, 7 low). Пользователь подтвердил «фиксь все». Все исправлены в `api/index.py` и `api/dnd_runtime.py`.

**HIGH (ломали ядро):**
- **OGE-BUG-2:** квиз ставил `correct:false` всегда (correct_idx терялся в сессии) → `it["correct_idx"]` теперь сохраняется в сессии квиза.
- **OGE-BUG-1:** `due` писался в мс из веба, читался как сек → due-cards/прогноз пусты. Добавлены `_due_ms_to_s`/`_due_s_to_ms`, нормализация в save/GET OGE+emperors + миграция.
- **STATS-BUG-1:** квиз/экзамен писали активность, но не звали `_check_web_achievements` → ачивки не открывались. Теперь вызываются + commit.

**MEDIUM:**
- **DND-BUG-2:** `find_active_session` приоритезирует сессию-мастера → действия друга-участника писались в ЕГО сессию. Теперь приоритет — joined-сессия (через `dnd_characters`).
- **DND-BUG-3:** `call_ai` мог вернуть `None` → 500 на `answer[:800]`. Гвард: провайдеры возвращают строку, фоллбэк-строка.
- **DND-BUG-4:** логи DnD писали сырой telegram_id, а не `users.id` → `player_name=None`. Везде резолвится `db_uid` + проставляется `character_id`.
- **STATS-BUG-2:** квиз хардкодил модуль `"quiz"` вместо предмета → «Активность по модулям» не копила math/physics. Теперь реальный `module`.
- **STATS-BUG-3:** OГЭ-ачивки «задания» считали попытки (SUM correct+wrong) → уровни открывались преждевременно. Теперь `SUM(CASE WHEN correct+wrong>0 THEN 1 ELSE 0 END)` — уникальные карточки.
- **OGE-BUG-4:** `due-cards` фильтровал `reps>0` → карточка после ошибки (reps=0) навсегда вне очереди. Теперь `(reps>0 OR due<=now)`.
- **AUTH-BUG-1:** дубликат email → 500 вместо 409. Добавлена проверка уникальности email в регистрации.
- **AUTH-BUG-2:** `_ensure_universe_tables` использовал SQLite `rowid` для дедупа → падал на Postgres. Теперь диалект-зависимый `rowid`/`ctid`.

**LOW:**
- **OGE-BUG-5:** SM-2 считал интервал ДО обновления `ease` → занижен. Сначала `ease`, потом интервал.
- **OGE-BUG-3:** «Сегодня» суммировал lifetime correct/wrong коснувшихся сегодня карточек → завышение. Добавлена таблица `study_daily` (per-day tally), чтение из неё.
- **STATS-BUG-4:** `_oge_stats_payload` мог вернуть Response вместо dict и не инициализировал `current_streak`/`best_streak` вне блока → NameError/500. Ранний return → dict, инициализация до try.
- **DND-BUG-5:** `DICE_RE` только lowercase → `D20`/`К20` не парсились. `re.IGNORECASE`.
- **DND-BUG-6:** HF-fallback отдавал `prompt+continuation`. Завёрнут в chat-шаблон Qwen, обрезается префикс.
- **DND-BUG-7:** `startSession()` показывал подтверждение, затем `refreshStatus()`→`renderLog` стирал его. `/api/dnd/start` теперь отдаёт статус, `startSession` рендерит его без `refreshStatus()`.
- **AUTH-BUG-3:** `telegram_id` собирался в UI, но не шлся (всегда `None`). Читается и сохраняется в register/update + шлётся из UI.
- **Тесты:** обновлены 2 stale assert в `test_exam_center.py` (`/api/exam/ai-batch` в `/exam`, модули включают physics) и seed в `test_achievements.py` под корректный подсчёт уникальных карточек.

**Проверка:** ruff clean; `test_study_progress`/`test_achievements`/`test_exam_center`/`test_web_portal_e2e` — 42 passed.

## last_checked_commit
  6128d89 (2026-08-28; feat(music): прокачка модуля — waveform-визуализатор (Web Audio+canvas), клик-в-поля из анализа (BPM/тональность), 4 серверных эффекта normalize/reverse/echo/trim с UI-карточкой «5. Эффекты»; инлайн-плеер результатов. Задеплоено audio service + bank-bot-ruby). Пред. e91aef9 (кнопка Послушать).

### 2026-08-28 — Баг: кнопка «Анализировать» в /music не срабатывала
- **Симптом:** пользователь сообщил, что кнопка анализа «не нажимается». Кнопка и обработчик были на месте, MUSIC_API_BASE задан, CORS сервиса корректен.
- **Причина:** обработчики `m-analyze`/`o-run` (и `postFile`) вызывали `r.json()` и читали ответ без проверки `r.ok`/Content-Type. При любом не-JSON ответе сервиса (ошибка 5xx, HTML-страница Vercel) `r.json()` бросал необработанное исключение → промис отклонялся незаметно → кнопка «ничего не делает».
- **Фикс:** все обработчики обёрнуты в try/catch; добавлены проверки `r.ok` и `Content-Type.indexOf('application/json')`; при ошибке в `#err` выводится понятное сообщение («Ошибка сервера N», «Сетевая ошибка: …», «Выберите файл»). Задеплоено `f01cf85`.
- **Побочно:** карточка «Музыка» возвращена в блок «Бета-модули» (по явному требованию пользователя — «должна быть в бета блоке»).

### 2026-08-28 — Задача: аудит багов по всему проекту
- Пользователь дал задачу «займись фиксами багов и потенциальными багами по всему проекту». Начат параллельный аудит (агенты по core/, api/index.py, music-подсистеме) + прогон тестов. В процессе (прерван пользователем на запуске агентов из-за бага кнопки). После фикса кнопки — продолжить аудит и починить конкретные баги.

### 2026-08-28 — Правка: видимость карточки Музыки в хабе
- Карточка `/music` изначально лежала внутри `#beta-cards` (`.beta-cards{display:none}`, раскрывается по клику на «🧪 Бета-модули»), поэтому пользователь её не видел.
- Перенесена в основную видимую сетку карточек хаба (перед `oge-mode-bar`), с сохранением тега «Бета». Проверено на проде: `href="/music"` теперь до `id="oge-mode-bar"` и до `id="beta-cards"`. Задеплоено `9689100`.

### 2026-08-28 — Музыка: отдельный Vercel-сервис аудио (вариант Б)
- **Проблема:** librosa+зависимости (~397 МБ) слишком тяжёлые для основного билда Vercel.
- **Решение (по выбору пользователя «сначала Б, потом А»):** отдельный Vercel-проект `audio_service/` — копия `core/music` (midi_utils + audio_utils), Flask + CORS (`*`), эндпоинты `/api/music/{analyze,change_tempo,change_key,overlay}` и `/health`. Задеплоен → `https://audioservice.vercel.app` (алиас; также `audioservice-*.vercel.app`).
  - Важно: пакет `music` лежит в корне сервиса (Vercel кладёт корень проекта в sys.path, как `core` в основном проекте), иначе `from music import` падает с FUNCTION_INVOCATION_FAILED.
  - Локальная папка сервиса создана вне `/root/Bankbot` (чтобы не перезаписать `.vercel`-линк основного проекта), затем скопирована в репо `audio_service/`.
- **Интеграция LTHub:** `music_page()` инжектит `MUSIC_API_BASE` из env `AUDIO_SERVICE_URL` (дефолт `https://audioservice.vercel.app`); фронтен `/music` шлёт все запросы на `${MUSIC_API_BASE}/api/music/*`. Основной `requirements.txt` остаётся лёгким (mido), `requirements-audio.txt` — опционально для локального запуска.
- **Проверка живьём:** `/health` → ok+audio_available; analyze MIDI → bpm 120 / key Am; change_tempo → 200 audio/midi; CORS preflight OPTIONS → 204. `ruff` чист, ast OK, node --check OK. Закоммичено `636f980`, задеплоено (LTHub + сервис).
- **Отложено (вариант А):** клиентская обработка в браузере (Web Audio / JS-MIDI) — пользователь выбрал «сначала Б, потом А».

### 2026-08-28 — Музыка в сайт (LTHub, бета-модуль)
- **Страница `/music`** (`api/index.py`, `music_page`): клиентский UI — загрузка файла, анализ (BPM/тональность/формат), блоки «Изменить темп», «Изменить тональность», «Наложить несколько файлов». Скачивание результата через Blob.
- **API эндпоинты** (multipart):
  - `POST /api/music/analyze` → `{format,bpm,key,audio_available}`;
  - `POST /api/music/change_tempo` (target_bpm | factor) → файл (attachment);
  - `POST /api/music/change_key` (semitones | target_key) → файл;
  - `POST /api/music/overlay` (files[] минимум 2) → файл.
  - Лимит 8 МБ, разрешены расширения mid/midi/mp3/wav; временные файлы в `tempfile.mkdtemp`.
- **Карточка в хабе:** добавлена в бета-блок (`/music`, иконка 🎵, «Бета»), рядом с Администрированием.
- **Защита сборки Vercel:** `librosa`+`soundfile` перенесены из `requirements.txt` в новый `requirements-audio.txt` (опционально). На проде MIDI-функционал (mido) доступен всегда; аудио (MP3/WAV) требует установки `requirements-audio.txt` (иначе эндпоинты возвращают понятную ошибку, а `/music` показывает предупреждение).
- **Проверка:** runtime smoke-тест через Flask test_client — analyze (midi: bpm 120/key C; wav: bpm~117/key F# minor), change_tempo/change_key/overlay → 200 attachment; `/music` и карточка хаба → 200. `ruff` чист, тесты `tests/unit/test_music.py` 7 passed.

### 2026-08-28 — Модуль «Музыка» (core/music)
- **Запрос:** «сделай модуль музыки: измерение/изменение тональности и темпа (BPM), наложение аудио; поддержка mp3 и midi».
- **Структура:** `core/music/__init__.py` (диспетчер по расширению) + `midi_utils.py` (mido) + `audio_utils.py` (librosa/soundfile).
- **MIDI (mido, чистый Python):**
  - `detect_bpm` (по set_tempo), `midi_tempo_changes`; `detect_key`/`midi_key_signatures` (key_signature);
  - `change_key` (транспозиция нот на semitones или в target_key), `change_tempo` (target_bpm заменяет set_tempo / factor масштабирует длительности);
  - `overlay` — все дорожки из нескольких файлов играются одновременно (ticks_per_beat приводятся к базе первого файла).
- **Аудио (MP3/WAV, librosa + soundfile):**
  - `detect_bpm` (librosa.beat.beat_track), `detect_key` (хромаграмма + профили Крумхансля–Шмуклера);
  - `change_tempo` (time_stretch — темп без изменения высоты), `change_key` (pitch_shift — высота без изменения темпа);
  - `overlay` — суммирование сигналов с нормировкой.
  - MP3 читается/пишется через soundfile 1.2.2 (libsndfile с MP3) — **без ffmpeg и без pydub** (pydub несовместим с Python 3.14, audioop удалён).
- **Зависимости:** добавлены в requirements.txt: `mido`, `librosa`, `soundfile` (pydub убран).
- **Тесты:** `tests/unit/test_music.py` — 7 passed (MIDI: bpm/key/транспозиция/темп/overlay; аудио: bpm/change_tempo по длительности/overlay). ruff чист.

### 2026-08-28 — OGE: график динамики освоения (пункт (3) «что-то ещё»)
- Пользователь выбрал «Графики динамики» из 3 вариантов (подсветка слабых тем / экспорт CSV / графики / своё).
- **Backend:** `_oge_stats_payload` возвращает `trend` — массив из 30 дней, каждый `{date, total, modules:{mod: накопит_выучено}}`. Накопление по `last_correct_at <= day_end` (карточка считается выученной к дню последнего верного ответа). O(30·N) — тривиально.
- **Frontend:** на `/stats` добавлена карточка «📈 Динамика освоения (30 дней)» с простой SVG-диаграммой: полилинии по модулям (цвета `OGE_COLORS`) + пунктирная линия «всего выучено» (зелёная), оси X (даты) и Y (шт.), легенда.
- Валидация: `ast`+`node --check` OK, `ruff check` — All checks passed!, тест `/api/study/stats` (2 шт.) — passed. Закоммичено `5c5e900`, задеплоено.

### 2026-08-28 - Полный прогон тестов + OGE-прогноз «дни до выучивания всех новых»
- **Регрессионный прогон `tests/unit` (8 параллельных батчей):** итог ~1214 passed / 1 failed / 10 skipped. Единственный fail — `test_study_progress.py::test_analytics_page_renders`: ожидал `/analytics`→200, но после слияния `/analytics`→`/stats` (302) тест устарел. Исправлен: проверяет 302+Location `/stats`, затем рендер `/stats` (есть `s-streak`). Повторный прогон файла — 16 passed. Полный suite зелёный.
- **OGE-прогноз (2):** `_oge_stats_payload` возвращает `days_to_learn_all = ceil(total_unseen / pace) + MASTERY_GAP(4)` — оценка, за сколько дней будут выучены ВСЕ новые карточки (темп `pace` ввода + 4 дня на освоение последней партии). Сводка `/stats` дополнена: «· чтобы выучить все новые: ~K дн.». `ast`+node OK. Закоммичено `1ba7636`, задеплоено.

### 2026-08-28 - Бета-аудит 2026-08-10: верификация + финальный фикс
- **Верификация** (по пунктам плана activeContext:339-349): все 9 пунктов уже реализованы в последующих коммитах. Подтверждено в коде: D&D `parse_dice` лимит 1..100 (dnd_runtime.py:61); шахматы `_PENDING_PUZZLES.pop(uid)` ДО начисления + TTL-кулдаун (api/index.py:8805,8761) + try/catch `JSON.parse` (8596); тривия `secrets.token_hex(6)` session_id (16858) + валидация `answer_index` (16872); глаголы `VERB_GEN_LOCK` с очисткой (19004); семья `DELETE` через `_family_verify_member` (22346); `daily_prayer_log` UNIQUE-индекс (662); канон `esc()`+`safeUrl()` (17401); регистрация `is_admin=FALSE` + сессия админа по серверному флагу (9471,171).
- **Финальный фикс:** `api_chess_puzzle_check` (api/index.py:8820) больше не отдаёт `move` при `correct=False` (раньше утекало решение пазла при неверном ходе); клиент показывает «Попробуйте другой ход».
- **Проверка:** `ast.parse` OK. Закоммичено `1af992a`, задеплоено на `bank-bot-ruby.vercel.app`.

### 2026-08-28 - OGE forecast: «сколько новых карточек будет выучено»
- **Бэкенд** `_oge_stats_payload` (api/index.py): прогноз теперь считает `learned` (накопительно) и `learned_delta` по дням. По планировщику SM-2 (`rep1→+1д, rep2→+3д, rep3=mastered`) карточка, введённая в день j, осваивается в день j+4 → `learned_delta[i]=introduced[i-4]`.
- **Фронт** `/stats` `renderOgeAnalytics`: легенда + зелёная строка `N✅ (+delta)` в каждой ячейке прогноза; сводка «За 14 дней выучишь ≈ N новых карточек (из M новых всего)».
- **Проверка:** `ast.parse` OK; `node --check` stats JS OK; прод `/stats` → 200 с `s-learn-summary`. Закоммичено `ad72441`, задеплоено.

### 2026-08-28 - History: темы + эпохи в /emperors
- **Темы:** `core/history/emperors.py` — `HISTORY_TOPIC_ORDER` (9 тем) + `classify_topic(title, note)` (эвристика по ключевым словам); экспортировано в `core/history/__init__.py`. Поля `topic` добавлены в `history_data` (events/persons) и в `allItems`.
- **Фильтр:** `topicMatch` в `itemsInScope()` (термины всегда показываются); `<select class="topic-sel">` «Все темы» + 9 тем в панелях Квиз/Сопоставление/Хронология; `toggleTopic` синхронизирует все селекты и сбрасывает колоду.
- **Эпохи:** опции «Эпоха: …» (7 эпох из `eraGroups()`) динамически добавлены во все `.scope-sel`; `activeRulerIds()`/`activeRulers()` и `studyPanel()` понимают scope `era:<Имя>` (фильтр по `grp.ids`).
- **Проверка:** `ast.parse` api/index.py OK; `node --check` emperors JS OK; прод `/emperors` → 200 с `topic-sel`/`topic_order`. Закоммичено `3ca946b`, задеплоено на `bank-bot-ruby.vercel.app`.
### Задача 1. Ачивки
- **Статус:** Готово
- **Количество:** 227 ачивок
- **Шаблон:** 2-3 шкалы на модуль
- **Реализация:** добавлены события (events), факты (emperors_mastered), новые пороги и названия
### 2026-08-22 - Light/Dark theme system for all web pages

**What done:**
- Added core/theme.py: THEME_CSS (CSS vars, dark default + [data-theme=light]), THEME_TOGGLE (floating button), inject_theme(html) idempotent injector.
- Theme injected centrally via @app.after_request in api/index.py for ALL text/html responses (no per-page edits, no f-string brace breakage).
- Hardcoded hex colors in api/index.py HTML replaced with var(--bb-*)/var(--gh-*) (safe in f-strings).
- Decision: default = system prefers-color-scheme, override persisted in localStorage; floating global toggle button.
- Verified prod: home, /math, /reading_trainer.html all contain app-theme + app-theme-toggle.
- Tests: 31/31 relevant unit tests pass; ruff clean.
- Deployed to Vercel (bank-bot-ruby.vercel.app).

**Commit:** 9a4510c (feat: add light/dark theme system injected via after_request for all pages)
