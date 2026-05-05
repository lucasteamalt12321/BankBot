# Дизайн: Исправление критических проблем проекта

## Архитектурный обзор

Рефакторинг будет выполняться поэтапно с сохранением работоспособности системы на каждом этапе. Используется стратегия "Strangler Fig Pattern" для постепенной замены проблемных компонентов.

## Технические решения

### 1. Унификация конфигурации

**Подход:**
- Оставляем `src/config.py` как единственный источник конфигурации
- Используем Pydantic для валидации настроек
- Поддержка множественных окружений через переменную `ENV`

**Структура:**
```python
# src/config.py
from pydantic import BaseSettings, Field, validator
from typing import Optional
import os

class Settings(BaseSettings):
    # Environment
    ENV: str = Field(default="development", env="ENV")
    
    # Bot Configuration
    BOT_TOKEN: str = Field(..., env="BOT_TOKEN")
    ADMIN_TELEGRAM_ID: int = Field(..., env="ADMIN_TELEGRAM_ID")
    
    # Database
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    
    # Parsing
    PARSING_ENABLED: bool = Field(default=False, env="PARSING_ENABLED")
    
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

**Миграция:**
1. Создать mapping старых импортов на новые
2. Добавить deprecation warnings в старые модули
3. Постепенно обновлять импорты
4. Удалить старые файлы после полной миграции

### 2. Управление конфиденциальными данными

**Подход:**
- Все секреты в `.env` файле
- Использование `python-dotenv` для загрузки
- Валидация при старте приложения

**Файл `.env.example`:**
```env
# Environment (development, test, production)
ENV=development

# Telegram Bot Configuration
BOT_TOKEN=your_bot_token_here
ADMIN_TELEGRAM_ID=123456789

# Database
DATABASE_URL=sqlite:///data/bot.db

# Parsing
PARSING_ENABLED=false

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/bot.log

# Background Tasks
TASK_CHECK_INTERVAL=300
```

**Замена хардкода:**
```python
# Было:
ADMIN_ID = 2091908459

# Стало:
from src.config import settings
ADMIN_ID = settings.ADMIN_TELEGRAM_ID
```

### 3. Управление зависимостями

**Структура файлов:**
```
requirements.txt          # Production dependencies
requirements-dev.txt      # Development and testing
requirements-docs.txt     # Documentation generation
```

**requirements.txt:**
```
aiogram==3.4.1
aiohttp==3.9.1
sqlalchemy==2.0.25
alembic==1.13.1
pydantic==2.5.3
python-dotenv==1.0.0
psycopg2-binary==2.9.9
redis==5.0.1
```

**requirements-dev.txt:**
```
-r requirements.txt
pytest==7.4.3
pytest-asyncio==0.23.2
pytest-cov==4.1.0
hypothesis==6.92.1
black==23.12.1
flake8==7.0.0
mypy==1.8.0
```

### 4. Исправление импортов

**Создание compatibility layer:**
```python
# utils/compat.py
import warnings
from utils.admin.admin_system import *  # noqa

warnings.warn(
    "Importing from utils.admin_system is deprecated. "
    "Use utils.admin.admin_system instead.",
    DeprecationWarning,
    stacklevel=2
)
```

**Автоматизация замены:**
```python
# scripts/fix_imports.py
import re
from pathlib import Path

REPLACEMENTS = {
    r'from utils\.admin_system import': 'from utils.admin.admin_system import',
    r'from utils\.simple_db import': 'from utils.database.simple_db import',
    r'from utils\.config import': 'from src.config import',
}

def fix_imports(file_path: Path):
    content = file_path.read_text()
    for old, new in REPLACEMENTS.items():
        content = re.sub(old, new, content)
    file_path.write_text(content)
```

### 5. Унификация работы с БД

**Архитектура:**
```
┌─────────────────┐
│  Telegram Bot   │
└────────┬────────┘
         │
