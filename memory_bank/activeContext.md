# Active Context

**Последнее обновление:** 2026-08-16  
**Текущая фаза:** Ребрендинг BankBot → LTHub (LucasTeam Hub)  
**Последнее действие:** модуль «Императоры России» — важность 1–5 + расширенный режим «Все правители» (Рюрик–Путин)

## Модуль «Императоры России» /emperors (2026-08-13)

- **Повод:** пользователь завтра играет в игру «сопоставь имена/события с императорами России» и плохо знает историю. Прислал полные списки событий (хронологическая лента по царствованиям) и личностей (5 рядов плаката).
- **Данные:** `core/history/emperors.py` — `EMPERORS` (5, годы правления), `EVENTS` (48, `(year, title, emperor_id, note)`), `PERSONS` (42, `(name, emperor_id, description)`). У всех есть краткое описание для подсказок. Решение пользователя: «найди маппинг личностей в источниках» — сделано по пикам славы/главным достижениям.
- **Страница:** `/emperors` в `api/index.py` — вкладки «📚 Изучить» (карточки периодов с цветными чипами, описания в tooltip) и «🧠 Тренажёр» (вопрос → 5 императоров, подсветка + 📎 описание при проверке, счёт `emperors_score`, режим «только ошибки» `emperors_wrong` в localStorage, сброс). Без БД: данные внедряются как JSON при рендере (`history_data`).
- **Хаб:** карточка «Императоры России» в бета-блоке (`/` → `/emperors`).
- **Маппинг личностей (согласован):** Александр I — Кутузов/Барклай/Крузенштерн/Лазарев/Карамзин/Грибоедов; Николай I — Пушкин/Пестель/Нахимов/Тон/Зинин; Александр II — Достоевский/Горчаков/Менделеев/Толстой/Герцен/Айвазовский/Монюшко/Нобель/Дарвин; Александр III — Чайковский/Боткин/Мечников/Ван Гог; Николай II — остальные 17 (включая ряд 5 учёных и иностранцев).
- **Тесты:** `tests/unit/test_emperors_module.py` (11), `/emperors` в `test_web_pages_render`. Полный `tests/unit` **984 passed / 10 skipped**; ruff clean; `node --check` JS ок. Задеплоено на прод (Ready). Не закоммичено.
- **Итерация 2 (по фидбеку):** год события убран из вопроса тренажёра (кнопки показывают годы правления, год «сдавал» ответ); вопросы — из перемешанной колоды, при ошибке элемент возвращается в колоду + wrongItems → ошибки повторяются чаще.
- **Итерация 3 (2 алгоритма):** переключатель в тренажёре — «Классика (колода)» (итерация 2) и «Флешки (интервалы)» (SM-2: `localStorage['emperors_flash']` = `{reps, interval, ease, due}`, пул = due<=now, верно→интервал растёт, ошибка→сброс+возврат в пул; экран «Все карточки изучены на сегодня!»; счёт показывает «· к изучению: N»). Выбор в `localStorage['emperors_algo']`; «Сбросить счёт» чистит flash. Задеплоено.
- **Итерация 4 («Всё по максимуму»):** бэкенд-прогресс в БД (`emperors_progress` + `/api/emperors/progress` GET/POST/reset, привязка `_web_user_id`, JS debounce `pushFlash` + merge при загрузке); умные «Флешки» (приоритет по due, чередование типов/императоров); статистика и топ ошибок по императорам + прогресс-бар; вкладка «Сопоставление» (разложить карточки по императорам); UX: клавиатура 1-5/Enter, кнопка «💡 Подсказка». Полный `tests/unit` **987 passed / 10 skipped**, ruff clean, `node --check` ок. Задеплоено на прод (Ready), API проверен. Не закоммичено.
- **Итерация 4.1 (дебаг):** кнопка «🔧 Дебаг» → полупрозрачная панель в углу со всеми карточками и их SM-2-данными (reps/interval/ease/due/✓/✗), просроченные помечены ⏰ и идут первыми. Задеплоено.
- **Итерация 4.2 (приоритет флешек):** `pickFlash` приоритет 1) ошибочные (wrong>0), 2) новые (нет записи), 3) обычные повторы; внутри — по due. Задеплоено.
- **Итерация 4.3 (3-й алгоритм «Счётчик»):** counter (+1/−1 на ответ), выбор с весом выше у низкого counter. Все 3 алгоритма пишут единые данные в БД (`recordAnswer` — counter + SM-2 + correct/wrong всегда), выбор алгоритма = только метод подбора. Колонка `emperors_progress.counter`. Задеплоено, API проверен.
- **Итерация 4.4 (прогресс привязан к аккаунту):** GET/POST `/api/emperors/progress` резолвят uid только из сессии (`_get_session_user` + `_auth_token_from_request`); без валидного токена GET возвращает пустые cards, POST → 401. JS: `pushFlash`/загрузка/reset слают `X-Auth-Token` только если `localStorage.web_token` есть; без токена прогресс живёт только в localStorage. Прогресс синхронизируется между устройствами через аккаунт. Тест обновлён (token-based + анонимные кейсы 401/пусто). Задеплоено, прод проверен.
- **Итерация 4.5 (описания во вкладке «Изучить»):** чипы событий/личностей кликабельны (`data-type`/`data-text`, `app.showInfo(this)`), модалка `#info-modal` показывает описание (`note`/`description`), год и императора цветом. Закрытие ✕/по фону. Задеплоено.
- **Итерация 4.6 (важность 1–5 + расширенный режим):** `HistoryEvent`/`Person` получили `importance` (1–5, по умолчанию 3); добавлен `RULERS` — ~33 правителя от Рюрика до Путина (включая советских и Путина). Ключевые правители (Владимир, Ярослав, Иван III, Грозный, Пётр I, Екатерина II, Сталин и др.) получили больше событий/личностей (4–9 событий, 3–6 личностей, включая мировых деятелей), второстепенные (Игорь, Ольга, Калита, Годунов, Павел I) — 1–3 события, 1–2 личности. Итого 157 событий / 119 личностей. На странице: переключатель `#scope-select` «5 императоров / Все правители» (в `localStorage['emperors_scope']`), всё фильтруется по scope; importance влияет на выбор во «Флешках» (сортировка) и «Счётчике» (вес = база×importance); звёзды важности в чипах «Изучить» и модалке. Цвета правителей — `PALETTE` (33 цвета, по индексу). Тесты обновлены (18), ruff clean, `node --check` ок, задеплоено, прод проверен. Не закоммичено.
- **⚠️ Грабли:** `\n` внутри JS-кода в Python-строке страницы надо писать `\\n` — иначе Python превращает в реальный перенос строки и JS падает («Invalid or unexpected token»).

## Фиксы багов memory bank (2026-08-13)

- **[TRIVIA-BUG-1] ПОЧИНЕНО:** всем вопросам `core/canon/questions.py` без ручных `distractors` (tracks id 4-11, 18, 24 + candy id 12-15) добавлены 3 реалистичных варианта. Вопрос id 24 — три частичных проявления Олеговируса (вокальные/моторные тики/множественные личности) из материала `explanation`. Фолбэки генераторов (web `api_trivia_question` :7588 и `_vercel_trivia_question` :4961 в `api/index.py`, а также `bot/trivia/questions.py::generate_trivia_question`) теперь берут ручные distractors при наличии. Вопросов без distractors — 0. Полный `tests/unit`: **973 passed / 10 skipped**; ruff clean.
- **[SETTINGS-BUG-1] — код готов, нужен деплой:** в рабочей копии `/settings` → 301 на `/account` (`api/index.py:6757-6759`), админ-панель на `/admin` (:7181), `account_page` :6477. Баг был вызван тем, что прод работал на старой задеплоенной версии. Фикс = задеплоить рабочую копию на Vercel.

## Объединение личного кабинета и настроек (2026-08-11)

