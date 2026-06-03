# Vercel Migration: Command List

**Дата:** 2026-06-03  
**Статус:** В процессе (20/35 готово, работает)

## Команды для переноса на Vercel

### ✅ Готово и протестировано (20/35)

**Базовые (7):**
1. ✅ `/start` — приветствие
2. ✅ `/balance` — баланс из Supabase
3. ✅ `/profile` / `/user` — профиль
4. ✅ `/stats` — статистика
5. ✅ `/history` — история транзакций
6. ✅ `/ping` — проверка

**Режимы (4):**
7. ✅ `/short` — краткий режим
8. ✅ `/long` — полный режим
9. ✅ `/short_all` — краткий для всех
10. ✅ `/long_all` — полный для всех

**Специальные (1):**
11. ✅ `/reading_trainer` — тренажёр чтения

**Админ (8):**
12. ✅ `/admin` — админ панель
13. ✅ `/add_points` / `/add_coins` — начислить очки
14. ✅ `/add_admin` — назначить админа
15. ✅ `/admin_users` — список пользователей (работает)
16. ✅ `/admin_balances` — топ баланс (работает)
17. ✅ `/admin_transactions` — транзакции юзера
18. ✅ `/admin_stats` — статистика системы (работает)
19. ✅ `/broadcast` — рассылка (заглушка)

### ⏳ В работе (15/35)

**AI команды (5):**
- ⏳ `/ai` / `/ask` — AI помощник
- ⏳ `/ai_help` — помощь по AI
- ⏳ `/chat` — чат с AI
- ⏳ `/generate_prayer` — генерация молитв
- ⏳ `/ask_canon` — вопросы по канону

**Магазин (10):**
- ⏳ `/shop` — список товаров
- ⏳ `/buy` — покупка товара
- ⏳ `/buy_contact` — покупка контактов
- ⏳ `/buy_1` до `/buy_8` — быстрая покупка (8 команд)
- ⏳ `/inventory` — инвентарь пользователя

**Игры (1):**
- ⏳ `/trivia` — викторина

## Технические детали

**Работает:**
- SQLAlchemy + Supabase PostgreSQL
- BOT_TOKEN настроен в Vercel production
- Webhook: `https://bank-bot-ruby.vercel.app/telegram/webhook/{secret}`
- Все stateless команды работают

**Требуется для оставшихся команд:**
- AI: интеграция с Groq/HF API (уже есть в `/reading_trainer`)
- Магазин: queries к таблицам `shop_items`, `shop_categories`, `user_purchases`
- Trivia: простая викторина с вопросами/ответами
