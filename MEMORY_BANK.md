# Memory Bank: HF ↔ Render Failover

## Этап 1: Подготовка кода для Render ✅
- [x] Создать `Procfile`
- [x] Создать `wsgi.py` (entry point для gunicorn)
- [x] Создать `runtime.txt` (Python 3.12)
- [x] Проверить, что `HF_WEBHOOK_SECRET` берётся из env (для консистентности между HF и Render)
  - ✅ Уже работает: секрет вычисляется из `BOT_TOKEN` через HMAC

## Этап 2: Обновление Watchdog Workflow ✅
- [x] Обновить `.github/workflows/hf-watchdog.yml`:
  - ✅ Проверка HF health
  - ✅ Если HF unhealthy → set Telegram webhook → Render
  - ✅ Если HF healthy → set Telegram webhook → HF
  - ✅ Restart HF при проблемах
  - ✅ Поддержка `FORCE_FAILOVER` для ручного переключения

## Этап 3: Добавление секретов в GitHub (нужно сделать)
- [ ] `HF_TOKEN` — Hugging Face token (уже добавлен)
- [ ] `BOT_TOKEN` — Telegram bot token (нужно добавить!)
- [ ] `RENDER_WEBHOOK_URL` — URL Render сервиса (нужно добавить после создания Render)

## Этап 4: Создание Render сервиса (нужно сделать)
- [ ] Зарегистрироваться на https://render.com
- [ ] Создать New Web Service из GitHub repo `lucasteamalt12321/BankBot`
- [ ] Настроить Environment Variables:
  - `BOT_TOKEN` = тот же токен из HF
  - `DATABASE_URL` = тот же Supabase URL
  - `WEBHOOK_BASE_URL` = URL Render сервиса (например `https://bankbot-xxx.onrender.com`)
  - `PROXY_URL` или `VPN_SUBSCRIPTION_URL` = если нужен proxy для Telegram API
- [ ] Скопировать остальные секреты из HF

## Этап 5: Тестирование Failover (нужно сделать)
- [ ] Проверить HF работает (webhook на HF)
- [ ] Симулировать падение HF (через `FORCE_FAILOVER`)
- [ ] Проверить, что webhook переключился на Render
- [ ] Восстановить HF
- [ ] Проверить, что webhook вернулся на HF

## Этап 6: Документирование (нужно сделать)
- [ ] Обновить README с инструкциями по failover