- **`/account`** теперь единая страница «Личный кабинет»: профиль (аватар, имя, @логин, статус), 💎 монеты, форма редактирования (имя, GD, Telegram, Lichess — была на `/settings`) с кнопкой «Сохранить» (`/api/auth/update`), подсказка «Рекомендуем заполнить», «Выйти».
- **Для админов** в личном кабинете показывается кнопка «🛠 Админ-панель» → `/admin` (рендерится только при `p.is_admin`).
- **`/settings`** → редирект 301 на `/account` (старые ссылки и закладки работают).
- **`/admin`** — отдельная страница админ-панели; добавлена вкладка «💡 Предложения» (была только в embedded-панели `/settings`) с фильтрами Все/Баги/Предложения/Открытые + удаление (`loadFeedback`/`deleteFeedback`), стиль `.badge-danger`.
- Ссылки обновлены: карточка «Администрирование» на хабе `/` → `/admin`; подсказка на `/register` → `/account`.
- Всё в `api/index.py`; импорт `redirect` добавлен. Тесты `tests/unit` → **973 passed / 10 skipped**; ruff clean. Не закоммичено.

## Фиксы бета-модулей (2026-08-11)

Закрыты последние открытые пункты аудита бета-модулей:
1. **Family Circle — stored XSS в списке участников** (`api/index.py:13428`): `data.members.map(escapeHtml).join(', ')`.
2. **Шахматы — `JSON.parse` без try/catch** в `checkMove` (`api/index.py:6087`): при не-JSON ответе теперь показывается «Ошибка сервера.», кнопка не залипает.
3. **Шахматы — TTL `_PENDING_PUZZLES`**: добавлена константа `_PENDING_PUZZLE_TTL = 1800` (`api/index.py:260`) + ленивая чистка устаревших записей при выдаче нового пазла (`api_chess_puzzle`); проверка «задача устарела» в `api_chess_puzzle_check` переведена на константу.

Остальной аудит 2026-08-11 подтвердил: все ранее зафиксированные баги уже исправлены в рабочей копии (см. `progress.md`).


## Режим тестирования бета-модулей (2026-08-10)

Пользователь вручную тестирует бета-модули портала. Протокол:
- Модуль работает → пользователь просит **перенести в основной раздел** (убрать из бета-блока).
- Модуль с багом → пользователь указывает на баг, я **записываю его в memory bank** (не фикс на месте).
- Баг фиксится отдельной сессией после накопления списка.

**Статус:** отложено пользователем 2026-08-10 («нет времени сейчас тестировать»). Протокол и список зафиксированы, ждём возобновления. Первый баг [GD-BUG-1] уже записан.

**Список бета-модулей** (блок «Бета-модули» на хабе `/`, строки ~3256-3327 `api/index.py`):
1. **D&D AI Master** — `/dnd` (текстовая RPG с AI-мастером)
2. **Geometry Dash** — `/gd` (профили, топ уровней, статистика прохождений)
3. **Викторина** — `/trivia` (брейн-ринг по канону)
4. **Шахматы** — `/chess` (рейтинги Lichess, поиск игроков, пазлы)
5. **Практика глаголов** — `/irregular_verbs`
6. **Family Circle** — `/family` (семейная медиация с ИИ)
7. **Молитва дня** — `/daily_prayer`
8. **Канон** — `/canon` (полный текст, произведения, глоссарий)
9. **Администрирование** — `/admin` (пользователи, монеты, статистика, ошибки, предложения)
(Вне бета-блока: «Предложения» `/suggest` — уже в основном)

### Зафиксированные баги бета-модулей

- **2026-08-13 · Админ · [ADMIN-BUG-2] Админ-панель `/admin` пустая — ПОЧИНЕНО (2026-08-13):** **Root cause — JS syntax error в странице `/admin`:** в Python-строках, собирающих HTML через JS-конкатенацию внутри одинарных кавычек, `\'` не экранировалось для JS (`api/index.py`):
  1. `onkeydown="if(event.key===\'Enter\'){...}"` (:7320) — в Python `\'` даёт голый `'` → JS-строка `'...if(event.key==='Enter')...'` обрывается на `'Enter'` → `SyntaxError: Unexpected identifier 'Enter'`.
  2. `onclick="viewCoins(' + u.id + ',\'' + esc(u.login) + '\')"` (:7330) — Python `',\''` → JS `','` → `SyntaxError: Unexpected string`.
  3. `onclick="loadFeedback(\'bug\')"` и т.п. (:7415-7417) — то же самое.
  Весь `<script>` админки не парсился → `init()` не выполнялся → `#gate` и `#app` оставались `display:none` → панель выглядит пустой. Проверено `node --check` на прод-HTML (fail) и после фикса (OK). Остальной JS портала (страницы в тройных кавычках/raw HTML) не затронут.
  **Фикс:** `\'` → `\\\'` в 3 местах `api/index.py` (Python-эскейп `\\\'` даёт JS-эскейп `\'`). Проверки: извлечённый JS `/admin` → `node --check` OK; `/account` JS тоже OK; полный `tests/unit` **984 passed / 10 skipped**; ruff All checks passed. **Не задеплоено** — нужен деплой на Vercel.
  Ранее предполагавшаяся причина (is_admin колонка у «lucasteam») — НЕ подтвердилась; проверять её больше не нужно.

- **2026-08-11 · Настройки/Админ · [SETTINGS-BUG-1] Админ-панель совмещена с настройками (на проде) — код готов, нужен деплой:** пользователь на «Настройки» видит форму профиля И админ-панель на одной странице (Статистика/Пользователи/Начислить монеты/Ошибки/Предложения). **Root cause:** это старая версия `/settings` на проде — рефактор 2026-08-11 (объединение `/account` + `/settings` в единую страницу, вынос админ-панели на отдельную `/admin`, `/settings` → 301 на `/account`) есть в рабочей копии `api/index.py` (`account_page` :6477, `settings_page` :6757-6759, `admin_page` :7181), НО не задеплоен. **Фикс:** задеплоить текущую рабочую копию на Vercel (проверено: в рабочей копии фикс на месте, отдельная задача на деплой). *(UPD 2026-08-13: задеплоено — `/settings` → 301, `/admin` работает; остаток проблемы — см. [ADMIN-BUG-2])*

- **2026-08-11 · Тривиа · [TRIVIA-BUG-1] «Идиотские» варианты ответов — ПОЧИНЕНО (2026-08-13):** вопрос id 24 «Какие варианты проявления Олеговируса согласно статье «Olegovirus checkmarevus»?» (группа `tracks`, `core/canon/questions.py:73-79`) имел `distractors: []`. Генератор `api_trivia_question` (`api/index.py:7587-7606`): при `len(manual) < 3` фолбэк тянул `correct_text` других вопросов той же группы `tracks` → в варианты попадали названия треков/статей («Olegovirus checkmarevus» (Лука, апрель 2026), «LukasTeamLuke sp. nov.» (неканон, 🔴), «Восемь километров (походный дневник)»), никак не связанные с вопросом про симптомы → абсурдный набор. Проблема была системной: ручные `distractors` были только у групп rules/tea/ltrs/glossary; у всех вопросов `tracks` (id 4-11, 18, 24) и `candy` (id 12-15) они были пустые, фолбэк подставлял названия произведений. **Фикс:** добавлены 3 реалистичных ручных `distractors` всем вопросам без них (вопрос id 24 — по материалу `explanation`: только вокальные тики «кхм-кхм»/«бум-бум»/«тыц-тыц», только моторные тики — хлопанье в ладоши с качанием шеи, только множественные личности — Степан/Иван/Олег-диктатор); фолбэки всех генераторов (web :7588, `_vercel_trivia_question` :4961, `bot/trivia/questions.py`) переведены на ручные distractors.

- **2026-08-10 · GD · [GD-BUG-1] Веб-заявка без медиа — ПОЧИНЕНО (2026-08-10):** веб-заявка GD теперь требует прикрепить видео/фото с прохождением (multipart в `POST /api/gd/submit`, хранится как data-URL в `media_file_id`, `media_type` определяется по MIME/расширению), в `/gd` добавлено поле загрузки файла `#sub-media`, JS `submitRecord()` переведён на FormData + `xhr.timeout=30000` (+`ontimeout` возвращает кнопку — больше не «висит минуту»), модератор в `/gd` видит ссылку «🎬 Смотреть медиа» для data-URL. Тест `test_gd_web_submit_requires_media` в `tests/unit/test_web_portal_e2e.py` (БД `submissions` добавлена в `_make_engine`). Задеплоено.

- **2026-08-10 · Бета-аудит (список пользователя, целиком ниже):** пользователь провёл аудит всех 9 бета-модулей — улучшения + вероятные баги. Критичные: (1) privilege escalation в `/settings`/`/admin`, (2) DELETE `/api/family/rooms/<id>` без авторизации, (3) Stored XSS (глаголы, канон, family), (4) двойное начисление монет в шахматных пазлах, (5) DoS через `/api/dnd/roll` (count без лимита). Детальный план фиксов — ниже в «Бета-аудит 2026-08-10».

