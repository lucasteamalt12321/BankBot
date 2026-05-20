# HF Webhook Migration Plan — BankBot

## Статус

- **Режим:** планирование, реализация ещё не начата.
- **Причина:** Hugging Face polling (`getUpdates`) регулярно ловит `TimedOut`, из-за чего бот может не получать команды в группе.
- **Цель:** перенести production BankBot на Telegram webhook в Hugging Face, убрать polling из HF runtime, упростить нерабочие/лишние модули и оставить только нужный стабильный контур.
- **Решения пользователя:**
  - фоновые задачи отключаем;
  - из response modes оставляем только `/short` и `/long`;
  - `/shop`, `/games`, `/dnd` не работают — убираем из runtime;
  - BridgeBot и VK Bot убираем из runtime;
  - небезопасный fallback “вставить текст карты вручную” не возвращать;
  - сначала план, реализацию не начинать без отдельного подтверждения.

---

## 1. Целевая архитектура

### Было

```text
HF Space process
  ├─ Flask /health /logs
  └─ BankBot polling loop
       └─ Telegram getUpdates → периодические TimedOut
```

### Должно стать

```text
Telegram
  └─ POST https://lucasteam-bankbot.hf.space/telegram/webhook/<secret>
       └─ HF Flask endpoint
            └─ PTB Application.process_update(update)
                 └─ существующие handlers BankBot
```

### Главный принцип

Production на HF работает через webhook. Polling остаётся только для локального/dev fallback.

---

## 2. Модуль `run_bot.py`

### Сейчас

`run_bot.py` поднимает Flask-сервер и затем вызывает `bot.main`, который запускает polling.

### Переносим

- Flask-приложение остаётся главным HF entrypoint.
- Оставляем endpoints:
  - `/` — диагностическая страница;
  - `/health` — health check;
  - `/logs` — последние логи;
  - `/feedback` — внешний feedback reader, если не мешает;
  - `/metrics` — можно оставить, если не ломает старт.
- Добавляем endpoint:
  - `POST /telegram/webhook/<WEBHOOK_SECRET>`.

### Меняем

- В HF mode `run_bot.py` больше не должен запускать polling.
- При старте создаётся один экземпляр Telegram Application.
- Webhook endpoint десериализует update:

```python
update = Update.de_json(request.json, application.bot)
await application.process_update(update)
```

- Webhook endpoint должен быстро возвращать `200 OK`, чтобы Telegram не ретраил update бесконечно.

### Безопасность

Используем один из вариантов:

1. Секрет в URL:
   `POST /telegram/webhook/<WEBHOOK_SECRET>`
2. И/или Telegram secret header:
   `X-Telegram-Bot-Api-Secret-Token`.

Рекомендуется использовать оба:

- `WEBHOOK_SECRET` хранится в HF Secrets;
- `set_webhook(..., secret_token=WEBHOOK_SECRET)`;
- endpoint проверяет path secret и header.

### Не переносим

- `bridge` и `vk` режимы запуска из `run_bot.py` в production HF больше не нужны.
- Можно оставить код как legacy/dev, но production default должен быть только BankBot webhook.

---

## 3. Модуль `bot/bot.py`

### Сейчас

`TelegramBot` создаёт Application, регистрирует handlers, запускает background tasks и вызывает `run_polling()`.

### Переносим

Оставляем:

- создание PTB `Application`;
- регистрацию handlers;
- error handler;
- DI cleanup handler;
- парсинг;
- основные команды;
- admin-команды, если они не требуют polling/background loops.

### Меняем

Нужно разделить:

1. **build/setup**:
   - создать Application;
   - зарегистрировать handlers;
   - подготовить зависимости.
2. **runtime mode**:
   - `webhook` для HF;
   - `polling` для local/dev.

Предлагаемый API:

```python
bot = TelegramBot()
application = bot.application
await bot.initialize_for_webhook()
```

И отдельно:

```python
bot.run_polling()  # только local/dev
```

### Убираем из HF runtime

- внешний `while not shutdown: run_polling(...)`;
- retry loop polling;
- HF polling timeout tweaks как production механизм.

### Оставляем локально

- Polling можно оставить для локальной разработки, где нет публичного webhook URL.

---

## 4. Telegram webhook setup

### Что добавить

При старте HF нужно зарегистрировать webhook:

```python
await application.bot.set_webhook(
    url="https://lucasteam-bankbot.hf.space/telegram/webhook/<secret>",
    allowed_updates=Update.ALL_TYPES,
    drop_pending_updates=False,
    secret_token=WEBHOOK_SECRET,
)
```

### Что проверить

После установки:

```python
info = await application.bot.get_webhook_info()
```

Логировать:

- webhook URL;
- pending updates;
- last error;
- allowed updates.

### На HF restart

При каждом restart/rebuild webhook переустанавливается автоматически.

---

## 5. Background tasks

### Решение пользователя

Фоновые задачи отключаем.

### Что отключить в HF webhook runtime

- `BackgroundTaskManager` periodic cleanup loop;
- periodic monitoring loop;
- cleanup expired access loop;
- sticker cleanup loop;
- parsing health monitor loop;
- любые бесконечные `while`/periodic tasks, которые не нужны для обработки webhook update.

