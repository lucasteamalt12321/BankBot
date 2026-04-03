# 🏗️ Архитектура проекта BankBot

**Версия:** 3.0  
**Дата:** 2026-04-03

---

## 📋 Содержание

- [Обзор архитектуры](#обзор-архитектуры)
- [Диаграмма слоев](#диаграмма-слоев)
- [Диаграмма компонентов](#диаграмма-компонентов)
- [Поток данных](#поток-данных)
- [Технологический стек](#технологический-стек)
- [Паттерны проектирования](#паттерны-проектирования)

---

## Обзор архитектуры

BankBot построен на основе многослойной архитектуры с четким разделением ответственности:

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                    │
│              (Telegram Bot Interface)                    │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                     │
│         (Commands, Handlers, Middleware)                 │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                     Business Layer                       │
│      (Systems, Managers, Parsers, Logic)                 │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                      Data Layer                          │
│         (Database, Models, Repositories)                 │
└─────────────────────────────────────────────────────────┘
```

---

## Диаграмма слоев

### 1. Presentation Layer (Слой представления)

**Ответственность:** Взаимодействие с пользователем через Telegram API

```
┌──────────────────────────────────────────────────────┐
│                  Telegram Bot API                     │
│                                                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │  Commands  │  │  Callbacks │  │  Messages  │    │
│  │  Handler   │  │  Handler   │  │  Handler   │    │
│  └────────────┘  └────────────┘  └────────────┘    │
│                                                       │
│  ┌────────────────────────────────────────────┐     │
│  │         Error Handler & Middleware         │     │
│  └────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────┘
```

**Компоненты:**
- `bot/bot.py` - Главный класс бота
- `bot/handlers/` - Обработчики сообщений
- `bot/middleware/` - Middleware (авто-регистрация, логирование)

### 2. Application Layer (Слой приложения)

**Ответственность:** Обработка команд и координация бизнес-логики

```
┌──────────────────────────────────────────────────────┐
│                  Command Handlers                     │
│                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  │
│  │    Admin     │  │   Config     │  │  User    │  │
│  │   Commands   │  │   Commands   │  │ Commands │  │
│  └──────────────┘  └──────────────┘  └──────────┘  │
│                                                       │
│  ┌────────────────────────────────────────────┐     │
│  │         Parsing Handler (NEW)              │     │
│  │  - Manual parsing trigger                  │     │
│  │  - Game message detection                  │     │
│  └────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────┘
```

**Компоненты:**
- `bot/commands/admin_commands.py` - Административные команды (aiogram)
- `bot/commands/admin_commands_ptb.py` - Административные команды (PTB, 25 команд)
- `bot/commands/advanced_admin_commands.py` - Расширенные админ-команды
- `bot/commands/config_commands.py` - Конфигурационные команды
- `bot/commands/core_commands.py` - Core команды (welcome, balance, history, profile, stats)
- `bot/commands/shop_commands_ptb.py` - Shop команды (shop, buy, inventory)
- `bot/handlers/parsing_handler.py` - Обработчик парсинга

### 3. Business Layer (Бизнес-слой)

**Ответственность:** Бизнес-логика и правила приложения

```
┌──────────────────────────────────────────────────────────────┐
│                      Business Systems                         │
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Shop    │  │  Games   │  │   D&D    │  │  Social  │    │
│  │  System  │  │  System  │  │  System  │  │  System  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │Achievem. │  │Broadcast │  │Motivat.  │  │ Parsing  │    │
│  │  System  │  │  System  │  │  System  │  │  System  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│                                                               │
│                      Business Managers                        │
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Admin   │  │  Config  │  │  Shop    │  │ Sticker  │    │
│  │ Manager  │  │ Manager  │  │ Manager  │  │ Manager  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│                                                               │
│  ┌──────────┐  ┌──────────┐                                  │
│  │Backgr.   │  │Scheduler │                                  │
│  │Task Mgr  │  │ Manager  │                                  │
│  └──────────┘  └──────────┘                                  │
└──────────────────────────────────────────────────────────────┘
```

**Компоненты:**
- `core/systems/` - Игровые и функциональные системы
- `core/managers/` - Менеджеры бизнес-логики
- `core/parsers/` - Парсеры игровых сообщений
- `core/handlers/` - Обработчики бизнес-событий

### 4. Data Layer (Слой данных)

**Ответственность:** Хранение и управление данными

```
┌──────────────────────────────────────────────────────┐
│                   Data Access Layer                   │
│                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  │
│  │  Repository  │  │    Models    │  │  Utils   │  │
│  │   Pattern    │  │  (SQLAlch.)  │  │          │  │
│  └──────────────┘  └──────────────┘  └──────────┘  │
│                                                       │
│  ┌────────────────────────────────────────────┐     │
│  │            Database Connection             │     │
│  │         (Centralized via get_db())         │     │
│  └────────────────────────────────────────────┘     │
│                                                       │
│  ┌────────────────────────────────────────────┐     │
│  │              SQLite / PostgreSQL           │     │
│  └────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────┘
```

**Компоненты:**
- `database/database.py` - SQLAlchemy модели
- `database/connection.py` - Централизованное подключение
- `src/repository/` - Repository паттерн
- `database/migrations/` - Миграции БД

---

## Диаграмма компонентов

### Основные компоненты и их взаимодействие

```
┌─────────────────────────────────────────────────────────────────┐
│                         TelegramBot                              │
│                      (Main Application)                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Initialization                         │  │
│  │  • AdminSystem                                            │  │
│  │  • AdvancedAdminCommands                                  │  │
│  │  • BackgroundTaskManager                                  │  │
│  │  • ParsingHandler                                         │  │
│  │  • MonitoringSystem                                       │  │
│  │  • BackupSystem                                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   Handler Registration                    │  │
│  │  • Command Handlers                                       │  │
│  │  • Message Handlers                                       │  │
│  │  • Callback Query Handlers                                │  │
│  │  • Error Handler                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Core Components                             │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Systems    │  │   Managers   │  │   Parsers    │         │
│  │              │  │              │  │              │         │
│  │ • Shop       │  │ • Admin      │  │ • Shmalala   │         │
│  │ • Games      │  │ • Config     │  │ • GD Cards   │         │
│  │ • D&D        │  │ • Shop       │  │ • True Mafia │         │
│  │ • Social     │  │ • Sticker    │  │ • Bunker RP  │         │
│  │ • Achievem.  │  │ • Background │  │              │         │
│  │ • Broadcast  │  │ • Scheduler  │  │              │         │
│  │ • Motivation │  │              │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Utility Components                          │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │    Admin     │  │  Monitoring  │  │   Database   │         │
│  │              │  │              │  │              │         │
│  │ • System     │  │ • Monitoring │  │ • Connection │         │
│  │ • Middleware │  │ • Notificat. │  │ • Backup     │         │
│  │              │  │ • Alert      │  │ • Simple DB  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │     Core     │  │    Config    │                            │
│  │              │  │              │                            │
│  │ • User Mgr   │  │ • Settings   │                            │
│  │ • Error Hdl  │  │ • Env Vars   │                            │
│  └──────────────┘  └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────┐
│                         Data Layer                               │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    SQLAlchemy ORM                         │  │
│  │  • User Model                                             │  │
│  │  • Transaction Model                                      │  │
│  │  • Shop Models (Items, Categories, Purchases)            │  │
│  │  • Achievement Models                                     │  │
│  │  • Notification Models                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  Database (SQLite/PostgreSQL)             │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Поток данных

### 1. Обработка команды пользователя

```
User → Telegram API → Bot Handler → Command Handler → Business Logic → Database
                                                                           ↓
User ← Telegram API ← Bot Handler ← Response ← Business Logic ← Database Query
```

### 2. Парсинг игрового сообщения (ручной)

```
User replies "парсинг" to game message
         ↓
ParsingHandler detects trigger
         ↓
Extract original message
         ↓
Parse with appropriate parser (Shmalala/GD Cards/etc)
         ↓
Calculate points with currency coefficient
         ↓
Update user balance in database
         ↓
Create transaction record
         ↓
Send confirmation to user
```

### 3. Фоновые задачи

```
BackgroundTaskManager (every 5 minutes)
         ↓
┌────────┴────────┐
│                 │
Check expired     Monitor
privileges        system health
│                 │
Update DB         Send alerts
│                 │
└────────┬────────┘
         ↓
    Continue loop
```

---

## Технологический стек

### Backend
- **Python 3.8+** - Основной язык программирования
- **python-telegram-bot 20.0+** - Telegram Bot API wrapper
- **SQLAlchemy 2.0+** - ORM для работы с БД
- **Pydantic Settings** - Управление конфигурацией
- **structlog** - Структурированное логирование

### Database
- **SQLite** - База данных (development/small deployments)
- **PostgreSQL** - База данных (production, опционально)

### Testing
- **pytest** - Фреймворк тестирования
- **hypothesis** - Property-based тестирование
- **pytest-asyncio** - Асинхронные тесты

### Development Tools
- **Git** - Контроль версий
- **pip** - Управление зависимостями
- **venv** - Виртуальные окружения

---

## Паттерны проектирования

### 1. Repository Pattern
Абстракция доступа к данным для упрощения тестирования и замены источника данных.

```python
# src/repository/base.py
class BaseRepository:
    def get_by_id(self, id: int)
    def get_all(self)
    def create(self, data: dict)
    def update(self, id: int, data: dict)
    def delete(self, id: int)
```

### 2. Singleton Pattern
Единственный экземпляр конфигурации и подключения к БД.

```python
# src/config.py
settings = get_settings()  # Singleton instance

# database/connection.py
def get_connection():  # Returns same connection
```

### 3. Middleware Pattern
Обработка запросов через цепочку middleware.

```python
# utils/admin/admin_middleware.py
@auto_registration_middleware
async def command_handler(update, context):
    # User is automatically registered
```

### 4. Decorator Pattern
Проверка прав доступа через декораторы.

```python
# utils/admin/admin_system.py
@admin_required
async def admin_command(update, context):
    # Only admins can execute
```

### 5. Factory Pattern
Создание парсеров для разных игр.

```python
# core/parsers/registry.py
def get_parser(game_type: str):
    return PARSER_REGISTRY.get(game_type)
```

### 6. Observer Pattern
Система уведомлений и событий.

```python
# utils/monitoring/notification_system.py
class NotificationSystem:
    def notify_admins(self, message)
    def notify_user(self, user_id, message)
```

### 7. Strategy Pattern
Различные стратегии начисления очков для разных игр.

```python
# core/parsers/
- shmalala.py (1:1 rate)
- gdcards.py (2:1 rate)
- truemafia.py (15:1 rate)
- bunkerrp.py (20:1 rate)
```

---

## Масштабируемость

### Горизонтальное масштабирование
- Использование PostgreSQL вместо SQLite
- Внешний Redis для кэширования
- Балансировка нагрузки через несколько инстансов бота

### Вертикальное масштабирование
- Увеличение размера пула соединений БД
- Оптимизация запросов через индексы
- Кэширование часто запрашиваемых данных

### Мониторинг и отказоустойчивость
- Система мониторинга здоровья
- Автоматические бэкапы БД
- Graceful shutdown при ошибках
- Уведомления администратора об ошибках

---

## Безопасность

### Уровни защиты

1. **Аутентификация**
   - Проверка Telegram ID
   - Административные права

2. **Авторизация**
   - Декоратор `@admin_required`
   - Проверка прав на уровне команд

3. **Валидация данных**
   - Pydantic для конфигурации
   - SQLAlchemy для БД
   - Проверка входных параметров

4. **Защита данных**
   - `.env` файлы не в git
   - Секреты в переменных окружения
   - Шифрование чувствительных данных

---

## Дальнейшее развитие

### Планируемые улучшения

1. **Микросервисная архитектура**
   - Разделение на отдельные сервисы
   - API Gateway
   - Message Queue (RabbitMQ/Kafka)

2. **Расширенная аналитика**
   - Дашборды с метриками
   - Анализ поведения пользователей
   - A/B тестирование функций

3. **Интеграции**
   - Webhook для игровых ботов
   - REST API для внешних систем
   - GraphQL для гибких запросов

4. **DevOps**
   - Docker контейнеризация
   - CI/CD pipeline
   - Kubernetes оркестрация
   - Автоматическое масштабирование

---

**Документ обновлен:** 2026-04-03  
**Версия архитектуры:** 3.0

## Модули (BridgeBot, VK Bot)

### BridgeBot (`bridge_bot/`)
Telegram → VK ретранслятор постов.

| Файл | Описание |
|------|----------|
| `main.py` | Точка входа BridgeBot |
| `handlers.py` | Обработка постов из Telegram-канала |
| `vk_publisher.py` | Публикация в VK API |
| `media.py` | Скачивание/загрузка медиа |
| `queue.py` | Очередь сообщений + rate limiting |
| `loop_guard.py` | Защита от циклов пересылки |
| `vk_listener.py` | VK Long Poll listener |

### VK Bot (`vk_bot/`)
VK сообщество для публикации постов.

| Файл | Описание |
|------|----------|
| `main.py` | Точка входа VK Bot (Long Poll) |
| `bot.py` | Инициализация VK API |
| `handlers.py` | Обработка входящих сообщений |
| `config.py` | Конфигурация |

### Тесты
- `tests/bridge/` — 43 теста для BridgeBot + VK Bot