#### Бета-аудит 2026-08-10 (план фиксов)

1. **D&D — `/dnd`** `api/dnd_runtime.py:56` `parse_dice()`: нет лимита `count` — `999999d20` = ~1 млн синхронных `random.randint` → воркер Vercel зависает, вечное «Отправка...» (DoS через `/api/dnd/roll`). Фикс: `if count < 1 or count > 100: return None` (закрывает веб и бота).
2. **GD — `/gd`**: `submitRecord()` `api/index.py` — уже добавлен `xhr.timeout=30000` + `ontimeout` (из GD-BUG-1). GD-BUG-1 (медиа-флоу) — починен выше.
3. **Викторина — `/trivia`**: (a) при `q.error`/`onerror` показать кнопку «Повторить» (сейчас `#next-btn` скрыт → застревание; `api/index.py:7717,7732`); (b) ключ `_TRIVIA_SESSIONS` только по `q["id"]` без user_id — два игрока на одном вопросе перезаписывают сессию → ложный результат; фикс: ключ `f"{qid}:{secrets.token_hex(6)}"`, возвращать клиенту; (c) нет валидации `answer_index` — `"1"` → 500, `true` засчитывается как индекс 1; фикс: `isinstance(idx, int) and not isinstance(idx, bool)` → иначе 400; при неверном ответе отдавать правильный `correct_text`.
4. **Шахматы — `/chess`**: (a) try/catch вокруг `JSON.parse` в `checkMove` (`api/index.py:6082`) — не-JSON (HTML 500) навсегда блокирует кнопку «Проверить»; (b) **двойное начисление монет**: `del _PENDING_PUZZLES[uid]` идёт ПОСЛЕ `update_user_coins`; двойной клик = +10 вместо +5; фикс: `pending = _PENDING_PUZZLES.pop(uid, None)` атомарно ДО начисления; (c) решение возвращается клиенту даже при неверном ходе; нет TTL у `_PENDING_PUZZLES` (закрытая вкладка = запись навсегда → ложное «неверно»); фикс: не отдавать `first_move` при ошибке + TTL/кулдаун при выдаче пазла.
5. **Глаголы — `/irregular_verbs`**: (a) `xhr.timeout` в `generateExercise`/`submitExercise` (`api/index.py:9461`) — зависший AI = вечная «Генерация...»; (b) **Stored XSS**: `s.name` и строки ошибок в innerHTML без экранирования (`api/index.py:9526-9528`) — имя `<img onerror=...>` исполняется у преподавателя; фикс: `escapeHtml`/`textContent`; (c) `VERB_GEN_LOCK` не очищается (утечка памяти), не снимается при ошибке AI, анонимы делят ключ 0; фикс: чистить записи старше ~60 с.
6. **Family Circle — `/family`**: (a) таймаут в общем хелпере `api()` (`api/index.py:13100`) — `chat/send` и `report/generate` ходят в AI; при зависании «✏️ ИИ печатает...» бесконечно; (b) **DELETE `/api/family/rooms/<id>` без авторизации** (`api/index.py:12935`) — 6-значные id перебираются, любой удаляет чужую комнату; фикс: требовать `_family_verify_member` перед удалением; (c) имена участников в innerHTML без экранирования (`api/index.py:13325`), хотя `escapeHtml` уже есть — сохранённый XSS; фикс: `escapeHtml`.
7. **Молитва — `/daily_prayer`**: (a) при ошибке восстанавливать кнопку вместо `display:none` (`api/index.py:7869-7881`); (b) молитва не привязана ко дню — каждый «Ещё» = новая случайная; фикс: детерминированный выбор от `(today, user_id)`; (c) нет UNIQUE на `(user_id, prayer_date)` в `daily_prayer_log` (`api/index.py:584-588`) → `ON CONFLICT DO NOTHING` не работает, гонка даёт дубликаты; фикс: `CREATE UNIQUE INDEX IF NOT EXISTS uq_daily_prayer_log_user_date`.
8. **Канон — `/canon`**: (a) экранировать title/author/url в `renderWorks` (`api/index.py:8140`) — единственная точка без `esc()`; (b) **Stored XSS через заявки**: сырые title/author/url после approve в innerHTML, `json.dumps` в `<script>` без `</` → `<\/` (`api/index.py:7972,8096`); фикс: экранировать + валидировать схему URL (http/https/t.me, не `javascript:`) + `.replace("</", "<\\/")`; (c) нет валидации длины author/url → «слепой» 500 при >100 символов (`api/index.py:8330`); фикс: 400 с сообщением.
9. **Администрирование — `/settings`, `/admin`**: (a) клиентская + серверная валидация длин в `saveSettings`/`api_auth_update` (`api/index.py:7103-7144`) — превышение лимита БД = «Ошибка сервера» и потеря формы; (b) **PRIVILEGE ESCALATION (приоритет №1)**: `is_admin` вычисляется из клиентского поля `telegram_id` без проверки принадлежности — регистрация с чужим `telegram_id == ADMIN_TELEGRAM_ID` даёт полный админ-доступ (`api/index.py:7045,7128`), а `_web_admin_session` ещё и оверрайдит по этому полю (`api/index.py:166`); фикс: НИКОГДА не брать `telegram_id` из формы; права админа строго по колонке `is_admin`; привязку Telegram — только серверной верификацией; (c) `api_auth_update`/register не валидируют длины (VARCHAR(100)/64) → «слепой» 500; фикс: серверные проверки + `maxlength` в форме.

## Текущий фокус

### CANON-03 — Аудио для треков + просмотр текста для статей ✅ (завершён, 2026-08-09)

**Цель:** У треков канона должна быть аудиозапись (админ загружает, сайт показывает плеер), у статей — читаемый полный текст.

**Сделано (всё в `api/index.py` + тесты):**
- **БД:** `_ensure_canon_tables()` — колонки `audio_data BYTEA`, `audio_name`, `audio_mime`, `audio_size` (CREATE + ALTER `ADD COLUMN IF NOT EXISTS` для прод-таблицы Supabase); SQLite-зеркало в `tests/unit/test_web_portal_e2e.py::_make_engine()`.
- **Admin API (`_admin_require` → 403):** `POST /api/admin/canon/works/<id>/audio` (multipart `audio`, лимит 4 МБ `_MAX_AUDIO_BYTES`, whitelist `_ALLOWED_AUDIO_MIME` mp3/ogg/wav/m4a/aac через `_canon_audio_mime()`), `DELETE /api/admin/canon/works/<id>/audio`.
- **Публичное API:** `GET /api/canon/work/<id>/audio` — бинарный стрим (Content-Type из БД, inline, Cache-Control 1 день, 404 не-approve/без аудио). `/api/canon/works` и `/api/canon/work/<id>` возвращают `audio_name`/`audio_mime`/`audio_size`/`has_audio` (нормализация `bool()` — SQLite отдаёт 0/1).
- **Страницы:** `/canon/work/<id>` — блок `#audio` с плеером (имя + размер через новый хелпер `format_bytes()`) для треков; `/canon` — кнопка «🎧 Слушать» на карточке; `/admin/canon` — в редакторе трека поле загрузки + кнопки «⬆️ Загрузить»/«🗑 Удалить» (JS `uploadAudio`/`removeAudio`).
- **Тесты:** `tests/unit/test_canon_requests_e2e.py::test_audio_upload_stream_delete` — полный цикл загрузка→has_audio→плеер→стрим→403/400→удаление→404. Полный `tests/unit`: **972 passed / 10 skipped / 0 failed**; ruff All checks passed.

**Не закоммичено** — изменения в рабочей копии (правила AGENTS.md: коммит после подтверждения/большого блока).


**Цель:** На `/canon` должны отображаться сами канонические произведения (полный текст), любой зарегистрированный пользователь может подать «заявку на канонизацию», админ модерирует заявки и имеет право редактировать тексты произведений и основной документ канона (canon.md через БД-overlay).

**Решения пользователя (2026-08-07):**
- Тексты произведений админ вносит через интерфейс (в репо полных текстов нет, только метаданные + ссылки t.me). Сид из `core.canon.works.py` (метаданные), полный текст — админ-редактор.
- «Право изменения текста канона» = и произведения, И основной документ (canon.md через БД-overlay).
- Полный текст произведения — на отдельной странице `/canon/work/<id>`.