### Что оставить

- Одноразовую инициализацию схемы БД;
- одноразовую проверку конфигурации;
- lazy/ручные admin-команды для cleanup, если они есть и не запускают loops.

### Почему

Webhook должен быть максимально лёгким и предсказуемым. Любые фоновые loops на HF могут конкурировать за CPU/network и усложнять отладку.

---

## 6. Response modes

### Решение пользователя

Оставляем только:

- `/short`;
- `/long`;
- возможно admin-варианты `/short_all`, `/long_all`, если они уже рабочие и нужны.

### Убираем/отключаем

- `/watch`;
- `/watch_all`;
- quick-reply watch actions;
- ADB notifications;
- ntfy realtime-watch flow;
- любые часы/ADB/ntfy realtime integrations как production dependency.

### Что оставить технически

Можно оставить код в репозитории, но убрать регистрацию handlers и runtime effects.

### Почему

Watch/ADB/ntfy не являются частью главной цели webhook/parsing и уже создавали дополнительную сложность.

---

## 7. Команды, которые остаются в webhook production

### Основные

- `/start`;
- `/user` как alias `/profile`;
- `/profile`;
- `/balance`;
- `/history`;
- `/stats`;
- `/short`;
- `/long`;
- `/short_all` / `/long_all` — если подтверждены как нужные admin-команды;
- `/admin` и критичные admin tools;
- `/add_points`, `/admin_addcoins`, `/admin_removecoins` — если нужны для ручного управления балансом;
- `/feedback`, `/suggest`, `/complaint`, `/feedback_list` — если остаются в продукте;
- parsing trigger: текст `Парсинг` ответом на реальное сообщение игры.

### Парсинг

Оставляем и считаем главным контуром:

- GDcards начисления: `🤩 Орбы: +X`;
- GDcards profile: `Орбы: X (#Y)` с delta logic;
- Shmalala money: `Монеты: +A (B)💰`;
- Shmalala karma: `Теперь его рейтинг: X ❤️`;
- Гуся Cards: `💰 Монеты • +X [Y]`.

---

## 8. Команды/модули, которые убираем из production runtime

### Решение пользователя

`shop`, `games`, `dnd` не работают — убираем.

### Убрать регистрацию handlers

- `/shop`;
- `/buy`, `/buy_contact`, `/buy_1` … `/buy_8`;
- `/inventory`;
- `/games`;
- `/play`;
- `/join`;
- `/startgame`;
- `/turn`;
- `/dnd`;
- `/dnd_create`;
- `/dnd_join`;
- `/dnd_roll`;
- `/dnd_sessions`.

### Документация/ответы

Убрать эти команды из:

- `/start` text;
- `/help`/commands menu, если есть;
- AI-lite knowledge hints, если быстро и безопасно;
- docs/README runtime command list.

### Код

На первом этапе код можно не удалять физически, только отключить handlers. Физическое удаление — отдельный cleanup PR после стабилизации webhook.

---

## 9. BridgeBot и VK Bot

### Решение пользователя

Убираем.

### Что означает “убираем” на первом этапе

- Не запускать `bridge`/`vk` из HF production;
- убрать из `run_bot.py` production routing;
- убрать из docs как активные runtime-компоненты;
- оставить файлы в репозитории до отдельной cleanup-задачи, чтобы не ломать импорты/тесты резко.

### Что можно сделать позже

- удалить `bridge_bot/` и `vk_bot/` физически;
- удалить связанные tests/docs/config;
- пересчитать project deliverables, где Bridge/VK сейчас отмечены completed.

---

## 10. AI-lite

### Предложение

Оставить, если не мешает.

### Риск

Webhook HTTP request может держаться, если AI-команда долго обрабатывается.

### Правило

Если AI-lite начнёт давать timeout — отключить handlers `/ai`, `/ask`, `/ai_help` вторым этапом.

---

## 11. Feedback

### Предложение

Оставить.

### Почему

Сейчас пользователь активно сообщает баги через чат, feedback может быть полезен.

### Что проверить

- `/feedback` не должен зависеть от background tasks;
- `/feedback_list` должен использовать safe send in groups/admin chats.

---

## 12. Admin commands

### Оставляем критичные

- `/admin`;
- управление балансом;
- просмотр пользователей/транзакций, если работает;
- reload parsing config, если работает;
- health/status commands, если не завязаны на polling.

### Убираем/отключаем сомнительные

- background task admin commands;
- ADB/watch/ntfy diagnostics;
- shop admin commands, если shop отключён;
- game admin commands, если games отключены.

### Правило

Не удалять admin code физически на первом этапе. Только убрать handlers, которые явно связаны с отключёнными модулями.

---

## 13. Database

### Оставляем

- PostgreSQL/Supabase production;
- SQLAlchemy models;
- Alembic/schema sync;
- users/balances/transactions;
- `user_resources`;
- `conversion_rates`;
- `parsed_transactions`.

### Не трогаем

