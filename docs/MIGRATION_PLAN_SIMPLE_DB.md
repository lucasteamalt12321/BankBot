# План миграции с simple_db.py на Repository Pattern

## Обзор

Этот документ описывает план миграции с устаревшего модуля `utils.database.simple_db` на современный паттерн Repository с использованием SQLAlchemy ORM.

## Статус

- **Текущая версия**: simple_db.py помечен как deprecated с warnings
- **Целевая дата удаления**: 1 апреля 2026
- **Статус миграции**: В процессе (Phase 2)

## Причины миграции

### Проблемы текущей системы (simple_db.py)

1. **Дублирование кода**: Функции simple_db дублируют функциональность SQLAlchemy
2. **Отсутствие транзакционности**: Каждая функция создает свою сессию, что затрудняет атомарные операции
3. **Неэффективность**: Множественные открытия/закрытия сессий вместо переиспользования
4. **Ограниченная функциональность**: Базовые CRUD операции без расширенных возможностей
5. **Сложность тестирования**: Трудно мокировать и изолировать тесты
6. **Устаревший подход**: Возврат словарей вместо ORM объектов

### Преимущества Repository Pattern

1. **Единая точка доступа**: Все операции с данными через репозитории
2. **Транзакционность**: Поддержка Unit of Work для атомарных операций
3. **Расширяемость**: Легко добавлять новые методы запросов
4. **Тестируемость**: Простое мокирование репозиториев
5. **Type Safety**: Работа с типизированными ORM объектами
6. **Производительность**: Эффективное управление сессиями и кэширование

## Архитектура

### Текущая (Deprecated)

```
Bot Commands → simple_db.py → SQLAlchemy Session → Database
                    ↓
            (создает новую сессию каждый раз)
            (возвращает dict)
```

### Целевая (Repository Pattern)

```
Bot Commands → Services → Repositories → SQLAlchemy Session → Database
                              ↓
                    (переиспользует сессию)
                    (возвращает ORM объекты)
                    (поддержка транзакций)
```

## Mapping функций

### Таблица соответствия

| simple_db функция | Новый подход | Примечания |
|-------------------|--------------|------------|
| `get_db_connection()` | `SessionLocal()` | Прямое использование SQLAlchemy |
| `get_user_by_id(user_id)` | `UserRepository.get_by_telegram_id(user_id)` | Возвращает User объект вместо dict |
| `get_user_by_username(username)` | `UserRepository.get_by_username(username)` | Возвращает User объект |
| `update_user_balance(user_id, amount)` | `UserService.add_points(user_id, amount, reason)` | Через сервис с транзакциями |
| `get_internal_user_id(telegram_id)` | `UserRepository.get_by_telegram_id(telegram_id).id` | Прямой доступ к атрибуту |
| `add_transaction(...)` | `Transaction(...)` + `session.add()` | Прямое использование модели |
| `get_users_count()` | `UserRepository.count_total_users()` | Специализированный метод |
| `register_user(...)` | `UserRepository.get_or_create(...)` | Паттерн get-or-create |
| `init_database()` | `database.connection.init_db()` | Централизованная инициализация |

## Этапы миграции

### Phase 1: Подготовка (Завершена ✅)

- [x] Создать `src/repository/base.py` с BaseRepository
- [x] Создать `src/repository/user_repository.py` с UserRepository
- [x] Добавить deprecation warnings в simple_db.py
- [x] Создать compatibility layer в utils/compat.py
- [x] Обновить документацию

### Phase 2: Постепенная миграция (Текущая фаза 🔄)

**Цель**: Мигрировать код постепенно, модуль за модулем

#### 2.1 Идентификация использования

Найти все места использования simple_db:

```bash
# Поиск импортов
grep -r "from utils.database.simple_db import" --include="*.py"
grep -r "from utils.simple_db import" --include="*.py"

# Поиск вызовов функций
grep -r "get_user_by_id\|get_user_by_username\|update_user_balance" --include="*.py"
```

**Текущие места использования**:
- `tests/property/test_auto_registration_pbt.py`
- `tests/integration/test_task_9_verification.py`
- `utils/compat.py` (compatibility layer)
- Возможно другие модули (требуется полный аудит)

