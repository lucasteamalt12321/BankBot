# System Patterns

## Архитектура проекта

BankBot следует многослойной архитектуре с четким разделением ответственности:

### Слои архитектуры

1. **Presentation Layer (bot/)**
   - Telegram-бот на основе aiogram
   - Обработчики команд и сообщений
   - Роутеры и middleware
   
2. **Application Layer (core/)**
   - Service Layer - бизнес-логика
   - Repository Layer - доступ к данным
   - Managers - управление конфигурацией и состоянием
   - Systems - высокоуровневые подсистемы (магазин, социальные функции, игры)

3. **Domain Layer (core/models/, src/models.py)**
   - Модели данных и бизнес-объекты
   - Базовые классы парсеров
   - Интерфейсы репозиториев

4. **Infrastructure Layer**
   - Database (database/) - работа с БД через SQLAlchemy
   - Utils - вспомогательные утилиты
   - Monitoring - система мониторинга и уведомлений

### Ключевые паттерны

- **Repository Pattern** - абстракция доступа к данным
- **Service Layer** - инкапсуляция бизнес-логики
- **Unit of Work** - управление транзакциями
- **Parser Registry** - централизованная система парсинга
- **Dependency Injection** - внедрение зависимостей (в разработке)

### Поток данных

```
Telegram Message → bot/router.py → core/handlers/ → core/services/ → core/repositories/ → database/
                                                              ↑
                                                      core/managers/ ← database/
```

### Парсинг игровых сообщений

```
Message → ParserRegistry → BaseParser → ParseResult → BalanceManager → UnitOfWork → Database
```