**План (утверждён пользователем):**

**Фаза 1 — БД-слой (`_ensure_canon_tables` в api/index.py):**
- `canon_works` — id, title, kind, author, date, canon_level, url, `content TEXT`, status (approved/pending/rejected), submitted_by, created_at/updated_at. Сид из `CANON_WORKS` при пустой таблице (status='approved', content='').
- `canon_requests` — id, user_id, title, kind, author, date, canon_level, url, content, status (pending/approved/rejected), reviewer_id, review_note, timestamps.
- `canon_doc` — overlay большого документа: id, content TEXT, updated_by, updated_at. Нет записи → каноном остаётся canon.md.
- Правило: БД-запросы обёрнуты в try/except; при недоступности БД публичные эндпоинты фолбэкуют на статику (CANON_WORKS / load_canon_text).

**Фаза 2 — Публичные API:** `GET /api/canon/works` (approved + content, фолбэк статика), `GET /api/canon/work/<id>`, `GET /api/canon/documents` (эффективный текст), `POST /api/canon/request` (auth-токен).

**Фаза 3 — Админ API (`_admin_require`):** `GET /api/admin/canon/requests?status=`, `POST /api/admin/canon/requests/<id>/approve|reject`, `PUT /api/admin/canon/works/<id>`, `GET/PUT/DELETE /api/admin/canon/doc`.

**Фаза 4 — Страницы:** `/canon` (кнопка «Читать» → `/canon/work/<id>`, кнопка «Отправить заявку», админ-кнопки), `/canon/work/<id>`, `/canon/request`, `/admin/canon`.

**Фаза 5 — Тесты:** расширить `_make_engine()` DDL, новый `tests/unit/test_canon_requests_e2e.py`, ruff + pytest, существующие тесты не должны сломаться.

**После:** деплой на Vercel, финальный memory bank, коммит.

**ИТОГ (2026-08-08):** все 5 фаз выполнены и задеплоены на https://bank-bot-ruby.vercel.app.
- БД-слой: `_ensure_canon_tables()` + вызов из `get_db_engine()` (try/except — сбой БД не роняет старт). Таблицы `canon_works`/`canon_requests`/`canon_doc` + сид 16 метаданных-произведений из `CANON_WORKS`.
- Публичные API: `/api/canon/works` (`?level=&kind=`, content), `/api/canon/work/<id>` (фолбэк статика), `/api/canon/documents` (`source: db|file`), `POST /api/canon/request` (auth, валидация title/author/content, canon_level/kind).
- Админ API (`_admin_require` → 403): requests list/approve/reject (approve → INSERT в canon_works + reviewer_id/review_note/reviewed_at), `PUT works/<id>`, `GET/PUT/DELETE /admin/canon/doc` (PUT upsert, DELETE сброс к `canon.md`).
- Страницы: `/canon` — кнопки «📩 Отправить заявку» + admin-actions, «📖 Читать» на карточках; `/canon/work/<id>` (бейджи, ссылка на t.me, prev/next); `/canon/request` (для зарегистрированных); `/admin/canon` (вкладки Заявки/Произведения/Документ, доступ через JS+API как в `/admin` — страница рендерится, API защищены).
- Фаза 5: `tests/unit/test_canon_requests_e2e.py` (7 тестов) + расширение `_make_engine()` (DDL-зеркала + сид-work, `now_impl`→ISO-строка). Полный `tests/unit` **971 passed / 10 skipped**.
- Прод: `/canon`, `/canon/work/1`, `/canon/request`, `/admin/canon` → 200; `/api/canon/works` → 16 сид-произведений; `/api/admin/canon/requests` без токена → 403.

**Баг-фиксы, найденные по ходу (полезно помнить):**
- `@app.route("/canon")` висел на `_canon_doc_effective()` вместо `canon_page()` → страница отдавала голый текст (исправлен). Проверять, что декоратор стоит над правильной функцией.
- `_html_escape` отсутствовал — добавлен (html.escape).
- SQLite UDF не умеет возвращать `datetime` → теперь ISO-строка.

### CANON01 — Модуль хранения канона ✅ (завершён, 2026-08-07)

**План (утверждён пользователем):**

**Фаза 1 — Пакет `core/canon/` (готово):**
- `core/canon/canon.md` — ПОЛНЫЙ оригинальный текст канона v2.9 (с markdown-разметкой, гиперссылками на t.me, блок-цитатами — как в google-документе). Read-only артефакт репозитория → переживает cold start.
- `core/canon/__init__.py` — ЛЁГКИЙ (только stdlib+dataclasses, как `core/rates.py`, без structlog/aiohttp — критично для Vercel): `CANON_VERSION`, `CANON_DOC_ID`, `CANON_DOC_URL`, `CANON_DOC_EXPORT_URL`, `CANON_FILE_PATH`, `load_canon_text()`, `canon_version()`, `canon_sections()` (4 блока), `find_canon(query, limit)`, `render_markdown()` (свой stdlib-рендерер: **жирный**, *курсив*, `###`, `>` цитаты, списки, автоссылки, `---`), датаклассы `CanonWork`/`CanonTerm`, хелперы `get_glossary()`/`get_works()` (переименованы из `glossary()`/`works()` — конфликт имён с подмодулями!).
- `core/canon/works.py` — 16 произведений Блока 3.2 (8 треков 🔵, «Лука» 🟡, «Вирус LucasTeamLuke» 🔴, 3 статьи 🔵, «Olegovirus checkmarevus» 🟡, «LukasTeamLuke sp. nov.» 🔴, архив «Пивология») + `works_by_level()`/`works_by_kind()`.
- `core/canon/glossary.py` — 22 термина Блока 4.
- `core/canon/questions.py` — ЕДИНЫЙ пул 24 вопросов trivia (объединил bot 23 + api пул; тексты из bot с корректными написаниями «Olegovirus», из api — статичные distractors).
- `core/canon/prayers.py` — 15 молитв + `random_prayer(rng)`.

**Фаза 2 — Перевод потребителей (готово):**
- api/index.py: импорт `load_canon_text`/`_PRAYERS`/`_TRIVIA_QUESTIONS`/`CANON_WORKS`/`GLOSSARY_TERMS` из core.canon; удалены локальные дубли `_TRIVIA_QUESTIONS` (4606), `_PRAYERS` (7574); `_load_canon_trivia()` → `load_canon_text()`; `generate_trivia_from_canon()` читает из core.canon.
- bot/trivia/questions.py: `_CANON_PATH` убран, `TRIVIA_QUESTIONS` импортируется из core.canon.questions.
- bot/ai/knowledge.py: `CANON_DOC_URL`/`CANON_VERSION`/`PROHIBITED_CANON_KEYWORDS` из core.canon.
- bot/ai/knowledge_updater.py: `LOCAL_CANON_PATH` → `core/canon/canon.md`; URL-ы из core.canon.
- bot/commands/ai_commands_ptb.py + ai_commands.py: `_load_canon_knowledge()`/`_load_canon_snippet()` → `load_canon_text()`.
- bot/ai/service.py: `_match_knowledge()` — приоритет групп dynamic > статика CANON_KNOWLEDGE > local (чинит конкуренцию «сырых» local-записей против кураторских при полном тексте canon.md).
- Удалены `data/canon_knowledge.txt` + `api/canon_knowledge.txt` (grep-проверка: в коде ссылок нет).

**Фаза 3 — Веб-страница `/canon` (готово):**
- 3 вкладки (GitHub Dark, inline HTML в api/index.py): «📜 Полный текст» (полный оригинальный текст канона с разметкой и гиперссылками), «🎵 Произведения» (фильтры уровень 🔵🟡🔴/тип, ссылки t.me), «🧩 Глоссарий» (поиск).
- API: `GET /api/canon/text`, `GET /api/canon/works?level=&kind=`, `GET /api/canon/glossary?q=`, `GET /api/canon/search?q=`. Карточка «Канон» на хабе `/`.

**Фаза 5 — Тесты (готово):**
- `tests/unit/test_canon_module.py` — 25 тестов (загрузка, версия 2.9, секции, find_canon, works/glossary/questions/prayers, render_markdown, страница /canon, все API).
- `/canon` добавлен в `test_web_portal_e2e.py::test_web_pages_render`.
- Проверка: `pytest tests/unit` → **964 passed / 10 skipped**; ruff clean.

