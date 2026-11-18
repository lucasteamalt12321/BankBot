-- Вход через Google в LTHub
-- Date: 2026-11-18
-- Revision: 012
--
-- OAuth 2.0 (code + PKCE) через Google: аккаунт LTHub создаётся из профиля
-- Google или находится по google_subject. Email хранится отдельно
-- (google_email), колонка web_users.email не затрагивается.
--
-- Колонки также добавляются автоматически при старте приложения
-- (`_ensure_web_user_columns` в api/index.py). Этот файл фиксирует схему
-- в миграциях и позволяет применить её вручную в Supabase SQL Editor,
-- если у runtime-роли нет прав на DDL.
--
-- Применение: Supabase Dashboard → SQL Editor → вставить файл → Run.

ALTER TABLE web_users ADD COLUMN IF NOT EXISTS google_subject VARCHAR(64);
ALTER TABLE web_users ADD COLUMN IF NOT EXISTS google_email VARCHAR(255);

CREATE UNIQUE INDEX IF NOT EXISTS ix_web_users_google_subject
    ON web_users (google_subject);

-- Проверка после применения:
-- SELECT column_name FROM information_schema.columns
-- WHERE table_name = 'web_users' AND column_name LIKE 'google_%';