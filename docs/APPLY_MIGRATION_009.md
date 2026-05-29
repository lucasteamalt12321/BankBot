# Применение миграции 009 (Phase 2 Tables) к Supabase

**Дата:** 2026-05-24  
**Статус:** Готово к применению

## Проблема

Автоматическое применение миграции через Python-скрипт зависает из-за таймаутов подключения к Supabase.

## Решение: Ручное применение через Supabase Dashboard

### Шаг 1: Открыть SQL Editor в Supabase

1. Перейти на https://supabase.com/dashboard
2. Выбрать проект `xrrdliznuyausiutxqwv`
3. Открыть **SQL Editor** в левом меню

### Шаг 2: Скопировать SQL-скрипт

Открыть файл `database/migrations/009_phase2_tables_supabase.sql` и скопировать весь его содержимый.

### Шаг 3: Выполнить SQL

1. Вставить скопированный SQL в редактор
2. Нажать **Run** (или Ctrl+Enter)
3. Дождаться сообщения об успешном выполнении

### Шаг 4: Проверить созданные таблицы

Выполнить следующий запрос для проверки:

```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN (
    'levels', 'submissions', 'player_stats', 'level_completions',
    'chess_accounts', 'user_coins',
    'infection_status', 'daily_prayer_log',
    'user_preferences'
)
ORDER BY table_name;
```

Должно вернуться 9 таблиц:
- `chess_accounts`
- `daily_prayer_log`
- `infection_status`
- `level_completions`
- `levels`
- `player_stats`
- `submissions`
- `user_coins`
- `user_preferences`

## Альтернатива: Применение через psql

Если есть доступ к `psql`:

```bash
# Экспортировать DATABASE_URL
export DATABASE_URL="postgresql://postgres.xrrdliznuyausiutxqwv:MCrXT7RSsjQdn7wl@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"

# Применить миграцию
psql $DATABASE_URL -f database/migrations/009_phase2_tables_supabase.sql
```

## Что создаётся

### Geometry Dash Module (4 таблицы)
- `levels` — уровни для топа (1-100)
- `submissions` — заявки на прохождение
- `player_stats` — статистика игроков (хардест, количество прохождений)
- `level_completions` — прохождения уровней (many-to-many)

### Chess Module (2 таблицы)
- `chess_accounts` — привязка к Lichess
- `user_coins` — монеты за шахматные задачи

### Universe Module (2 таблицы)
- `infection_status` — заражение олеговирусом/LTL
- `daily_prayer_log` — лог ежедневных молитв

### AI Module (1 таблица)
- `user_preferences` — выбор AI-модели

## После применения

1. ✅ Обновить статус GD-01 в `projectbrief.md` на `completed`
2. ✅ Обновить `progress.md` с записью о миграции
3. ✅ Закоммитить изменения
4. ✅ Начать реализацию AI Manager (AI-01)

## Troubleshooting

**Ошибка: "relation already exists"**
- Таблицы уже созданы, миграция применена ранее
- Можно пропустить или использовать `DROP TABLE IF EXISTS` перед повторным применением

**Ошибка: "permission denied"**
- Проверить права доступа к БД
- Убедиться, что используется правильный пользователь (postgres)

**Таймаут подключения**
- Использовать Connection Pooler URL (не прямой URL)
- Проверить, что IP не заблокирован Supabase

---

**Статус:** Ожидает ручного применения через Supabase Dashboard
