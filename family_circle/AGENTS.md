# Family Circle — проект для OpenCode

## Команды
- Запуск бэкенда: `cd backend && uvicorn app.main:app --reload`
- Миграции: `cd backend && alembic upgrade head`
- Установка: `pip install -r backend/requirements.txt`

## Структура
- Все промпты — в `backend/app/llm/prompts.py`
- Модели БД — в `backend/app/models.py`
- API — в `backend/app/routers/`

## Важно
- Не использовать платные API. Только Hugging Face Inference API (free).
- Все сообщения шифровать.
- Промпты копировать **дословно** из ТЗ.
