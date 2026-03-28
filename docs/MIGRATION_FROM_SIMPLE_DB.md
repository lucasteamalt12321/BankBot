# План миграции от simple_db.py к Repository Pattern

## Обзор

Этот документ описывает план миграции от устаревшего `utils/database/simple_db.py` к современному Repository Pattern с использованием SQLAlchemy ORM.

## Статус

- **Дата начала:** Февраль 2026
- **Целевая дата завершения:** Апрель 2026
- **Дата удаления simple_db.py:** Май 2026 (версия 2.0.0)

## Причины миграции

### Проблемы simple_db.py

1. **Прямые SQL запросы** - Подвержены SQL injection, сложны в поддержке
2. **Отсутствие типизации** - Возвращает Dict вместо типизированных объектов
3. **Дублирование кода** - Повторяющаяся логика подключения/закрытия
4. **Сложное тестирование** - Требует реальной БД для тестов
5. **Отсутствие транзакций** - Нет поддержки атомарных операций
6. **Смешивание SQLite и SQLAlchemy** - Два разных подхода в одном проекте

### Преимущества Repository Pattern

1. **Безопасность** - Параметризованные запросы через ORM
2. **Типизация** - Возвращает типизированные модели
3. **Переиспользование** - Базовый репозиторий с CRUD операциями
4. **Тестируемость** - Легко мокать репозитории
5. **Транзакции** - Встроенная поддержка через Unit of Work
6. **Единообразие** - Один подход ко всей БД

## Файлы для миграции

### Критический приоритет (используются активно)

1. **utils/database/simple_db.py** - Основной файл
   - `get_user_by_id()` → `UserRepository.get_by_telegram_id()`
   - `get_user_by_username()` → `UserRepository.get_by_username()`
   - `update_user_balance()` → `UserRepository.update()`
   - `add_transaction()` → `TransactionRepository.create()`
   - `get_users_count()` → `UserRepository.count()`
   - `register_user()` → `UserRepository.get_or_create()`

2. **utils/admin/admin_system.py** - Система администрирования
   - Прямые SQL запросы для проверки is_admin
   - Создание пользователей через SQL

3. **utils/admin/create_admin.py** - Создание администраторов
   - Прямые SQL запросы для создания/обновления админов

### Средний приоритет (используются редко)

4. **utils/core/error_handling.py** - Обработка ошибок
   - Метод `safe_execute()` - не использует SQL напрямую

## Mapping: Старые функции → Новые методы

### simple_db.py → UserRepository

| Старая функция | Новый метод | Пример |
|----------------|-------------|--------|
| `get_user_by_id(user_id)` | `repo.get_by_telegram_id(user_id)` | `user = user_repo.get_by_telegram_id(123)` |
| `get_user_by_username(username)` | `repo.get_by_username(username)` | `user = user_repo.get_by_username("john")` |
| `update_user_balance(user_id, amount)` | `repo.update(user.id, balance=new_balance)` | `user_repo.update(user.id, balance=user.balance + amount)` |
| `get_users_count()` | `repo.count_total_users()` | `count = user_repo.count_total_users()` |
| `register_user(user_id, username, first_name)` | `repo.get_or_create(user_id, ...)` | `user = user_repo.get_or_create(123, username="john")` |
| `get_internal_user_id(telegram_id)` | `repo.get_by_telegram_id(telegram_id).id` | `user = repo.get_by_telegram_id(123); user_id = user.id` |

### Прямые SQL → Repository методы

| Прямой SQL | Repository метод |
|------------|------------------|
| `cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (id,))` | `repo.get_by_telegram_id(id)` |
| `cursor.execute('SELECT * FROM users WHERE username = ?', (name,))` | `repo.get_by_username(name)` |
| `cursor.execute('UPDATE users SET balance = ? WHERE telegram_id = ?', ...)` | `repo.update(user.id, balance=new_balance)` |
| `cursor.execute('INSERT INTO users ...')` | `repo.create(...)` |
| `cursor.execute('SELECT COUNT(*) FROM users')` | `repo.count()` |
| `cursor.execute('SELECT is_admin FROM users WHERE telegram_id = ?', ...)` | `user = repo.get_by_telegram_id(id); is_admin = user.is_admin` |

## Пошаговый план миграции

### Фаза 1: Подготовка (Неделя 1)

- [x] Создать BaseRepository
- [x] Создать UserRepository
- [x] Написать тесты для репозиториев
- [x] Добавить deprecation warning в simple_db.py
- [x] Создать этот план миграции

