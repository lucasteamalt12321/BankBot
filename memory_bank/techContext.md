# Tech Context

## Стек технологий

| Компонент | Технология | Версия |
|-----------|-----------|--------|
| Язык | Python | 3.x |
| Telegram API | python-telegram-bot | 20.7 |
| БД | SQLite через SQLAlchemy | >=2.0.36 |
| Конфигурация | Pydantic Settings | — |
| Планировщик | APScheduler | — |
| Тесты | pytest + hypothesis | — |
| Логирование | structlog | 23.1.0 |
| Миграции | Alembic | >=1.13.0 |
| Мониторинг | psutil | 5.9.6 |

## Структура проекта

```
BankBot/
├── AGENTS.md           # Правила и план разработки
├── memory_bank/        # Memory Bank (этот файл)
├── run_bot.py          # Точка входа
├── bot/                # Telegram-бот
│   ├── main.py         # Инициализация бота
│   ├── router.py       # Регистрация роутеров
│   ├── commands/       # Команды по группам
│   ├── handlers/       # Обработчики сообщений
│   └── middleware/     # Error handler
├── core/               # Бизнес-логика
│   ├── services/       # Service layer
│   ├── managers/       # Менеджеры
│   ├── parsers/        # Парсеры игр
│   └── systems/        # Игровые системы
├── src/                # Новая архитектура
│   ├── config.py       # Pydantic Settings
│   ├── repository/     # Репозитории
│   ├── process_manager.py
│   └── startup_validator.py
├── database/           # SQLAlchemy модели и миграции
├── config/             # .env файлы, bot_config.yaml
├── tests/              # unit / integration / property
│   ├── unit/
│   ├── integration/
│   └── property/
└── docs/               # Документация
    └── memory-bank/    # Старый Memory Bank (устарел)
```

## Конфигурация окружений

```
config/
├── .env                    # Общие настройки
├── .env.development        # Разработка
├── .env.test               # Тесты
├── .env.staging            # Стейджинг
└── .env.production         # Продакшн
```

Обязательные переменные:
- `BOT_TOKEN` — токен Telegram бота
- `ADMIN_TELEGRAM_ID` — Telegram ID администратора
- `DATABASE_URL` — путь к БД (default: `sqlite:///data/bot.db`)

## Команды разработки

```bash
# Запуск бота
python run_bot.py

# Тесты (одиночный прогон)
pytest --tb=short

# Инициализация БД
python database/initialize_system.py
```

## Ограничения и особенности

- Windows-среда разработки (PowerShell)
- SQLite — не поддерживает настоящий connection pooling
- Нет CI/CD пайплайна
- Тесты используют временные SQLite БД (создаются в корне проекта)
