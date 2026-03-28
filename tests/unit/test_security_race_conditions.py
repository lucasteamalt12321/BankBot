"""Security tests for race condition prevention."""

import pytest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.database import Base, User
from core.services.transaction_service import TransactionService
from core.repositories.user_repository import UserRepository


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()


@pytest.fixture
def user_repository(in_memory_db):
    """Create a UserRepository instance."""
    return UserRepository(in_memory_db)


@pytest.fixture
def transaction_service(user_repository, in_memory_db):
    """Create a TransactionService instance with test session."""
    return TransactionService(user_repository, session=in_memory_db)


class TestRaceConditionPrevention:
    """Test that race conditions are prevented via locking mechanisms."""

    def test_concurrent_balance_updates_are_atomic(self, transaction_service, in_memory_db):
        """Test that concurrent balance updates maintain data integrity."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=100
        )
        in_memory_db.add(user)
        in_memory_db.commit()

        async def run_test():
            results = await asyncio.gather(
                transaction_service.add_points(user.id, 10, "First"),
                transaction_service.add_points(user.id, 20, "Second"),
                transaction_service.add_points(user.id, 30, "Third"),
            )
            return results

        results = asyncio.run(run_test())

        in_memory_db.expire_all()
        final_user = in_memory_db.query(User).filter(User.id == user.id).first()
        
        expected_balance = 100 + 10 + 20 + 30
        assert final_user.balance == expected_balance, (
            f"Race condition detected: expected {expected_balance}, got {final_user.balance}"
        )

    def test_multiple_sequential_operations_correct_balance(self, transaction_service, in_memory_db):
        """Test that sequential operations maintain correct balance."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=100
        )
        in_memory_db.add(user)
        in_memory_db.commit()

        async def run_test():
            await transaction_service.add_points(user.id, 50, "Add 50")
            await transaction_service.subtract_points(user.id, 30, "Subtract 30")
            await transaction_service.add_points(user.id, 20, "Add 20")

        asyncio.run(run_test())

        in_memory_db.expire_all()
        final_user = in_memory_db.query(User).filter(User.id == user.id).first()
        
        expected_balance = 100 + 50 - 30 + 20
        assert final_user.balance == expected_balance, (
            f"Balance mismatch: expected {expected_balance}, got {final_user.balance}"
        )


class TestUnitOfWorkAtomicity:
    """Test that Unit of Work provides atomic transactions."""

    def test_failed_operation_rolls_back(self, transaction_service, in_memory_db):
        """Test that failed operations don't leave partial state."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=100
        )
        in_memory_db.add(user)
        in_memory_db.commit()

        initial_balance = user.balance

        async def run_test():
            await transaction_service.add_points(user.id, 50, "Add 50")
            with pytest.raises(ValueError):
                await transaction_service.subtract_points(user.id, 200, "Too much")
            return True

        asyncio.run(run_test())

        in_memory_db.expire_all()
        final_user = in_memory_db.query(User).filter(User.id == user.id).first()
        
        assert final_user.balance == initial_balance + 50, (
            "Failed operation should have left partial state if not properly rolled back"
        )