### Фаза 2: Миграция критических файлов (Недели 2-3)

#### 2.1 Миграция utils/admin/admin_system.py

**Текущий код:**
```python
cursor.execute("SELECT is_admin FROM users WHERE telegram_id = ?", (user_id,))
result = cursor.fetchone()
```

**Новый код:**
```python
from src.repository.user_repository import UserRepository
from database.connection import get_connection

session = get_connection()
user_repo = UserRepository(User, session)
user = user_repo.get_by_telegram_id(user_id)
is_admin = user.is_admin if user else False
session.close()
```

**Или с Unit of Work:**
```python
from src.repository.unit_of_work import transaction
from src.repository.user_repository import UserRepository

with transaction() as session:
    user_repo = UserRepository(User, session)
    user = user_repo.get_by_telegram_id(user_id)
    is_admin = user.is_admin if user else False
```

#### 2.2 Миграция utils/admin/create_admin.py

**Текущий код:**
```python
cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (user_id,))
if cursor.fetchone():
    cursor.execute('UPDATE users SET is_admin = TRUE ...')
else:
    cursor.execute('INSERT INTO users ...')
```

**Новый код:**
```python
with transaction() as session:
    user_repo = UserRepository(User, session)
    user = user_repo.get_or_create(
        telegram_id=user_id,
        username=username,
        first_name=first_name
    )
    user_repo.update(user.id, is_admin=True)
```

#### 2.3 Обновление вызовов simple_db функций

Найти все вызовы:
```bash
grep -r "from utils.database.simple_db import" --include="*.py"
grep -r "simple_db\." --include="*.py"
```

Заменить на:
```python
from src.repository.user_repository import UserRepository
from database.database import User
from database.connection import get_connection
```

### Фаза 3: Тестирование (Неделя 4)

- [ ] Запустить все unit тесты
- [ ] Запустить integration тесты
- [ ] Проверить работу в staging окружении
- [ ] Провести ручное тестирование критических функций

### Фаза 4: Очистка (Неделя 5)

- [ ] Удалить неиспользуемые функции из simple_db.py
- [ ] Обновить все импорты
- [ ] Обновить документацию
- [ ] Создать release notes

### Фаза 5: Удаление (Май 2026, версия 2.0.0)

- [ ] Полностью удалить utils/database/simple_db.py
- [ ] Удалить compatibility layer из utils/compat.py
- [ ] Обновить CHANGELOG

## Примеры миграции

### Пример 1: Простой запрос пользователя

**До:**
```python
from utils.database.simple_db import get_user_by_id

user_dict = get_user_by_id(123456)
if user_dict:
    balance = user_dict['balance']
```

**После:**
```python
from src.repository.user_repository import UserRepository
from database.database import User
from database.connection import get_connection

session = get_connection()
user_repo = UserRepository(User, session)
user = user_repo.get_by_telegram_id(123456)
if user:
    balance = user.balance
session.close()
```

**После (с context manager):**
```python
from src.repository.unit_of_work import transaction
from src.repository.user_repository import UserRepository
from database.database import User

with transaction() as session:
    user_repo = UserRepository(User, session)
    user = user_repo.get_by_telegram_id(123456)
    if user:
        balance = user.balance
```

### Пример 2: Обновление баланса

**До:**
```python
from utils.database.simple_db import update_user_balance

new_balance = update_user_balance(123456, 100)
```

**После:**
```python
from src.repository.unit_of_work import transaction
from src.repository.user_repository import UserRepository
from database.database import User

with transaction() as session:
    user_repo = UserRepository(User, session)
    user = user_repo.get_by_telegram_id(123456)
    if user:
        user_repo.update(user.id, balance=user.balance + 100)
```

### Пример 3: Создание пользователя

**До:**
```python
from utils.database.simple_db import register_user

success = register_user(123456, "john_doe", "John")
```

**После:**
```python
from src.repository.unit_of_work import transaction
from src.repository.user_repository import UserRepository
from database.database import User

with transaction() as session:
    user_repo = UserRepository(User, session)
    user = user_repo.get_or_create(
        telegram_id=123456,
        username="john_doe",
        first_name="John"
    )
```

### Пример 4: Транзакция с несколькими операциями

**До:**
```python
conn = get_db_connection()
cursor = conn.cursor()
try:
    cursor.execute('UPDATE users SET balance = balance - ? WHERE telegram_id = ?', (100, from_user))
    cursor.execute('UPDATE users SET balance = balance + ? WHERE telegram_id = ?', (100, to_user))
    conn.commit()
except:
    conn.rollback()
finally:
    conn.close()
```

