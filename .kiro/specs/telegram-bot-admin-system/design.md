# Design Document

## Overview

Проект направлен на доработку существующего Telegram-бота с добавлением полноценной системы администрирования и магазина. Основная цель - создать простую и надежную систему управления пользователями и очками, которая будет интегрирована с существующей архитектурой бота.

Текущий бот уже имеет сложную архитектуру с SQLAlchemy ORM и продвинутой системой парсинга игровых результатов. Новая система администрирования должна быть совместима с существующей структурой, но использовать упрощенный подход с прямыми SQL-запросами для административных функций.

## Architecture

### Hybrid Database Approach

Проект будет использовать гибридный подход к работе с базой данных:

1. **Существующая SQLAlchemy архитектура** - остается для сложных операций (парсинг, игры, достижения)
2. **Простая SQLite архитектура** - для административных функций и базовых операций с пользователями

Это решение обусловлено:
- Необходимостью сохранить существующий функционал
- Простотой реализации административных команд
- Независимостью административной системы от сложной игровой логики

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Bot Layer                       │
├─────────────────────────────────────────────────────────────┤
│  Command Handlers  │  Admin Decorators  │  Shop System     │
├─────────────────────────────────────────────────────────────┤
│                  Database Abstraction                       │
├─────────────────────────────────────────────────────────────┤
│  Simple SQLite     │  Existing SQLAlchemy │  Transaction    │
│  (Admin Functions) │  (Game Functions)    │  Logging        │
├─────────────────────────────────────────────────────────────┤
│                      SQLite Database                        │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Database Schema Updates

#### Users Table (Simplified)
```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,              -- Telegram ID
    username TEXT,                       -- @username без @
    first_name TEXT,                     -- Имя пользователя
    balance REAL DEFAULT 0,              -- Баланс очков
    is_admin BOOLEAN DEFAULT FALSE       -- Флаг администратора
);
```

#### Transactions Table
```sql
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,                     -- Ссылка на users.id
    amount REAL,                         -- Сумма транзакции
    type TEXT,                          -- 'add', 'remove', 'buy'
    admin_id INTEGER,                   -- ID администратора (если применимо)
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (admin_id) REFERENCES users (id)
);
```

### 2. Admin System Component

#### AdminChecker Class
```python
class AdminChecker:
    def is_admin(self, user_id: int) -> bool
    def admin_required(self, func) -> decorator
```

#### UserManager Class (Simplified)
```python
class SimpleUserManager:
    def register_user(self, user_id, username, first_name) -> bool
    def get_user_by_username(self, username) -> dict
    def update_balance(self, user_id, amount) -> float
    def set_admin_status(self, user_id, is_admin) -> bool
    def get_users_count(self) -> int
```

#### TransactionManager Class
```python
class TransactionManager:
    def add_transaction(self, user_id, amount, type, admin_id=None) -> int
    def get_user_transactions(self, user_id, limit=10) -> list
```

### 3. Shop System Component

#### ShopManager Class
```python
class ShopManager:
    def get_available_items(self) -> list
    def purchase_item(self, user_id, item_id) -> dict
    def notify_admins(self, message) -> bool
```

#### Shop Items Configuration
```python
SHOP_ITEMS = {
    'contact': {
        'name': 'Сообщение админу',
        'price': 10,
        'description': 'Администратор свяжется с вами'
    }
}
```

### 4. Command Handlers

#### Admin Commands
- `/admin` - Панель администратора с точным форматом:
  ```
  Админ-панель:
  /add_points @username [число] - начислить очки
  /add_admin @username - добавить администратора
  Всего пользователей: [число]
  ```
- `/add_points @username [число]` - Начисление очков с подтверждением:
  ```
  Пользователю @username начислено [число] очков. Новый баланс: [новый_баланс]
  ```
- `/add_admin @username` - Назначение администратора с подтверждением:
  ```
  Пользователь @username теперь администратор
  ```

#### User Commands
- `/start` - Приветствие и автоматическая регистрация
- `/balance` - Проверка баланса пользователя
- `/shop` - Просмотр магазина с точным форматом:
  ```
  Магазин:
  1. Сообщение админу - 10 очков
  Для покупки введите /buy_contact
  ```
- `/buy_contact` - Покупка контакта с подтверждениями:
  - Пользователю: `Вы купили контакт. Администратор свяжется с вами.`
  - Администраторам: `Пользователь @username купил контакт. Его баланс: [новый_баланс] очков`