**Осталось отдельной задачей:** pre-existing падения tests/property (test_bunker_profile_parser, test_mafia_profile_parser — 4 failed).

### QUALITY — ruff-clean всего репозитория (A) ✅ + автотесты веб-портала (B) ✅

### QUALITY — ruff-clean всего репозитория (A) ✅ + автотесты веб-портала (B) 🚧

**Цель (по заказу пользователя):** A — ruff-clean всего репозитория → B — автотесты на веб-фичи → C — разбор TODO → обновление memory_bank.

**A — завершено:**
- `api/dnd_runtime.py`: удалён мёртвый `msg_type = "action"` / `"dice"`.
- 4 субагента исправили E712/F841 в unit/property/integration/pbt-тестах + ручной фикс `tests/unit/test_command_validation_edge_cases.py:330` (F841).
- Итог: `python -m ruff check . --exclude .venv --exclude vk_mini_app --exclude node_modules` → **All checks passed!**; полный прогон tests/unit+integration+property+smoke → 30 failed / 1242 passed / 32 skipped / 3 errors — те же падения на чистом HEAD (git stash) → pre-existing, не связаны с ruff-правками.

**B — в работе:**
- Создан `tests/unit/test_web_portal_e2e.py` (новый, не в conftest collect_ignore): E2E по auth (register/login/me/update/logout), feedback+admin, admin stats/users/coins, trivia (question/answer, реалистичные дистракторы), веб-страницы, reading_trainer (MOM-05 маркеры + чистота HTML), /suggest форма, reading_generate fallback.
- **10/10 passed.** Решённые проблемы:
  - sqlite-совместимая схема в `_make_engine()` (свои DDL вместо PG-only `_ensure_web_auth_tables`): `web_users`, `web_sessions`, `web_coin_log`, `web_feedback`, `users`, `user_coins` + регистрация функции `NOW()`.
  - PG-only `ANY(:ids)` в `/api/admin/users` (api/index.py:7039) → на движке зарегистрирована sqlite-функция `ANY` (парсит JSON) + `@event.listens_for(engine, "do_execute")` сериализует список в JSON перед bind.
  - Некорректная проверка `{currentData` (легитимный JS template literal `${currentData.title}`) заменена на проверку `id="stats-bar"`.
- Проверка: `pytest tests/unit` → **939 passed / 10 skipped / 0 failed** (включая новый файл), ruff на новом файле — All checks passed.

**Дальше по QUALITY:** C — разбор TODO (`api/index.py:9347` вернуть cooldown пазлов; `bot/commands/gd_admin_commands_ptb.py:276` — админ-проверка через AdminSystem). Затем финальное обновление memory_bank.

### MOM-05 — доработка тренажёра чтения ✅ (2026-08-03)

**Цель:** Дополнительные улучшения тренажёра чтения: озвучивание, статистика, подсказка.

**Сделано (production `api/index.py`, `/reading_trainer.html`):**
- **🔊 Озвучивание (TTS):** кнопка «Слушать» на экране чтения (читает текст через Web Speech API, `ru-RU`, rate 0.9) + кнопка «🔊 Вопрос» у каждого вопроса. Fallback: alert, если `speechSynthesis` недоступен.
- **💡 Подсказка:** кнопка «Подсказка» у каждого вопроса — раскрывает правильный ответ (XSS-safe через `escapeHtml`).
- **📊 Статистика:** панель `stats-bar` под заголовком; после каждой проверки сохраняется в `localStorage` (`reading_trainer_stats`: runs/questions/correct) и показывает «Заданий · Вопросов · Верно (%)». При печати панель и подсказки скрываются.
- CSS: `.btn-voice`, `.btn-hint`, `.toolbar`, `.question-tools`, `.hint-box`, `.stats-bar`; @media print скрывает `.hint-box`/`.stats-bar`.

**Проверка:** ruff 0 errors; py_compile OK (только pre-existing SyntaxWarning); JS извлечён → `node --check` OK; flask test client `/reading_trainer.html` → 200 + все новые маркеры; test_vercel_webhook_start + test_vercel_parsing_e2e — 23 passed.

**Осталось по MOM:** MOM-TEST (ручное тестирование, 2%).

### BUGFIX01 — фикс юнит-тестов + регрессий ✅ (2026-08-03)

**Проблема:** полный `tests/unit` падал на 10 тестах (GD-модели, AI-lite, short_mode, admin DB01) — большинство pre-existing, ещё были TypeError от `filters.DOCUMENT` (PTB 21 нет такого) и нулевых SQLAlchemy `default=` в памяти объектов.

**Сделано:**
- `database/database.py`: хелпер `get_db_session()` (единый источник сессий) + `__init__`-дефолты в GD-моделях (`Level.created_at`, `Submission.status/submitted_at`, `PlayerStats.total_approved`, `LevelCompletion.completed_at`) — применяются при создании объекта, т.к. SQLAlchemy `default=` срабатывает только на INSERT.
- `bot/commands/gd_commands_ptb.py`: убран невалидный `username` у `Submission`; создание `PlayerStats` без несуществующих колонок; `context.user_data.clear()` при отмене; `filters.DOCUMENT` → `filters.Document.ALL`.
- `utils/admin/admin_system.py`: совместимый `get_db_connection()` (закрывает регрессию DB01), восстановлено тело `get_users_count()`.
- Тесты обновлены под LTHub/scope: `test_gd_commands` (3 хендлера), `test_vercel_webhook_start`, `test_short_mode` (`/profile`), `test_ai_lite`, `test_gd_player_stats` (`SimpleNamespace`).

**Проверка:** 924 passed / 10 skipped, tests/smoke 12 passed, ruff clean, py_compile OK.

**Осталось (часть 3 PARSE01):** единый source of truth курсов (gdcards 2:1 bot vs 2.5 api), E2E PTB-тесты (handle_manual_parsing с реальной БД).

### PARSE01 — Production E2E парсинг игровых сообщений ✅ (завершён, 2026-08-03)

**Цель:** Довести парсинг игровых сообщений по ответам до production E2E. Исследование выявило 3 несогласованных стека парсера (core/parsers, bank_bot ParsingService, api/index.py), отсутствие записи в `parsed_transactions` и мониторинга неуспехов.

**Сделано (часть 1 — мониторинг):**
- `api/index.py`: `_ensure_parsing_tables()` (таблица `parsed_transactions` + колонка `status`), `_log_parsed_transaction()`, `_record_parsing_result()` (резолв users.id, success/failed). Ручной парсинг «парсинг» по reply теперь пишется в БД: успех и неудача (unknown/failed).
- `admin_manager.get_parsing_stats()`: считает `failed_parses` по `status != 'success'` (было закомментировано `=0`), суммы только по успешным.
- `database/database.py`: `ParsedTransaction.status` (default 'success').
- Тест-мок обновлён (status='success').

**Осталось (часть 3):** единый source of truth курсов (сейчас gdcards 2:1 в bot vs 2.5 в api), E2E PTB-тесты (handle_manual_parsing с реальной БД).

### PARSE01 часть 2 — idempotency + защита от ложных начислений ✅ (2026-08-03)

**Сделано:**
- `api/index.py` `_ensure_parsing_tables()`: колонки `chat_id BIGINT`, `message_id BIGINT` + `CREATE UNIQUE INDEX IF NOT EXISTS uq_parsed_transactions_msg ON parsed_transactions(chat_id, message_id) WHERE message_id IS NOT NULL` (частичный, обёрнут try/except).
- `_log_parsed_transaction()` / `_record_parsing_result()`: принимают `chat_id`/`message_id`; `_record_parsing_result` возвращает bool. Убран предварительный SELECT-дубль — детект дубля через UNIQUE-индекс (IntegrityError `duplicate`/`unique` → False).
- Webhook: проверка `reply_from.get("is_bot")` — если reply на сообщение НЕ бота → запись `not_bot` (failed) + сообщение «Парсинг доступен только в ответ на сообщение игрового бота...». Повторный парсинг того же сообщения → `recorded=False` → «ℹ️ Это сообщение уже было распарсено ранее.» без начисления.
- Тест-хелпер `_build_parsing_update` получил `is_bot: True` у reply_to.from; добавлен тест `test_webhook_parsing_reply_from_user_rejected`.

**Проверка:** 41 passed (test_vercel_parsing_e2e + test_admin_manager), полный test/unit 914 passed / 10 failed — 10 падений **pre-existing** (gd_models/gd_player_stats/short_mode, подтверждено git stash: падают и без моих правок). ruff 0 errors, SYNTAX OK. Задеплоено.