- Миграции без необходимости;
- существующие таблицы shop/games/dnd можно оставить в БД, даже если runtime handlers отключены.

---

## 14. Безопасность парсинга

### Оставляем запрет

Не возвращать fallback “пользователь вручную вставляет текст карты/профиля”.

### Разрешённый сценарий

Только реальный Telegram reply на сообщение игры, если Telegram передал `reply_to_message` боту.

### Если Telegram не передал reply

Бот отвечает:

```text
Я не вижу сообщение, на которое вы ответили. Для защиты от накрутки парсинг работает только по реальному reply...
```

### Причина

Иначе пользователь может изменить текст и накрутить баланс.

---

## 15. Логи и диагностика webhook

### Добавить в logs

- `Webhook update received`;
- chat id/type;
- user id;
- update type;
- handler processing success/failure;
- webhook secret validation failure;
- setWebhook result.

### Добавить в `/health`

Расширить JSON:

```json
{
  "status": "healthy",
  "service": "BankBot",
  "database": "postgresql",
  "telegram_runtime": "webhook",
  "webhook_configured": true
}
```

### Возможный endpoint

- `/telegram/webhook/status` — только diagnostic; можно защитить токеном.

---

## 16. Тестовый чеклист после реализации

### Startup

- HF `/health` returns healthy;
- logs contain `Webhook mode enabled`;
- logs contain successful `setWebhook`;
- Telegram `getWebhookInfo` shows correct URL;
- no `run_polling` in HF logs;
- no recurring `Polling interrupted by network error`.

### Group commands

- `/start@lt_lo_game_bot`;
- `/user@lt_lo_game_bot`;
- `/balance@lt_lo_game_bot`;
- `/profile@lt_lo_game_bot`;
- `/short@lt_lo_game_bot`;
- `/long@lt_lo_game_bot`.

### Parsing

- Reply `Парсинг` to GDcards new card;
- Reply `Парсинг` to GDcards profile;
- Reply `Парсинг` to Shmalala money;
- Reply `Парсинг` to Shmalala karma;
- Duplicate parsing is blocked;
- No manual text paste fallback.

### Removed/disabled commands

- `/shop` should be absent or reply “temporarily disabled”;
- `/games` should be absent or reply “temporarily disabled”;
- `/dnd` should be absent or reply “temporarily disabled”;
- bridge/vk modes are not active in HF.

---

## 17. Implementation phases

### Phase 0 — approval

- User approves this plan.
- No code changes before approval.

### Phase 1 — runtime split

- Refactor `bot/bot.py` so Application setup is separate from polling startup.
- Add `TELEGRAM_RUNTIME_MODE=webhook|polling` or auto-detect HF.
- Polling remains local fallback.

### Phase 2 — Flask webhook endpoint

- Add `POST /telegram/webhook/<secret>` in `run_bot.py`.
- Validate secret path/header.
- Deserialize update and call `Application.process_update`.
- Return fast `200 OK`.

### Phase 3 — webhook registration

- Add startup `setWebhook`.
- Add webhook info diagnostics.
- Ensure no `deleteWebhook` during HF webhook mode.

### Phase 4 — disable modules per decision

- Disable background tasks in HF webhook mode.
- Remove handler registration for shop/games/dnd.
- Remove watch/ADB/ntfy runtime handlers except `/short` and `/long`.
- Remove Bridge/VK from production HF entrypoint.

### Phase 5 — docs and Memory Bank

- Update `docs/README.md`;
- update `RUN.md`;
- update `memory_bank/activeContext.md`;
- update `memory_bank/progress.md`;
- if deliverables are changed, update `projectbrief.md` carefully.

### Phase 6 — validation and deploy

- Run ruff;
- run focused tests;
- deploy to HF;
- verify `/health`, `/logs`, Telegram webhook info;
- run group command checklist;
- run parsing checklist.

---

## 18. Non-goals for this migration

- Не чинить shop/games/dnd — они отключаются.
- Не чинить BridgeBot/VK Bot — они убираются из production runtime.
- Не возвращать unsafe paste fallback для парсинга.
- Не расширять watch/ADB/ntfy.
- Не добавлять новые игровые механики.
- Не делать физическое удаление больших папок до стабилизации webhook.

---

## 19. Open questions before implementation

1. Оставляем ли `/short_all` и `/long_all` или только личные `/short` и `/long`?
2. Оставляем ли `/ai`, `/ask`, `/ai_help` на первом этапе webhook?
3. Оставляем ли `/feedback` и `/feedback_list`?
4. Для отключённых `/shop`, `/games`, `/dnd`: команда должна молчать или отвечать “временно отключено”?
5. Нужно ли физически скрыть отключённые команды из `/start` сразу в первом этапе? Рекомендация: да.

---

## 20. Recommended first implementation scope

Минимальный безопасный первый PR/commit после approval:

1. Webhook endpoint + setWebhook;
2. no polling on HF;
3. disable background loops in HF webhook mode;
4. disable shop/games/dnd handlers;
5. disable watch/ADB/ntfy handlers;
6. keep parsing + core commands + admin basics;
7. update docs/memory bank;
8. deploy and test.