#### Error Handling Commands
- Обработка неверных форматов команд с инструкциями
- Обработка ошибок "пользователь не найден"
- Обработка ошибок недостаточного баланса
- Проверка прав доступа для административных команд

## Data Models

### User Model (Simplified)
```python
@dataclass
class SimpleUser:
    id: int                    # Telegram ID
    username: str             # Username без @
    first_name: str           # Имя
    balance: float            # Баланс
    is_admin: bool            # Права администратора
```

### Transaction Model
```python
@dataclass
class Transaction:
    id: int                   # Автоинкремент ID
    user_id: int             # ID пользователя
    amount: float            # Сумма
    type: str                # Тип операции
    admin_id: int            # ID администратора
    timestamp: datetime      # Время операции
```

### Shop Item Model
```python
@dataclass
class ShopItem:
    id: str                  # Уникальный ID товара
    name: str               # Название
    price: int              # Цена в очках
    description: str        # Описание
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

После анализа acceptance criteria, следующие свойства корректности были выделены для автоматического тестирования:

### Property 1: Authorization consistency
*For any* user and any admin-only command, the system should deny access if and only if the user's is_admin flag is False
**Validates: Requirements 1.2, 2.6, 3.5, 8.2**

### Property 2: Balance arithmetic correctness  
*For any* user and any positive amount, adding points should increase the user's balance by exactly that amount
**Validates: Requirements 2.1**

### Property 3: Transaction logging completeness
*For any* admin operation (add_points, add_admin), the system should create exactly one corresponding transaction record with correct type and admin_id
**Validates: Requirements 2.2, 5.3**

### Property 4: User count accuracy
*For any* database state, the admin panel should display the exact count of users in the database
**Validates: Requirements 1.4**

### Property 5: Admin status persistence
*For any* user, setting admin status should permanently update the is_admin flag in the database until changed again
**Validates: Requirements 3.1, 3.4**

### Property 6: Purchase balance validation
*For any* purchase attempt, the system should allow the purchase if and only if the user's balance is greater than or equal to the item price
**Validates: Requirements 5.1, 5.2**

### Property 7: User registration idempotence
*For any* user, multiple registration attempts should result in exactly one user record in the database
**Validates: Requirements 6.2, 6.4**

### Property 8: Error handling consistency
*For any* invalid input (non-existent user, wrong format, insufficient balance), the system should return an appropriate error message without crashing
**Validates: Requirements 2.4, 2.5, 5.6, 8.3, 8.4, 8.5**

### Property 9: Database integrity preservation
*For any* sequence of operations, foreign key constraints should remain valid and no orphaned records should exist
**Validates: Requirements 7.3, 8.6**

### Property 10: Shop accessibility universality
*For any* registered user, the /shop command should be accessible and return the complete list of available items
**Validates: Requirements 4.2, 4.3**

## Error Handling

### Error Categories

1. **User Not Found Errors**
   - Пользователь не найден по username
   - Обработка: Возврат понятного сообщения пользователю

2. **Insufficient Balance Errors**
   - Недостаточно очков для покупки
   - Обработка: Показ текущего баланса и требуемой суммы

3. **Permission Errors**
   - Попытка использования админ-команд обычным пользователем
   - Обработка: Сообщение об отсутствии прав

4. **Database Errors**
   - Ошибки подключения к БД
   - Ошибки выполнения запросов
   - Обработка: Логирование + общее сообщение об ошибке

### Error Handling Strategy

```python
def handle_command_error(func):
    @wraps(func)
    def wrapper(message):
        try:
            return func(message)
        except UserNotFoundError as e:
            bot.reply_to(message, f"❌ {str(e)}")
        except InsufficientBalanceError as e:
            bot.reply_to(message, f"💰 {str(e)}")
        except PermissionError as e:
            bot.reply_to(message, f"🔒 {str(e)}")
        except Exception as e:
            logger.error(f"Command error: {e}")
            bot.reply_to(message, "❌ Произошла ошибка. Попробуйте позже.")
    return wrapper
