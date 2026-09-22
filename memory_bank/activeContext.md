# Active Context

## 📋 Задачи от пользователя (живой список, сессия 2026-08-31)

> Стоящее указание пользователя: **«все задания, которые я тебе пишу, записывай в mb»**. Каждая новая задача из чата ДОПИСЫВАЕТСЯ сюда. Перед деплоем собрать все незакоммиченные правки и прогнать `ruff` + `pytest`.

### 🟡 В работе (сессия 2026-09-22): 🎛 Freemium-гейтинг 67/33 во всех модулях
- [TASK] «во всех модулях сделать 2 уровня возможностей: ~67% работает без регистрации, ~33% требуют регистрации, чтобы мотивировать регистрироваться». Решения пользователя: **стратегия смешанная** — база всем; где супер-фишек много (code/dnd/chess) — выпиливаем треть у анонимов, где мало — добавляем гейт на доп фичи сверху. **Целевая таблица 88/58/30 утверждена** (функц. модули = 34% за вход; системная часть auth/social/achievements — всегда за вход). Email при регистрации → **опционально**.
- План реализации в `memory_bank/projectbrief.md` → Phase 9 (FRE-01..FRE-09). Ключевые изменения: `_auth_user_or_401()` + единый 401 `{auth_required}` + глобальный фронт-патч `_FREEMIUM_AUTH_JS` (модалка логина на каждой HTML-странице; SUPPRESS-список для фоновых эндпоинтов); раскрыть базу code (analyze+чтение гостевых), dnd (status/join/act/roll), chess (puzzle) анонимам с rate-limit; гейт md2pdf-ИИ, music-overlay, study-ИИ/chat/hint/stats, exam ai-record, verbs submit, trivia answer (+1 монета); регистрация без email (NULL — фикс пустой строки) + бонус 100 монет + source-метрика.
- **Состояние:** backend все гейты внедрены; регрессия зелёная (32 теста: test_md2pdf 9, test_freemium_gates 6, test_code_explainer 10, test_achievements 7), ruff clean. Найденные по ходу прод-баги: (1) `code_projects.user_id NOT NULL` ломал гостевой analyze (фикс DDL + idempotent ALTER), (2) пустой email писался `''` → ломал UNIQUE для второй регистрации без email (фикс `or None`), (3) любой `log_error` в тестах вешал прогон навсегда — Telegram nо сети (фикс: conftest autouse no-op `send_telegram_message` при ENV=test). **Осталось:** git push + vercel deploy + прод smoke + Changelog/last_checked_commit (FRE-09).

### ✅ Выполнено (в этой сессии, 2026-09-21): 🔍 Багхант md2pdf — fix non-JSON AI errors
- **Найден и исправлен UX-баг** (коммит `95d7cf2`): `improveMd()` при не-JSON ответе (Vercel 504 HTML при таймауте ИИ) — «Unexpected token '<'». Теперь `r.text()` + try-catch JSON.parse → русские сообщения: 429 → «Слишком много запросов…», 502/504 → «ИИ временно недоступен…», сеть → «сервис недоступен (проверьте сеть)». Тесты 8/8 (+сообщение «ИИ временно недоступен»), jsdom подтверждает.
- **Проверено (багов НЕТ):** inline font-size на `#pdfPage` переживает `render()`; шрифт из localStorage восстанавливается; A+/A− clamp; printCss() с текущим размером (px); черновик сохраняется после ИИ-подстановки.

### ✅ Выполнено (в этой сессии, 2026-09-21): 🔤 md2pdf — изменение размера шрифта
- **[TASK] «добавь возможность изменить размер шрифта»** (коммит `925dee5`, задеплоено). В тулбаре `/md2pdf`: кнопки **A− / A+** + **селект** (11–24). Размер применяется к превью и к PDF/print (`printCss()`/`PRINT_CSS_SKEL`), заголовки/код/таблицы масштабируются через em; выбор сохраняется в localStorage (`md2pdf_fontsize`, дефолт 14.5). Исправлен баг `applyFontSize()` (читал глобал вместо значения select → теперь `applyFontSize(this.value)`). Тесты `test_md2pdf.py` 8/8, code-explainer 10/10.

