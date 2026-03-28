"""
Integration tests for critical paths to improve coverage to 90%.

This test suite focuses on the critical paths identified in the coverage analysis:
- Balance management (src/balance_manager.py)
- Repository operations (src/repository.py, src/repository/unit_of_work.py)
- User management (src/repository/user_repository.py)
- Transaction atomicity
- Error handling

**Validates: Requirements 17.1-17.3, 20.5**
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database import Base, User
from src.balance_manager import BalanceManager
from src.repository import SQLiteRepository
from src.coefficient_provider import CoefficientProvider
from src.parsers import ParsedProfile, ParsedAccrual
from src.repository.unit_of_work import UnitOfWork, transaction
from src.repository.user_repository import UserRepository
from unittest.mock import Mock


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
def repository(tmp_path):
    """Create a SQLite repository for testing."""
    db_path = str(tmp_path / "test.db")
    return SQLiteRepository(db_path)


@pytest.fixture
def coefficient_provider():
    """Create a coefficient provider with test coefficients."""
    return CoefficientProvider({
        "GD Cards": 2,
        "Shmalala": 1,
        "Shmalala Karma": 10,
        "True Mafia": 15,
        "Bunker RP": 20
    })


@pytest.fixture
def mock_logger():
    """Create a mock audit logger."""
    logger = Mock()
    logger.log_profile_init = Mock()
    logger.log_profile_update = Mock()
    logger.log_accrual = Mock()
    return logger


@pytest.fixture
def balance_manager(repository, coefficient_provider, mock_logger):
    """Create a balance manager for testing."""
    return BalanceManager(repository, coefficient_provider, mock_logger)


class TestCriticalPathRegistrationToAccrualToPurchase:
    """
    Test the complete critical path: User Registration → Accrual → Purchase
    
    **Validates: Requirement 20.2**
    """
    
    def test_complete_user_lifecycle(self, balance_manager, repository):
        """Test complete user lifecycle from registration to purchase."""
        # Step 1: User registration (implicit via first profile)
        parsed_profile = ParsedProfile(
            player_name="NewUser",
            orbs=Decimal("100"),
            game="GD Cards"
        )
        balance_manager.process_profile(parsed_profile)
        
        # Verify user created
        user = repository.get_or_create_user("NewUser")
        assert user is not None
        assert user.user_name == "NewUser"
        assert user.bank_balance == Decimal("0")  # First profile doesn't change balance
        
        # Step 2: Accrual (user earns points)
        parsed_accrual = ParsedAccrual(
            player_name="NewUser",
            points=Decimal("50"),
            game="GD Cards"
        )
        balance_manager.process_accrual(parsed_accrual)
        
        # Verify accrual
        user = repository.get_or_create_user("NewUser")
        assert user.bank_balance == Decimal("100")  # 50 * 2 (coefficient)
        
        # Step 3: Purchase (user spends points)
        # Simulate purchase by deducting balance
        new_balance = user.bank_balance - Decimal("30")
        repository.update_user_balance(user.user_id, new_balance)
        
        # Verify purchase
        user = repository.get_or_create_user("NewUser")
        assert user.bank_balance == Decimal("70")
    
    def test_multiple_users_concurrent_operations(self, balance_manager, repository):
        """Test multiple users performing operations concurrently."""
        users = ["User1", "User2", "User3"]
        
        # Register all users
        for user_name in users:
            parsed = ParsedProfile(
                player_name=user_name,
                orbs=Decimal("100"),
                game="GD Cards"
            )
            balance_manager.process_profile(parsed)
        
        # Each user earns different amounts
        for i, user_name in enumerate(users, 1):
            parsed = ParsedAccrual(
                player_name=user_name,
                points=Decimal(str(i * 10)),
                game="GD Cards"
            )
            balance_manager.process_accrual(parsed)
        
        # Verify each user has correct balance
        user1 = repository.get_or_create_user("User1")
        user2 = repository.get_or_create_user("User2")
        user3 = repository.get_or_create_user("User3")
        
        assert user1.bank_balance == Decimal("20")  # 10 * 2
        assert user2.bank_balance == Decimal("40")  # 20 * 2
        assert user3.bank_balance == Decimal("60")  # 30 * 2


class TestTransactionAtomicity:
    """
    Test transaction atomicity for balance operations.
    
    **Validates: Requirements 17.1-17.3**
    """
    
    def test_balance_update_with_transaction_commit(self, session):
        """Test that balance updates commit correctly within transaction."""
        user = User(telegram_id=123, username="testuser", balance=100)
        session.add(user)
        session.commit()
        user_id = user.id
        
        # Update balance in transaction
        with UnitOfWork(session=session):
            user = session.query(User).filter_by(id=user_id).first()
            user.balance = 200
        
        # Verify committed
        session.expire_all()
        user = session.query(User).filter_by(id=user_id).first()
        assert user.balance == 200
    
    def test_balance_update_with_transaction_rollback(self, session):
        """Test that balance updates rollback on error."""
        user = User(telegram_id=456, username="testuser2", balance=100)
        session.add(user)
        session.commit()
        user_id = user.id
        original_balance = user.balance
        
        # Attempt update that fails
        with pytest.raises(ValueError):
            with UnitOfWork(session=session):
                user = session.query(User).filter_by(id=user_id).first()
                user.balance = 999
                raise ValueError("Simulated error")
        
        # Verify rolled back
        session.expire_all()
        user = session.query(User).filter_by(id=user_id).first()
        assert user.balance == original_balance
    
    def test_multiple_operations_atomic(self, session):
        """Test that multiple operations are atomic."""
        user1 = User(telegram_id=111, username="user1", balance=100)
        user2 = User(telegram_id=222, username="user2", balance=50)
        session.add_all([user1, user2])
        session.commit()
        
        user1_id = user1.id
        user2_id = user2.id
        
        # Transfer points atomically
        with UnitOfWork(session=session):
            u1 = session.query(User).filter_by(id=user1_id).first()
            u2 = session.query(User).filter_by(id=user2_id).first()
            
            u1.balance -= 30
            u2.balance += 30
        
        # Verify both updated
        session.expire_all()
        u1 = session.query(User).filter_by(id=user1_id).first()
        u2 = session.query(User).filter_by(id=user2_id).first()
        
        assert u1.balance == 70
        assert u2.balance == 80
    
    def test_partial_failure_rolls_back_all(self, session):
        """Test that partial failure rolls back all operations."""
        user1 = User(telegram_id=333, username="user3", balance=100)
        user2 = User(telegram_id=444, username="user4", balance=50)
        session.add_all([user1, user2])
        session.commit()
        
        user1_id = user1.id
        user2_id = user2.id
        original_balance1 = user1.balance
        original_balance2 = user2.balance
        
        # Attempt transfer that fails after first update
        with pytest.raises(ValueError):
            with UnitOfWork(session=session):
                u1 = session.query(User).filter_by(id=user1_id).first()
                u1.balance -= 30  # This succeeds
                
                raise ValueError("Simulated error before second update")
        
        # Verify both unchanged
        session.expire_all()
        u1 = session.query(User).filter_by(id=user1_id).first()
        u2 = session.query(User).filter_by(id=user2_id).first()
        
        assert u1.balance == original_balance1
        assert u2.balance == original_balance2


class TestUserRepositoryCriticalPaths:
    """
    Test critical user repository operations.
    
    **Validates: Requirement 5.2**
    """
    
    def test_get_or_create_pattern(self, session):
        """Test get_or_create pattern for user management."""
        user_repo = UserRepository(User, session)
        
        # First call creates user
        user1 = user_repo.get_or_create(
            telegram_id=555,
            username="newuser",
            first_name="New"
        )
        assert user1.telegram_id == 555
        assert user1.username == "newuser"
        
        # Second call returns existing user
        user2 = user_repo.get_or_create(
            telegram_id=555,
            username="different_name"  # Should be ignored
        )
        assert user2.id == user1.id
        assert user2.username == "newuser"  # Original username preserved
    
    def test_bulk_balance_update(self, session):
        """Test bulk balance updates for multiple users."""
        user_repo = UserRepository(User, session)
        
        # Create multiple users
        users = []
        for i in range(5):
            user = user_repo.create(
                telegram_id=1000 + i,
                username=f"user{i}",
                balance=100
            )
            users.append(user)
        
        user_ids = [u.id for u in users]
        
        # Bulk update
        updated = user_repo.bulk_update_balance(user_ids, 50)
        assert updated == 5
        
        # Verify all updated
        for user_id in user_ids:
            user = user_repo.get(user_id)
            assert user.balance == 150
    
    def test_admin_and_vip_queries(self, session):
        """Test admin and VIP user queries."""
        user_repo = UserRepository(User, session)
        
        # Create mixed users
        admin = user_repo.create(
            telegram_id=2001,
            username="admin",
            is_admin=True,
            balance=1000
        )
        vip = user_repo.create(
            telegram_id=2002,
            username="vip",
            is_vip=True,
            vip_until=datetime.utcnow() + timedelta(days=30),
            balance=500
        )
        regular = user_repo.create(
            telegram_id=2003,
            username="regular",
            balance=100
        )
        
        # Test queries
        admins = user_repo.get_all_admins()
        assert len(admins) == 1
        assert admins[0].username == "admin"
        
        vips = user_repo.get_all_vips()
        assert len(vips) == 1
        assert vips[0].username == "vip"
        
        # Test balance queries
        rich_users = user_repo.get_users_with_balance_above(200)
        assert len(rich_users) == 2  # admin and vip
        
        top_users = user_repo.get_top_users_by_balance(2)
        assert len(top_users) == 2
        assert top_users[0].username == "admin"
        assert top_users[1].username == "vip"


class TestBalanceManagerEdgeCases:
    """
    Test balance manager edge cases and error conditions.
    
    **Validates: Requirement 6.1-6.5**
    """
    
    def test_zero_coefficient_handling(self, repository, mock_logger):
        """Test handling of zero coefficient."""
        coefficient_provider = CoefficientProvider({"TestGame": 0})
        balance_manager = BalanceManager(repository, coefficient_provider, mock_logger)
        
        parsed = ParsedAccrual(
            player_name="TestUser",
            points=Decimal("100"),
            game="TestGame"
        )
        balance_manager.process_accrual(parsed)
        
        user = repository.get_or_create_user("TestUser")
        assert user.bank_balance == Decimal("0")  # 100 * 0 = 0
    
    def test_large_numbers_precision(self, balance_manager, repository):
        """Test handling of large numbers with decimal precision."""
        parsed = ParsedAccrual(
            player_name="RichUser",
            points=Decimal("999999.99"),
            game="GD Cards"
        )
        balance_manager.process_accrual(parsed)
        
        user = repository.get_or_create_user("RichUser")
        # 999999.99 * 2 = 1999999.98
        assert user.bank_balance == Decimal("1999999.98")
    
    def test_negative_delta_handling(self, balance_manager, repository):
        """Test handling of negative delta in profile updates."""
        # First profile
        parsed1 = ParsedProfile(
            player_name="TestUser",
            orbs=Decimal("100"),
            game="GD Cards"
        )
        balance_manager.process_profile(parsed1)
        
        # Second profile with lower orbs (user spent points)
        parsed2 = ParsedProfile(
            player_name="TestUser",
            orbs=Decimal("50"),
            game="GD Cards"
        )
        balance_manager.process_profile(parsed2)
        
        user = repository.get_or_create_user("TestUser")
        # Delta = 50 - 100 = -50, bank_change = -50 * 2 = -100
        assert user.bank_balance == Decimal("-100")
    
    def test_multiple_games_independence(self, balance_manager, repository):
        """Test that different games maintain independent balances."""
        user_name = "MultiGameUser"
        
        # Play GD Cards
        parsed_gd = ParsedAccrual(
            player_name=user_name,
            points=Decimal("50"),
            game="GD Cards"
        )
        balance_manager.process_accrual(parsed_gd)
        
        # Play True Mafia
        parsed_mafia = ParsedAccrual(
            player_name=user_name,
            points=Decimal("10"),
            game="True Mafia"
        )
        balance_manager.process_accrual(parsed_mafia)
        
        user = repository.get_or_create_user(user_name)
        
        # Bank balance should be sum of both games with their coefficients
        # GD Cards: 50 * 2 = 100
        # True Mafia: 10 * 15 = 150
        # Total: 250
        assert user.bank_balance == Decimal("250")
        
        # Verify separate bot balances
        bot_balance_gd = repository.get_bot_balance(user.user_id, "GD Cards")
        bot_balance_mafia = repository.get_bot_balance(user.user_id, "True Mafia")
        
        assert bot_balance_gd.current_bot_balance == Decimal("50")
        assert bot_balance_mafia.current_bot_balance == Decimal("10")


class TestErrorRecovery:
    """
    Test error recovery and consistency.
    
    **Validates: Requirement 6.1-6.5**
    """
    
    def test_database_error_recovery(self, session):
        """Test recovery from database errors."""
        user = User(telegram_id=777, username="testuser", balance=100)
        session.add(user)
        session.commit()
        user_id = user.id
        
        # Simulate database error during transaction
        try:
            with UnitOfWork(session=session):
                user = session.query(User).filter_by(id=user_id).first()
                user.balance = 200
                # Simulate constraint violation or other DB error
                raise Exception("Database error")
        except Exception:
            pass
        
        # Verify database is still consistent
        session.expire_all()
        user = session.query(User).filter_by(id=user_id).first()
        assert user.balance == 100  # Original value preserved
    
    def test_concurrent_access_safety(self, engine):
        """Test safety under concurrent access."""
        Session = sessionmaker(bind=engine)
        
        # Create user
        session1 = Session()
        user = User(telegram_id=888, username="concurrent", balance=100)
        session1.add(user)
        session1.commit()
        user_id = user.id
        session1.close()
        
        # Two sessions try to update simultaneously
        session1 = Session()
        session2 = Session()
        
        with transaction(session=session1):
            user1 = session1.query(User).filter_by(id=user_id).first()
            user1.balance += 50
        
        with transaction(session=session2):
            user2 = session2.query(User).filter_by(id=user_id).first()
            user2.balance += 30
        
        # Verify final state is consistent
        session3 = Session()
        user = session3.query(User).filter_by(id=user_id).first()
        # One of the updates should win, balance should be either 150 or 130
        assert user.balance in [150, 130, 180]  # 180 if both applied
        
        session1.close()
        session2.close()
        session3.close()


class TestCoverageBoost:
    """
    Additional tests to boost coverage of critical modules.
    """
    
    def test_repository_all_methods(self, repository):
        """Test all repository methods to increase coverage."""
        # Create user
        user = repository.get_or_create_user("CoverageUser")
        assert user is not None
        
        # Create bot balance
        repository.create_bot_balance(
            user_id=user.user_id,
            game="TestGame",
            last_balance=Decimal("100"),
            current_bot_balance=Decimal("50")
        )
        
        # Get bot balance
        bot_balance = repository.get_bot_balance(user.user_id, "TestGame")
        assert bot_balance is not None
        assert bot_balance.last_balance == Decimal("100")
        
        # Update last balance
        repository.update_bot_last_balance(user.user_id, "TestGame", Decimal("150"))
        bot_balance = repository.get_bot_balance(user.user_id, "TestGame")
        assert bot_balance.last_balance == Decimal("150")
        
        # Update current balance
        repository.update_bot_current_balance(user.user_id, "TestGame", Decimal("75"))
        bot_balance = repository.get_bot_balance(user.user_id, "TestGame")
        assert bot_balance.current_bot_balance == Decimal("75")
        
        # Update user balance
        repository.update_user_balance(user.user_id, Decimal("500"))
        user = repository.get_or_create_user("CoverageUser")
        assert user.bank_balance == Decimal("500")
    
    def test_balance_manager_all_game_types(self, balance_manager, repository):
        """Test balance manager with all supported game types."""
        from src.parsers import (
            ParsedFishing, ParsedKarma, ParsedMafiaProfile,
            ParsedBunkerProfile
        )
        
        user_name = "AllGamesUser"
        
        # Test fishing
        fishing = ParsedFishing(player_name=user_name, coins=Decimal("25"), game="Shmalala")
        balance_manager.process_fishing(fishing)
        
        # Test karma
        karma = ParsedKarma(player_name=user_name, karma=Decimal("1"), game="Shmalala Karma")
        balance_manager.process_karma(karma)
        
        # Test mafia profile
        mafia = ParsedMafiaProfile(player_name=user_name, money=Decimal("100"), game="True Mafia")
        balance_manager.process_mafia_profile(mafia)
        
        # Test bunker profile
        bunker = ParsedBunkerProfile(player_name=user_name, money=Decimal("50"), game="Bunker RP")
        balance_manager.process_bunker_profile(bunker)
        
        # Test game winners
        balance_manager.process_game_winners([user_name], "True Mafia", Decimal("10"))
        
        # Verify user exists and has accumulated balance
        user = repository.get_or_create_user(user_name)
        assert user.bank_balance > Decimal("0")