```

## Testing Strategy

### Dual Testing Approach

Система тестирования использует комбинацию unit тестов и property-based тестов для обеспечения полного покрытия:

- **Unit tests**: Проверяют конкретные примеры, граничные случаи и условия ошибок
- **Property tests**: Проверяют универсальные свойства на множестве входных данных
- Оба подхода дополняют друг друга и необходимы для комплексного покрытия

### Unit Tests

1. **Database Operations**
   - Тестирование CRUD операций для пользователей
   - Тестирование транзакций
   - Тестирование проверки прав администратора
   - Конкретные примеры создания пользователей и обновления балансов

2. **Business Logic**
   - Тестирование логики начисления очков
   - Тестирование логики покупок
   - Тестирование валидации команд
   - Граничные случаи (нулевые балансы, максимальные значения)

3. **Command Handlers**
   - Мокирование Telegram API
   - Тестирование обработки команд
   - Тестирование обработки ошибок
   - Конкретные примеры форматирования сообщений

### Property-Based Tests

Используя библиотеку **Hypothesis** для Python, каждое свойство корректности должно быть реализовано как property-based тест:

1. **Configuration**: Минимум 100 итераций на тест
2. **Tagging**: Каждый тест помечается комментарием с ссылкой на свойство дизайна
3. **Format**: **Feature: telegram-bot-admin-system, Property {number}: {property_text}**

Примеры property-based тестов:

```python
from hypothesis import given, strategies as st
import pytest

@given(st.integers(min_value=1, max_value=1000000), 
       st.integers(min_value=1, max_value=10000))
def test_balance_arithmetic_correctness(user_id, amount):
    """Feature: telegram-bot-admin-system, Property 2: Balance arithmetic correctness"""
    # Arrange
    initial_balance = get_user_balance(user_id)
    
    # Act
    add_points(user_id, amount)
    
    # Assert
    final_balance = get_user_balance(user_id)
    assert final_balance == initial_balance + amount

@given(st.integers(min_value=1, max_value=1000000))
def test_user_registration_idempotence(user_id):
    """Feature: telegram-bot-admin-system, Property 7: User registration idempotence"""
    # Act
    register_user(user_id, "test_user", "Test")
    register_user(user_id, "test_user", "Test")  # Second registration
    
    # Assert
    user_count = count_users_by_id(user_id)
    assert user_count == 1
```

### Integration Tests

1. **Database Integration**
   - Тестирование с реальной SQLite БД
   - Тестирование миграций схемы
   - Тестирование совместимости с существующей архитектурой

2. **Bot Integration**
   - Тестирование полного цикла команд
   - Тестирование автоматической регистрации
   - Тестирование уведомлений администраторов

### Test Data Management

```python
@pytest.fixture
def test_db():
    # Создание тестовой БД
    conn = sqlite3.connect(':memory:')
    init_test_database(conn)
    yield conn
    conn.close()

@pytest.fixture
def admin_user():
    return {
        'id': 123456789,
        'username': 'testadmin',
        'first_name': 'Test',
        'is_admin': True,
        'balance': 1000
    }
```

## Integration with Existing System

### Compatibility Considerations

1. **Database Coexistence**
   - Простая SQLite схема не конфликтует с SQLAlchemy моделями
   - Использование разных таблиц для разных функций
   - Возможность постепенной миграции на единую систему

2. **User Identification**
   - Использование Telegram ID как первичного ключа
   - Совместимость с существующей системой UserManager
   - Возможность синхронизации данных между системами

3. **Transaction Logging**
   - Простая система логирования для административных операций
   - Совместимость с существующей системой транзакций
   - Возможность объединения отчетов

### Migration Strategy

1. **Phase 1**: Создание параллельной простой системы
2. **Phase 2**: Интеграция с существующими командами
3. **Phase 3**: Опциональная унификация систем

## Security Considerations

### Admin Rights Management
- Проверка прав на уровне базы данных
- Логирование всех административных действий
- Защита от SQL-инъекций через параметризованные запросы

### Transaction Security
- Валидация сумм транзакций
- Проверка существования пользователей
- Атомарность операций с балансом

### Input Validation
- Валидация username (удаление @, проверка формата)
- Валидация числовых значений
- Защита от XSS в сообщениях

## Performance Considerations

### Database Optimization
- Индексы на часто используемые поля (user_id, username)
- Ограничение количества записей в запросах
- Использование подготовленных запросов

### Memory Management
- Закрытие соединений с БД после операций
- Ограничение размера кэша пользователей
- Оптимизация частоты обновления статистики

### Scalability
- Простая архитектура легко масштабируется
- Возможность добавления кэширования
- Готовность к переходу на PostgreSQL при необходимости