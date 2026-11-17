-- Личный AI-ключ пользователя LTHub
-- Date: 2026-11-17
-- Revision: 011
--
-- Зарегистрированный пользователь может сохранить свой API-ключ нейросети
-- (OpenRouter / Gemini / Groq). Ключ хранится в открытом виде (шифрование
-- запланировано отдельно) и используется приоритетно для запросов этого
-- пользователя; при отказе ключа — fallback на серверную цепочку провайдеров.
--
-- Колонки также добавляются автоматически при старте приложения
-- (`_ensure_web_user_columns` в api/index.py). Этот файл фиксирует схему
-- в миграциях и позволяет применить её вручную в Supabase SQL Editor,
-- если у runtime-роли нет прав на DDL.
--
-- Применение: Supabase Dashboard → SQL Editor → вставить файл → Run.

ALTER TABLE web_users ADD COLUMN IF NOT EXISTS ai_provider VARCHAR(32);
ALTER TABLE web_users ADD COLUMN IF NOT EXISTS ai_api_key VARCHAR(255);
ALTER TABLE web_users ADD COLUMN IF NOT EXISTS ai_model VARCHAR(128);

-- Проверка после применения:
-- SELECT column_name FROM information_schema.columns
-- WHERE table_name = 'web_users' AND column_name LIKE 'ai_%';