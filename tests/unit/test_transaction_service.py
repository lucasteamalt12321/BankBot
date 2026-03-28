"""Unit tests for TransactionService implementation."""

import pytest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.services.transaction_service import TransactionService
from src.repository.user_repository import UserRepository
from database.database import Base, User, Transaction


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


class TestTransactionServiceInitialization:
    """Test TransactionService initialization."""
    
    def test_init_creates_service(self, user_repository):
        """Test that TransactionService is created successfully."""
        service = TransactionService(user_repository)
        assert service is not None
        assert service.user_repo == user_repository
        assert len(service._locks) == 0


class TestTransactionServiceAddPoints:
    """Test add_points method."""
    
    def test_add_points_success(self, transaction_service, in_memory_db):
        """Test successful addition of points."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=100
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        async def run_test():
            updated_user = await transaction_service.add_points(
                user_id=user.id,
                amount=50,
                reason="Test accrual",
                source_game="gdcards"
            )
            return updated_user
        
        updated_user = asyncio.run(run_test())
        
        assert updated_user is not None
        assert updated_user.balance == 150
        assert updated_user.total_earned == 50  # Only the added amount
        
        # Check transaction was created
        transaction = in_memory_db.query(Transaction).filter_by(
            user_id=user.id
        ).first()
        assert transaction is not None
        assert transaction.amount == 50
        assert transaction.transaction_type == "credit"
        assert transaction.source_game == "gdcards"
    
    def test_add_points_user_not_found(self, transaction_service):
        """Test adding points to non-existent user."""
        async def run_test():
            await transaction_service.add_points(
                user_id=999999,
                amount=50,
                reason="Test"
            )
        
        with pytest.raises(ValueError, match="User 999999 not found"):
            asyncio.run(run_test())
    
    def test_add_points_multiple_times(self, transaction_service, in_memory_db):
        """Test adding points multiple times."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=100
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        async def run_test():
            user1 = await transaction_service.add_points(user.id, 50, "First")
            user2 = await transaction_service.add_points(user.id, 30, "Second")
            return user1, user2
        
        user1, user2 = asyncio.run(run_test())
        
        assert user1.balance == 180  # 100 + 50 + 30
        assert user2.balance == 180
        assert user2.total_earned == 80  # 50 + 30 from both operations


class TestTransactionServiceSubtractPoints:
    """Test subtract_points method."""
    
    def test_subtract_points_success(self, transaction_service, in_memory_db):
        """Test successful subtraction of points."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=100
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        async def run_test():
            updated_user = await transaction_service.subtract_points(
                user_id=user.id,
                amount=30,
                reason="Test purchase"
            )
            return updated_user
        
        updated_user = asyncio.run(run_test())
        
        assert updated_user is not None
        assert updated_user.balance == 70
        
        # Check transaction was created
        transaction = in_memory_db.query(Transaction).filter_by(
            user_id=user.id
        ).first()
        assert transaction is not None
        assert transaction.amount == 30
        assert transaction.transaction_type == "debit"
    
    def test_subtract_points_insufficient_balance(self, transaction_service, in_memory_db):
        """Test subtracting more points than user has."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=50
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        async def run_test():
            await transaction_service.subtract_points(
                user_id=user.id,
                amount=100,
                reason="Test"
            )
        
        with pytest.raises(ValueError, match="Insufficient balance"):
            asyncio.run(run_test())
    
    def test_subtract_points_user_not_found(self, transaction_service):
        """Test subtracting points from non-existent user."""
        async def run_test():
            await transaction_service.subtract_points(
                user_id=999999,
                amount=50,
                reason="Test"
            )
        
        with pytest.raises(ValueError, match="User 999999 not found"):
            asyncio.run(run_test())