┌────────▼────────┐
│   Services      │  (Business Logic)
└────────┬────────┘
         │
┌────────▼────────┐
│  Repositories   │  (Data Access)
└────────┬────────┘
         │
┌────────▼────────┐
│  SQLAlchemy     │
│     Models      │
└─────────────────┘
```

**Базовый репозиторий:**
```python
# src/repository/base.py
from typing import Generic, TypeVar, Type, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import DeclarativeMeta

T = TypeVar('T', bound=DeclarativeMeta)

class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T], session: Session):
        self.model = model
        self.session = session
    
    def get(self, id: int) -> Optional[T]:
        return self.session.query(self.model).filter_by(id=id).first()
    
    def get_all(self) -> List[T]:
        return self.session.query(self.model).all()
    
    def create(self, **kwargs) -> T:
        instance = self.model(**kwargs)
        self.session.add(instance)
        self.session.commit()
        return instance
    
    def update(self, id: int, **kwargs) -> Optional[T]:
        instance = self.get(id)
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            self.session.commit()
        return instance
    
    def delete(self, id: int) -> bool:
        instance = self.get(id)
        if instance:
            self.session.delete(instance)
            self.session.commit()
            return True
        return False
```

**Репозиторий пользователей:**
```python
# src/repository/user_repository.py
from typing import Optional
from src.repository.base import BaseRepository
from src.models import User

class UserRepository(BaseRepository[User]):
    def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        return self.session.query(self.model).filter_by(
            telegram_id=telegram_id
        ).first()
    
    def get_by_username(self, username: str) -> Optional[User]:
        return self.session.query(self.model).filter_by(
            username=username
        ).first()
    
    def get_or_create(self, telegram_id: int, **kwargs) -> User:
        user = self.get_by_telegram_id(telegram_id)
        if not user:
            user = self.create(telegram_id=telegram_id, **kwargs)
        return user
```

### 6. Улучшение обработки ошибок

**Глобальный обработчик:**
```python
# bot/middleware/error_handler.py
from aiogram import types
from aiogram.dispatcher.middlewares import BaseMiddleware
from src.logging_config import logger
from src.config import settings

class ErrorHandlerMiddleware(BaseMiddleware):
    async def on_process_message(self, message: types.Message, data: dict):
        try:
            yield
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            
            # Notify user
            await message.answer(
                "Произошла ошибка при обработке команды. "
                "Администраторы уже уведомлены."
            )
            
            # Notify admin
            if settings.ADMIN_TELEGRAM_ID:
                await message.bot.send_message(
                    settings.ADMIN_TELEGRAM_ID,
                    f"⚠️ Error in bot:\n{str(e)}\n\n"
                    f"User: {message.from_user.id}\n"
                    f"Message: {message.text}"
                )
```

### 7. Унификация конфигурации парсинга

**Модель БД:**
```python
# src/models/parsing_rule.py
from sqlalchemy import Column, Integer, String, Float, Boolean, JSON
from database.database import Base

class ParsingRule(Base):
    __tablename__ = 'parsing_rules'
    
    id = Column(Integer, primary_key=True)
    game_name = Column(String, unique=True, nullable=False)
    parser_class = Column(String, nullable=False)
    coefficient = Column(Float, default=1.0)
    enabled = Column(Boolean, default=True)
    config = Column(JSON, default={})
```

**API для управления:**
```python
# core/managers/parsing_config_manager.py
from typing import Dict, Optional
from src.repository.base import BaseRepository
from src.models.parsing_rule import ParsingRule

class ParsingConfigManager:
    def __init__(self, repository: BaseRepository[ParsingRule]):
        self.repository = repository
    
    def get_rule(self, game_name: str) -> Optional[ParsingRule]:
        return self.repository.session.query(ParsingRule).filter_by(
            game_name=game_name
        ).first()
    
    def update_coefficient(self, game_name: str, coefficient: float):
        rule = self.get_rule(game_name)
        if rule:
            rule.coefficient = coefficient
            self.repository.session.commit()
    
    def get_all_active_rules(self) -> Dict[str, ParsingRule]:
        rules = self.repository.session.query(ParsingRule).filter_by(
            enabled=True
        ).all()
        return {rule.game_name: rule for rule in rules}