#### 2.2 Приоритизация миграции

**Высокий приоритет** (критические пути):
1. Bot command handlers (если используют)
2. Admin system
3. Parsing system
4. Background tasks

**Средний приоритет**:
1. Utility functions
2. Helper modules
3. Non-critical features

**Низкий приоритет**:
1. Tests (мигрировать последними)
2. Scripts
3. Development tools

#### 2.3 Миграция по модулям

Для каждого модуля:

1. **Создать ветку**: `git checkout -b migrate-simple-db-<module-name>`

2. **Обновить импорты**:
   ```python
   # Было:
   from utils.database.simple_db import get_user_by_id, update_user_balance
   
   # Стало:
   from database.database import SessionLocal
   from src.repository.user_repository import UserRepository
   from database.database import User
   ```

3. **Обновить код**:
   ```python
   # Было:
   user_dict = get_user_by_id(telegram_id)
   if user_dict:
       balance = user_dict['balance']
   
   # Стало:
   session = SessionLocal()
   try:
       user_repo = UserRepository(User, session)
       user = user_repo.get_by_telegram_id(telegram_id)
       if user:
           balance = user.balance
   finally:
       session.close()
   ```

4. **Для сервисов - использовать dependency injection**:
   ```python
   class UserService:
       def __init__(self, user_repo: UserRepository):
           self.user_repo = user_repo
       
       def get_user_balance(self, telegram_id: int) -> int:
           user = self.user_repo.get_by_telegram_id(telegram_id)
           return user.balance if user else 0
   ```

5. **Обновить тесты**:
   ```python
   # Использовать fixtures для репозиториев
   @pytest.fixture
   def user_repo(db_session):
       return UserRepository(User, db_session)
   
   def test_get_user(user_repo):
       user = user_repo.get_by_telegram_id(123456)
       assert user is not None
   ```

6. **Запустить тесты**: `pytest tests/`

7. **Code review и merge**

### Phase 3: Удаление compatibility layer (Q2 2026)

**Предварительные условия**:
- Все production код мигрирован
- Все тесты обновлены
- Нет warnings в логах о использовании deprecated функций

**Действия**:
1. Удалить `utils/simple_db.py`
2. Удалить `utils/database/simple_db.py`
3. Удалить simple_db re-exports из `utils/compat.py`
4. Обновить документацию
5. Создать release notes

## Примеры миграции

### Пример 1: Простое получение пользователя

**До миграции**:
```python
from utils.database.simple_db import get_user_by_id

def handle_profile_command(telegram_id: int):
    user = get_user_by_id(telegram_id)
    if user:
        return f"Balance: {user['balance']}"
    return "User not found"
```

**После миграции**:
```python
from database.database import SessionLocal
from src.repository.user_repository import UserRepository
from database.database import User

def handle_profile_command(telegram_id: int):
    session = SessionLocal()
    try:
        user_repo = UserRepository(User, session)
        user = user_repo.get_by_telegram_id(telegram_id)
        if user:
            return f"Balance: {user.balance}"
        return "User not found"
    finally:
        session.close()
```

**Лучший вариант (с сервисом)**:
```python
# В bot/commands/user_commands.py
from core.services.user_service import UserService

async def profile_command(message: types.Message, user_service: UserService):
    user = await user_service.get_user(message.from_user.id)
    if user:
        await message.answer(f"Balance: {user.balance}")
    else:
        await message.answer("User not found")
```

### Пример 2: Обновление баланса

**До миграции**:
```python
from utils.database.simple_db import update_user_balance, add_transaction

def add_points(telegram_id: int, amount: int, reason: str):
    new_balance = update_user_balance(telegram_id, amount)
    if new_balance is not None:
        add_transaction(telegram_id, amount, "admin_add", description=reason)
        return True
    return False
```

**После миграции (с транзакциями)**:
```python
from database.database import SessionLocal, User, Transaction
from src.repository.user_repository import UserRepository
from datetime import datetime

def add_points(telegram_id: int, amount: int, reason: str):
    session = SessionLocal()
    try:
        user_repo = UserRepository(User, session)
        user = user_repo.get_by_telegram_id(telegram_id)
        
        if not user:
            return False
        
        # Атомарная операция в одной транзакции
        user.balance += amount
        
        transaction = Transaction(
            user_id=user.id,
            amount=amount,
            transaction_type="admin_add",
            description=reason,
            created_at=datetime.now()
        )
        session.add(transaction)
        session.commit()
        return True
        
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()
```