### ✅ Выполнено (в этой сессии, 2026-09-21): ✨ md2pdf — ИИ-улучшение форматирования
- **[TASK] «сделай в md2pdf функцию (добавить форматирование), где ии будет сам улучшать md»** (коммит `624f3a3`, задеплоено). Кнопка **«✨ Улучшить форматирование»** в тулбаре `/md2pdf` → POST `/api/md2pdf/format` (`api/index.py`): ИИ перестраивает Markdown (заголовки/списки/таблицы/цитаты/код/`---`/жирный) без изменения смысла, возвращает готовый MD, фронт подставляет его в редактор и перерисовывает превью. Публичный, `_check_ai_rate` 8/60с на IP; лимит 20000 символов. Тесты: `test_md2pdf.py` 7/7 (+3), code-explainer 10/10, ruff/node --check чисто.

### ✅ Выполнено (в этой сессии, 2026-09-21): 📄 Markdown → PDF — упрощение до 2 окон + фикс рендера/темы
- **[TASK] «короче сделай там экран поделенным на 2 окна: в одно человек вставляет гипертекст, в другом в реальном времени показывается превью пдф. есть кнопки скачать pdf и печать»** (коммиты `e5210ed`, `0447d52`, задеплоено). Убрана промежуточная панель настроек (шрифты/цвета/размер) — осталось чистое разделение `workspace` grid `1fr 1fr`: слева `#mdInput`, справа живое превью `.pdf-page#pdfPage`; кнопки «🖨️ Печать» (`printPage()`) и «⬇️ Скачать PDF» (`downloadPdf()`) через общий `openPrintDialog()` (скрытый iframe `#printFrame`).
- **🐛 Фикс (коммит `0447d52`):** жалобы «не работает переключение светлая/тёмная тема» и «превью pdf всегда белый прямоугольник». Причины: 1) превью было пустым — в inline-JS Python-строка `html = """..."""` превращала `join('\n')`/`split('\n')` в РЕАЛЬНЫЙ перевод строки внутри JS-литерала → `SyntaxError` ломал весь скрипт; исправлено экранированием `'\\n'` (проверка: extraction через `test_client` + `node --check`); 2) страница сама задавала `:root{--bb-*}` поверх `inject_theme` (равная специфичность, но позже в документе) → светлая тема не применялась; переопределение удалено, хардкод-цвета (textarea/фон превью) переведены на `var(--bb-*)`.
- Тесты: `test_md2pdf.py` 4/4 + `test_code_explainer.py` 10/10; ruff чист; `node --check` отрендеренного JS — OK; прод-смоук: `GET /md2pdf` 200, маркеры (mdInput/pdfPage/Скачать PDF/Печать/printFrame/printPage) на месте.

### ✅ Выполнено (в этой сессии, 2026-09-20): 📄 Markdown → PDF (`/md2pdf`)
- **[TASK] «новый модуль: md to pdf. экран разделен на 2 части: с одной стороны человек вставляет гипертекст, а с другой он же но pdf. и кнопка скачать. типа markdowntopdf.com»** (коммит `64b15f2`, задеплоено, прод-смоук прошёл). SPA `/md2pdf`: слева textarea Markdown, справа живое превью «PDF-лист A4» (marked.js + highlight.js с CDN, GFM+breaks, задача-чекбоксы, подсветка кода); кнопка «⬇️ Скачать PDF» = браузерный print-to-PDF через скрытый same-origin iframe со своими print-CSS (`@page A4`), фолбек `window.print()` (механизм выбран пользователем). localStorage-автосохранение черновика, кнопки «Пример»/«Очистить», счётчик строк/слов, карточка в beta-хабе. Тесты: 4/4 (`test_md2pdf.py`), code-explainer 10/10, ruff+node --check чисто. 🐛 Нюанс реализации: `core/theme.py::inject_theme` подменяет первую строку `</body>` в HTML-ответе → JS-строка с литералом `</body>` внутри была загрязнена THEME_TOGGLE; обходится сборкой тега через конкатенацию `'<' + '/body>'`.