### PARSE01 часть 3 — единый source of truth курсов конвертации ✅ (2026-08-03)

**Проблема:** 3 несогласованных источника курсов (api-словарь был мёртвым fallback — прод-таблица `conversion_rates` засеяна 1.0 миграцией 005; legacy `bot/handlers/parsing_handler.py` — жёсткие 2:1/1:1/15:1/20:1; `/admin_rate` правил только in-memory).

**Сделано:**
- **`core/rates.py`**: канонический модуль — `BOT_CONVERSION_RATES` (api-значения: gdcards 2.5, gusya 5.0, shmalala 2.5, karma 0.5, bunkerrp 50, chaometer 1.0), `DEFAULT_CONVERSION_RATE=1.0`, `PARSING_RESOURCE_TYPES`, `get_conversion_rate()`.
- **`api/index.py`**: импорт канона (~2519); `_sync_conversion_rates(conn)` в `_ensure_parsing_tables` — INSERT отсутствующих, UPDATE только строк с k==1.0 (сохраняет админ-правки).
- **`bank_bot/services/parsing_service.py`** fallback-курс; **`bot/handlers/parsing_handler.py`** legacy GD Cards/Shmalala по канону; **миграция 005** seed 5.0/2.5/2.5; тест fallback ждёт gdcards 2.5.
- **Блокер:** импорт `core.parsers.rates` тянул тяжёлый `core/parsers/__init__.py` → `structlog` (нет на Vercel) → первый деплой 500. Перенос в `core/rates.py`.

**Проверка:** 924 passed / 10 skipped / 0 failed (полный unit), ruff clean, 70 passed (таргетированные). Задеплоено: `/api/dnd/status` → 400 (нормальный запуск, импорт ок).

**Финал PARSE01 (E2E PTB-тест + фикс бага):**
- **`tests/unit/test_manual_parsing_handler_e2e.py`** — 5 тестов на реальной SQLite (tmp-файл), оба DB-контура: целевой путь GD Cards (`🤩 Орбы: +10` → 25 монет), legacy True Mafia профиль (`💵 Деньги: 3000` → 200 монет 15:1), идемпотентность (повтор блокируется), нераспознанное / без reply. Патчи: `database.database.engine`/`SessionLocal` + `utils.admin.admin_system.SessionLocal`.
- **Баг (найден тестом):** `balance_repository.add_balance()` — `TypeError: NoneType += int` из-за NULL `total_earned` (raw INSERT `register_user` без него). Фикс: `user.balance = (user.balance or 0) + amount`, `user.total_earned = (user.total_earned or 0) + amount`.

**PARSE01 полностью завершён** (все части: мониторинг, idempotency, канон курсов, E2E PTB).

### TRIVIA01 — Брейн-Ринг по Канону (completed) ✅

**Цель:** Довести мини-игру до готовности: починить сломанный тест, Vercel-вебхук `/trivia`, синхронизировать награду и документацию.

**Как работает trivia:**
- Команда `/trivia` → нативная неанонимная Telegram-викторина (quiz-poll) с вопросом по канону (`data/canon_knowledge.txt` + пул `bot/trivia/questions.py`, 23 вопроса)
- Первый правильный ответ через `PollAnswerHandler` → победитель, +10 монет (`TRIVIA_COINS_REWARD`), транзакция `trivia_win` в PostgreSQL
- Антиспам: 60 сек таймаут на чат (`active_trivia` в bot_data)
- AI-генерация `generate_trivia_question()` (async) с fallback на пул

**Исправления 2026-08-03:**
- Тест `tests/unit/test_trivia_game.py:41` → async + await (падал с coroutine TypeError)
- Vercel webhook `/trivia` (`api/index.py:8833`) → `asyncio.run(generate_trivia_question())` (был TypeError без await, молча проглатывался)
- Тексты награды «+25» → «+10» (2 места, фактическая награда 10)
- `projectbrief.md`: TRIVIA01 completed + notes (quiz-poll не inline-кнопки)
- Добавлен `bot/trivia/__init__.py`

**Проверка:** pytest 3 passed, ruff 0 errors, задеплоено.

### Личный кабинет, Войти, Зарегистрироваться — раздельные страницы ✅

**Цель:** Разделить вход, регистрацию и личный кабинет на отдельные страницы (была одна кнопка «Войти / Зарегистрироваться», личного кабинета не было).

**Как работает:**
- **`/account`** — новая страница «Личный кабинет»: аватар, имя, @логин, 💎 монеты (из `/api/auth/me`), поля профиля (GD, Telegram, Lichess), статус (админ/пользователь), кнопки «Редактировать профиль» (/settings), «На главную», «Выйти». Если не залогинен → редирект на /login.
- **`/login`** — вход по логину/паролю (существовала)
- **`/register`** — регистрация (существовала)
- **`/api/auth/me`** теперь дополнительно возвращает `coins` (баланс из `user_coins` через `_web_user_id("u<id>")`)
- Хаб `/`: аноним видит две отдельные ссылки «Войти» (/login) и «Зарегистрироваться» (/register); залогиненный — «Личный кабинет» (/account) и «Выйти»

**Проверка на проде:** register (user_id=10) → me возвращает coins=0; /account 200 + «Личный кабинет»; /login и /register 200. ruff 0 errors, py_compile OK.

### Функция «Предложения» (новое) ✅

**Цель:** Пользователь может отправить предложение по улучшению проекта или сообщить о баге.

**Как работает:**
- Таблица `web_feedback` (user_id, login, author_name, category[bug|suggestion], module, message, status[open], created_at)
- Страница `/suggest` — форма: категория (🐛 баг / 💡 предложение), раздел (выпадающий список модулей), текст
- Карточка «Предложения» в бета-блоке хаба
- Плавающая кнопка 🐛 появляется при JS-ошибке (window.onerror / unhandledrejection) на хубе → ведёт на `/suggest?type=bug&module=hub`
- Вкладка «Предложения» в админ-панели настроек (просмотр по типам, удаление)
- Уведомление админу в Telegram через `notify_admin`

**API:** `POST /api/feedback` (подача), `GET /api/admin/feedback?status=`, `DELETE /api/admin/feedback/<id>`

### Пакет исправлений багов (2026-08-03) ✅

Исправлены 5 багов из обращения пользователя:

1. **Шахматы жёсткого off-by-one** (web + telegram): позиция задачи выводилась на `initialPly` полуходов, а не `initialPly + 1`, что давало инверсию цвета («Ход: Белых», но «правильный ход — за чёрных»). Эмпирически подтверждено на 19+ задачах Lichess: `solution[0]` легален именно на `initialPly + 1`. Mirror при ходе чёрных СОХРАНЁН (телеграм-бот не ломался). `turn` теперь считается от `(initialPly + 1) % 2`.

2. **D&D пустая страница**: панели скрывались навсегда, т.к. `refreshStatus()` молча глотал ошибки. Исправлено: `#start-panel` видна по умолчанию, добавлены `xhr.onerror`/`xhr.status !== 200`/`catch`, ошибка показывается в `start-result`; серверный `/api/dnd/status` обёрнут в try/except → `{"active": false}` вместо 500, ошибка логируется в `log_error`.

3. **GD рекорд без GD-ника**: раньше ник из профиля не подтягивался, сохранялась заглушка `web_<hash>`. Исправлено: клиент при пустом поле имени автоматически берёт `gd_nickname` из `/api/auth/me` (если залогинен), сервер добавляе фолбэк через токен (поле `token` в payload) → `_get_session_user(token).gd_nickname`.

4. **Нереалистичные варианты викторины**: в малых группах (rules/tea/ltrs/glossary) фолбэк брал ответы из всей базы («Высокий канон» попадал в вопрос про LTRS). Добавлены ручные поля `distractors` (3 реалистичных варианта) к вопросам групп rules(1-3), tea(16-17), ltrs(19-20), glossary(21-23); генераторы `api_trivia_question()` и telegram `generate_trivia_question()` теперь отут ручные дистракторы.

5. **Молитвы не по канону**: списки `_PRAYERS` (web + telegram дубль) состояли из IT-юмора. Переписаны по канону чайной религии (многократное «чай» + просьба + финальное «eight-nine»). Telegram теперь использует единый `_PRAYERS` (`random.choice(_PRAYERS)`) без дублирующего кода; убран дубликат `<div class="prayer-amen">eight-nine!</div>` на web-странице.