**После:**
```python
from src.repository.unit_of_work import UnitOfWork
from src.repository.user_repository import UserRepository
from database.database import User

with UnitOfWork() as uow:
    user_repo = UserRepository(User, uow.session)
    
    from_user_obj = user_repo.get_by_telegram_id(from_user)
    to_user_obj = user_repo.get_by_telegram_id(to_user)
    
    user_repo.update(from_user_obj.id, balance=from_user_obj.balance - 100)
    user_repo.update(to_user_obj.id, balance=to_user_obj.balance + 100)
    # Автоматический commit при выходе из контекста
```

## Скрипт автоматической миграции

Создать `scripts/migrate_from_simple_db.py`:

```python
#!/usr/bin/env python3
"""
Скрипт для автоматической замены вызовов simple_db на Repository.
"""

import re
from pathlib import Path

REPLACEMENTS = {
    r'from utils\.database\.simple_db import get_user_by_id': 
        'from src.repository.user_repository import UserRepository\nfrom database.database import User',
    
    r'get_user_by_id\((\w+)\)':
        'user_repo.get_by_telegram_id(\\1)',
    
    r'get_user_by_username\((\w+)\)':
        'user_repo.get_by_username(\\1)',
}

def migrate_file(file_path: Path):
    """Мигрировать один файл."""
    content = file_path.read_text()
    original = content
    
    for pattern, replacement in REPLACEMENTS.items():
        content = re.sub(pattern, replacement, content)
    
    if content != original:
        file_path.write_text(content)
        print(f"✓ Migrated: {file_path}")
        return True
    return False

def main():
    """Главная функция."""
    project_root = Path(__file__).parent.parent
    python_files = project_root.rglob('*.py')
    
    migrated = 0
    for file_path in python_files:
        if 'simple_db.py' in str(file_path):
            continue
        if migrate_file(file_path):
            migrated += 1
    
    print(f"\nMigrated {migrated} files")

if __name__ == '__main__':
    main()
```

## Чеклист миграции

### Для каждого файла:

- [ ] Найти все вызовы simple_db функций
- [ ] Заменить на Repository методы
- [ ] Добавить импорты UserRepository и User
- [ ] Обернуть в transaction() или UnitOfWork
- [ ] Обновить тесты
- [ ] Проверить работоспособность
- [ ] Удалить старые импорты

### Общие проверки:

- [ ] Все тесты проходят
- [ ] Нет импортов simple_db в production коде
- [ ] Документация обновлена
- [ ] Производительность не ухудшилась
- [ ] Логирование работает корректно

## Риски и митигация

### Риск 1: Изменение поведения

**Проблема:** Repository может вести себя иначе чем simple_db  
**Митигация:** Комплексное тестирование, постепенная миграция

### Риск 2: Производительность

**Проблема:** ORM может быть медленнее прямого SQL  
**Митигация:** Профилирование, оптимизация запросов, использование bulk операций

### Риск 3: Ошибки в production

**Проблема:** Баги после миграции  
**Митигация:** Staging тестирование, постепенный rollout, мониторинг

### Риск 4: Обратная совместимость

**Проблема:** Старый код может сломаться  
**Митигация:** Compatibility layer в utils/compat.py до версии 2.0.0

## Мониторинг прогресса

### Метрики:

- Количество файлов с simple_db импортами: **4 файла**
- Количество прямых SQL запросов: **~30 запросов**
- Покрытие тестами: **Целевое 90%**
- Производительность: **Не хуже текущей**

### Отслеживание:

```bash
# Найти оставшиеся импорты simple_db
grep -r "from utils.database.simple_db" --include="*.py" | wc -l

# Найти прямые SQL запросы
grep -r "cursor.execute" --include="*.py" | wc -l

# Проверить покрытие тестами
pytest --cov=src/repository --cov-report=term-missing
```

## Контакты и поддержка

При возникновении вопросов по миграции:
1. Проверьте этот документ
2. Посмотрите примеры в `tests/unit/test_user_repository.py`
3. Изучите документацию Repository Pattern
4. Обратитесь к команде разработки

## Заключение

Миграция от simple_db.py к Repository Pattern - важный шаг к улучшению качества кода, безопасности и поддерживаемости проекта. Следуя этому плану, мы обеспечим плавный переход без нарушения работы системы.

**Целевая дата завершения:** Апрель 2026  
**Дата удаления simple_db.py:** Май 2026 (версия 2.0.0)