**Лучший вариант (с Unit of Work)**:
```python
from src.repository.unit_of_work import UnitOfWork
from core.services.transaction_service import TransactionService

def add_points(telegram_id: int, amount: int, reason: str):
    session = SessionLocal()
    uow = UnitOfWork(session)
    transaction_service = TransactionService(uow)
    
    try:
        return transaction_service.add_points(telegram_id, amount, reason)
    finally:
        session.close()
```

### Пример 3: Регистрация пользователя

**До миграции**:
```python
from utils.database.simple_db import register_user, get_user_by_id

def ensure_user_registered(telegram_id: int, username: str, first_name: str):
    user = get_user_by_id(telegram_id)
    if not user:
        register_user(telegram_id, username, first_name)
        user = get_user_by_id(telegram_id)
    return user
```

**После миграции**:
```python
from database.database import SessionLocal, User
from src.repository.user_repository import UserRepository

def ensure_user_registered(telegram_id: int, username: str, first_name: str):
    session = SessionLocal()
    try:
        user_repo = UserRepository(User, session)
        # get_or_create автоматически обрабатывает оба случая
        user = user_repo.get_or_create(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            balance=0,
            is_admin=False
        )
        return user
    finally:
        session.close()
```

## Тестирование

### Unit тесты

Создать тесты для каждого мигрированного модуля:

```python
# tests/unit/test_user_repository_migration.py
import pytest
from database.database import User
from src.repository.user_repository import UserRepository

def test_get_by_telegram_id(db_session):
    """Test migration from get_user_by_id to repository"""
    user_repo = UserRepository(User, db_session)
    
    # Create test user
    user = user_repo.create(
        telegram_id=123456,
        username="testuser",
        balance=100
    )
    
    # Test retrieval
    found_user = user_repo.get_by_telegram_id(123456)
    assert found_user is not None
    assert found_user.telegram_id == 123456
    assert found_user.username == "testuser"
    assert found_user.balance == 100

def test_get_or_create(db_session):
    """Test migration from register_user to get_or_create"""
    user_repo = UserRepository(User, db_session)
    
    # First call creates user
    user1 = user_repo.get_or_create(
        telegram_id=123456,
        username="testuser"
    )
    assert user1.telegram_id == 123456
    
    # Second call returns existing user
    user2 = user_repo.get_or_create(
        telegram_id=123456,
        username="different_name"  # Should be ignored
    )
    assert user2.id == user1.id
    assert user2.username == "testuser"  # Original username preserved
```

### Integration тесты

Проверить работу в реальных сценариях:

```python
# tests/integration/test_migration_scenarios.py
import pytest
from database.database import SessionLocal, User
from src.repository.user_repository import UserRepository

def test_balance_update_with_transaction():
    """Test that balance updates work correctly after migration"""
    session = SessionLocal()
    try:
        user_repo = UserRepository(User, session)
        
        # Create user
        user = user_repo.get_or_create(
            telegram_id=123456,
            username="testuser",
            balance=0
        )
        
        # Update balance
        user.balance += 100
        session.commit()
        
        # Verify
        user_repo.session.refresh(user)
        assert user.balance == 100
        
    finally:
        session.close()
```

### Regression тесты

Убедиться, что старые тесты продолжают работать:

```bash
# Запустить все тесты
pytest tests/

# Запустить только тесты, связанные с пользователями
pytest tests/ -k "user"

# Проверить coverage
pytest tests/ --cov=src/repository --cov=core/services
```

## Checklist миграции

### Для каждого модуля

- [ ] Идентифицированы все использования simple_db функций
- [ ] Создана ветка для миграции
- [ ] Обновлены импорты
- [ ] Обновлен код для использования репозиториев
- [ ] Добавлена обработка сессий (try/finally)
- [ ] Обновлены тесты
- [ ] Все тесты проходят
- [ ] Code review выполнен
- [ ] Изменения задокументированы
- [ ] Ветка смержена в main

