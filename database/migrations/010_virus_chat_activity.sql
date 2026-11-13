-- Universe Module: активность вируса в чате
-- Date: 2026-11-13
-- Revision: 010
--
-- Нужна для автоответа бота на вопрос «что это такое?»: бот помнит, в каких
-- чатах он недавно подменял сообщения заражённых, и отвечает на общее
-- «что это?» только там, где вирус реально активен.
--
-- Таблица также создаётся автоматически при старте приложения
-- (`_ensure_universe_tables` в api/index.py — CREATE TABLE IF NOT EXISTS).
-- Этот файл нужен, чтобы схема была зафиксирована в миграциях и таблицу
-- можно было создать вручную в Supabase SQL Editor, если у runtime-роли
-- нет прав на DDL.
--
-- Применение: Supabase Dashboard → SQL Editor → вставить файл → Run.

CREATE TABLE IF NOT EXISTS virus_chat_activity (
    chat_id BIGINT PRIMARY KEY,
    virus_type VARCHAR(50),
    updated_at TIMESTAMPTZ
);

-- Проверка после применения:
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public' AND table_name = 'virus_chat_activity';