```

### 8. Валидация окружения

**Startup validator:**
```python
# src/startup_validator.py
from pathlib import Path
from src.config import settings
from src.logging_config import logger
import sys

class StartupValidator:
    @staticmethod
    def validate_env_file():
        env_path = Path("config/.env")
        if not env_path.exists():
            logger.error(
                "❌ .env file not found at config/.env\n"
                "Please copy config/.env.example to config/.env "
                "and fill in the required values."
            )
            sys.exit(1)
    
    @staticmethod
    def validate_required_settings():
        required = {
            'BOT_TOKEN': settings.BOT_TOKEN,
            'ADMIN_TELEGRAM_ID': settings.ADMIN_TELEGRAM_ID,
            'DATABASE_URL': settings.DATABASE_URL,
        }
        
        missing = [k for k, v in required.items() if not v]
        if missing:
            logger.error(
                f"❌ Missing required environment variables: {', '.join(missing)}\n"
                "Please check your config/.env file."
            )
            sys.exit(1)
    
    @staticmethod
    def validate_database():
        from database.connection import test_connection
        if not test_connection():
            logger.error("❌ Cannot connect to database")
            sys.exit(1)
    
    @classmethod
    def validate_all(cls):
        logger.info("🔍 Validating startup configuration...")
        cls.validate_env_file()
        cls.validate_required_settings()
        cls.validate_database()
        logger.info("✅ All validations passed")
```

### 9. Безопасное завершение процессов

**PID management:**
```python
# src/process_manager.py
from pathlib import Path
import os
import signal
import sys

class ProcessManager:
    PID_FILE = Path("data/bot.pid")
    
    @classmethod
    def write_pid(cls):
        cls.PID_FILE.parent.mkdir(exist_ok=True)
        cls.PID_FILE.write_text(str(os.getpid()))
    
    @classmethod
    def read_pid(cls) -> int:
        if cls.PID_FILE.exists():
            return int(cls.PID_FILE.read_text())
        return None
    
    @classmethod
    def remove_pid(cls):
        if cls.PID_FILE.exists():
            cls.PID_FILE.unlink()
    
    @classmethod
    def kill_existing(cls):
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

**Graceful shutdown:**
```python
# bot/main.py
import signal
import asyncio
from src.process_manager import ProcessManager

class BotApplication:
    def __init__(self):
        self.shutdown_event = asyncio.Event()
    
    def setup_signal_handlers(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.shutdown_event.set()
    
    async def shutdown(self):
        logger.info("Shutting down gracefully...")
        # Close database connections
        await self.db.close()
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
        # Close bot session
        await self.bot.session.close()
        ProcessManager.remove_pid()
        logger.info("Shutdown complete")
    
    async def run(self):
        ProcessManager.write_pid()
        self.setup_signal_handlers()
        
        try:
            await self.start()
            await self.shutdown_event.wait()
        finally:
            await self.shutdown()
```

### 10. Рефакторинг bot.py

**Новая структура:**
```
bot/
├── __init__.py
├── main.py                 # Entry point, bot initialization
├── router.py               # Command routing
├── commands/
│   ├── __init__.py
│   ├── admin_commands.py   # Admin-only commands
│   ├── user_commands.py    # User commands (profile, balance)
│   ├── shop_commands.py    # Shop-related commands
│   ├── game_commands.py    # Game-related commands
│   └── system_commands.py  # System commands (start, help)
├── handlers/
│   ├── __init__.py
│   ├── message_handler.py  # Message processing
│   └── callback_handler.py # Callback queries
└── middleware/
    ├── __init__.py
    ├── auth_middleware.py
    └── error_handler.py
```