class TestTransactionServiceTransferPoints:
    """Test transfer_points method."""
    
    def test_transfer_points_success(self, transaction_service, in_memory_db):
        """Test successful transfer of points."""
        sender = User(
            telegram_id=111111,
            username="sender",
            first_name="Sender",
            balance=100
        )
        receiver = User(
            telegram_id=222222,
            username="receiver",
            first_name="Receiver",
            balance=50
        )
        in_memory_db.add_all([sender, receiver])
        in_memory_db.commit()
        
        async def run_test():
            result = await transaction_service.transfer_points(
                from_user_id=sender.id,
                to_user_id=receiver.id,
                amount=30,
                reason="Gift"
            )
            return result
        
        sender_updated, receiver_updated = asyncio.run(run_test())
        
        assert sender_updated.balance == 70
        assert receiver_updated.balance == 80
        
        # Check both transactions were created
        sender_tx = in_memory_db.query(Transaction).filter_by(
            user_id=sender.id,
            transaction_type="transfer_out"
        ).first()
        receiver_tx = in_memory_db.query(Transaction).filter_by(
            user_id=receiver.id,
            transaction_type="transfer_in"
        ).first()
        
        assert sender_tx is not None
        assert receiver_tx is not None
    
    def test_transfer_points_insufficient_balance(self, transaction_service, in_memory_db):
        """Test transferring more points than sender has."""
        sender = User(
            telegram_id=111111,
            username="sender",
            first_name="Sender",
            balance=50
        )
        receiver = User(
            telegram_id=222222,
            username="receiver",
            first_name="Receiver",
            balance=100
        )
        in_memory_db.add_all([sender, receiver])
        in_memory_db.commit()
        
        async def run_test():
            await transaction_service.transfer_points(
                from_user_id=sender.id,
                to_user_id=receiver.id,
                amount=100,
                reason="Test"
            )
        
        with pytest.raises(ValueError, match="Insufficient balance"):
            asyncio.run(run_test())
    
    def test_transfer_points_sender_not_found(self, transaction_service, in_memory_db):
        """Test transferring from non-existent sender."""
        receiver = User(
            telegram_id=222222,
            username="receiver",
            first_name="Receiver",
            balance=100
        )
        in_memory_db.add(receiver)
        in_memory_db.commit()
        
        async def run_test():
            await transaction_service.transfer_points(
                from_user_id=999999,
                to_user_id=receiver.id,
                amount=50,
                reason="Test"
            )
        
        with pytest.raises(ValueError, match="Sender 999999 not found"):
            asyncio.run(run_test())
    
    def test_transfer_points_receiver_not_found(self, transaction_service, in_memory_db):
        """Test transferring to non-existent receiver."""
        sender = User(
            telegram_id=111111,
            username="sender",
            first_name="Sender",
            balance=100
        )
        in_memory_db.add(sender)
        in_memory_db.commit()
        
        async def run_test():
            await transaction_service.transfer_points(
                from_user_id=sender.id,
                to_user_id=999999,
                amount=50,
                reason="Test"
            )
        
        with pytest.raises(ValueError, match="Receiver 999999 not found"):
            asyncio.run(run_test())


class TestTransactionServiceGetTransactions:
    """Test transaction history methods."""
    
    def test_get_user_transactions(self, transaction_service, in_memory_db):
        """Test getting user's transaction history."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=100
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        # Create multiple transactions with different timestamps
        from datetime import datetime, timedelta
        base_time = datetime.utcnow()
        
        t1 = Transaction(user_id=user.id, amount=50, transaction_type="credit", description="First")
        t1.created_at = base_time - timedelta(hours=2)
        
        t2 = Transaction(user_id=user.id, amount=30, transaction_type="credit", description="Second")
        t2.created_at = base_time - timedelta(hours=1)
        
        t3 = Transaction(user_id=user.id, amount=20, transaction_type="debit", description="Third")
        t3.created_at = base_time
        
        in_memory_db.add_all([t1, t2, t3])
        in_memory_db.commit()
        
        tx_list = transaction_service.get_user_transactions(user.id)
        assert len(tx_list) == 3
        descriptions = [tx.description for tx in tx_list]
        assert "First" in descriptions
        assert "Second" in descriptions
        assert "Third" in descriptions
    
    def test_get_user_transactions_empty(self, transaction_service, in_memory_db):
        """Test getting transactions for user with no transactions."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=100
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        tx_list = transaction_service.get_user_transactions(user.id)
        assert len(tx_list) == 0
    
    def test_get_user_total_transactions(self, transaction_service, in_memory_db):
        """Test getting total count of user's transactions."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=100
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        transactions = [
            Transaction(user_id=user.id, amount=50, transaction_type="credit", description="First"),
            Transaction(user_id=user.id, amount=30, transaction_type="credit", description="Second"),
        ]
        in_memory_db.add_all(transactions)
        in_memory_db.commit()
        
        total = transaction_service.get_user_total_transactions(user.id)
        assert total == 2


class TestTransactionServiceConcurrency:
    """Test concurrent operations."""
    
    def test_concurrent_add_points(self, transaction_service, in_memory_db):
        """Test concurrent addition of points to same user."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=100
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        async def add_points_task(amount):
            return await transaction_service.add_points(
                user_id=user.id,
                amount=amount,
                reason="Concurrent test"
            )
        
        async def run_test():
            results = await asyncio.gather(
                add_points_task(10),
                add_points_task(20),
                add_points_task(30)
            )
            return results
        
        results = asyncio.run(run_test())
        
        # All operations should have succeeded
        assert len(results) == 3
        # Final balance should be initial + sum of all amounts
        assert results[0].balance == 160  # 100 + 10 + 20 + 30
