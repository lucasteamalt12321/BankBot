# 🤖 BankBot — Telegram-банк агрегатор

**Версия:** 2.0 | **Python:** 3.10+ | **Лицензия:** MIT

---

Мета-игровая платформа для автоматического отслеживания активности в играх и начисления банковских монет. Единая экосистема для нескольких игровых платформ с общей валютой.

## 🎯 Возможности

| Возможность | Описание |
|------------|---------|
| **Единый баланс** | Монеты накапливаются с разных игр в одном месте |
| **Автопарсинг** | Бот распознаёт сообщения от игровых ботов |
| **Магазин** | Покупка привилегий и товаров за монеты |
| **Админ-панель** | Управление пользователями, рассылки, статистика |
| **Мост TG ↔ VK** | Пересылка сообщений между Telegram и VK |
| **Достижения** | Система достижений с наградами |
| **Graceful Shutdown** | Корректное завершение при перезапуске |

---

## 📋 Содержание

1. [Быстрый старт](#-быстрый-старт)
2. [Команды бота](#-команды-бота)
3. [Поддерживаемые игры](#-поддерживаемые-игры)
4. [Архитектура](#-архитектура-проекта)
5. [Конфигурация](#-конфигурация)
6. [Безопасность](#-безопасность)
7. [База данных](#-база-данных)
8. [Тестирование](#-тестирование)
9. [Деплой](#-деплой)
10. [Разработка](#-разработка)
11. [Устранение проблем](#-устранение-проблем)

---

## 🚀 Быстрый старт

### Предварительные требования

| Требование | Версия | Где получить |
|-----------|--------|-------------|
| Python | 3.10+ | [python.org](https://python.org) |
| pip | latest | Включён в Python |
| Telegram Bot Token | — | [@BotFather](https://t.me/BotFather) |
| Telegram User ID | — | [@userinfobot](https://t.me/userinfobot) |

### Шаг 1: Установка

```bash
# Клонирование репозитория
git clone https://github.com/lucasteamalt12321/BankBot.git
cd BankBot

# Создание виртуального окружения (рекомендуется)
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Установка зависимостей
pip install -r requirements.txt
```

### Шаг 2: Настройка

```bash
# Создайте файл .env из примера
cp config/.env.example config/.env

# Отредактируйте файл
nano config/.env  # или любой другой редактор
```

**Минимальная конфигурация (config/.env):**

```env
# Обязательные параметры
BOT_TOKEN=123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
ADMIN_TELEGRAM_ID=123456789
DATABASE_URL=sqlite:///data/bot.db

# Опционально
ENV=development
LOG_LEVEL=INFO
```

### Шаг 3: Инициализация базы данных

```bash
# Создание таблиц
python database/initialize_system.py

# Или через бота (первый запуск)
python run_bot.py
```

### Шаг 4: Запуск

```bash
python run_bot.py
```

**Ожидаемый вывод:**

```
[START] Запуск Telegram-бота банк-аггрегатора LucasTeam...
[INFO] Подключение к базе данных...
[INFO] Загрузка конфигурации...
[INFO] Регистрация обработчиков команд...
[INFO] Бот успешно запущен!
[INFO] Ожидание сообщений...
```

### Шаг 5: Первое использование

1. Откройте Telegram
2. Найдите бота по username (указан в @BotFather)
3. Отправьте `/start`
4. Получите приветственное сообщение
5. Проверьте баланс: `/balance`

---

## 📋 Команды бота

### Основные команды

Команды доступны всем пользователям после регистрации.

| Команда | Описание | Пример использования |
|---------|---------|---------------------|
| `/start` | Приветствие и регистрация в системе | `/start` |
| `/balance` | Показать текущий баланс монет | `/balance` |
| `/balance @user` | Баланс другого пользователя (админ) | `/balance @username` |
| `/history [N]` | История транзакций (последние N записей) | `/history 20` |
| `/profile` | Профиль пользователя со статистикой | `/profile` |
| `/stats` | Подробная персональная статистика | `/stats` |
| `/help` | Справка по командам | `/help` |
| `/language` | Сменить язык интерфейса | `/language` |

### Магазин и покупки

| Команда | Описание | Пример |
|---------|---------|--------|
| `/shop` | Просмотр доступных товаров | `/shop` |
| `/buy <номер>` | Купить товар по номеру | `/buy 1` |
| `/buy_1` | Быстрая покупка товара #1 | `/buy_1` |
| `/buy_2` | Быстрая покупка товара #2 | `/buy_2` |
| `/buy_3` | Быстрая покупка товара #3 | `/buy_3` |
| `/buy_contact` | Купить связь с админом (10 монет) | `/buy_contact` |
| `/inventory` | Список купленных товаров | `/inventory` |
| `/sell <номер>` | Продать товар из инвентаря | `/sell 1` |

### Социальные функции

| Команда | Описание | Пример |
|---------|---------|--------|
| `/gift <сумма>` | Перевести монеты другому пользователю | `/gift 100` |
| `/top` | Топ пользователей по балансу | `/top` |
| `/achievements` | Ваши достижения | `/achievements` |
| `/achievements @user` | Достижения другого пользователя | `/achievements @username` |
| `/notifications` | Ваши уведомления | `/notifications` |
| `/notifications_clear` | Очистить все уведомления | `/notifications_clear` |
| `/referral` | Ваша реферальная ссылка | `/referral` |

### Парсинг игровых сообщений

| Команда | Описание |
|---------|---------|
| `парсинг` (ответ) | Обработать сообщение игрового бота |
| `/my_parsers` | Ваши активные парсеры |
| `/parser_stats` | Статистика парсинга |

**Как использовать парсинг:**

1. Получите сообщение от игрового бота (Shmalala, GD Cards и т.д.)
2. Нажмите "Ответить" на это сообщение
3. Напишите слово `парсинг`
4. Отправьте сообщение
5. Бот обработает и начислит монеты

### Административные команды

> **Требуют прав администратора**

| Команда | Описание | Пример |
|---------|---------|--------|
| `/admin` | Главное меню администратора | `/admin` |
| `/add_points <@user> <сумма>` | Начислить очки | `/add_points @user 100` |
| `/remove_points <@user> <сумма>` | Снять очки | `/remove_points @user 50` |
| `/set_balance <@user> <сумма>` | Установить баланс | `/set_balance @user 1000` |
| `/add_admin <@user>` | Назначить админа | `/add_admin @username` |
| `/remove_admin <@user>` | Удалить админа | `/remove_admin @username` |
| `/admin_stats` | Системная статистика | `/admin_stats` |
| `/admin_users` | Список пользователей | `/admin_users` |
| `/admin_balances` | Топ по балансу | `/admin_balances` |
| `/admin_transactions <@user>` | Транзакции пользователя | `/admin_transactions @user` |
| `/admin_health` | Проверка здоровья системы | `/admin_health` |
| `/admin_ban <@user>` | Заблокировать пользователя | `/admin_ban @username` |
| `/admin_unban <@user>` | Разблокировать пользователя | `/admin_unban @username` |
| `/mute <@user> [время]` | Замутить пользователя | `/mute @username 1h` |
| `/unmute <@user>` | Размутить пользователя | `/unmute @username` |

### Расширенные команды

| Команда | Описание | Пример |
|---------|---------|--------|
| `/parsing_stats [24h\|7d\|30d]` | Статистика парсинга | `/parsing_stats 7d` |
| `/user_stats <@user>` | Детальная статистика | `/user_stats @username` |
| `/broadcast <текст>` | Рассылка всем | `/broadcast Привет всем!` |
| `/add_item <название> <цена>` | Добавить товар | `/add_item VIP 500` |
| `/remove_item <номер>` | Удалить товар | `/remove_item 5` |
| `/edit_item <номер> <цена>` | Изменить цену | `/edit_item 3 300` |
| `/list_items` | Список всех товаров | `/list_items` |

### Конфигурационные команды

| Команда | Описание |
|---------|---------|
| `/reload_config` | Перезагрузить конфигурацию без перезапуска |
| `/config_status` | Текущий статус конфигурации |
| `/list_parsing_rules` | Список правил парсинга |
| `/add_parsing_rule <игра> <шаблон>` | Добавить правило парсинга |
| `/update_parsing_rule <id> <новый шаблон>` | Обновить правило |
| `/delete_parsing_rule <id>` | Удалить правило |
| `/export_config` | Экспорт конфигурации в JSON |
| `/import_config` | Импорт конфигурации из JSON |
| `/backup_config` | Создать бэкап конфигурации |
| `/restore_config <номер>` | Восстановить из бэкапа |
| `/list_backups` | Список доступных бэкапов |
| `/validate_config` | Валидация конфигурации |
| `/reset_daily` | Сбросить ежедневные лимиты |

---

## 🎮 Поддерживаемые игры

Бот автоматически распознаёт сообщения от игровых ботов и начисляет монеты.

### Таблица игр

| Игра | Бот | Активность | Курс | Описание |
|------|-----|-----------|------|----------|
| **Shmalala** | @ShmalalaBot | 🎣 Рыбалка | 1:1 | Начисление за пойманную рыбу |
| **Shmalala** | @ShmalalaBot | ❤️ Карма | 1:1 | Начисление за карму |
| **Shmalala** | @ShmalalaBot | 🏠 Ограбления | 1:1 | Начисление за ограбления |
| **GD Cards** | @GDCardsBot | 🃏 Новые карты | 2:1 | Начисление за полученные карты |
| **GD Cards** | @GDCardsBot | 📊 Профиль | 2:1 | Обновление профиля |
| **True Mafia** | @TrueMafiaBot | 🎮 Победа | 15:1 | Победы в мафии |
| **True Mafia** | @TrueMafiaBot | 📊 Профиль | 15:1 | Обновление профиля |
| **Bunker RP** | @BunkerRPBot | 🎮 Выживание | 20:1 | Выживание в бункере |
| **Bunker RP** | @BunkerRPBot | 📊 Профиль | 20:1 | Обновление профиля |

### Что означает курс?

Курс показывает сколько игровых монет = 1 банковская монета:

- **1:1** — 1 игровая монета = 1 банковская
- **2:1** — 2 игровые монеты = 1 банковская
- **15:1** — 15 игровых монет = 1 банковская
- **20:1** — 20 игровых монет = 1 банковская

### Пример парсинга

**Сообщение от ShmalalaBot:**

```
🎣 [Рыбалка] 🎣
Рыбак: PlayerName
Опыт: +8 (392 / 782)
На крючке: 🐸 Ротан (2.37 кг)
Монеты: +25 (3916)
💰Энергии осталось: 6
```

**После ответа "парсинг":**

```
✅ Сообщение обработано!
🎮 Игра: Shmalala
📝 Тип: Рыбалка
💰 Начислено: 25 монет
💰 Новый баланс: 3941
```

---

## 🏗️ Архитектура проекта

### Общая схема

```
┌─────────────────────────────────────────────────────────────────┐
│                        Telegram                                  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────┐ │
│  │   Users     │     │  Game Bots  │     │   Admin Bot      │ │
│  └──────┬──────┘     └──────┬──────┘     └────────┬────────┘ │
│         │                    │                     │          │
│         ▼                    ▼                     │          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                      BankBot                            │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │  │
│  │  │ Commands │  │ Parsing  │  │  Admin Panel          │ │  │
│  │  │ Handlers │  │ System   │  │  /admin, /broadcast   │ │  │
│  │  └──────────┘  └──────────┘  └──────────────────────┘ │  │
│  │                          │                              │  │
│  │                          ▼                              │  │
│  │  ┌────────────────────────────────────────────────────┐ │  │
│  │  │              Business Logic (core/)                 │ │  │
│  │  │  ┌────────────┐ ┌────────────┐ ┌───────────────┐  │ │  │
│  │  │  │ Repository │ │  Service   │ │   Managers    │  │ │  │
│  │  │  │   Layer    │ │   Layer    │ │               │  │ │  │
│  │  │  └────────────┘ └────────────┘ └───────────────┘  │ │  │
│  │  └────────────────────────────────────────────────────┘ │  │
│  │                          │                              │  │
│  │                          ▼                              │  │
│  │  ┌────────────────────────────────────────────────────┐ │  │
│  │  │              Database (SQLAlchemy)                 │ │  │
│  │  │  users │ balances │ transactions │ items │ ...     │ │  │
│  │  └────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (BridgeBot)
┌─────────────────────────────────────────────────────────────────┐
│                          VK                                     │
│  ┌──────────────┐     ┌──────────────┐     ┌───────────────┐  │
│  │  VK Users    │     │  BridgeBot   │────▶│  VK Channel   │  │
│  └──────────────┘     └──────────────┘     └───────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Структура каталогов

```
BankBot/
│
├── run_bot.py              # Точка входа для BankBot
│
├── bot/                    # Основной Telegram-бот (python-telegram-bot)
│   ├── bot.py             # Главный файл (~4000 строк)
│   ├── __init__.py
│   ├── commands/          # Обработчики команд
│   │   ├── admin.py      # Админ-команды
│   │   ├── balance.py    # Команды баланса
│   │   ├── shop.py       # Команды магазина
│   │   └── system.py     # Системные команды
│   ├── bridge/           # Модуль моста (shim → bridge_bot/)
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── loop_guard.py
│   │   ├── main_bridge.py
│   │   ├── vk_listener.py
│   │   └── ...
│   └── handlers/          # Обработчики событий
│
├── bridge_bot/            # Мост TG → VK (aiogram)
│   ├── __init__.py
│   ├── main.py           # Точка входа aiogram-бота
│   ├── bot.py            # Инициализация бота
│   ├── config.py         # Конфигурация моста
│   ├── handlers.py        # Обработчики TG → VK
│   ├── vk_publisher.py   # Публикация в VK
│   ├── media.py          # Обработка медиафайлов
│   ├── queue.py          # Очередь сообщений
│   ├── loop_guard.py     # Защита от циклов
│   └── state_manager.py  # Управление состоянием
│
├── vk_bot/                # VK Bot (vk_api)
│   ├── __init__.py
│   ├── main.py           # Long Poll точка входа
│   ├── bot.py            # Инициализация
│   ├── config.py         # Конфигурация
│   └── handlers.py        # Обработчики
│
├── bank_bot/              # Новая модульная структура (pytelegrambotapi)
│   ├── __init__.py
│   ├── main.py           # Точка входа
│   ├── bot.py            # Инициализация
│   ├── handlers/         # Обработчики команд
│   │   ├── __init__.py
│   │   ├── start.py
│   │   ├── balance.py
│   │   ├── admin.py
│   │   └── shop.py
│   ├── services/         # Бизнес-логика
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   ├── balance_service.py
│   │   └── shop_service.py
│   ├── repositories/     # Доступ к данным
│   │   ├── __init__.py
│   │   ├── user_repository.py
│   │   ├── balance_repository.py
│   │   └── transaction_repository.py
│   └── di.py             # Dependency Injection
│
├── core/                  # Бизнес-логика (общая)
│   ├── __init__.py
│   ├── repositories/     # Repository pattern
│   │   ├── base.py
│   │   ├── user_repository.py
│   │   ├── balance_repository.py
│   │   ├── transaction_repository.py
│   │   └── item_repository.py
│   ├── services/         # Service layer
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   ├── balance_service.py
│   │   ├── shop_service.py
│   │   └── parsing_service.py
│   ├── parsers/          # Парсеры сообщений
│   │   ├── __init__.py
│   │   ├── registry.py  # Реестр парсеров
│   │   ├── base.py      # Базовый класс
│   │   └── games/       # Парсеры игр
│   │       ├── __init__.py
│   │       ├── shmalala.py
│   │       ├── gd_cards.py
│   │       ├── true_mafia.py
│   │       └── bunker_rp.py
│   ├── managers/         # Менеджеры
│   │   ├── __init__.py
│   │   ├── config_manager.py
│   │   └── task_manager.py
│   └── middleware/       # Middleware
│       ├── __init__.py
│       └── error_handler.py
│
├── database/             # База данных
│   ├── __init__.py
│   ├── database.py       # SQLAlchemy модели
│   ├── connection.py     # Connection pooling
│   ├── session.py        # Управление сессиями
│   ├── models.py         # Модели (users, balances, etc.)
│   └── migrations/       # Миграции Alembic
│       ├── versions/
│       └── README_*.md
│
├── common/                # Общие модули
│   ├── __init__.py
│   ├── config.py        # Pydantic Settings (источник истины)
│   ├── database.py       # Re-export БД
│   └── logging.py        # Логирование
│
├── src/                   # Дополнительные модули
│   ├── __init__.py
│   ├── config.py         # Конфигурация (перенесена в common/)
│   ├── repository/       # Repository паттерн
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user_repository.py
│   │   └── unit_of_work.py
│   └── models/           # Модели
│
├── config/                # Конфигурация
│   ├── __init__.py
│   ├── .env.example      # Пример .env файла
│   ├── .env.development
│   ├── .env.test
│   ├── .env.production
│   ├── requirements.txt  # Основные зависимости
│   ├── requirements-dev.txt
│   └── requirements-prod.txt
│
├── tests/                 # Тесты
│   ├── __init__.py
│   ├── conftest.py       # Fixtures
│   ├── unit/            # Unit-тесты
│   │   ├── __init__.py
│   │   ├── test_settings.py
│   │   ├── test_user_service.py
│   │   ├── test_balance_service.py
│   │   └── ...
│   ├── integration/     # Интеграционные тесты
│   │   ├── __init__.py
│   │   ├── test_admin_manager.py
│   │   └── ...
│   ├── bridge/          # Тесты BridgeBot
│   │   ├── __init__.py
│   │   ├── test_loop_guard.py
│   │   ├── test_queue.py
│   │   ├── test_vk_publisher.py
│   │   └── test_media.py
│   ├── vk_bot/          # Тесты VK Bot
│   │   ├── __init__.py
│   │   └── test_main.py
│   └── property/        # Property-based тесты
│       ├── test_balance_properties.py
│       └── test_shop_display.py
│
├── docs/                  # Документация
│   ├── ARCHITECTURE.md   # Архитектура
│   ├── CONFIGURATION.md  # Конфигурация
│   ├── DEPLOYMENT.md     # Деплой
│   └── PARSING.md       # Парсинг
│
├── memory_bank/          # Контекст AI-агента
│   ├── projectbrief.md   # Цели и deliverables
│   ├── progress.md        # Прогресс
│   ├── activeContext.md  # Текущий контекст
│   ├── productContext.md # Продуктовый контекст
│   ├── systemPatterns.md # Паттерны
│   └── techContext.md    # Технологии
│
├── scripts/              # Скрипты
│   ├── migrate_*.py     # Миграции
│   └── fix_*.py         # Исправления
│
├── utils/                # Утилиты
│   └── README.md
│
├── data/                 # Данные (runtime)
│   ├── bot.db           # SQLite база данных
│   └── backups/         # Бэкапы
│
├── logs/                 # Логи
│   └── bot.log
│
├── AGENTS.md             # Инструкции для AI-агента
├── README.md             # Этот файл
├── requirements.txt     # Зависимости (симлинк на config/)
├── Dockerfile
├── docker-compose.yml
└── .gitignore
```

### Технологический стек

| Компонент | Технология | Версия | Назначение |
|-----------|-----------|--------|------------|
| **BankBot** | python-telegram-bot | 20.x | Telegram API |
| **BridgeBot** | aiogram | 3.x | Telegram API (async) |
| **VK Bot** | vk_api | 11.x | VK API |
| **База данных** | SQLAlchemy | 2.x | ORM |
| **Конфигурация** | Pydantic | 2.x | Settings validation |
| **Логирование** | structlog | 24.x | Structured logging |
| **Тесты** | pytest | 9.x | Testing framework |
| **Миграции** | Alembic | 1.13.x | DB migrations |

---

## ⚙️ Конфигурация

Подробная документация: [docs/CONFIGURATION.md](docs/CONFIGURATION.md)

### Переменные окружения

#### Обязательные

| Переменная | Описание | Пример | Комментарий |
|------------|----------|--------|-------------|
| `BOT_TOKEN` | Токен бота от @BotFather | `123456:ABC-...` | Без него бот не запустится |
| `ADMIN_TELEGRAM_ID` | Ваш Telegram ID | `123456789` | Становится первым админом |
| `DATABASE_URL` | URL базы данных | `sqlite:///data/bot.db` | PostgreSQL для продакшн |

#### Опциональные

**Окружение:**

| Переменная | Описание | По умолчанию | Возможные значения |
|------------|----------|--------------|-------------------|
| `ENV` | Окружение | `development` | `development`, `test`, `staging`, `production` |
| `APP_ENV` | Алиас окружения | `dev` | `dev`, `prod`, `test` |

**Telegram:**

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `BOT_NAME` | Название бота | `LucasTeam Bot` |
| `BOT_USERNAME` | Username бота | — |

**Bridge (мост TG ↔ VK):**

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `BRIDGE_ENABLED` | Включить мост | `false` |
| `BRIDGE_TG_CHAT_ID` | ID Telegram чата | `0` |
| `VK_TOKEN` | Токен VK сообщества | — |
| `VK_PEER_ID` | ID VK получателя | `0` |
| `VK_GROUP_ID` | ID VK группы | `0` |
| `BRIDGE_ADMIN_CHAT_ID` | Admin chat ID для моста | `None` |

**База данных:**

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `DB_POOL_MIN` | Мин. соединений пула | `2` |
| `DB_POOL_MAX` | Макс. соединений пула | `10` |
| `DB_POOL_TIMEOUT` | Таймаут (сек) | `30` |

**Парсинг:**

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `PARSING_ENABLED` | Автопарсинг | `false` |
| `TASK_CHECK_INTERVAL` | Интервал проверки (сек) | `300` |

**Логирование:**

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `LOG_LEVEL` | Уровень логов | `INFO` |
| `LOG_FILE` | Файл логов | `None` |

### Примеры конфигурации

**Минимальная (.env):**

```env
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
ADMIN_TELEGRAM_ID=123456789
DATABASE_URL=sqlite:///data/bot.db
```

**Development (.env.development):**

```env
ENV=development
BOT_TOKEN=dev_token
ADMIN_TELEGRAM_ID=123456789
DATABASE_URL=sqlite:///data/bot_dev.db
LOG_LEVEL=DEBUG
PARSING_ENABLED=false
```

**Production (.env.production):**

```env
ENV=production
BOT_TOKEN=prod_token
ADMIN_TELEGRAM_ID=123456789
DATABASE_URL=postgresql://user:pass@localhost:5432/bankbot
DB_POOL_MIN=5
DB_POOL_MAX=20
LOG_LEVEL=INFO
LOG_FILE=/var/log/bankbot/bot.log
PARSING_ENABLED=true
BRIDGE_ENABLED=true
VK_TOKEN=vk_token_here
```

---

## 🔐 Безопасность

### Защита данных

| Механизм | Описание |
|----------|---------|
| **Токены в .env** | BOT_TOKEN и VK_TOKEN хранятся только в .env |
| `.env` в .gitignore | Файл не попадает в репозиторий |
| **Валидация ввода** | Все данные проверяются перед использованием |
| **SQL-инъекции** | Все запросы параметризованы через SQLAlchemy |
| **XSS** | Telegram фильтрует HTML, экранирование не требуется |

### Защита команд

| Механизм | Описание |
|----------|---------|
| **Права админа** | Проверка перед выполнением `/admin` команд |
| **Блокировка пользователей** | `/admin_ban` исключает из системы |
| **Муты** | Временные ограничения через `/mute` |
| **Rate limiting** | Защита от спама (опционально) |

### Graceful Shutdown

Бот корректно завершает работу при получении сигналов:

```python
# SIGTERM / SIGINT → graceful shutdown
# 1. Остановка фоновых задач
# 2. Закрытие очереди сообщений
# 3. Сохранение состояния
# 4. Закрытие соединений БД
# 5. Закрытие сессии бота
```

---

## 💾 База данных

### Схема данных

```
┌─────────────┐     ┌──────────────┐
│   users     │────▶│  balances    │
│─────────────│     │──────────────│
│ id (PK)     │     │ user_id (FK) │
│ telegram_id │     │ currency     │
│ username    │     │ amount       │
│ is_admin    │     │ updated_at   │
│ is_banned   │     └──────────────┘
│ created_at  │            │
└─────────────┘            │
      │                    │
      ├────────────────────┤
      │                    │
      ▼                    ▼
┌──────────────┐   ┌──────────────┐
│ transactions │   │    items     │
│──────────────│   │──────────────│
│ id (PK)      │   │ id (PK)      │
│ user_id (FK) │   │ name         │
│ type         │   │ price        │
│ amount       │   │ type         │
│ description  │   │ is_active    │
│ created_at   │   │ created_at   │
└──────────────┘   └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  purchases   │
                    │──────────────│
                    │ id (PK)      │
                    │ user_id (FK) │
                    │ item_id (FK) │
                    │ expires_at   │
                    │ created_at   │
                    └──────────────┘

┌─────────────────┐
│  parsing_rules  │
│─────────────────│
│ id (PK)         │
│ game            │
│ pattern         │
│ currency_rate   │
│ is_active       │
│ created_at      │
└─────────────────┘
```

### Модели SQLAlchemy

| Модель | Таблица | Описание |
|--------|---------|---------|
| `User` | `users` | Пользователи бота |
| `Balance` | `balances` | Балансы пользователей |
| `Transaction` | `transactions` | История операций |
| `Item` | `items` | Товары магазина |
| `Purchase` | `purchases` | Покупки |
| `ParsingRule` | `parsing_rules` | Правила парсинга |
| `Achievement` | `achievements` | Достижения |
| `UserAchievement` | `user_achievements` | Достижения пользователей |

---

## 🧪 Тестирование

### Запуск тестов

```bash
# Все тесты
pytest tests/ -v

# С покрытием
pytest tests/ --cov=. --cov-report=html

# Только unit
pytest tests/unit/ -v

# Только интеграционные
pytest tests/integration/ -v

# Только Bridge/VK
pytest tests/bridge/ tests/vk_bot/ -v
```

### Структура тестов

```
tests/
├── conftest.py           # Общие fixtures
├── unit/
│   ├── test_settings.py           # Конфигурация
│   ├── test_user_service.py       # Сервис пользователей
│   ├── test_balance_service.py    # Сервис баланса
│   └── ...
├── integration/
│   ├── test_admin_manager.py     # Админ-менеджер
│   └── ...
├── bridge/
│   ├── test_loop_guard.py         # Защита от циклов
│   ├── test_queue.py             # Очередь сообщений
│   ├── test_vk_publisher.py      # VK publisher
│   └── test_media.py             # Медиа
├── vk_bot/
│   └── test_main.py              # VK Bot
└── property/
    ├── test_balance_properties.py
    └── test_shop_display.py
```

### Текущий статус тестов

| Категория | Количество | Статус |
|-----------|-----------|--------|
| unit/test_settings.py | 36 | ✅ Проходят |
| bridge/ | 33 | ✅ Проходят |
| vk_bot/ | 10 | ✅ Проходят |
| unit/ (остальные) | ~700 | ⚠️ Частично |
| **Итого** | **~800** | **~90%** |

---

## 🚀 Деплой

Подробная документация: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

### Docker

```bash
# Сборка
docker build -t bankbot:latest .

# Запуск (prod)
docker run -d \
  --name bankbot \
  --env-file config/.env.production \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  bankbot:latest
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  bankbot:
    build: .
    env_file: config/.env.production
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped

  # Опционально: PostgreSQL
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: bankbot
      POSTGRES_USER: bankbot
      POSTGRES_PASSWORD: secret
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

```bash
# Запуск
docker-compose up -d
```

### Systemd (Linux)

```ini
# /etc/systemd/system/bankbot.service
[Unit]
Description=BankBot Telegram Bot
After=network.target postgresql.service

[Service]
Type=simple
User=bankbot
WorkingDirectory=/opt/bankbot
Environment=ENV=production
ExecStart=/opt/bankbot/venv/bin/python run_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# Активация
sudo systemctl enable bankbot
sudo systemctl start bankbot

# Проверка
sudo systemctl status bankbot
```

---

## 🔧 Разработка

### Добавление команды

```python
# bot/commands/my_command.py

from telegram import Update
from telegram.ext import ContextTypes

async def handle_my_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /my_command"""
    user_id = update.effective_user.id
    
    # Бизнес-логика
    result = await balance_service.get_balance(user_id)
    
    # Ответ
    await update.message.reply_text(f"Результат: {result}")
```

### Добавление парсера

```python
# core/parsers/games/my_game.py

from core.parsers.base import BaseParser

class MyGameParser(BaseParser):
    """Парсер для MyGame"""
    
    GAME_NAME = "mygame"
    
    def match(self, text: str) -> bool:
        """Проверка, относится ли сообщение к этой игре"""
        return "mygame" in text.lower()
    
    def parse(self, text: str) -> dict | None:
        """Извлечение данных из сообщения"""
        # Регулярные выражения и т.д.
        return {
            "type": "mygame_activity",
            "user": "PlayerName",
            "amount": 100
        }
    
    def get_currency_rate(self) -> float:
        """Курс конвертации"""
        return 1.0
```

### Структура Service Layer

```python
# Пример: core/services/balance_service.py

from typing import Optional
from database.models import User, Balance, Transaction
from sqlalchemy.orm import Session

class BalanceService:
    """Сервис для работы с балансами"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_balance(self, user_id: int) -> float:
        """Получить баланс пользователя"""
        balance = self.session.query(Balance).filter_by(user_id=user_id).first()
        return balance.amount if balance else 0.0
    
    def add_points(self, user_id: int, amount: int, description: str) -> bool:
        """Начислить очки"""
        # Логика начисления с транзакцией
        pass
```

---

## 🐛 Устранение проблем

### Бот не отвечает

**Проверьте:**

1. **Токен бота:**
   ```bash
   grep BOT_TOKEN config/.env
   ```

2. **Запущен ли бот:**
   ```bash
   ps aux | grep run_bot
   ```

3. **Логи:**
   ```bash
   tail -f logs/bot.log
   ```

### Ошибка "BOT_TOKEN cannot be empty"

```bash
# Файл .env не найден или токен пустой
# Проверьте существование файла
ls -la config/.env

# Создайте из примера
cp config/.env.example config/.env
```

### Ошибка базы данных

```bash
# База данных повреждена
# Удалите и создайте заново
rm -f data/bot.db
python database/initialize_system.py
```

### Парсинг не работает

1. Убедитесь что отвечаете **на сообщение** бота (Reply)
2. Проверьте что игра поддерживается
3. Включите `PARSING_ENABLED=true` для автопарсинга

---

## 📈 Статистика

| Метрика | Значение |
|---------|----------|
| Строк кода | 15,000+ |
| Команд бота | 50+ |
| Тестов | 800+ |
| Покрытие тестами | ~55% |
| Поддерживаемых игр | 4 |
| Модулей | 20+ |

---

## 🤝 Вклад

1. Fork репозитория
2. Создайте ветку (`git checkout -b feature/amazing`)
3. Commit (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing`)
5. Pull Request

---

## 📄 Лицензия

MIT License — подробности в файле LICENSE.

---

## 📞 Контакты

| Канал | Ссылка |
|-------|--------|
| Telegram | @LucasTeamLuke |
| GitHub | [lucasteamalt12321/BankBot](https://github.com/lucasteamalt12321/BankBot) |
| Issues | [GitHub Issues](https://github.com/lucasteamalt12321/BankBot/issues) |

---

**🎉 Готово!** Отправьте `/start` боту чтобы начать использовать.