### ✅ Выполнено (в этой сессии, 2026-09-17): 💻 Code Explainer — анализ больших репозиториев (коммит `15ef1ba`, задеплоено)
- **[TASK] «фикси code explainer пока он не сможет грамотно просмотреть https://github.com/lucasteamalt12321/BankBot (добавить комментарии ко всем основным файлам и функциям)»** — Changelog-запись и детали фиксов в `progress.md`:
  - **Что было сломано на реальном репо (885 файлов, `api/index.py` = 29442 строк / 1.5MB):** главный файл вообще пропускался (лимит 400KB), анализировались только первые 500 строк файла, в БД попадали только top-35 файлов, `data/chat_export/*.html` (1MB каждый) съедали AI-бюджет, re-analyze не имел прогресса.
  - **Фиксы (состав):** лимиты увеличены (`_CODE_MAX_STORE_BYTES=3MB`, `_CODE_MAX_STORE_LINES=60k`), Skip-листы артефактов (`data/`, min.js/css, lock-файлы), **чанкованный анализ** больших файлов (шаг 450 строк, бюджет `_CODE_CHUNKS_PER_RUN=20` чанков/вызов, реальные номера строк комментариев), персист ВСЕХ файлов с heuristic-сводками для non-AI пула, колонки `ai_chunks_done`/`ai_chunks_total` (+ idempotent ALTER), `api_code_reanalyze` с **resume** (повторные «🤖 Разобрать» дожимают анализ), UI-бейдж «🔍 N%» в дереве/шапке файла, подсказка «нажмите Разобрать ещё раз».
  - Тесты: 10/10 code-explainer (в т.ч. +`test_artifacts_skipped_and_all_files_stored`, +`test_large_file_chunking_and_resume`), ruff+py_compile чисто, `node --check` `/code` OK. Прод-дым: `/code` 200 с новыми маркерами; E2E Spoon-Knife → 3 файла `done/total 0/1`, reanalyze → 3/3 AI (RU-summary + line-comments). Смоук-проекты удалены.
  - 🟡 **Known blocker (pre-existing):** полный синхронный анализ самого BankBot не влезает в Vercel maxDuration 60с (клон ~51с даже без AI → 504). Для средних репо работает. **Следующий шаг (предложи пользователю):** фоновый клон/анализ (background task/отдельная функция с бОльшим таймаутом или очередь), чтобы BankBot анализировался целиком.
- 🐛 Открытый хвост прошлой GD-сессии: **медиа nikiktos → Acid factory** (`media_file_id=NULL`) — ждём от пользователя ссылку/файл для `POST /api/gd/admin/player/nikiktos/level/6/media`.

### ✅ Выполнено (2026-09-15): 🎮 GD — case-insensitive merge персон в топе (коммит `c574b1d`, задеплоено)
- **[TASK] «nikiktos почемуто в топе в 2 экземплярах. оставь того, кто с большой буквы»:** причина — `get_gd_players` группировал персоны по точному регистру (`nikiktos` ≠ `Nikiktos`). Группировка переведена на `casefold()`; каноническое отображение через `_gd_persona_display_name()`: приоритет — вариант с заглавной первой буквой (=> «Nikiktos»), затем совпадение с `web_users.gd_nickname`, затем первый порядок. `get_gd_level_completions` дедупликация тоже casefold.
- Прод-смоук: топ = LucasTeam12321 2129 / ShadowRaven 500 / Nikiktos 325 (2 проходжения: Maethrillian + Acid factory) / EnidBlaiton 143 / Ololo112 111 — дубликата нет.