### Общий прогресс

- [x] Phase 1: Подготовка инфраструктуры
- [ ] Phase 2: Миграция production кода
  - [ ] Bot commands
  - [ ] Admin system
  - [ ] Parsing system
  - [ ] Background tasks
  - [ ] Utility modules
  - [ ] Tests
- [ ] Phase 3: Удаление deprecated кода

## Риски и митигация

### Риск 1: Breaking changes в production

**Митигация**:
- Постепенная миграция модуль за модулем
- Сохранение compatibility layer до полной миграции
- Тщательное тестирование каждого изменения
- Возможность быстрого rollback через git

### Риск 2: Производительность

**Митигация**:
- Использование connection pooling
- Переиспользование сессий где возможно
- Мониторинг производительности после миграции
- Оптимизация запросов при необходимости

### Риск 3: Несовместимость данных

**Митигация**:
- Работа с теми же таблицами и моделями
- Нет изменений в схеме БД
- Тестирование на копии production данных

### Риск 4: Забытые места использования

**Митигация**:
- Автоматический поиск всех использований
- Deprecation warnings в логах
- Мониторинг warnings в production
- Финальный аудит перед удалением

## Поддержка и вопросы

### Где получить помощь

1. **Документация**:
   - `src/repository/README.md` - Документация по репозиториям
   - `docs/ARCHITECTURE.md` - Общая архитектура
   - Этот документ - План миграции

2. **Примеры кода**:
   - `src/repository/user_repository.py` - Пример репозитория
   - `core/services/user_service.py` - Пример сервиса
   - `tests/unit/test_user_repository.py` - Примеры тестов

3. **Code review**:
   - Создавайте PR для каждого мигрированного модуля
   - Запрашивайте review у команды
   - Обсуждайте сложные случаи

### FAQ

**Q: Можно ли использовать simple_db в новом коде?**
A: Нет, все новый код должен использовать Repository Pattern.

**Q: Что делать, если нужна функция, которой нет в репозитории?**
A: Добавьте новый метод в соответствующий репозиторий (например, UserRepository).

**Q: Как тестировать код с репозиториями?**
A: Используйте fixtures для создания репозиториев с тестовой БД. См. примеры в tests/conftest.py.

**Q: Нужно ли мигрировать все сразу?**
A: Нет, миграция постепенная. Compatibility layer позволяет старому и новому коду работать вместе.

**Q: Когда будет удален simple_db?**
A: Планируется удаление 1 апреля 2026, после полной миграции всего кода.

## Метрики успеха

### Критерии завершения миграции

1. ✅ **Нет использований simple_db в production коде**
   - Проверка: `grep -r "from utils.database.simple_db" src/ core/ bot/`
   
2. ✅ **Все тесты проходят**
   - Проверка: `pytest tests/ --tb=short`
   
3. ✅ **Нет deprecation warnings в логах**
   - Проверка: Мониторинг production логов
   
4. ✅ **Coverage не снизился**
   - Проверка: `pytest --cov=src --cov=core --cov-report=term`
   
5. ✅ **Производительность не ухудшилась**
   - Проверка: Сравнение метрик до/после миграции

### Текущий прогресс

- **Инфраструктура**: 100% ✅
- **Production код**: 0% 🔄
- **Тесты**: 0% ⏳
- **Документация**: 100% ✅

## Timeline

| Фаза | Период | Статус |
|------|--------|--------|
| Phase 1: Подготовка | Неделя 3-4 | ✅ Завершена |
| Phase 2: Миграция | Неделя 5-7 | 🔄 В процессе |
| Phase 3: Удаление | Q2 2026 | ⏳ Запланирована |

## Заключение

Миграция с simple_db.py на Repository Pattern - это важный шаг к современной, поддерживаемой и масштабируемой архитектуре. Постепенный подход с сохранением compatibility layer обеспечивает безопасность миграции без нарушения работы системы.

Следуйте этому плану, тестируйте каждое изменение, и миграция пройдет гладко.

---

**Последнее обновление**: 2025-01-XX  
**Версия документа**: 1.0  
**Автор**: Development Team