**Command registration:**
```python
# bot/router.py
from aiogram import Router
from bot.commands import (
    admin_commands,
    user_commands,
    shop_commands,
    game_commands,
    system_commands
)

def setup_routers() -> Router:
    router = Router()
    
    # Register command modules
    router.include_router(system_commands.router)
    router.include_router(user_commands.router)
    router.include_router(shop_commands.router)
    router.include_router(game_commands.router)
    router.include_router(admin_commands.router)
    
    return router
```

**Example command module:**
```python
# bot/commands/user_commands.py
from aiogram import Router, types
from aiogram.filters import Command
from core.services.user_service import UserService

router = Router()

@router.message(Command("profile"))
async def profile_command(message: types.Message, user_service: UserService):
    """Show user profile"""
    user = await user_service.get_user(message.from_user.id)
    await message.answer(
        f"👤 Профиль\n"
        f"Баланс: {user.balance} очков\n"
        f"Уровень: {user.level}"
    )

@router.message(Command("balance"))
async def balance_command(message: types.Message, user_service: UserService):
    """Show user balance"""
    user = await user_service.get_user(message.from_user.id)
    await message.answer(f"💰 Ваш баланс: {user.balance} очков")
```

### 11. Разделение уровней абстракции

**Архитектура слоев:**
```
Presentation Layer (bot/commands/)
         ↓
Service Layer (core/services/)
         ↓
Repository Layer (src/repository/)
         ↓
Data Layer (database/models/)
```

**Service example:**
```python
# core/services/user_service.py
from typing import Optional
from src.repository.user_repository import UserRepository
from src.models import User
from core.services.transaction_service import TransactionService

class UserService:
    def __init__(
        self,
        user_repo: UserRepository,
        transaction_service: TransactionService
    ):
        self.user_repo = user_repo
        self.transaction_service = transaction_service
    
    async def get_user(self, telegram_id: int) -> Optional[User]:
        return self.user_repo.get_by_telegram_id(telegram_id)
    
    async def add_points(
        self,
        telegram_id: int,
        amount: int,
        reason: str
    ) -> User:
        user = await self.get_user(telegram_id)
        if not user:
            raise ValueError(f"User {telegram_id} not found")
        
        # Use transaction service for atomicity
        return await self.transaction_service.add_points(
            user=user,
            amount=amount,
            reason=reason
        )
```

### 12. Упрощение системы парсинга

**Parser registry:**
```python
# core/parsers/registry.py
from typing import Dict, Type
from core.parsers.base import BaseParser

class ParserRegistry:
    _parsers: Dict[str, Type[BaseParser]] = {}
    
    @classmethod
    def register(cls, game_name: str):
        def decorator(parser_class: Type[BaseParser]):
            cls._parsers[game_name] = parser_class
            return parser_class
        return decorator
    
    @classmethod
    def get_parser(cls, game_name: str) -> Type[BaseParser]:
        return cls._parsers.get(game_name)
    
    @classmethod
    def list_parsers(cls) -> Dict[str, Type[BaseParser]]:
        return cls._parsers.copy()
```

**Parser registration:**
```python
# core/parsers/gdcards.py
from core.parsers.registry import ParserRegistry
from core.parsers.base import BaseParser

@ParserRegistry.register("gdcards")
class GDCardsParser(BaseParser):
    def parse(self, message: str) -> dict:
        # Implementation
        pass
```

### 13. Управление deprecated кодом

**Deprecation decorator:**
```python
# src/deprecation.py
import warnings
from functools import wraps
from datetime import datetime

def deprecated(reason: str, removal_date: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(
                f"{func.__name__} is deprecated: {reason}. "
                f"Will be removed on {removal_date}",
                DeprecationWarning,
                stacklevel=2
            )
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

**Usage:**
```python
from src.deprecation import deprecated