### Единая регистрация (WEB-11) ✅

**Цель:** Единый пользователь для всех модулей (AI Chat, GD, Chess, Budget, Family, Verbs) без обязательной регистрации.

**Как работает:**
- Анонимный `web_user_id` генерируется в localStorage при первом визите — пользоваться можно без регистрации
- Страница `/register` — регистрация с логином+паролем (обязательно) и опциональными полями: имя, GD nickname, Telegram ID, Lichess nickname
- Зарегистрированный пользователь = `u<user_id>` в localStorage + `web_token` (сессия из таблицы `web_sessions`) → синхронизация между устройствами
- Хаб `/` показывает user-bar: аватар, имя, статус, кнопку «Войти / Зарегистрироваться» или «Выйти» (+ «Настройки»)
- Страницы: `/register`, `/login`, `/settings` (профиль через `/api/auth/me`, обновление через `/api/auth/update`)
- **Поле «Имя» (display_name) предназначено для модулей «Психолог» и «Тренажёр английского»** — в тренажёре глаголов теперь подставляется как имя ученика по умолчанию
- Пароли: PBKDF2-SHA256 (100k итераций), хэш `salt_hex:digest_hex`; сессии: `secrets.token_hex(32)`
- Вспомогательные функции: `_hash_password()`, `_verify_password()`, `_create_session()`, `_get_session_user()`, `_auth_token_from_request()`, `_ensure_web_auth_tables()`
- AI Chat, GD, Chess, Verbs переведены с `ai_user_id` на единый `web_user_id`

**API:** `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/update`, `POST /api/auth/logout`

### Виртуальный компьютер для AI Chat (WEB-09) ✅

**Цель:** AI-персонажи получили «руки» как в Manus: запускают Python, браузят сайты, работают с файлами, редактируют фото. Пользователь видит только текстовый ответ.

**Как работает:**
- `POST /api/ai_chat` — агентный цикл tool-calling через Groq `llama-3.3-70b-versatile` (tools + tool_choice=auto, до 6 итераций)
- Инструменты: `run_python` (реальный subprocess в tempdir), `browse_web` (requests), `list_dir`/`read_file`/`write_file`/`get_cwd`/`set_cwd` (виртуальная ФС в памяти), `edit_image` (Pillow: resize/grayscale/rotate/blur/flip/mirror/thumbnail/invert/contrast)
- Виртуальная ФС: `_VIRTUAL_PC[user_id]` — дерево `{type, children/content/data}`, cwd, uploads
- Загрузка файлов: кнопка 📎 в чате, base64 в `files[]`, сохраняются в `/home/user/uploads/`
- Картинки после edit_image возвращаются как data URI → рендерятся под ответом бота
- Фронтенд теперь шлёт `history` (последние 20 сообщений)

**Файлы:** `api/index.py` (весь бэкенд + inline HTML страницы), `api/requirements.txt` (+Pillow)

### Практика глаголов — новый модуль (WEB-08) ✅

**Цель:** Создать веб-приложение для практики неправильных глаголов английского языка с AI-генерацией заданий.

**Роли:** Учитель (создаёт задания, смотрит результаты) / Ученик (выполняет, получает проверку).

**Как работает:**
- Страница `/irregular_verbs` — роли «Я учитель» / «Я ученик», тёмная тема
- Учитель: создаёт задание (глаголы, кол-во 1-50, режим 2/3 формы, пожелания) → AI генерирует → превью с правильными ответами → подтвердить и получить share-ссылку → «Мои задания» (id, кол-во заданий, учеников) → результаты с ошибками
- Ученик: вводит ID или переходит по share-ссылке → если имя не задано, спрашивает «Как тебя зовут?» (сохраняется в localStorage `verbs_name`) → заполняет пропуски → проверка с подсветкой ✓/✗ и счётом
- Имя ученика по умолчанию подставляется из профиля (display_name) для зарегистрированных пользователей
- Режимы: mode=3 (1 подсказка + 2 пропуска), mode=2 (первые 2 формы видны, пропущен Past Participle)
- Share-ссылка: `/irregular_verbs/exercise/<id>` → 302 на `?exercise=<id>`

**API:**
- `POST /api/verbs/generate` — AI генерирует задание (Groq llama-3.3-70b), лимит 10 сек между генерациями (`VERB_GEN_LOCK`)
- `GET /api/verbs/exercises` — список заданий учителя (+ student_count)
- `GET /api/verbs/exercise/<id>` — задание с пропусками для ученика
- `POST /api/verbs/submit` — проверка ответов ученика (посимвольно по inf/past/pp)
- `GET /api/verbs/exercise/<id>/results` — результаты по заданию (только учитель, 403 иначе)

**БД:** `verb_exercises` (id, teacher_id, verbs, task_count, mode, wishes, tasks JSON, created_at), `verb_submissions` (exercise_id, user_id, name, score, total, details JSON, timestamp). Хелперы `_save_verb_exercise`/`_load_verb_exercise`/`_load_teacher_exercises`/`_save_verb_submission`/`_load_verb_submissions`.

### Web Portal — все модули бота в браузере

**Цель:** Построить веб-портал, дублирующий большинство функций Telegram-бота в браузере. Все страницы на чистом HTML+JS (без фреймворков), Flask сервит через `api/index.py`.

**Архитектурное решение:** Все веб-страницы — inline HTML в `api/index.py` (как уже сделано с тренажёрами и хабом), API эндпоинты там же. Единая точка входа — хаб на `/`.

## Модули для портирования (утверждено)

| # | Модуль | Статус |
|---|--------|--------|
| 1 | AI / Чат-модуль | ✅ Портирован |
| 2 | Викторина (/trivia) | ✅ Портирован |
| 3 | D&D AI Master | ✅ Портирован (аналог StoryForge) |
| 4 | GD модуль | ✅ Портирован |
| 5 | Практика глаголов | ✅ Портирован |
| 6 | Шахматы | ✅ Портирован |
| 7 | Ежедневная молитва | ⏳ Утверждён |
| 8 | Админ-панель | ⏳ Утверждён |
| 9 | Family Circle (медиация) | ✅ Портирован (объединён с LTHub) |

**Не портируются:** магазин, личный кабинет/профиль, вселенная (infect/tea), парсинг реплаев, основные команды.

**Прогресс Phase 3: 123/123** (WEB-00, WEB-01, WEB-02, WEB-03, WEB-04, WEB-05, WEB-06, WEB-07, WEB-08, WEB-09, WEB-10, WEB-11).

## План архитектуры

### 1. AI / Чат-модуль
- **Страница:** `/ai_chat`
- **API:** `POST /api/ai_chat` — принимает `{message, character}`, возвращает `{reply}`
- **UI:** Поле ввода, история сообщений (лента), выбор персонажа (нейтральный/олеговирус/чай)
- **Данные:** Переиспользует `call_ai_api()` из `api/index.py`

### 2. Викторина (/trivia)
- **Страница:** `/trivia`
- **API:** `GET /api/trivia_question` — вопрос + варианты; `POST /api/trivia_answer` — проверка ответа
- **UI:** Карточка с вопросом, 4 кнопки-варианта, подсветка правильного/неправильного, счёт
- **Данные:** Брать вопросы из `bot/ai/knowledge.py` или новой таблицы

### 3. D&D AI Master (StoryForge-like) ✅ Портирован
- **Страница:** `/dnd` — SPA в стиле GitHub Dark (статус, чат-лог, старт, действие, кубик, исправление, стоп)
- **API:** `GET /api/dnd/status`, `POST /api/dnd/start`, `POST /api/dnd/act`, `POST /api/dnd/roll`, `POST /api/dnd/stop`, `POST /api/dnd/fix`
- **UI:** Лог сессии (лента сообщений user/ai/dice/system), поле ввода действия, бросок кубика (d20 / 2d6+3 + цель), исправление мастера, "новая сессия", остановка
- **Данные:** обёртки над `api/dnd_runtime.py`; `user_id` через `_gd_web_uid()`; ответы в Telegram-HTML → `_dnd_plain()`
- **Схема:** прод-таблица `dnd_sessions` (старый проект) без `paused_at` → `ALTER TABLE ADD COLUMN IF NOT EXISTS` в `_ensure_dnd_tables`

