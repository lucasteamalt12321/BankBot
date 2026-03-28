# 🚀 Руководство по развертыванию BankBot

**Версия:** 2.1  
**Дата:** 2026-02-20

---

## 📋 Содержание

- [Предварительные требования](#предварительные-требования)
- [Архитектурный обзор](#архитектурный-обзор)
- [Система конфигурации](#система-конфигурации)
- [Сравнение окружений](#сравнение-окружений)
- [Развертывание в Development](#развертывание-в-development)
- [Развертывание в Staging](#развертывание-в-staging)
- [Развертывание в Production](#развертывание-в-production)
- [Миграции базы данных](#миграции-базы-данных)
- [Управление процессами](#управление-процессами)
- [Мониторинг и обслуживание](#мониторинг-и-обслуживание)
- [Резервное копирование](#резервное-копирование)
- [Устранение неполадок](#устранение-неполадок)

---

## Архитектурный обзор

BankBot построен на основе многослойной архитектуры с четким разделением ответственности:

```
┌─────────────────────────────────────────┐
│     Presentation Layer (bot/)           │
│  - Telegram handlers                    │
│  - Command routing                      │
│  - User interaction                     │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│     Application Layer (core/services/)  │
│  - Business logic                       │
│  - Transaction management               │
│  - Service orchestration                │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│     Data Layer (src/repository/)        │
│  - Repository pattern                   │
│  - Data access abstraction              │
│  - Query optimization                   │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│     Database Layer (database/)          │
│  - SQLAlchemy models                    │
│  - Migrations                           │
│  - Connection pooling                   │
└─────────────────────────────────────────┘
```

### Ключевые компоненты

- **Unified Configuration System**: Централизованная конфигурация через Pydantic Settings (`src/config.py`)
- **Graceful Shutdown**: Корректное завершение работы с обработкой сигналов SIGTERM/SIGINT
- **PID Management**: Безопасное управление процессами через PID-файлы
- **Repository Pattern**: Абстракция доступа к данным для упрощения тестирования
- **Dependency Injection**: Слабая связанность компонентов
- **Error Handling Middleware**: Централизованная обработка ошибок с уведомлениями

Подробнее: [docs/ARCHITECTURE.md](ARCHITECTURE.md)

---

## Система конфигурации

BankBot использует унифицированную систему конфигурации на основе Pydantic Settings, которая обеспечивает:

- ✅ **Единый источник истины**: Все настройки в `src/config.py`
- ✅ **Автоматическая валидация**: Проверка корректности значений при запуске
- ✅ **Поддержка окружений**: development, test, staging, production
- ✅ **Безопасность**: Конфиденциальные данные только в `.env` файлах
- ✅ **Type Safety**: Строгая типизация через Pydantic

### Структура конфигурации

```python
# src/config.py
from pydantic import BaseSettings, Field, validator

class Settings(BaseSettings):
    # Environment
    ENV: str = Field(default="development", env="ENV")
    
    # Bot Configuration
    BOT_TOKEN: str = Field(..., env="BOT_TOKEN")
    ADMIN_TELEGRAM_ID: int = Field(..., env="ADMIN_TELEGRAM_ID")
    
    # Database
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    
    # Валидация при загрузке
    @validator("BOT_TOKEN")
    def validate_bot_token(cls, v):
        if not v or v == "":
            raise ValueError("BOT_TOKEN cannot be empty")
        return v
    
    class Config:
        env_file = "config/.env"
        env_file_encoding = "utf-8"

# Singleton instance
settings = Settings()
```

### Валидация при запуске

Бот автоматически проверяет конфигурацию при запуске через `StartupValidator`:

```python
# src/startup_validator.py
class StartupValidator:
    @classmethod
    def validate_all(cls):
        logger.info("🔍 Validating startup configuration...")
        cls.validate_env_file()          # Проверка существования .env
        cls.validate_required_settings()  # Проверка обязательных переменных
        cls.validate_database()           # Проверка подключения к БД
        logger.info("✅ All validations passed")
```

Если конфигурация невалидна, бот **не запустится** и выведет понятное сообщение об ошибке.

### Множественные окружения

Создайте отдельные файлы конфигурации для каждого окружения:

```
config/
├── .env                    # Активная конфигурация (symlink)
├── .env.example            # Шаблон с документацией
├── .env.development        # Разработка
├── .env.test               # Тестирование
├── .env.staging            # Предпродакшн
└── .env.production         # Продакшн
```

Переключение между окружениями:

```bash
# Linux/macOS
ln -sf .env.production config/.env

# Windows (cmd as admin)
del config\.env
mklink config\.env config\.env.production

# Или через переменную окружения
ENV=production python run_bot.py
```

Подробнее: [docs/MULTIPLE_ENVIRONMENTS.md](MULTIPLE_ENVIRONMENTS.md)

---

## Сравнение окружений

### Таблица различий окружений

| Параметр | Development | Staging | Production |
|----------|-------------|---------|------------|
| **Цель** | Локальная разработка | Предпродакшн тестирование | Реальные пользователи |
| **База данных** | SQLite (локальная) | SQLite или PostgreSQL | PostgreSQL |
| **Логирование** | DEBUG уровень | INFO уровень | INFO/WARNING уровень |
| **Парсинг** | Отключен (по умолчанию) | Включен | Включен |
| **Бэкапы** | Не требуются | Опционально | Обязательно (каждые 12ч) |
| **Мониторинг** | Не требуется | Базовый | Полный (healthcheck) |
| **Автозапуск** | Вручную | systemd service | systemd service |
| **Уведомления админа** | Опционально | Включены | Включены |
| **Rate limiting** | Отключен | Включен | Включен |
| **SSL/TLS** | Не требуется | Опционально | Обязательно |
| **Firewall** | Не требуется | Рекомендуется | Обязательно |
| **Ротация логов** | Не требуется | 7 дней | 30 дней |
| **Connection pooling** | Минимальный | Средний | Оптимизированный |

### Рекомендуемые настройки по окружениям

#### Development (.env.development)
```env
ENV=development
BOT_TOKEN=your_dev_bot_token
ADMIN_TELEGRAM_ID=your_telegram_id
DATABASE_URL=sqlite:///data/bot_dev.db
LOG_LEVEL=DEBUG
LOG_FILE=logs/bot_dev.log
PARSING_ENABLED=false
ADMIN_NOTIFICATIONS_ENABLED=false
RATE_LIMIT_ENABLED=false
BACKUP_ENABLED=false
```

**Особенности:**
- Максимально подробное логирование для отладки
- Парсинг отключен для ускорения разработки
- Уведомления отключены, чтобы не спамить
- Используется отдельный тестовый бот

#### Staging (.env.staging)
```env
ENV=staging
BOT_TOKEN=your_staging_bot_token
ADMIN_TELEGRAM_ID=your_telegram_id
DATABASE_URL=sqlite:///data/bot_staging.db
LOG_LEVEL=INFO
LOG_FILE=/home/botuser/BankBot/logs/bot_staging.log
PARSING_ENABLED=true
PARSING_CHECK_INTERVAL=60
ADMIN_NOTIFICATIONS_ENABLED=true
RATE_LIMIT_ENABLED=true
RATE_LIMIT_MAX_REQUESTS=20
BACKUP_ENABLED=true
BACKUP_INTERVAL=86400
BACKUP_RETENTION=7
```

**Особенности:**
- Максимально приближен к production
- Используется для финального тестирования перед релизом
- Все функции включены, как в production
- Отдельный тестовый бот для staging

#### Production (.env.production)
```env
ENV=production
BOT_TOKEN=your_production_bot_token
ADMIN_TELEGRAM_ID=your_telegram_id
DATABASE_URL=postgresql://botuser:secure_password@localhost:5432/botdb
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
LOG_LEVEL=INFO
LOG_FILE=/var/log/bankbot/bot.log
STRUCTURED_LOGGING=true
PARSING_ENABLED=true
PARSING_CHECK_INTERVAL=30
ADMIN_NOTIFICATIONS_ENABLED=true
NOTIFICATION_COOLDOWN=300
RATE_LIMIT_ENABLED=true
RATE_LIMIT_MAX_REQUESTS=15
TASK_CHECK_INTERVAL=300
BACKUP_ENABLED=true
BACKUP_INTERVAL=43200
BACKUP_RETENTION=14
SHOP_ENABLED=true
GAMES_ENABLED=true
ACHIEVEMENTS_ENABLED=true
SOCIAL_FEATURES_ENABLED=true
```

**Особенности:**
- PostgreSQL для надежности и производительности
- Оптимизированный connection pooling
- Частые бэкапы с длительным хранением
- Строгий rate limiting для защиты
- Все функции включены

### Когда использовать каждое окружение

**Development:**
- Разработка новых функций
- Отладка и исправление багов
- Локальное тестирование
- Эксперименты с кодом

**Staging:**
- Финальное тестирование перед релизом
- Проверка миграций БД
- Нагрузочное тестирование
- Демонстрация новых функций

**Production:**
- Работа с реальными пользователями
- Стабильная версия приложения
- Максимальная надежность и безопасность

---

## Предварительные требования

### Системные требования

#### Минимальные (Development)
- **CPU:** 1 core
- **RAM:** 512 MB
- **Disk:** 1 GB
- **OS:** Windows, Linux, macOS

#### Рекомендуемые (Production)
- **CPU:** 2+ cores
- **RAM:** 2+ GB
- **Disk:** 10+ GB (с учетом логов и бэкапов)
- **OS:** Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+)

### Программное обеспечение

- **Python:** 3.8 или выше
- **pip:** Последняя версия
- **Git:** Для клонирования репозитория
- **SQLite:** Встроен в Python (для development)
- **PostgreSQL:** 12+ (опционально, для production)

### Telegram

- Аккаунт в Telegram
- Токен бота от [@BotFather](https://t.me/BotFather)
- Telegram ID администратора от [@userinfobot](https://t.me/userinfobot)

---

## Развертывание в Development

Development окружение предназначено для локальной разработки и отладки. Оно максимально упрощено для быстрого старта и итераций.

### Преимущества Development окружения

- ✅ Быстрый старт без сложной настройки
- ✅ Подробное логирование для отладки
- ✅ Не требует внешних зависимостей (PostgreSQL, Redis)
- ✅ Легко сбросить состояние (удалить БД и начать заново)
- ✅ Безопасно экспериментировать с кодом

### Шаг 1: Клонирование репозитория

```bash
git clone https://github.com/your-username/BankBot.git
cd BankBot
```

### Шаг 2: Создание виртуального окружения

**Windows:**
```cmd
python -m venv .venv
.venv\Scripts\activate
```

**Linux/macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Проверка активации:**
```bash
which python  # Должен показать путь внутри .venv
python --version  # Должен быть Python 3.8+
```

### Шаг 3: Установка зависимостей

```bash
# Обновить pip
pip install --upgrade pip

# Установить production зависимости
pip install -r config/requirements.txt

# Для разработки также установите dev-зависимости
pip install -r requirements-dev.txt
```

**Что включено в dev-зависимости:**
- pytest, pytest-asyncio, pytest-cov - тестирование
- hypothesis - property-based тестирование
- black, flake8, mypy - линтеры и форматтеры
- ipython - улучшенная консоль для отладки

### Шаг 4: Настройка конфигурации

1. Создайте файл конфигурации из шаблона:
```bash
cp config/.env.example config/.env.development
```

2. Получите необходимые данные:
   - **BOT_TOKEN**: Создайте тестового бота через [@BotFather](https://t.me/BotFather)
     - Отправьте `/newbot`
     - Следуйте инструкциям
     - Скопируйте токен (формат: `1234567890:ABCdefGHI...`)
   - **ADMIN_TELEGRAM_ID**: Узнайте свой ID через [@userinfobot](https://t.me/userinfobot)
     - Отправьте `/start`
     - Скопируйте ваш ID (число, например: `123456789`)

3. Отредактируйте `config/.env.development`:
```env
# Environment
ENV=development

# Telegram (замените на ваши значения)
BOT_TOKEN=1234567890:ABCdefGHI-jklMNOpqrsTUVwxyz
ADMIN_TELEGRAM_ID=123456789

# Database (SQLite для development)
DATABASE_URL=sqlite:///data/bot_dev.db

# Logging (подробное для отладки)
LOG_LEVEL=DEBUG
LOG_FILE=logs/bot_dev.log

# Features (отключите парсинг для ускорения)
PARSING_ENABLED=false
ADMIN_NOTIFICATIONS_ENABLED=false
RATE_LIMIT_ENABLED=false
BACKUP_ENABLED=false

# Development-specific
DEBUG_MODE=true
```

4. Активируйте конфигурацию:

**Linux/macOS:**
```bash
ln -s .env.development config/.env
```

**Windows (cmd as admin):**
```cmd
mklink config\.env config\.env.development
```

**Альтернатива (любая ОС):**
```bash
cp config/.env.development config/.env
```

### Шаг 5: Инициализация базы данных

```bash
# Создать директорию для данных
mkdir -p data

# Инициализировать БД
python database/initialize_system.py
```

**Ожидаемый вывод:**
```
🔍 Validating startup configuration...
✅ All validations passed
📊 Initializing database...
✅ Database initialized successfully
✅ All tables created
✅ Admin user configured (ID: 123456789)
```

**Если возникла ошибка:**
```bash
# Проверить конфигурацию
python -c "from src.config import settings; print('✅ Config OK')"

# Проверить права доступа
ls -la data/
```

### Шаг 6: Запуск бота

```bash
python run_bot.py
```

**Ожидаемый вывод:**
```
[2026-02-20 10:30:00] [INFO] 🔍 Validating startup configuration...
[2026-02-20 10:30:00] [INFO] ✅ All validations passed
[2026-02-20 10:30:01] [INFO] [START] Запуск Telegram-бота банк-аггрегатора LucasTeam...
[2026-02-20 10:30:01] [INFO] Environment: development
[2026-02-20 10:30:01] [INFO] Database: sqlite:///data/bot_dev.db
[2026-02-20 10:30:02] [INFO] [INFO] Бот успешно запущен!
[2026-02-20 10:30:02] [INFO] Press Ctrl+C to stop
```

### Шаг 7: Тестирование

Откройте Telegram и найдите вашего тестового бота. Отправьте команды:

```
/start          # Регистрация/приветствие
/help           # Список команд
/balance        # Проверка баланса
/profile        # Ваш профиль
```

**Ожидаемые ответы:**
- `/start` - Приветственное сообщение с описанием бота
- `/balance` - Ваш текущий баланс (0 очков для нового пользователя)
- `/profile` - Информация о вашем профиле

### Шаг 8: Запуск тестов (опционально)

```bash
# Запустить все тесты
pytest tests/

# Запустить с coverage
pytest tests/ --cov=src --cov=core --cov=bot

# Запустить только unit тесты
pytest tests/unit/

# Запустить конкретный тест
pytest tests/unit/test_config.py -v
```

### Полезные команды для разработки

**Остановка бота:**
```bash
# Нажмите Ctrl+C в терминале
# Или отправьте SIGTERM
kill -TERM $(cat data/bot.pid)
```

**Сброс базы данных:**
```bash
# Удалить БД и начать заново
rm data/bot_dev.db
python database/initialize_system.py
```

**Просмотр логов:**
```bash
# В реальном времени
tail -f logs/bot_dev.log

# Последние 50 строк
tail -n 50 logs/bot_dev.log

# Поиск ошибок
grep ERROR logs/bot_dev.log
```

**Проверка кода:**
```bash
# Форматирование
black src/ core/ bot/

# Линтинг
flake8 src/ core/ bot/

# Проверка типов
mypy src/ core/ bot/
```

**Интерактивная отладка:**
```bash
# Запустить Python консоль с загруженной конфигурацией
python -i -c "from src.config import settings; from database.connection import get_connection"

# Теперь можно выполнять команды:
>>> settings.BOT_TOKEN
>>> conn = get_connection()
>>> cursor = conn.cursor()
>>> cursor.execute("SELECT COUNT(*) FROM users").fetchone()
```

### Типичные проблемы в Development

**Проблема:** Бот не отвечает на команды

**Решение:**
1. Проверьте, что бот запущен: `ps aux | grep "python run_bot.py"`
2. Проверьте логи: `tail -f logs/bot_dev.log`
3. Проверьте токен: `grep BOT_TOKEN config/.env`
4. Убедитесь, что используете правильного бота в Telegram

**Проблема:** `ModuleNotFoundError`

**Решение:**
```bash
# Убедитесь, что виртуальное окружение активировано
which python  # Должен показать путь в .venv

# Переустановите зависимости
pip install -r config/requirements.txt
```

**Проблема:** База данных заблокирована

**Решение:**
```bash
# Найти процессы, использующие БД
lsof data/bot_dev.db

# Остановить бота
kill -TERM $(cat data/bot.pid)

# Подождать 2 секунды и запустить снова
sleep 2 && python run_bot.py
```

### Советы по разработке

1. **Используйте отдельного тестового бота** - не используйте production бота для разработки
2. **Включайте DEBUG логирование** - это поможет быстро находить проблемы
3. **Регулярно запускайте тесты** - `pytest tests/` перед каждым коммитом
4. **Используйте git branches** - создавайте отдельную ветку для каждой функции
5. **Сбрасывайте БД при необходимости** - не бойтесь удалять `bot_dev.db` для чистого старта

---

## Развертывание в Staging

Staging окружение максимально приближено к production для финального тестирования перед релизом. Используйте его для проверки новых функций, миграций БД и нагрузочного тестирования.

### Цели Staging окружения

- ✅ Финальное тестирование перед production релизом
- ✅ Проверка миграций базы данных
- ✅ Нагрузочное тестирование
- ✅ Демонстрация новых функций заказчику
- ✅ Обучение пользователей на безопасной копии

### Шаг 1: Подготовка сервера

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка необходимых пакетов
sudo apt install -y python3 python3-pip python3-venv git sqlite3

# Опционально: PostgreSQL для staging (рекомендуется)
sudo apt install -y postgresql postgresql-contrib

# Создание пользователя для бота
sudo useradd -m -s /bin/bash botuser
sudo passwd botuser  # Установите пароль

# Переключение на пользователя бота
sudo su - botuser
```

### Шаг 2: Клонирование и настройка

```bash
# Клонирование репозитория
git clone https://github.com/your-username/BankBot.git
cd BankBot

# Создание виртуального окружения
python3 -m venv .venv
source .venv/bin/activate

# Установка зависимостей
pip install --upgrade pip
pip install -r config/requirements.txt

# Если используете PostgreSQL
pip install psycopg2-binary
```

### Шаг 3: Конфигурация staging

Создайте `config/.env.staging`:

**Вариант 1: SQLite (проще, для небольших нагрузок)**
```env
# Environment
ENV=staging

# Telegram
BOT_TOKEN=your_staging_bot_token
ADMIN_TELEGRAM_ID=your_telegram_id

# Database (SQLite)
DATABASE_URL=sqlite:///data/bot_staging.db

# Logging
LOG_LEVEL=INFO
LOG_FILE=/home/botuser/BankBot/logs/bot_staging.log

# Features (все включено, как в production)
PARSING_ENABLED=true
PARSING_CHECK_INTERVAL=60

# Notifications
ADMIN_NOTIFICATIONS_ENABLED=true
NOTIFICATION_COOLDOWN=300

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_MAX_REQUESTS=20

# Background Tasks
TASK_CHECK_INTERVAL=300

# Backups
BACKUP_ENABLED=true
BACKUP_INTERVAL=86400  # 24 часа
BACKUP_RETENTION=7     # 7 дней

# Features
SHOP_ENABLED=true
GAMES_ENABLED=true
ACHIEVEMENTS_ENABLED=true
```

**Вариант 2: PostgreSQL (рекомендуется, ближе к production)**
```env
# Environment
ENV=staging

# Telegram
BOT_TOKEN=your_staging_bot_token
ADMIN_TELEGRAM_ID=your_telegram_id

# Database (PostgreSQL)
DATABASE_URL=postgresql://botuser:staging_password@localhost:5432/botdb_staging
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30

# Остальные настройки как в варианте 1...
```

Активируйте конфигурацию:
```bash
ln -s .env.staging config/.env
```

### Шаг 4: Настройка PostgreSQL (если используете)

```bash
# Переключение на пользователя postgres
sudo -u postgres psql

# В psql консоли:
CREATE DATABASE botdb_staging;
CREATE USER botuser WITH ENCRYPTED PASSWORD 'staging_password';
GRANT ALL PRIVILEGES ON DATABASE botdb_staging TO botuser;
\q
```

Проверьте подключение:
```bash
psql -U botuser -h localhost -d botdb_staging -c "SELECT 1;"
```

### Шаг 5: Инициализация БД

```bash
# Создать директории
mkdir -p data logs

# Инициализировать БД
python database/initialize_system.py
```

**Ожидаемый вывод:**
```
🔍 Validating startup configuration...
✅ All validations passed
📊 Initializing database...
✅ Database initialized successfully
✅ All tables created
✅ Admin user configured
```

### Шаг 6: Настройка systemd service

Создайте `/etc/systemd/system/bankbot-staging.service`:

```bash
sudo tee /etc/systemd/system/bankbot-staging.service << 'EOF'
[Unit]
Description=BankBot Telegram Bot (Staging)
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/BankBot
Environment="PATH=/home/botuser/BankBot/.venv/bin"
Environment="ENV=staging"
ExecStart=/home/botuser/BankBot/.venv/bin/python run_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Graceful shutdown
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
```

Активируйте сервис:
```bash
sudo systemctl daemon-reload
sudo systemctl enable bankbot-staging
sudo systemctl start bankbot-staging
```

Проверьте статус:
```bash
sudo systemctl status bankbot-staging
```

**Ожидаемый вывод:**
```
● bankbot-staging.service - BankBot Telegram Bot (Staging)
   Loaded: loaded (/etc/systemd/system/bankbot-staging.service; enabled)
   Active: active (running) since Wed 2026-02-20 10:30:00 UTC; 5s ago
 Main PID: 12345 (python)
   Status: "Bot is running"
```

### Шаг 7: Настройка логирования

```bash
# Создание директории для логов (если еще не создана)
mkdir -p /home/botuser/BankBot/logs

# Настройка ротации логов
sudo tee /etc/logrotate.d/bankbot-staging << 'EOF'
/home/botuser/BankBot/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 botuser botuser
    sharedscripts
    postrotate
        systemctl reload bankbot-staging > /dev/null 2>&1 || true
    endscript
}
EOF
```

Проверьте конфигурацию logrotate:
```bash
sudo logrotate -d /etc/logrotate.d/bankbot-staging
```

### Шаг 8: Тестирование staging окружения

**1. Проверка базовых команд:**
```
/start
/help
/balance
/profile
```

**2. Проверка admin команд:**
```
/admin_health
/admin_stats
/config_status
```

**3. Проверка парсинга (если включен):**
- Отправьте тестовое сообщение с результатами игры
- Проверьте, что очки начислены корректно

**4. Проверка уведомлений:**
- Вызовите ошибку (например, неверная команда)
- Проверьте, что администратор получил уведомление

### Шаг 9: Мониторинг staging

**Просмотр логов в реальном времени:**
```bash
# Через journalctl
sudo journalctl -u bankbot-staging -f

# Через файл логов
tail -f /home/botuser/BankBot/logs/bot_staging.log
```

**Проверка статуса:**
```bash
# Статус сервиса
sudo systemctl status bankbot-staging

# Использование ресурсов
ps aux | grep "python run_bot.py"
top -p $(pgrep -f "python run_bot.py")
```

**Проверка БД:**
```bash
# SQLite
sqlite3 data/bot_staging.db "SELECT COUNT(*) FROM users;"

# PostgreSQL
psql -U botuser -d botdb_staging -c "SELECT COUNT(*) FROM users;"
```

### Полезные команды для staging

**Перезапуск бота:**
```bash
sudo systemctl restart bankbot-staging
```

**Остановка бота:**
```bash
sudo systemctl stop bankbot-staging
```

**Просмотр последних ошибок:**
```bash
sudo journalctl -u bankbot-staging -p err -n 50
```

**Обновление кода:**
```bash
# Остановить бота
sudo systemctl stop bankbot-staging

# Обновить код
sudo -u botuser bash << 'EOF'
cd /home/botuser/BankBot
git pull origin main
source .venv/bin/activate
pip install -r config/requirements.txt
EOF

# Применить миграции (если есть)
sudo -u botuser bash << 'EOF'
cd /home/botuser/BankBot
source .venv/bin/activate
python database/migrations/migrate.py
EOF

# Запустить бота
sudo systemctl start bankbot-staging
```

### Тестирование перед production

Перед развертыванием в production выполните следующие проверки:

- [ ] Все основные команды работают корректно
- [ ] Парсинг работает и очки начисляются правильно
- [ ] Уведомления администратора приходят
- [ ] Логи не содержат критических ошибок
- [ ] База данных работает стабильно
- [ ] Миграции применяются без ошибок
- [ ] Бэкапы создаются автоматически
- [ ] Graceful shutdown работает корректно
- [ ] Нагрузочное тестирование пройдено
- [ ] Документация обновлена

### Типичные проблемы в Staging

**Проблема:** Сервис не запускается

**Решение:**
```bash
# Проверить логи
sudo journalctl -u bankbot-staging -n 50

# Проверить конфигурацию
sudo -u botuser bash << 'EOF'
cd /home/botuser/BankBot
source .venv/bin/activate
python -c "from src.config import settings; print('✅ Config OK')"
EOF

# Проверить права доступа
ls -la /home/botuser/BankBot/
```

**Проблема:** Бот не отвечает после обновления

**Решение:**
```bash
# Полный перезапуск
sudo systemctl stop bankbot-staging
sleep 5
sudo systemctl start bankbot-staging
sudo systemctl status bankbot-staging
```

---

## Развертывание в Production

Production окружение требует максимальной надежности, безопасности и производительности. Следуйте этим инструкциям внимательно для обеспечения стабильной работы бота с реальными пользователями.

### Критические требования для Production

- ✅ PostgreSQL для надежности и производительности
- ✅ Автоматические бэкапы с внешним хранением
- ✅ Мониторинг и алертинг
- ✅ Firewall и безопасность
- ✅ SSL/TLS для всех соединений
- ✅ Ротация логов
- ✅ Graceful shutdown и автоперезапуск
- ✅ Документированный процесс обновления

### Шаг 1: Подготовка production сервера

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка необходимых пакетов
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    postgresql \
    postgresql-contrib \
    nginx \
    certbot \
    python3-certbot-nginx \
    fail2ban \
    ufw

# Создание пользователя для бота
sudo useradd -m -s /bin/bash botuser
sudo passwd botuser  # Установите СИЛЬНЫЙ пароль

# Добавление в группу для логов
sudo usermod -aG adm botuser
```

### Шаг 2: Настройка PostgreSQL

```bash
# Переключение на пользователя postgres
sudo -u postgres psql

# В psql консоли:
-- Создание БД и пользователя
CREATE DATABASE botdb;
CREATE USER botuser WITH ENCRYPTED PASSWORD 'STRONG_PASSWORD_HERE';
GRANT ALL PRIVILEGES ON DATABASE botdb TO botuser;

-- Настройка для production
ALTER DATABASE botdb SET timezone TO 'UTC';
ALTER ROLE botuser SET client_encoding TO 'utf8';
ALTER ROLE botuser SET default_transaction_isolation TO 'read committed';

\q
```

**Настройка PostgreSQL для production:**

Отредактируйте `/etc/postgresql/14/main/postgresql.conf`:
```ini
# Connection Settings
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 2621kB
min_wal_size = 1GB
max_wal_size = 4GB

# Logging
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
log_checkpoints = on
log_connections = on
log_disconnections = on
log_duration = off
log_lock_waits = on
```

Перезапустите PostgreSQL:
```bash
sudo systemctl restart postgresql
```

Проверьте подключение:
```bash
psql -U botuser -h localhost -d botdb -c "SELECT version();"
```

### Шаг 3: Клонирование и установка

```bash
# Переключение на пользователя бота
sudo su - botuser

# Клонирование репозитория
git clone https://github.com/your-username/BankBot.git
cd BankBot

# Создание виртуального окружения
python3 -m venv .venv
source .venv/bin/activate

# Установка зависимостей
pip install --upgrade pip
pip install -r config/requirements.txt
pip install psycopg2-binary  # PostgreSQL driver
```

### Шаг 4: Production конфигурация

Создайте `config/.env.production`:

```env
# ============================================
# PRODUCTION CONFIGURATION
# ============================================

# Environment
ENV=production

# ============================================
# TELEGRAM CONFIGURATION
# ============================================
BOT_TOKEN=YOUR_PRODUCTION_BOT_TOKEN_HERE
ADMIN_TELEGRAM_ID=YOUR_TELEGRAM_ID_HERE

# ============================================
# DATABASE CONFIGURATION (PostgreSQL)
# ============================================
DATABASE_URL=postgresql://botuser:STRONG_PASSWORD_HERE@localhost:5432/botdb
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600

# ============================================
# LOGGING CONFIGURATION
# ============================================
LOG_LEVEL=INFO
LOG_FILE=/var/log/bankbot/bot.log
STRUCTURED_LOGGING=true
LOG_ROTATION_SIZE=10485760  # 10MB
LOG_ROTATION_COUNT=30

# ============================================
# PARSING CONFIGURATION
# ============================================
PARSING_ENABLED=true
PARSING_CHECK_INTERVAL=30  # 30 секунд

# ============================================
# NOTIFICATIONS
# ============================================
ADMIN_NOTIFICATIONS_ENABLED=true
NOTIFICATION_COOLDOWN=300  # 5 минут между уведомлениями

# ============================================
# SECURITY & RATE LIMITING
# ============================================
RATE_LIMIT_ENABLED=true
RATE_LIMIT_MAX_REQUESTS=15  # Запросов в минуту
RATE_LIMIT_WINDOW=60        # Окно в секундах

# ============================================
# BACKGROUND TASKS
# ============================================
TASK_CHECK_INTERVAL=300  # 5 минут

# ============================================
# BACKUP CONFIGURATION
# ============================================
BACKUP_ENABLED=true
BACKUP_INTERVAL=43200   # 12 часов
BACKUP_RETENTION=14     # 14 дней
BACKUP_PATH=/home/botuser/BankBot/backups

# ============================================
# FEATURES
# ============================================
SHOP_ENABLED=true
GAMES_ENABLED=true
ACHIEVEMENTS_ENABLED=true
SOCIAL_FEATURES_ENABLED=true

# ============================================
# PERFORMANCE
# ============================================
CACHE_ENABLED=true
CACHE_TTL=300  # 5 минут
```

**ВАЖНО:** Замените следующие значения:
- `YOUR_PRODUCTION_BOT_TOKEN_HERE` - токен production бота от @BotFather
- `YOUR_TELEGRAM_ID_HERE` - ваш Telegram ID
- `STRONG_PASSWORD_HERE` - пароль PostgreSQL пользователя

Активируйте конфигурацию:
```bash
ln -s .env.production config/.env
```

Установите правильные права доступа:
```bash
chmod 600 config/.env.production
chmod 600 config/.env
```

### Шаг 5: Инициализация production БД

```bash
# Создать директории
mkdir -p data logs backups

# Инициализировать БД
python database/initialize_system.py
```

**Проверка инициализации:**
```bash
psql -U botuser -h localhost -d botdb -c "\dt"
```

Вы должны увидеть список таблиц: users, transactions, parsing_rules, и т.д.

### Шаг 6: Настройка systemd service

Создайте `/etc/systemd/system/bankbot.service`:

```bash
sudo tee /etc/systemd/system/bankbot.service << 'EOF'
[Unit]
Description=BankBot Telegram Bot (Production)
After=network.target postgresql.service
Requires=postgresql.service
Documentation=https://github.com/your-username/BankBot

[Service]
Type=simple
User=botuser
Group=botuser
WorkingDirectory=/home/botuser/BankBot
Environment="PATH=/home/botuser/BankBot/.venv/bin"
Environment="ENV=production"
Environment="PYTHONUNBUFFERED=1"

# Запуск
ExecStart=/home/botuser/BankBot/.venv/bin/python run_bot.py

# Перезапуск при сбоях
Restart=always
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5

# Graceful shutdown
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30
SendSIGKILL=yes

# Логирование
StandardOutput=journal
StandardError=journal
SyslogIdentifier=bankbot

# Безопасность
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/botuser/BankBot/data /var/log/bankbot /home/botuser/BankBot/backups
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true

# Ресурсы
MemoryLimit=1G
CPUQuota=80%

[Install]
WantedBy=multi-user.target
EOF
```

Активируйте сервис:
```bash
sudo systemctl daemon-reload
sudo systemctl enable bankbot
sudo systemctl start bankbot
```

Проверьте статус:
```bash
sudo systemctl status bankbot
```

### Шаг 7: Настройка логирования

```bash
# Создание директории для логов
sudo mkdir -p /var/log/bankbot
sudo chown botuser:botuser /var/log/bankbot
sudo chmod 755 /var/log/bankbot

# Настройка ротации логов
sudo tee /etc/logrotate.d/bankbot << 'EOF'
/var/log/bankbot/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 botuser botuser
    sharedscripts
    postrotate
        systemctl reload bankbot > /dev/null 2>&1 || true
    endscript
}
EOF

# Проверка конфигурации
sudo logrotate -d /etc/logrotate.d/bankbot
```

### Шаг 8: Настройка мониторинга

**Health check через systemd:**

```bash
# Создание health check сервиса
sudo tee /etc/systemd/system/bankbot-healthcheck.service << 'EOF'
[Unit]
Description=BankBot Health Check
After=bankbot.service

[Service]
Type=oneshot
User=botuser
WorkingDirectory=/home/botuser/BankBot
Environment="PATH=/home/botuser/BankBot/.venv/bin"
ExecStart=/home/botuser/BankBot/.venv/bin/python -c "from utils.monitoring.monitoring_system import check_health; check_health()"
StandardOutput=journal
StandardError=journal
EOF

# Создание таймера для health check
sudo tee /etc/systemd/system/bankbot-healthcheck.timer << 'EOF'
[Unit]
Description=BankBot Health Check Timer
Requires=bankbot.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min
Unit=bankbot-healthcheck.service

[Install]
WantedBy=timers.target
EOF

# Активация
sudo systemctl daemon-reload
sudo systemctl enable bankbot-healthcheck.timer
sudo systemctl start bankbot-healthcheck.timer
```

Проверьте таймер:
```bash
sudo systemctl list-timers bankbot-healthcheck.timer
```

### Шаг 9: Настройка firewall

```bash
# Базовая настройка UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Разрешить SSH (ВАЖНО: сделайте это ПЕРЕД включением firewall!)
sudo ufw allow ssh
sudo ufw allow 22/tcp

# Разрешить PostgreSQL только с localhost (если нужен внешний доступ)
# sudo ufw allow from 192.168.1.0/24 to any port 5432

# Включить firewall
sudo ufw enable

# Проверить статус
sudo ufw status verbose
```

### Шаг 10: Настройка fail2ban (защита от брутфорса)

```bash
# Создание фильтра для бота
sudo tee /etc/fail2ban/filter.d/bankbot.conf << 'EOF'
[Definition]
failregex = ^.*\[ERROR\].*Rate limit exceeded for user <HOST>.*$
            ^.*\[WARNING\].*Suspicious activity from <HOST>.*$
ignoreregex =
EOF

# Создание jail для бота
sudo tee /etc/fail2ban/jail.d/bankbot.conf << 'EOF'
[bankbot]
enabled = true
port = all
filter = bankbot
logpath = /var/log/bankbot/bot.log
maxretry = 5
bantime = 3600
findtime = 600
EOF

# Перезапуск fail2ban
sudo systemctl restart fail2ban
sudo fail2ban-client status bankbot
```

### Шаг 11: Настройка автоматических бэкапов

**Локальные бэкапы (встроенные):**

Бот автоматически создает бэкапы согласно настройкам в `.env`:
```env
BACKUP_ENABLED=true
BACKUP_INTERVAL=43200  # 12 часов
BACKUP_RETENTION=14    # 14 дней
```

**Внешние бэкапы (рекомендуется):**

Создайте скрипт для бэкапа на внешнее хранилище:

```bash
sudo tee /usr/local/bin/bankbot-backup.sh << 'EOF'
#!/bin/bash
set -e

# Конфигурация
BACKUP_DIR="/home/botuser/BankBot/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="botdb_${TIMESTAMP}.sql.gz"
S3_BUCKET="your-s3-bucket"  # Замените на ваш bucket

# Создание бэкапа
echo "[$(date)] Starting backup..."
pg_dump -U botuser -h localhost botdb | gzip > "${BACKUP_DIR}/${BACKUP_FILE}"

# Загрузка на S3 (если настроен AWS CLI)
if command -v aws &> /dev/null; then
    echo "[$(date)] Uploading to S3..."
    aws s3 cp "${BACKUP_DIR}/${BACKUP_FILE}" "s3://${S3_BUCKET}/backups/"
fi

# Удаление старых локальных бэкапов (старше 7 дней)
find "${BACKUP_DIR}" -name "botdb_*.sql.gz" -mtime +7 -delete

echo "[$(date)] Backup completed: ${BACKUP_FILE}"
EOF

sudo chmod +x /usr/local/bin/bankbot-backup.sh
```

Настройте cron для автоматических бэкапов:
```bash
sudo crontab -e

# Добавьте строку (бэкап каждые 6 часов):
0 */6 * * * /usr/local/bin/bankbot-backup.sh >> /var/log/bankbot/backup.log 2>&1
```

### Шаг 12: Финальная проверка

**Чеклист перед запуском:**

- [ ] PostgreSQL работает и доступен
- [ ] Конфигурация валидна (`python -c "from src.config import settings"`)
- [ ] База данных инициализирована
- [ ] Systemd service запущен и работает
- [ ] Логи пишутся корректно
- [ ] Firewall настроен
- [ ] Бэкапы работают
- [ ] Health check работает
- [ ] Бот отвечает на команды в Telegram

**Тестирование:**

```bash
# 1. Проверка сервиса
sudo systemctl status bankbot

# 2. Проверка логов
sudo journalctl -u bankbot -n 50

# 3. Проверка БД
psql -U botuser -d botdb -c "SELECT COUNT(*) FROM users;"

# 4. Проверка бота в Telegram
# Отправьте: /start, /help, /balance

# 5. Проверка admin команд
# Отправьте: /admin_health, /admin_stats
```

### Управление production ботом

**Просмотр логов:**
```bash
# Реальное время
sudo journalctl -u bankbot -f

# Последние 100 строк
sudo journalctl -u bankbot -n 100

# Только ошибки
sudo journalctl -u bankbot -p err

# За сегодня
sudo journalctl -u bankbot --since today

# Файловые логи
tail -f /var/log/bankbot/bot.log
```

**Перезапуск:**
```bash
# Graceful restart
sudo systemctl restart bankbot

# Проверка статуса
sudo systemctl status bankbot
```

**Остановка:**
```bash
sudo systemctl stop bankbot
```

**Мониторинг ресурсов:**
```bash
# CPU и память
top -p $(pgrep -f "python run_bot.py")

# Детальная информация
ps aux | grep "python run_bot.py"

# Использование диска
df -h
du -sh /home/botuser/BankBot/data
du -sh /var/log/bankbot
```

### Обновление production бота

**ВАЖНО:** Всегда создавайте бэкап перед обновлением!

```bash
# 1. Создать бэкап
sudo -u botuser pg_dump -U botuser botdb > /tmp/backup_before_update_$(date +%Y%m%d).sql

# 2. Остановить бота
sudo systemctl stop bankbot

# 3. Обновить код
sudo -u botuser bash << 'EOF'
cd /home/botuser/BankBot
git fetch origin
git checkout main
git pull origin main
source .venv/bin/activate
pip install --upgrade -r config/requirements.txt
EOF

# 4. Применить миграции БД (если есть)
sudo -u botuser bash << 'EOF'
cd /home/botuser/BankBot
source .venv/bin/activate
python database/migrations/migrate.py
EOF

# 5. Проверить конфигурацию
sudo -u botuser bash << 'EOF'
cd /home/botuser/BankBot
source .venv/bin/activate
python -c "from src.config import settings; print('✅ Config OK')"
EOF

# 6. Запустить бота
sudo systemctl start bankbot

# 7. Проверить статус
sudo systemctl status bankbot
sudo journalctl -u bankbot -n 50
```

### Откат к предыдущей версии

Если обновление вызвало проблемы:

```bash
# 1. Остановить бота
sudo systemctl stop bankbot

# 2. Откатить код
sudo -u botuser bash << 'EOF'
cd /home/botuser/BankBot
git log --oneline -10  # Найти предыдущий коммит
git checkout <previous-commit-hash>
EOF

# 3. Восстановить БД из бэкапа
sudo -u botuser psql -U botuser -d botdb < /tmp/backup_before_update_YYYYMMDD.sql

# 4. Запустить бота
sudo systemctl start bankbot
```

### Мониторинг и алертинг

**Настройка email уведомлений при сбоях:**

```bash
# Установка mailutils
sudo apt install -y mailutils

# Настройка systemd для отправки email при сбоях
sudo mkdir -p /etc/systemd/system/bankbot.service.d
sudo tee /etc/systemd/system/bankbot.service.d/email-on-failure.conf << 'EOF'
[Unit]
OnFailure=status-email@%n.service
EOF

sudo systemctl daemon-reload
```

### Безопасность в Production

**Регулярные задачи безопасности:**

1. **Обновление системы (еженедельно):**
```bash
sudo apt update && sudo apt upgrade -y
```

2. **Ротация секретов (ежемесячно):**
```bash
# Обновите BOT_TOKEN через @BotFather
# Обновите пароль PostgreSQL
# Обновите config/.env.production
sudo systemctl restart bankbot
```

3. **Проверка логов на подозрительную активность (ежедневно):**
```bash
sudo journalctl -u bankbot | grep -i "error\|warning\|suspicious"
```

4. **Проверка бэкапов (еженедельно):**
```bash
ls -lh /home/botuser/BankBot/backups/
# Проверьте, что бэкапы создаются регулярно
```

---

## Миграции базы данных

### Создание новой миграции

1. Создайте файл миграции в `database/migrations/`:

```python
# database/migrations/002_add_new_feature.py
"""
Migration: Add new feature table
Date: 2026-02-20
"""

def upgrade(conn):
    """Apply migration"""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS new_feature (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            feature_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()

def downgrade(conn):
    """Rollback migration"""
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS new_feature")
    conn.commit()
```

### Применение миграций

```bash
# Применить все миграции
python database/migrations/migrate.py

# Применить конкретную миграцию
python database/migrations/migrate.py --migration 002_add_new_feature.py
```

### Откат миграции

```bash
python database/migrations/migrate.py --rollback
```

### Проверка статуса миграций

```bash
python database/migrations/migrate.py --status
```

---

## Управление процессами

BankBot использует современную систему управления процессами с PID-файлами и graceful shutdown.

### PID Management

Система автоматически управляет PID-файлами для безопасного контроля процессов:

```python
# src/process_manager.py
class ProcessManager:
    PID_FILE = Path("data/bot.pid")
    
    @classmethod
    def write_pid(cls):
        """Записать PID текущего процесса"""
        cls.PID_FILE.parent.mkdir(exist_ok=True)
        cls.PID_FILE.write_text(str(os.getpid()))
    
    @classmethod
    def kill_existing(cls):
        """Безопасно завершить существующий процесс"""
        pid = cls.read_pid()
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                logger.info(f"Sent SIGTERM to process {pid}")
            except ProcessLookupError:
                logger.warning(f"Process {pid} not found")
            finally:
                cls.remove_pid()
```

### Graceful Shutdown

Бот корректно завершает работу при получении сигналов SIGTERM или SIGINT:

```python
# bot/main.py
class BotApplication:
    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов"""
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._signal_handler)
    
    async def shutdown(self):
        """Корректное завершение работы"""
        logger.info("Shutting down gracefully...")
        
        # 1. Закрыть соединения с БД
        await self.db.close()
        
        # 2. Отменить фоновые задачи
        for task in self.background_tasks:
            task.cancel()
        
        # 3. Закрыть сессию бота
        await self.bot.session.close()
        
        # 4. Удалить PID-файл
        ProcessManager.remove_pid()
        
        logger.info("Shutdown complete")
```

### Управление процессом

**Запуск:**
```bash
python run_bot.py
# PID записывается в data/bot.pid
```

**Остановка (graceful):**
```bash
# Отправить SIGTERM процессу
kill -TERM $(cat data/bot.pid)

# Или через systemd
sudo systemctl stop bankbot
```

**Перезапуск:**
```bash
# Через systemd (рекомендуется)
sudo systemctl restart bankbot

# Вручную
kill -TERM $(cat data/bot.pid) && sleep 2 && python run_bot.py
```

**Проверка статуса:**
```bash
# Проверить, запущен ли процесс
if [ -f data/bot.pid ]; then
    pid=$(cat data/bot.pid)
    if ps -p $pid > /dev/null; then
        echo "Bot is running (PID: $pid)"
    else
        echo "PID file exists but process is not running"
    fi
else
    echo "Bot is not running"
fi
```

### Автоматический перезапуск

При использовании systemd бот автоматически перезапускается при сбоях:

```ini
[Service]
Restart=always
RestartSec=10
```

Это обеспечивает высокую доступность в production окружении.

---

## Мониторинг и обслуживание

### Централизованная обработка ошибок

BankBot использует middleware для централизованной обработки ошибок:

```python
# bot/middleware/error_handler.py
class ErrorHandlerMiddleware(BaseMiddleware):
    async def on_process_message(self, message: types.Message, data: dict):
        try:
            yield
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            
            # Уведомить пользователя
            await message.answer(
                "Произошла ошибка при обработке команды. "
                "Администраторы уже уведомлены."
            )
            
            # Уведомить администратора (если включено)
            if settings.ADMIN_NOTIFICATIONS_ENABLED:
                await message.bot.send_message(
                    settings.ADMIN_TELEGRAM_ID,
                    f"⚠️ Error in bot:\n{str(e)}\n\n"
                    f"User: {message.from_user.id}\n"
                    f"Message: {message.text}"
                )
```

**Преимущества:**
- ✅ Дружественные сообщения пользователям
- ✅ Детальное логирование ошибок с полным стектрейсом
- ✅ Автоматические уведомления администратора о критических ошибках
- ✅ Отсутствие необработанных исключений
- ✅ Cooldown для предотвращения спама уведомлений

**Настройка в `.env`:**
```env
ADMIN_NOTIFICATIONS_ENABLED=true
NOTIFICATION_COOLDOWN=300  # 5 минут между уведомлениями об одной ошибке
```

### Проверка статуса бота

```bash
# Статус systemd service
sudo systemctl status bankbot

# Логи в реальном времени
sudo journalctl -u bankbot -f

# Последние 100 строк логов
sudo journalctl -u bankbot -n 100

# Логи за сегодня
sudo journalctl -u bankbot --since today
```

### Мониторинг через Telegram

Отправьте боту команды:
```
/admin_health       # Здоровье системы
/admin_stats        # Статистика
/config_status      # Статус конфигурации
```

### Мониторинг базы данных

```bash
# Размер БД
du -h data/bot.db

# Количество пользователей
sqlite3 data/bot.db "SELECT COUNT(*) FROM users;"

# Последние транзакции
sqlite3 data/bot.db "SELECT * FROM transactions ORDER BY timestamp DESC LIMIT 10;"
```

### Мониторинг ресурсов

```bash
# CPU и память
top -p $(pgrep -f "python run_bot.py")

# Использование диска
df -h

# Логи
tail -f /var/log/bankbot/bot.log
```

---

## Резервное копирование

### Автоматические бэкапы

Бот автоматически создает бэкапы согласно настройкам в `.env`:
```env
BACKUP_ENABLED=true
BACKUP_INTERVAL=43200  # 12 часов
BACKUP_RETENTION=14    # Хранить 14 бэкапов
```

Бэкапы сохраняются в `data/backups/`.

### Ручное создание бэкапа

```bash
# SQLite
cp data/bot.db data/backups/bot_manual_$(date +%Y%m%d_%H%M%S).db

# PostgreSQL
pg_dump -U botuser -h localhost botdb > backups/botdb_$(date +%Y%m%d_%H%M%S).sql
```

### Восстановление из бэкапа

**SQLite:**
```bash
# Остановить бота
sudo systemctl stop bankbot

# Восстановить БД
cp data/backups/bot_backup_20260220_120000.db data/bot.db

# Запустить бота
sudo systemctl start bankbot
```

**PostgreSQL:**
```bash
# Остановить бота
sudo systemctl stop bankbot

# Восстановить БД
psql -U botuser -h localhost botdb < backups/botdb_20260220_120000.sql

# Запустить бота
sudo systemctl start bankbot
```

### Настройка внешних бэкапов

Для production рекомендуется настроить бэкапы на внешнее хранилище:

```bash
# Пример: бэкап на S3 через cron
sudo tee /etc/cron.daily/bankbot-backup << 'EOF'
#!/bin/bash
BACKUP_FILE="/tmp/botdb_$(date +%Y%m%d).sql"
pg_dump -U botuser botdb > "$BACKUP_FILE"
aws s3 cp "$BACKUP_FILE" s3://your-bucket/backups/
rm "$BACKUP_FILE"
EOF

sudo chmod +x /etc/cron.daily/bankbot-backup
```

---

## Устранение неполадок

### Ошибки конфигурации

**Проблема:** `❌ .env file not found at config/.env`

**Причина:** Файл конфигурации не создан или находится в неправильном месте.

**Решение:**
```bash
# Создать из шаблона
cp config/.env.example config/.env

# Отредактировать и заполнить обязательные переменные
nano config/.env
```

---

**Проблема:** `BOT_TOKEN cannot be empty` или `ADMIN_TELEGRAM_ID must be a positive integer`

**Причина:** Обязательные переменные окружения не установлены или имеют неверный формат.

**Решение:**
```bash
# Проверить конфигурацию
cat config/.env | grep -E "BOT_TOKEN|ADMIN_TELEGRAM_ID"

# Получить токен бота от @BotFather
# Получить Telegram ID от @userinfobot

# Обновить config/.env:
BOT_TOKEN=1234567890:ABCdefGHI...
ADMIN_TELEGRAM_ID=123456789
```

---

**Проблема:** `ValidationError` при запуске

**Причина:** Неверный формат значений в `.env` файле.

**Решение:**
```bash
# Запустить валидацию конфигурации
python -c "from src.config import settings; print('✅ Configuration valid')"

# Проверить типы данных:
# - BOT_TOKEN: строка
# - ADMIN_TELEGRAM_ID: целое число
# - DATABASE_URL: строка (URL)
# - LOG_LEVEL: DEBUG|INFO|WARNING|ERROR|CRITICAL
```

### Бот не запускается

**Проблема:** Ошибка при запуске или бот сразу завершается

**Решение:**
```bash
# 1. Проверить логи systemd
sudo journalctl -u bankbot -n 50 --no-pager

# 2. Проверить валидацию конфигурации
python -c "from src.config import settings; print('✅ Config OK')"

# 3. Проверить подключение к БД
python -c "from database.connection import get_connection; conn = get_connection(); print('✅ DB OK')"

# 4. Проверить PID-файл (может быть старый процесс)
if [ -f data/bot.pid ]; then
    echo "Old PID file found, removing..."
    rm data/bot.pid
fi

# 5. Запустить в debug режиме
ENV=development LOG_LEVEL=DEBUG python run_bot.py
```

---

**Проблема:** `Cannot connect to database`

**Причина:** Неверный DATABASE_URL или БД недоступна.

**Решение:**
```bash
# SQLite: проверить путь и права
ls -la data/bot.db
chmod 644 data/bot.db

# PostgreSQL: проверить подключение
psql -U botuser -h localhost -d botdb -c "SELECT 1;"

# Проверить DATABASE_URL в .env
grep DATABASE_URL config/.env
```

### Бот не отвечает на команды

**Проблема:** Бот онлайн, но не отвечает

**Решение:**
```bash
# Перезапустить бота
sudo systemctl restart bankbot

# Проверить токен
grep BOT_TOKEN config/.env

# Проверить сеть
ping api.telegram.org
```

### Ошибки базы данных

**Проблема:** Database locked или connection errors

**Решение:**
```bash
# SQLite: проверить блокировки
lsof data/bot.db

# PostgreSQL: проверить соединения
psql -U botuser -c "SELECT * FROM pg_stat_activity WHERE datname='botdb';"

# Перезапустить БД (PostgreSQL)
sudo systemctl restart postgresql
```

### Высокое использование ресурсов

**Проблема:** Бот потребляет много CPU/RAM

**Решение:**
```bash
# Проверить процессы
ps aux | grep python

# Проверить логи на ошибки
sudo journalctl -u bankbot | grep ERROR

# Оптимизировать БД
sqlite3 data/bot.db "VACUUM;"
```

### Проблемы с парсингом

**Проблема:** Парсинг не работает

**Решение:**
```bash
# Проверить настройки
grep PARSING_ENABLED config/.env

# Проверить логи парсинга
sudo journalctl -u bankbot | grep -i parsing

# Тестовый парсинг
python -c "from core.parsers.simple_parser import parse_game_message; print(parse_game_message('test'))"
```

---

## Обновление бота

### Development

```bash
git pull origin main
pip install -r config/requirements.txt
python database/migrations/migrate.py
python run_bot.py
```

### Production

```bash
# Создать бэкап
sudo -u botuser pg_dump -U botuser botdb > /tmp/backup_before_update.sql

# Остановить бота
sudo systemctl stop bankbot

# Обновить код
sudo -u botuser bash << 'EOF'
cd /home/botuser/BankBot
git pull origin main
source .venv/bin/activate
pip install -r config/requirements.txt
python database/migrations/migrate.py
EOF

# Запустить бота
sudo systemctl start bankbot

# Проверить статус
sudo systemctl status bankbot
```

---

## Чеклист развертывания

### Pre-deployment
- [ ] Код протестирован локально
- [ ] Все тесты проходят (`pytest tests/`)
- [ ] Конфигурация проверена
- [ ] Создан бэкап текущей БД
- [ ] Документация обновлена

### Deployment
- [ ] Код развернут на сервере
- [ ] Зависимости установлены
- [ ] Конфигурация настроена
- [ ] Миграции применены
- [ ] Сервис запущен и работает

### Post-deployment
- [ ] Бот отвечает на команды
- [ ] Логи не содержат ошибок
- [ ] Мониторинг настроен
- [ ] Бэкапы работают
- [ ] Документация обновлена

---

## Безопасность

### Рекомендации по безопасности

#### 1. Защита конфиденциальных данных

```bash
# Никогда не коммитьте .env файлы
echo "config/.env*" >> .gitignore
echo "!config/.env.example" >> .gitignore

# Установите правильные права доступа
chmod 600 config/.env
chmod 600 data/bot.db

# В production используйте переменные окружения системы
export BOT_TOKEN="your_token"
export ADMIN_TELEGRAM_ID="123456789"
```

#### 2. Регулярная ротация секретов

```bash
# Обновите токен бота через @BotFather
# Обновите config/.env
# Перезапустите бота
sudo systemctl restart bankbot
```

#### 3. Ограничение доступа

```bash
# Создайте отдельного пользователя для бота
sudo useradd -m -s /bin/bash botuser

# Ограничьте права доступа
sudo chown -R botuser:botuser /home/botuser/BankBot
sudo chmod 750 /home/botuser/BankBot
```

#### 4. Firewall

```bash
# Разрешите только необходимые порты
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable
```

#### 5. Мониторинг безопасности

```bash
# Включите уведомления администратора
ADMIN_NOTIFICATIONS_ENABLED=true

# Включите rate limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_MAX_REQUESTS=15

# Используйте structured logging для анализа
STRUCTURED_LOGGING=true
```

#### 6. Обновления

```bash
# Регулярно обновляйте зависимости
pip list --outdated
pip install --upgrade -r config/requirements.txt

# Обновляйте систему
sudo apt update && sudo apt upgrade -y
```

### SQL Injection Protection

Бот защищен от SQL injection через:
- ✅ Использование SQLAlchemy ORM (параметризованные запросы)
- ✅ Запрет прямой конкатенации SQL
- ✅ Валидация всех входных данных через Pydantic
- ✅ Property-based тесты на SQL injection

### Rate Limiting

Защита от спама и злоупотреблений:
```env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_MAX_REQUESTS=20  # Запросов в минуту на пользователя
```

При превышении лимита пользователь получает сообщение о cooldown.

---

## Контакты и поддержка

- **Telegram:** @LucasTeamLuke
- **Документация:** [docs/](../docs/)
- **Issues:** GitHub Issues

---

**Документ обновлен:** 2026-02-20  
**Версия:** 2.0

**Изменения в версии 2.1:**
- ✅ Добавлен раздел "Архитектурный обзор" с описанием многослойной архитектуры
- ✅ Добавлен раздел "Система конфигурации" с Pydantic Settings и валидацией
- ✅ Добавлен раздел "Управление процессами" с PID management и graceful shutdown
- ✅ Расширен раздел "Мониторинг и обслуживание" с информацией об error handling middleware
- ✅ Улучшен раздел "Устранение неполадок" с детальными решениями проблем конфигурации
- ✅ Добавлен раздел "Безопасность" с рекомендациями и best practices