@deprecated(
    reason="Use utils.database.simple_db instead",
    removal_date="2026-04-01"
)
def old_function():
    pass
```

### 14. Устранение race conditions

**Lock management:**
```python
# core/services/transaction_service.py
import asyncio
from typing import Dict
from src.models import User

class TransactionService:
    def __init__(self):
        self._locks: Dict[int, asyncio.Lock] = {}
    
    def _get_lock(self, user_id: int) -> asyncio.Lock:
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]
    
    async def add_points(self, user: User, amount: int, reason: str):
        async with self._get_lock(user.id):
            # Critical section - protected by lock
            user.balance += amount
            transaction = Transaction(
                user_id=user.id,
                amount=amount,
                reason=reason
            )
            self.session.add(transaction)
            self.session.commit()
            return user
```

### 15. Защита от SQL injection

**Parameterized queries:**
```python
# ❌ BAD - SQL Injection vulnerable
query = f"SELECT * FROM users WHERE username = '{username}'"

# ✅ GOOD - Parameterized query
query = "SELECT * FROM users WHERE username = :username"
result = session.execute(query, {"username": username})
```

**SQLAlchemy ORM (preferred):**
```python
# ✅ BEST - ORM automatically handles escaping
user = session.query(User).filter_by(username=username).first()
```

### 16. Улучшение идентификации пользователей

**Alias management:**
```python
# core/services/alias_service.py
from typing import Optional, List
from src.models import User, UserAlias

class AliasService:
    def __init__(self, session):
        self.session = session
    
    def add_alias(self, user_id: int, alias: str):
        alias_obj = UserAlias(user_id=user_id, alias=alias)
        self.session.add(alias_obj)
        self.session.commit()
    
    def find_user_by_alias(self, alias: str) -> Optional[User]:
        alias_obj = self.session.query(UserAlias).filter_by(
            alias=alias
        ).first()
        return alias_obj.user if alias_obj else None
    
    def get_user_aliases(self, user_id: int) -> List[str]:
        aliases = self.session.query(UserAlias).filter_by(
            user_id=user_id
        ).all()
        return [a.alias for a in aliases]
```

### 17. Обеспечение атомарности транзакций

**Unit of Work pattern:**
```python
# src/repository/unit_of_work.py
from contextlib import contextmanager
from sqlalchemy.orm import Session

class UnitOfWork:
    def __init__(self, session: Session):
        self.session = session
    
    @contextmanager
    def transaction(self):
        try:
            yield self.session
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
```

**Usage:**
```python
# core/services/purchase_service.py
from src.repository.unit_of_work import UnitOfWork

class PurchaseService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow
    
    async def purchase_item(self, user_id: int, item_id: int):
        with self.uow.transaction() as session:
            user = session.query(User).filter_by(id=user_id).first()
            item = session.query(Item).filter_by(id=item_id).first()
            
            if user.balance < item.price:
                raise ValueError("Insufficient balance")
            
            # Both operations in same transaction
            user.balance -= item.price
            transaction = Transaction(
                user_id=user_id,
                amount=-item.price,
                reason=f"Purchase: {item.name}"
            )
            session.add(transaction)
            # Commit happens automatically if no exception
```

## Correctness Properties

### Property 1: Configuration Uniqueness
**Validates: Requirements 1.1, 1.2**

All configuration must come from a single source (`src/config.py`), and no duplicate config files should exist.

```python
def test_config_uniqueness():
    """Only one config.py should exist in the codebase"""
    config_files = find_files("config.py")
    assert len(config_files) == 1
    assert config_files[0] == "src/config.py"
```

### Property 2: No Hardcoded Secrets
**Validates: Requirements 2.1, 2.2**

No hardcoded sensitive data should exist in the codebase.

```python
@given(st.text())
def test_no_hardcoded_secrets(file_content):
    """No hardcoded Telegram IDs or tokens in code"""
    assert "2091908459" not in file_content
    assert not re.search(r'\d{10}:\w{35}', file_content)  # Bot token pattern