### ✅ Выполнено (2026-09-15): 🎮 GD — убрана «Top X» лестница сложностей + фикс кнопок редактирования на /gd (коммит `309d3c5`, задеплоено)
- **[TASK] «убери сложности со словом топ»:** из `GD_DIFFICULTY_TIERS`/`_COLORS`/`_RAW_MAP` и клиентских `DIFF_COLORS`/`DIFF_TIERS` удалены тиры `top_1000`..`top_10`. `_gd_tier_from_position()` всегда → `"unknown"`; legacy `"Top N"`/`top_*` в БД и авто-деривация по позиции убраны; unknown-бейдж серый (#94a3b8). Демоны считаются ТОЛЬКО для явных демон-тиров (unknown больше не демон → `demons_count` мог уменьшиться у уровней добавленных с Unknown). `/gd` page: `var IS_ADMIN` boot-fetch теперь пере-рисует лидерборд при апгрейде (`if (IS_ADMIN && !was && LB_LEVELS.length) loadLeaderboard()`) — фикс гонки, из-за которой пропадали кнопки ✏️/🗑️ если таблица рендерилась раньше `/api/auth/me`. Прод-смоук: топ = 1 Supersonic InsaneDemon / 2 TVoL Insane / 3 GreyTrap HardDemon / 4 Ultra EasyDemon / 5 Kororinpa EasyDemon / 6 Electroman Insane / 7 AcidFactory Hard / 8 CantLetGo Hard — «Top 10» больше нет; тесты 10/10, ruff clean, node --check OK.

### ✅ Выполнено (в этой сессии, 2026-09-14, 4-я часть): 🎮 GD — атрибуция по нику из заявки + админ «+» в профиле
- ✅ [TASK] **«LucasTeam это Лука, nikiktosik не помню, shadowraven привяжи к тестовому»** — **памятка**: LucasTeam = Лука; ShadowRaven = «тестовый» аккаунт (только TVOL); nikiktos = Acid factory (какой TG — пользователь не помнит). Атрибуция прохождений `submissions.username` (подробно в `progress.md` Changelog, коммит `7f5e2a5`, задеплоено, прод-дым: топ = LucasTeam 1333 / ShadowRaven 500 / LucasTeam12321 450 / nikiktos 200, is_first верен).
- ✅ [TASK] **«Кнопка + в профиле игрока: выбрать уровень как пройденный/удалить, при добавлении — медиа/ссылка»** — админ-панель на `/gd/player/<nick>`: кнопка «＋ Добавить уровень» → выпадающий список уровней (leaderboard) + поле «Ссылка на медиа» + `file`-инпут → POST `/api/gd/admin/player/<nick>/completions`; «✕» у каждого completion → DELETE (confirm). Детали/тест `test_gd_admin_completion_add_remove` в `progress.md` Changelog.
- ✅ [TASK] **«LucasTeam — на самом деле LucasTeam12321» + «хочу менять ник вручную — пишет нет прав администратора»**:
  - **Памятка:** GD-ник Луки = **LucasTeam12321** (персона 'LucasTeam' переименована и слита: Supersonic + Grey Trap + Ultra + Acid; ожидаемый топ после деплоя: LucasTeam12321 1783 / ShadowRaven 500 / nikiktos 200).
  - **Фикс 403:** все админ-fetch'и слали запросы БЕЗ `X-Auth-Token` → добавлен `admAuthHdr()` (токен из `localStorage.web_token`) в add/delete/rename.
  - **Переименование:** `_gd_rename_persona` + **PUT `/api/gd/admin/player/<nick>/nick`** (`new_nick`) + кнопка «✏️ Сменить ник» в карточке; авто-миграция `LucasTeam→LucasTeam12321` в `_ensure_gd_tables` (idempotent).
  - **Кнопки только у админа:** флаг `IS_ADMIN` рендерится СЕРВЕРНО (замена `__ADMIN_FLAG__` в `gd_player_page`), клиент лишь апгрейдит через `/api/gd/me` — не-админы не получают админ-кнопки даже в исходнике HTML.
- ✅ [TASK] **«чтобы из топа игроков переходило на карточку игрока, и в профиле был виджет карточки игрока»** — `/gd/players`: имя → всегда `/gd/player/<nick>` + «профиль →» при web_login; `/u/<login>`: виджет локальной карточки GDL (очки/демоны/уровни/hardest/список) + «Открыть карточку →», внешний GD-блок ниже. Проверено тестами + `node --check`.
- ⚠️ **Модель аккаунтов после восстановления данных:** один виртуальный аккаунт (1597272920) = две персоны (LucasTeam12321 за Supersonic + ShadowRaven за TVOL); gd_aliases удалены.
- 🐛 **[BUG] медиа nikiktos/Acid factory пропало в БД** (`media_file_id=NULL, media_type="manual"`, потеряно при восстановлении данных; исходной медиа нигде нет). Добавлен админ-эндпоинт `POST /api/gd/admin/player/<nick>/level/<level_id>/media` + кнопка «🖼 Заменить медиа» в карточке игрока. **Нужно от пользователя медиа (ссылка/файл) для nikiktos → Acid factory, чтобы прикрепить обратно.**
- 👤 **Аккаунты на проде (пароль `LucasTeam1`):** `shadowraven` (user_id 23, gd=ShadowRaven, персона привязана: web_login=shadowraven), `enidblaiton` (24, gd=EnidBlaiton), `ololo112` (25, gd=Ololo112). Emails `*@lthub.local`.
- 📨 **PENDING-заявки на проде (ожидают ручного одобрения админом):** #27 EnidBlaiton→Electroman Adventures (yt `Pg6KyewC_Vg`, позиция 7), #26 Ololo112→Cant Let Go (yt `nTlOljFl3Bw`, позиция 8). Уровней в топике ещё нет.

### ✅ Выполнено (в этой сессии, 2026-09-14): 🎮 GD — прохождения уровня + внешние ссылки медиа
- ✅ [TASK] **«Усовершенствовать систему прохождений в ГД»** (коммит `9b0b74d`, задеплоено, прод smoke прошёл):
  - Страница `/gd/level/<id>` (lazy-fetch) + `GET /api/gd/level/<id>/completions`: approved-прохождения с дедупом по игроку (`COALESCE(web_login, username)`), meta уровня (позиция/сложность), «профиль →» для web-игроков, медиа-ссылка + inline-превью, бирка «🔗 внешняя ссылка».
  - Имя уровня в лидерборде → ссылка на страницу прохождений (admin-edit жив).
  - Сабмит: переключатель «📎 Файл / 🔗 Ссылка» (`mode-file-btn`/`mode-link-btn`); http(s)-ссылка → `media_type="link"` (`media_file_id`=URL, urlparse-валидация, ≤2048, блок javascript/data/file/vbscript); файл ИЛИ ссылка (оба → 400); файл ≤16 МБ (413 + клиентская проверка).
  - Модерация: единый `gdMediaHtml(mediaId, mediaType)` — ссылка + превью прямых URL/`data:`-URL.
  - Тесты: +2 e2e (ddl-таблицы `levels`/`level_completions`/`player_stats`), 6/6 зелёные; ruff; `node --check` gd.js/gdlevel.js. Прод: link-submit `submission_id=24`, `javascript:`→400.
  - 🟡 **[BACKLOG, pre-existing]** `/api/gd/leaderboard` висит в проде на уровнях со сложностью `Unknown` (внешний gdbrowser без таймаута) — добавить timeout/кэш в `get_gd_difficulty_name`, проверить скорость ответа. Telegram-викторам `media_file_id` = Tg file_id (на вебе не открывается) — pre-existing.

### ✅ Выполнено (в этой сессии, 2026-09-14, 2-я часть): 🏆 GD демонлист — нормализованная сложность, очки, топ игроков
- ✅ [TASK] **Нормализованная сложность по реальному GDL + очки + топ игроков + карточка игрока + «⚡ Первый виктор» + фикс leaderboard** (код внесён, не задеплоен):
  - **Нормализация сложности:** `GD_DIFFICULTY_TIERS` (18 тиров easy→top_10 с weight/color/label); `_gd_norm_difficulty(value, position)` для маппинга произвольного текста; для `Unknown`/пусто — авто-тир по позиции (`top_X`). `get_gd_difficulty_name` с кэшем (TTL 1ч, timeout 5с), возвращает tier-key. Везде где пишется difficulty — нормализация; leaderboards/UI показывают цветные бейджи с label. Admin select из 18 тиров. Known issue FIXED: leaderboard больше не блокируется внешним API.
  - **Очки:** `player_stats.points`/`demons_count`, formula `round(1000/position)`. `_gd_sync_player_stats(conn, uid)` пересчитывает из level_completions. Вызывается при approve/PUT/DELETE позиции/уровня.
  - **Топ игроков:** `GET /api/gd/players` + `/gd/players` (ранг/ник/очки/демоны/хардест→карточка). Ссылки викторов → `/gd/player/<nick>`. Ссылка «🏆 Топ игроков» на `/gd`, `/gd/level/<id>`, хабе.
  - **Карточка игрока:** `/gd/player/<nick>` + `/api/gd/player/<nick>` (резолв web gd_nickname→tg username→s.username), очки/демоны/хардест, пройденные уровни с цветными бейджами + дата, внешние данные gdbrowser (stars/demons/creator), «профиль →».
  - **⚡ Первый виктор:** `get_gd_level_completions` → `is_first` по MIN(submitted_at); жёлтый бейдж на странице уровня.
  - Тесты: +3 e2e (`test_gd_normalized_difficulty`, `test_gd_players_page_and_api`, `test_gd_first_completion_badge`); DDL +points/demons_count. 9/9 зелёные (gd×6 + social×3); ruff + `node --check` (gd/gdlevel/gdplayers/gdplayer) чисто.
  - Задеплоено (bc24f69 + fix 57e6e84 lazy-backfill старых player_stats). Прод smoke: `/gd`+`/gd/players`+`/gd/player/LucasTeam`+`/api/gd/player/LucasTeam` 200, `/api/gd/players` → 4 игрока с очками (рейтинг filled), `/api/gd/leaderboard` 0.84s — ханг ушёл, `/api/gd/level/1/completions` → виктор с `is_first: true`, бейдж/ссылки в шаблонах страниц есть.
  - 🟢 **[BACKLOG] Known issue FIXED:** leaderboard больше не блокируется (энричмент только если позиция+тир оба неизвестны). Прод smoke pending. → закрыт, проверено.
  - ⚠️ Прод-нюанс данных: два tg-аккаунта с отображаемым именем «LucasTeam» — ники-ссылки ведут на резолв по `users.username`; при желании добавить учёт `first_name` в `_gd_resolve_player_uid` (коллизия имён останется).

### ✅ Выполнено (в этой сессии, 2026-09-14, 3-я часть): 🔗 gd_aliases — объединение аккаунтов в одного игрока
- ✅ [TASK] **«оба lucasteam — это я. shadowraven нет в топе»** — пользователь подтвердил «объедини 2»:
  - Таблица **`gd_aliases(user_id, alias)`**; бутстрап в `_ensure_gd_tables` (idempotent): `1597272920` и `2091908459` → `ShadowRaven`. Web-аккаунт `lucasteam` (uid 8) — отдельная запись (НЕ объединял).
  - Топ `/api/gd/players` + `/gd/players`: группировка по алиасу (сумма очков/демонов, hardest = min-позиция), LIMIT после группировки.
  - Карточка `/gd/player/<nick>`: алиас → объединённые члены (суммарные статы, union прохождений через `_gd_group_player_completions`).
  - Викторы на странице уровня + completers в лидерборде — дедуп/имя через алиас (alias-подзапрос).
  - Тест `test_gd_alias_merge`; 10/10 зелёные; ruff/py_compile чисто. Задеплоено; прод: «ShadowRaven» rank1 с суммой очков (1500+333) — готово для проверки пользователем.
  - ⚠️ Чтобы дальше управлять объединением без правки кода — позже можно добавить админ-эндпоинт/UI для `gd_aliases`.

### ✅ Выполнено (в этой сессии, 2026-09-13): 👥 Система профилей и друзей
- ✅ [TASK] **«добавь систему профилей и друзей»** (коммит `dbbacc5`, задеплоено, прод smoke прошёл):
  - Backend: `friend_requests` + `web_friends` (две строки на пару), `_ensure_social_tables`; роуты `/api/u/<login>`, `/api/users/search`, `/api/friends` (list/request/accept/decline/cancel/remove), `/api/friends/weekly`. Rate-limit заявок `frq:{uid}` 20/час; 403 на чужие заявки; 409 на дубли/self 400. Публичный профиль без email/telegram/hash.
  - Страницы: `/friends` (вкладки + поиск с debounce + топ недели), `/u/<login>` (профиль + GD-блок через `/api/gd/user/<nick>`, кнопки по `relation`), блок «Друзья» в `/account`, ссылка с бейджем заявок в user-bar хаба. JS через `data-*` + делегирование событий (без `onclick`-строка-конфликтов).
  - Тесты: `test_social.py` 3 теста зелёные; e2e DDL дополнен; ruff/py_compile/`node --check` чисто. Прод smoke: register→search→request→accept→weekly→remove→409 OK.

### ✅ Выполнено (в этой сессии, 2026-09-12 Bug Hunt + фича хаба)
- ✅ [TASK] **Охота на баги продолжена (коммит `61189c4`, до/после pull `4f6b25b`):**
  - **RCE: `_tool_run_python`** (/api/ai_chat) — AST blocklist `_BLOCKED_MODULES`/`_BLOCKED_KEYWORDS` + isolated `mkdtemp` cwd + sanitized env (PATH/HOME/TMP/TMPDIR/LC_ALL/PYTHONPATH; без DATABASE_URL/API-ключей) + rmtree в finally. Auth-гейт на чат отложен (фича «виртуальный ПК» анонимная).
  - **SSRF: browse_web** — единый `_blocked()` применяется и к исходному URL, и к редиректам (в т.ч. доменные имена внутренних ресурсов, не только литеральные IP).
  - **History quiz (всегда 500)**: `/api/quiz/generate` history переведён на реальные dataclasses `core.history.EVENTS/PERSONS` + `emperors.emperor_by_id` + `terms.TERMS`. Проверено 200 для history/informatics/math/russian/physics.
  - **Register**: rate-limit 5/5мин на IP → 429; `IntegrityError` → 409 «Логин или email уже заняты».
  - **audio_service**: temp-каталоги чистились до отправки → `_cleanup_after()` через `Response.call_on_close` для analyze/change_tempo/change_key/normalize/reverse/echo/trim; overlay — cap 8 файлов, 8MB/файл.
  - **core/di**: `close()` сбрасывает `_session = None`.
- ✅ [TASK] **Хаб: сортировка карточек по популярности:**
  - `GET /api/hub/popularity` — глобальная агрегация `web_activity_log` (SUM(actions), COUNT(DISTINCT user_id) по модулям).
  - JS `sortModulesByPopularity()` — reorder `.cards` и `#beta-cards` раздельно, score = actions*1000+users, fallback на дефолтный порядок. Endpoint 200, `node --check` OK.
- ✅ [AUDIT] **Переклассификация findings (см. progress.md 2026-09-12):** DnD/Chess auth = by-design (анонимная bearer-идентичность, НЕ IDOR); chess `force` = by-design/low; Family Budget IDOR — **исправлен remote** в `4f6b25b`; TransactionService = by-design; XSS `'` в esc() — нет эксплуатируемых single-quote интерполяций (`_gdEsc` DOM-based).

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
- ✅ [TASK] **Code Explainer AI Chat** — ИИ-ассистент в боковой панели (2026-09-02):
  - POST `/api/code/project/<id>/chat` — отправить вопрос ИИ с инструментами
  - ИИ умеет: читать файлы проекта, добавлять комментарии к строкам, отвечать на вопросы
  - Инструменты: read_file, add_comment, list_files, search
  - Использует ту же архитектуру, что и OGE-куратор (tool-calling)
  - История сохраняется в БД (таблица `code_chat_messages`)
  - Боковая панель чата в SPA /code
  - Кнопка «🤖 Разобрать» = ИИ анализирует весь проект и комментирует ключевые места
  - 7/7 тестов + ruff + py_compile чисто

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