### 4. GD модуль ✅ Портирован
- **Страница:** `/gd` — хаб GD с пятью вкладками: Поиск игрока / Топ уровней / Моя статистика / Отправить рекорд / Модерация
- **API:** `GET /api/gd/user/<nick>`, `GET /api/gd/leaderboard`, `GET /api/gd/my_stats?user_id=...`, `GET /api/gd/me`, `POST /api/gd/submit`, `GET /api/gd/moderate`, `POST /api/gd/moderate/reject`, `POST /api/gd/moderate/approve`
- **UI:** Поиск игрока (статистика из GD API), топ уровней (таблица из БД, сложность из GDDL через `get_gd_difficulty_name()`), моя статистика (карточки), отправка рекорда (уровень + имя), модерация (пагинация, ✅/❌, только админ)
- **Тёмная тема:** стиль GitHub Dark
- **Web-user identity:** `_gd_web_uid()` хеширует нечисловой `user_id` в int; числовой = Telegram id. `_gd_web_is_admin()` проверяет по ADMIN_TELEGRAM_ID.

### 5. Шахматы ✅ Портирован
- **Страница:** `/chess` — три вкладки: Моя статистика / Поиск игрока / Пазл
- **API:** `GET /api/chess/stats?user_id=...`, `GET /api/chess/user/<nick>`, `POST /api/chess/link`, `POST /api/chess/puzzle`, `POST /api/chess/puzzle/check`
- **UI:** Статистика привязанного Lichess аккаунта (рейтинги, winrate, история пазлов), поиск игрока, пазл с доской (FEN GIF с lichess1.org), поле ввода UCI хода, +5 монет за верный ход
- **Привязка аккаунта** прямо со страницы (валидация ника через Lichess API)

### 6. Ежедневная молитва
- **Страница:** `/prayer`
- **API:** `GET /api/prayer/today` — молитва дня
- **UI:** Карточка с текстом молитвы, дата, кнопка "обновить"

### 7. Ежедневная молитва
- **Страница:** `/prayer`
- **API:** `GET /api/prayer/today` — молитва дня
- **UI:** Карточка с текстом молитвы, дата, кнопка "обновить"

### 8. Админ-панель (WEB-07) ✅
- **Страница:** `/admin`
- **API:** `GET /api/admin/stats`, `GET /api/admin/users?q=`, `GET /api/admin/users/<id>/coins`, `POST /api/admin/coins/award`, `POST /api/admin/set_admin`, `GET /api/admin/errors`, `POST /api/admin/errors/clear`
- **UI:** 4 вкладки: Статистика / Пользователи / Начисление монет / Ошибки. Тёмная тема GitHub Dark.
- **Авторизация:** по токену профиля — `_web_admin_session()` (is_admin флаг в web_users ИЛИ telegram_id == ADMIN_TELEGRAM_ID). Не-админ → 403. Самим собой управлять нельзя.
- **Назначение админа:** авто-грант при регистрации/обновлении, если telegram_id == ADMIN_TELEGRAM_ID; кнопка «Сделать/снять админа» в списке.
- **Монеты:** `_award_web_coins()` — ключ `_web_user_id("u<web_users.id>")` (согласовано с chess/GD), лог в `web_coin_log`.
- **БД:** `web_users.is_admin` колонка + таблица `web_coin_log` (id, user_id, amount, description, created_at).

### Общий подход
- Каждая страница — отдельный route в `api/index.py` с inline HTML (как hub, reading_trainer, endings_trainer)
- JS-логика inline в том же HTML (или вынесена в `<script>` блок)
- API эндпоинты — `GET/POST /api/<module>/<action>`
- Авторизация: `?user_id=<telegram_id>` (как в budget)
- Все данные через существующие SQLAlchemy engine + get_db_engine()

## Приоритет сборки

1. **AI Chat** — ✅ Портирован
2. **D&D** — ✅ Портирован
3. **Trivia** — ✅ Портирован
4. **Prayer** — ✅ Портирован
5. **Chess** — ✅ Портирован
6. **GD** — ✅ Портирован
7. **Admin** — ✅ Портирован

**Phase 3 (Web Portal) завершён: 123/123.**

## Архитектура (схема)

```
api/index.py (Flask)
├── GET  /                     → хаб (карточки сервисов)
├── GET  /ai_chat              → AI Chat SPA
├── POST /api/ai_chat          → call_ai_api()
├── GET  /trivia               → Trivia SPA
├── GET  /api/trivia_question   → вопрос из knowledge.py
├── POST /api/trivia_answer    → проверка + монеты
├── GET  /dnd                  → D&D SPA (старт/логи/действие/кубик/стоп)
├── GET  /api/dnd/status       → find_active_session + лог
├── POST /api/dnd/start        → cmd_dnd_start
├── POST /api/dnd/act          → handle_free_text
├── POST /api/dnd/roll         → cmd_dnd_roll
├── POST /api/dnd/stop         → cmd_dnd_stop
├── POST /api/dnd/fix          → cmd_dnd_fix
├── GET  /gd                   → GD SPA
├── GET  /api/gd/user/<nick>  → fetch_gd_user()
├── GET  /api/gd/leaderboard   → get_gd_leaderboard() + GDDL сложность
├── GET  /api/gd/my_stats      → get_gd_player_stats()
├── GET  /api/gd/me            → is_admin по user_id
├── POST /api/gd/submit        → create_gd_submission(status='pending')
├── GET  /api/gd/moderate      → get_gd_pending_submissions()
├── POST /api/gd/moderate/reject → reject_gd_submission_db()
├── POST /api/gd/moderate/approve → add_gd_level() + approve_gd_submission_db()
├── GET  /chess                → Chess SPA
├── GET  /api/chess/stats      → fetch_lichess_user()
├── GET  /api/chess/user/<nick>→ fetch_lichess_user()
├── POST /api/chess/link       → link_chess_account()
├── POST /api/chess/puzzle     → _fetch_lichess_puzzle()
├── POST /api/chess/puzzle/check → validate UCI move + award coins
├── GET  /prayer               → Prayer SPA
├── GET  /api/prayer/today     → random prayer
├── GET  /admin                → Admin SPA
├── GET  /api/admin/*          → admin endpoints
├── GET  /endings_trainer.html → existing
├── POST /api/endings_process  → existing
├── GET  /reading_trainer.html → existing
├── GET  /family_budget        → existing
├── GET  /family               → Family Circle: создать комнату (медиация)
├── GET  /family/room          → Family Circle: вход + чат
├── GET  /family/result        → Family Circle: финальный отчёт
├── POST /api/family/rooms     → создать/получить/удалить комнату
├── POST /api/family/rooms/join→ присоединение участника
├── GET  /api/family/rooms/<id>→ инфо о комнате
├── DELETE /api/family/rooms/<id>→ удалить комнату
├── POST /api/family/chat/send → диалог с ИИ-медиатором
├── POST /api/family/chat/finish→ завершить диалог участника
├── POST /api/family/report/generate → генерация финального отчёта
└── POST /telegram             → webhook (existing)
```

**Важные файлы:**
- `bot/web/family_budget.py` — Flask API + VK endpoints
- `bot/commands/budget_commands.py` — команда `/linkvk`
- `database/database.py` — модель `LinkedVKAccount`
- `vk_mini_app/` — весь VK Mini App проект
- `config/.env.local` — VK ключи и токены

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

Нет активных блокеров (DATABASE_URL подключена).

## Следующая сессия

### Family Circle — объединён в LTHub (WEB-10)
- Отдельный Vercel-проект `family_circle` (familycircle-nine.vercel.app) удалён; медиация теперь часть LTHub
- Страницы `/family`, `/family/room`, `/family/result`, API `/api/family/*` в `api/index.py` (Flask)
- Таблицы rooms/members/messages/needs/final_reports создаются через `_ensure_family_tables()`
- LLM-вызовы через `call_ai_api()` (Groq llama-3.3), шифрование Fernet (ENCRYPTION_KEY выставлен в Vercel production)
- ⚠️ Существующие таблицы создавал Alembic старого проекта: `created_at`/`status`/`spoke_count`/`finished` — NOT NULL **без** DEFAULT на уровне БД. Поэтому во всех INSERT'ах поля передаются явно (datetime.now(timezone.utc)). При добавлении новых модулей с этими таблицами — тоже передавать явно или менять схему через ALTER.

### GD Module Testing
- Проверка всех GD команд через webhook
- Edge cases
- UI/UX

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
