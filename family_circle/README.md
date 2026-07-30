# 🫂 Family Circle

**Веб-сервис для асинхронной семейной медиации с ИИ-помощником.**

Семья создаёт комнату, каждый участник по очереди (асинхронно) общается с ИИ-медиатором, который помогает сформулировать потребности и снизить напряжение. Когда все высказались — генерируется структурированный финальный отчёт с рекомендациями.

## Стек

- **Бэкенд:** Python (FastAPI) + PostgreSQL + SQLAlchemy + Alembic
- **AI:** Hugging Face Inference API (бесплатные модели)
- **Фронтенд:** HTML + CSS + vanilla JavaScript

## Быстрый старт

### 1. Установка

```bash
cd backend
pip install -r requirements.txt
```

### 2. Настройка окружения

```bash
cp .env.example .env
```

Заполните `.env`:
- `HF_API_TOKEN` — ваш токен с [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (бесплатный)
- `DATABASE_URL` — строка подключения к PostgreSQL
- `ENCRYPTION_KEY` — ключ шифрования (сгенерируйте командой ниже)
- `SECRET_KEY` — любой случайный секрет

**Генерация ключа шифрования:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Запуск PostgreSQL (если нет)

```bash
# Через Docker:
docker run -d --name family-circle-pg -e POSTGRES_DB=family_circle -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password -p 5432:5432 postgres:16
```

### 4. Миграции БД

Таблицы создаются автоматически при первом запуске. Для ручного управления:

```bash
cd backend
alembic revision --autogenerate -m "init"
alembic upgrade head
```

### 5. Запуск сервера

```bash
cd backend
uvicorn app.main:app --reload
```

Бэкенд будет доступен на `http://localhost:8000`. Документация API: `http://localhost:8000/docs`.

### 6. Открыть фронтенд

Откройте `frontend/index.html` в браузере.

## API (основные эндпоинты)

| Метод | Путь | Описание |
|-------|------|----------|
| `POST` | `/api/rooms` | Создать комнату |
| `GET` | `/api/rooms/{id}` | Информация о комнате |
| `DELETE` | `/api/rooms/{id}` | Удалить комнату |
| `POST` | `/api/chat/send` | Отправить сообщение |
| `POST` | `/api/chat/finish` | Завершить диалог |
| `POST` | `/api/report/generate` | Сгенерировать отчёт |

## Структура проекта

```
family_circle/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI приложение
│   │   ├── models.py         # SQLAlchemy модели
│   │   ├── schemas.py        # Pydantic схемы
│   │   ├── database.py       # Подключение к БД
│   │   ├── crypto.py         # AES-256 шифрование
│   │   ├── crud.py           # Операции с БД
│   │   ├── routers/
│   │   │   ├── rooms.py       # Комнаты
│   │   │   ├── chat.py        # Чат
│   │   │   └── report.py      # Отчёт
│   │   └── llm/
│   │       ├── client.py      # Hugging Face API wrapper
│   │       └── prompts.py     # Системные промпты
│   ├── migrations/            # Alembic
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── room.html
│   ├── result.html
│   ├── style.css
│   └── script.js
├── AGENTS.md
└── README.md
```

## Модели ИИ

| Назначение | Модель | Запасная |
|-----------|--------|----------|
| Индивидуальный диалог | `Qwen/Qwen2.5-7B-Instruct` | `mistralai/Mistral-7B-Instruct-v0.3` |
| Финальный синтез | `Qwen/Qwen2.5-7B-Instruct` | — |

Модель можно сменить через переменную `DEFAULT_MODEL` в `.env`.

## Лицензия

MIT
