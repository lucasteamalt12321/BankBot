"""
Unit tests for Unit of Work pattern implementation.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database import Base, User
from src.repository.unit_of_work import (
    UnitOfWork,
    transaction,
    atomic,
    TransactionManager,
    nested_transaction
)


@pytest.fixture
def engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create database session for testing."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_user(session):
    """Create a test user."""
    user = User(
        telegram_id=123456,
        username="testuser",
        balance=100
    )
    session.add(user)
    session.commit()
    return user


class TestUnitOfWork:
    """Test UnitOfWork class."""
    
    def test_commit_on_success(self, session, test_user):
        """Test that changes are committed on successful completion."""
        user_id = test_user.id
        
        with UnitOfWork(session=session):
            user = session.query(User).filter_by(id=user_id).first()
            user.balance = 200
        
        # Verify changes persisted
        session.expire_all()
        user = session.query(User).filter_by(id=user_id).first()
        assert user.balance == 200
    
    def test_rollback_on_error(self, session, test_user):
        """Test that changes are rolled back on error."""
        user_id = test_user.id
        original_balance = test_user.balance
        
        with pytest.raises(ValueError):
            with UnitOfWork(session=session):
                user = session.query(User).filter_by(id=user_id).first()
                user.balance = 999
                raise ValueError("Test error")
        
        # Verify changes were rolled back
        session.expire_all()
        user = session.query(User).filter_by(id=user_id).first()
        assert user.balance == original_balance
    
    def test_manual_commit(self, session, test_user):
        """Test manual commit."""
        user_id = test_user.id
        
        with UnitOfWork(session=session) as uow:
            user = session.query(User).filter_by(id=user_id).first()
            user.balance = 300
            uow.commit()
        
        session.expire_all()
        user = session.query(User).filter_by(id=user_id).first()
        assert user.balance == 300
    
    def test_manual_rollback(self, session, test_user):
        """Test manual rollback."""
        user_id = test_user.id
        original_balance = test_user.balance
        
        with UnitOfWork(session=session) as uow:
            user = session.query(User).filter_by(id=user_id).first()
            user.balance = 999
            uow.rollback()
        
        session.expire_all()
        user = session.query(User).filter_by(id=user_id).first()
        assert user.balance == original_balance
    
    def test_flush(self, session):
        """Test flush operation."""
        with UnitOfWork(session=session) as uow:
            user = User(telegram_id=999, username="newuser", balance=50)
            session.add(user)
            uow.flush()
            
            # After flush, ID should be available
            assert user.id is not None
    
    def test_cannot_commit_after_rollback(self, session, test_user):
        """Test that commit after rollback raises error."""
        with pytest.raises(RuntimeError, match="Cannot commit after rollback"):
            with UnitOfWork(session=session) as uow:
                uow.rollback()
                uow.commit()


class TestTransactionContextManager:
    """Test transaction() context manager."""
    
    def test_transaction_commits_on_success(self, engine):
        """Test that transaction commits on success."""
        Session = sessionmaker(bind=engine)
        
        # Create user in transaction
        with transaction() as session:
            user = User(telegram_id=111, username="user1", balance=100)
            session.add(user)
        
        # Verify user exists
        session = Session()
        user = session.query(User).filter_by(telegram_id=111).first()
        assert user is not None
        assert user.balance == 100
        session.close()
    
    def test_transaction_rolls_back_on_error(self, engine):
        """Test that transaction rolls back on error."""
        Session = sessionmaker(bind=engine)
        
        with pytest.raises(ValueError):
            with transaction() as session:
                user = User(telegram_id=222, username="user2", balance=100)
                session.add(user)
                raise ValueError("Test error")
        
        # Verify user was not created
        session = Session()
        user = session.query(User).filter_by(telegram_id=222).first()
        assert user is None
        session.close()
    
    def test_transaction_with_existing_session(self, session, test_user):
        """Test transaction with provided session."""
        user_id = test_user.id
        
        with transaction(session=session) as s:
            assert s is session
            user = s.query(User).filter_by(id=user_id).first()
            user.balance = 500
        
        session.expire_all()
        user = session.query(User).filter_by(id=user_id).first()
        assert user.balance == 500


class TestAtomicDecorator:
    """Test @atomic decorator."""
    
    def test_atomic_function_commits(self, engine):
        """Test that atomic function commits changes."""
        @atomic
        def create_user(session, telegram_id, username, balance):
            user = User(telegram_id=telegram_id, username=username, balance=balance)
            session.add(user)
            return user
        
        user = create_user(telegram_id=333, username="user3", balance=150)
        
        # Verify user was created
        Session = sessionmaker(bind=engine)
        session = Session()
        found_user = session.query(User).filter_by(telegram_id=333).first()
        assert found_user is not None
        assert found_user.balance == 150
        session.close()
    
    def test_atomic_function_rolls_back_on_error(self, engine):
        """Test that atomic function rolls back on error."""
        @atomic
        def create_user_with_error(session, telegram_id):
            user = User(telegram_id=telegram_id, username="user4", balance=100)
            session.add(user)
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            create_user_with_error(telegram_id=444)
        
        # Verify user was not created
        Session = sessionmaker(bind=engine)
        session = Session()
        user = session.query(User).filter_by(telegram_id=444).first()
        assert user is None
        session.close()
    
    def test_atomic_with_provided_session(self, session, test_user):
        """Test atomic decorator with provided session."""
        @atomic
        def update_balance(session, user_id, new_balance):
            user = session.query(User).filter_by(id=user_id).first()
            user.balance = new_balance
        
        # Should use provided session without creating transaction
        update_balance(session=session, user_id=test_user.id, new_balance=777)
        
        session.commit()
        session.expire_all()
        user = session.query(User).filter_by(id=test_user.id).first()
        assert user.balance == 777


class TestTransactionManager:
    """Test TransactionManager class."""
    
    def test_basic_transaction(self, session, test_user):
        """Test basic transaction with TransactionManager."""
        user_id = test_user.id
        
        tm = TransactionManager(session=session)
        with tm:
            user = session.query(User).filter_by(id=user_id).first()
            user.balance = 888
        
        session.expire_all()
        user = session.query(User).filter_by(id=user_id).first()
        assert user.balance == 888
    
    def test_nested_transactions(self, session, test_user):
        """Test nested transactions with savepoints."""
        user_id = test_user.id
        original_balance = test_user.balance
        
        tm = TransactionManager(session=session)
        with tm:
            user = session.query(User).filter_by(id=user_id).first()
            user.balance = 200
            
            # Nested transaction that will be rolled back
            with pytest.raises(ValueError):
                with TransactionManager(session=session):
                    user.balance = 999
                    raise ValueError("Inner error")
            
            # Outer transaction should still be valid
            session.expire_all()
            user = session.query(User).filter_by(id=user_id).first()
            assert user.balance == 200
        
        # Final commit
        session.expire_all()
        user = session.query(User).filter_by(id=user_id).first()
        assert user.balance == 200
    
    def test_manual_begin_commit(self, session, test_user):
        """Test manual begin and commit."""
        user_id = test_user.id
        
        tm = TransactionManager(session=session)
        tm.begin()
        
        user = session.query(User).filter_by(id=user_id).first()
        user.balance = 555
        
        tm.commit()
        
        session.expire_all()
        user = session.query(User).filter_by(id=user_id).first()
        assert user.balance == 555


class TestNestedTransaction:
    """Test nested_transaction context manager."""
    
    def test_nested_transaction_commits(self, session, test_user):
        """Test that nested transaction commits on success."""
        user_id = test_user.id
        
        with transaction(session=session):
            user = session.query(User).filter_by(id=user_id).first()
            user.balance = 100
            
            with nested_transaction(session):
                user.balance = 200
        
        session.expire_all()
        user = session.query(User).filter_by(id=user_id).first()
        assert user.balance == 200
    
    def test_nested_transaction_rolls_back_independently(self, session, test_user):
        """Test that nested transaction can roll back independently."""
        user_id = test_user.id
        
        with transaction(session=session):
            user = session.query(User).filter_by(id=user_id).first()
            user.balance = 300
            
            try:
                with nested_transaction(session):
                    user.balance = 999
                    raise ValueError("Inner error")
            except ValueError:
                pass
            
            # Outer transaction should still have balance = 300
            session.expire_all()
            user = session.query(User).filter_by(id=user_id).first()
            assert user.balance == 300
        
        # Verify final state
        session.expire_all()
        user = session.query(User).filter_by(id=user_id).first()
        assert user.balance == 300


class TestTransactionIsolation:
    """Test transaction isolation and consistency."""
    
    def test_changes_not_visible_before_commit(self, engine):
        """Test that changes are not visible to other sessions before commit."""
        Session = sessionmaker(bind=engine)
        
        # Create user
        session1 = Session()
        user = User(telegram_id=555, username="user5", balance=100)
        session1.add(user)
        session1.commit()
        user_id = user.id
        session1.close()
        
        # Start transaction in session1
        session1 = Session()
        session1.begin()
        user = session1.query(User).filter_by(id=user_id).first()
        user.balance = 999
        
        # Check from session2 - should see old value
        session2 = Session()
        user2 = session2.query(User).filter_by(id=user_id).first()
        assert user2.balance == 100
        
        # Commit session1
        session1.commit()
        
        # Now session2 should see new value
        session2.expire_all()
        user2 = session2.query(User).filter_by(id=user_id).first()
        assert user2.balance == 999
        
        session1.close()
        session2.close()
    
    def test_rollback_restores_original_state(self, session, test_user):
        """Test that rollback restores original state."""
        user_id = test_user.id
        original_balance = test_user.balance
        
        # Make changes
        user = session.query(User).filter_by(id=user_id).first()
        user.balance = 999
        user.username = "changed"
        
        # Rollback
        session.rollback()
        
        # Verify original state restored
        session.expire_all()
        user = session.query(User).filter_by(id=user_id).first()
        assert user.balance == original_balance
        assert user.username == "testuser"