```

### Property 3: Import Correctness
**Validates: Requirements 4.1-4.4**

All imports must resolve correctly without errors.

```python
def test_all_imports_resolve():
    """All test modules should import without errors"""
    test_files = find_test_files()
    for test_file in test_files:
        try:
            import_module(test_file)
        except ImportError as e:
            pytest.fail(f"Import error in {test_file}: {e}")
```

### Property 4: Transaction Atomicity
**Validates: Requirements 17.1-17.3**

Balance changes and transaction logging must be atomic.

```python
@given(st.integers(min_value=1, max_value=1000))
def test_transaction_atomicity(amount):
    """Balance change and transaction log must be atomic"""
    initial_balance = user.balance
    initial_tx_count = count_transactions(user.id)
    
    try:
        add_points(user.id, amount, "test")
    except Exception:
        # On error, both should be unchanged
        assert user.balance == initial_balance
        assert count_transactions(user.id) == initial_tx_count
    else:
        # On success, both should be updated
        assert user.balance == initial_balance + amount
        assert count_transactions(user.id) == initial_tx_count + 1
```

### Property 5: SQL Injection Safety
**Validates: Requirements 15.1-15.3**

No SQL injection vulnerabilities should exist.

```python
@given(st.text())
def test_sql_injection_safety(malicious_input):
    """System should be safe from SQL injection"""
    # Try to inject SQL
    result = user_service.get_by_username(malicious_input)
    # Should either return None or valid user, never execute injected SQL
    assert result is None or isinstance(result, User)
    # Database should remain intact
    assert database_integrity_check()
```

### Property 6: Race Condition Safety
**Validates: Requirements 14.1-14.3**

Concurrent operations should not cause data corruption.

```python
@given(st.lists(st.integers(min_value=1, max_value=100), min_size=10, max_size=100))
async def test_concurrent_balance_updates(amounts):
    """Concurrent balance updates should not corrupt data"""
    initial_balance = user.balance
    expected_final = initial_balance + sum(amounts)
    
    # Execute all updates concurrently
    await asyncio.gather(*[
        add_points(user.id, amount, "test")
        for amount in amounts
    ])
    
    # Final balance should be correct
    user.refresh()
    assert user.balance == expected_final
```

## Testing Strategy

### Unit Tests
- Test individual functions and methods in isolation
- Mock external dependencies
- Fast execution (< 1 second per test)

### Integration Tests
- Test interaction between components
- Use test database
- Verify end-to-end workflows

### Property-Based Tests
- Use Hypothesis for property testing
- Generate random inputs to find edge cases
- Verify invariants hold for all inputs

### E2E Tests
- Test complete user scenarios
- Use real bot instance (test mode)
- Verify system behavior from user perspective

## Migration Plan

### Phase 1: Foundation (Week 1-2)
1. Create new config system
2. Add deprecation warnings to old configs
3. Fix requirements.txt
4. Fix import errors

### Phase 2: Architecture (Week 3-4)
5. Implement repository pattern
6. Create service layer
7. Add error handling middleware
8. Implement graceful shutdown

### Phase 3: Refactoring (Week 5-6)
9. Split bot.py into modules
10. Unify parsing system
11. Clean up deprecated code
12. Add transaction safety

### Phase 4: Polish (Week 7-8)
13. Update documentation
14. Add API docs
15. Improve test coverage
16. Performance optimization

## Rollback Strategy

Each phase has a rollback plan:
1. All changes in feature branches
2. Comprehensive testing before merge
3. Feature flags for new functionality
4. Database migrations are reversible
5. Keep old code with deprecation warnings until stable

## Success Metrics

- ✅ All 784 tests pass
- ✅ No import errors
- ✅ Code coverage > 80%
- ✅ No critical linter warnings
- ✅ Documentation coverage 100%
- ✅ Startup time < 5 seconds
