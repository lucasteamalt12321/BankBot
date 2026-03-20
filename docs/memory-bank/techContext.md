# Tech Context

## Стек

| Компонент | Технология |
|-----------|-----------|
| Язык | Python 3.x |
| Telegram API | python-telegram-bot 20.7 |
| БД | SQLite через SQLAlchemy 2.x |
| Конфигурация | Pydantic Settings |
| Планировщик | APScheduler |
| Тесты | pytest + hypothesis |
| Логирование | structlog |
| Миграции | Alembic |

## Структура проекта

```
BankBot/
├── bot/            # Telegram handlers и команды
│   ├── commands/   # Разбитые по группам команды
│   ├── handlers/   # Обработчики сообщений
│   └── middleware/ # Error handler
├── core/           # Бизнес-логика
│   ├── services/   # Service layer
│   ├── managers/   # Менеджеры (scheduler, shop, etc.)
│   ├── parsers/    # Парсеры игр
│   └── systems/    # Игровые системы
├── src/            # Новая архитектура
│   ├── config.py   # Pydantic Settings
│   ├── repository/ # Репозитории
│   └── process_manager.py
├── database/       # SQLAlchemy модели и миграции
├── config/         # .env файлы и bot_config.yaml
├── tests/          # unit / integration / property
└── docs/           # Документация и Memory Bank
```

## Конфигурация окружений

- `config/.env` — общие настройки
- `config/.env.development` — разработка
- `config/.env.test` — тесты
- `config/.env.production` — продакшн

Запуск: `ENV=production python run_bot.py`

## Ключевые зависимости

```
python-telegram-bot==20.7
sqlalchemy>=2.0.36
pydantic-settings
python-dotenv==1.0.0
structlog==23.1.0
apscheduler
pytest
hypothesis
```

## Команды разработки

```bash
# Запуск бота
python run_bot.py

# Тесты
pytest --tb=short

# Инициализация БД
python database/initialize_system.py
```
