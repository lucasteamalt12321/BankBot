<<<<<<< HEAD
"""Unit tests for UserRepository specialized methods."""

import pytest
from datetime import datetime, timedelta
from database.database import SessionLocal, User, Base, create_engine
from src.repository.user_repository import UserRepository
from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def engine():
    """Create in-memory SQLite database for testing."""
    engine = sa_create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a test database session."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
=======
"""Unit tests for UserRepository implementation."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.repository.user_repository import UserRepository
from database.database import Base, User


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    yield session
    
>>>>>>> f1369b8 (chore: minor update, possibly buggy)
    session.close()


@pytest.fixture
<<<<<<< HEAD
def user_repository(session):
    """Create a UserRepository instance."""
    return UserRepository(User, session)


@pytest.fixture
def sample_users(session):
    """Create sample users for testing."""
    users = [
        User(
            telegram_id=100001,
            username="admin_user",
            first_name="Admin",
            balance=5000,
            is_admin=True,
            is_vip=False,
            last_activity=datetime.utcnow()
        ),
        User(
            telegram_id=100002,
            username="vip_user",
            first_name="VIP",
            balance=3000,
            is_admin=False,
            is_vip=True,
            vip_until=datetime.utcnow() + timedelta(days=30),
            last_activity=datetime.utcnow() - timedelta(hours=2)
        ),
        User(
            telegram_id=100003,
            username="expired_vip",
            first_name="Expired",
            balance=1000,
            is_admin=False,
            is_vip=True,
            vip_until=datetime.utcnow() - timedelta(days=1),
            last_activity=datetime.utcnow() - timedelta(days=5)
        ),
        User(
            telegram_id=100004,
            username="rich_user",
            first_name="Rich",
            balance=10000,
            total_earned=15000,
            is_admin=False,
            is_vip=False,
            last_activity=datetime.utcnow() - timedelta(hours=1)
        ),
        User(
            telegram_id=100005,
            username="poor_user",
            first_name="Poor",
            balance=50,
            total_earned=100,
            is_admin=False,
            is_vip=False,
            sticker_unlimited=True,
            sticker_unlimited_until=datetime.utcnow() - timedelta(hours=1),
            last_activity=datetime.utcnow() - timedelta(days=10)
        ),
    ]
    
    for user in users:
        session.add(user)
    session.commit()
    
    return users


class TestUserRepositoryBasicMethods:
    """Test basic UserRepository methods."""
    
    def test_get_by_telegram_id(self, user_repository, sample_users):
        """Test getting user by Telegram ID."""
        user = user_repository.get_by_telegram_id(100001)
        assert user is not None
        assert user.username == "admin_user"
        assert user.telegram_id == 100001
    
    def test_get_by_telegram_id_not_found(self, user_repository, sample_users):
        """Test getting non-existent user by Telegram ID."""
        user = user_repository.get_by_telegram_id(999999)
        assert user is None
    
    def test_get_by_username(self, user_repository, sample_users):
        """Test getting user by username."""
        user = user_repository.get_by_username("vip_user")
        assert user is not None
        assert user.telegram_id == 100002
        assert user.is_vip is True
    
    def test_get_by_username_not_found(self, user_repository, sample_users):
        """Test getting non-existent user by username."""
        user = user_repository.get_by_username("nonexistent")
        assert user is None
    
    def test_get_or_create_existing(self, user_repository, sample_users):
        """Test get_or_create with existing user."""
        initial_count = user_repository.count_total_users()
        user = user_repository.get_or_create(
            telegram_id=100001,
            username="should_not_create"
        )
        assert user.username == "admin_user"  # Original username
        assert user_repository.count_total_users() == initial_count
    
    def test_get_or_create_new(self, user_repository, sample_users):
        """Test get_or_create with new user."""
        initial_count = user_repository.count_total_users()
        user = user_repository.get_or_create(
            telegram_id=200001,
            username="new_user",
            first_name="New"
        )
        assert user.username == "new_user"
        assert user.telegram_id == 200001
        assert user_repository.count_total_users() == initial_count + 1


class TestUserRepositoryAdminMethods:
    """Test admin-related methods."""
    
    def test_get_all_admins(self, user_repository, sample_users):
        """Test getting all admin users."""
        admins = user_repository.get_all_admins()
        assert len(admins) == 1
        assert admins[0].username == "admin_user"
        assert admins[0].is_admin is True
    
    def test_count_admins(self, user_repository, sample_users):
        """Test counting admin users."""
        count = user_repository.count_admins()
        assert count == 1


class TestUserRepositoryVIPMethods:
    """Test VIP-related methods."""
    
    def test_get_all_vips(self, user_repository, sample_users):
        """Test getting all VIP users."""
        vips = user_repository.get_all_vips()
        assert len(vips) == 2  # vip_user and expired_vip
        usernames = [vip.username for vip in vips]
        assert "vip_user" in usernames
        assert "expired_vip" in usernames
    
    def test_count_vips(self, user_repository, sample_users):
        """Test counting VIP users."""
        count = user_repository.count_vips()
        assert count == 2
    
    def test_get_users_with_expired_vip(self, user_repository, sample_users):
        """Test getting users with expired VIP."""
        now = datetime.utcnow()
        expired_vips = user_repository.get_users_with_expired_vip(now)
        assert len(expired_vips) == 1
        assert expired_vips[0].username == "expired_vip"
        assert expired_vips[0].vip_until < now


class TestUserRepositoryBalanceMethods:
    """Test balance-related methods."""
    
    def test_get_users_with_balance_above(self, user_repository, sample_users):
        """Test getting users with balance above threshold."""
        users = user_repository.get_users_with_balance_above(2000)
        assert len(users) == 3  # admin_user, vip_user, rich_user
        balances = [user.balance for user in users]
        assert all(balance >= 2000 for balance in balances)
    
    def test_get_users_with_balance_above_high_threshold(self, user_repository, sample_users):
        """Test getting users with high balance threshold."""
        users = user_repository.get_users_with_balance_above(5000)
        assert len(users) == 2  # admin_user, rich_user
    
    def test_get_top_users_by_balance(self, user_repository, sample_users):
        """Test getting top users by balance."""
        top_users = user_repository.get_top_users_by_balance(3)
        assert len(top_users) == 3
        assert top_users[0].username == "rich_user"
        assert top_users[0].balance == 10000
        assert top_users[1].username == "admin_user"
        assert top_users[1].balance == 5000
        assert top_users[2].username == "vip_user"
        assert top_users[2].balance == 3000
    
    def test_get_top_users_by_earnings(self, user_repository, sample_users):
        """Test getting top users by total earnings."""
        top_earners = user_repository.get_top_users_by_earnings(3)
        assert len(top_earners) == 3
        assert top_earners[0].username == "rich_user"
        assert top_earners[0].total_earned == 15000
    
    def test_bulk_update_balance(self, user_repository, sample_users):
        """Test bulk balance update."""
        # Get user IDs for admin_user and vip_user
        admin = user_repository.get_by_username("admin_user")
        vip = user_repository.get_by_username("vip_user")
        
        initial_admin_balance = admin.balance
        initial_vip_balance = vip.balance
        
        # Update balances
        updated = user_repository.bulk_update_balance([admin.id, vip.id], 500)
        assert updated == 2
        
        # Verify updates
        user_repository.session.refresh(admin)
        user_repository.session.refresh(vip)
        assert admin.balance == initial_admin_balance + 500
        assert vip.balance == initial_vip_balance + 500
    
    def test_bulk_update_balance_negative(self, user_repository, sample_users):
        """Test bulk balance update with negative amount."""
        admin = user_repository.get_by_username("admin_user")
        initial_balance = admin.balance
        
        updated = user_repository.bulk_update_balance([admin.id], -1000)
        assert updated == 1
        
        user_repository.session.refresh(admin)
        assert admin.balance == initial_balance - 1000


class TestUserRepositoryActivityMethods:
    """Test activity-related methods."""
    
    def test_get_active_users_since(self, user_repository, sample_users):
        """Test getting active users since datetime."""
        yesterday = datetime.utcnow() - timedelta(days=1)
        active_users = user_repository.get_active_users_since(yesterday)
        
        # Should get admin_user, vip_user, and rich_user
        assert len(active_users) >= 3
        usernames = [user.username for user in active_users]
        assert "admin_user" in usernames
        assert "vip_user" in usernames
        assert "rich_user" in usernames
        assert "poor_user" not in usernames  # Last active 10 days ago
    
    def test_get_active_users_since_recent(self, user_repository, sample_users):
        """Test getting very recent active users."""
        one_hour_ago = datetime.utcnow() - timedelta(hours=1, minutes=30)
        active_users = user_repository.get_active_users_since(one_hour_ago)
        
        # Should get admin_user and rich_user
        assert len(active_users) >= 2
        usernames = [user.username for user in active_users]
        assert "admin_user" in usernames
        assert "rich_user" in usernames


class TestUserRepositoryStickerMethods:
    """Test sticker-related methods."""
    
    def test_get_users_with_expired_stickers(self, user_repository, sample_users):
        """Test getting users with expired sticker access."""
        now = datetime.utcnow()
        expired_stickers = user_repository.get_users_with_expired_stickers(now)
        
        assert len(expired_stickers) == 1
        assert expired_stickers[0].username == "poor_user"
        assert expired_stickers[0].sticker_unlimited is True
        assert expired_stickers[0].sticker_unlimited_until < now


class TestUserRepositoryCountMethods:
    """Test counting methods."""
    
    def test_count_total_users(self, user_repository, sample_users):
        """Test counting total users."""
        count = user_repository.count_total_users()
        assert count == 5
    
    def test_count_total_users_empty(self, user_repository, session):
        """Test counting users in empty database."""
        count = user_repository.count_total_users()
        assert count == 0


class TestUserRepositoryEdgeCases:
    """Test edge cases and error handling."""
    
    def test_get_top_users_limit_exceeds_total(self, user_repository, sample_users):
        """Test getting top users when limit exceeds total users."""
        top_users = user_repository.get_top_users_by_balance(100)
        assert len(top_users) == 5  # Only 5 users exist
    
    def test_bulk_update_empty_list(self, user_repository, sample_users):
        """Test bulk update with empty user list."""
        updated = user_repository.bulk_update_balance([], 100)
        assert updated == 0
    
    def test_bulk_update_nonexistent_ids(self, user_repository, sample_users):
        """Test bulk update with non-existent user IDs."""
        updated = user_repository.bulk_update_balance([999999, 888888], 100)
        assert updated == 0
    
    def test_get_users_with_balance_above_zero(self, user_repository, sample_users):
        """Test getting users with balance above 0."""
        users = user_repository.get_users_with_balance_above(0)
        assert len(users) == 5  # All users have positive balance
=======
def user_repository(in_memory_db):
    """Create a UserRepository instance."""
    return UserRepository(in_memory_db)


class TestUserRepositoryInitialization:
    """Test UserRepository initialization."""
    
    def test_init_creates_repository(self, in_memory_db):
        """Test that UserRepository is created successfully."""
        repo = UserRepository(in_memory_db)
        assert repo is not None
        assert repo.model == User
        assert repo.session == in_memory_db


class TestUserRepositoryBaseMethods:
    """Test inherited CRUD methods from BaseRepository."""
    
    def test_create_user(self, user_repository):
        """Test creating a new user."""
        user = user_repository.create(
            telegram_id=123456,
            username="testuser",
            first_name="Test"
        )
        
        assert user.id is not None
        assert user.telegram_id == 123456
        assert user.username == "testuser"
        assert user.first_name == "Test"
        assert user.balance == 0  # default value
    
    def test_get_user_by_id(self, user_repository):
        """Test getting a user by ID."""
        user = user_repository.create(
            telegram_id=123456,
            username="testuser",
            first_name="Test"
        )
        
        retrieved_user = user_repository.get(user.id)
        assert retrieved_user is not None
        assert retrieved_user.id == user.id
        assert retrieved_user.telegram_id == 123456
    
    def test_get_user_not_found(self, user_repository):
        """Test getting a non-existent user."""
        user = user_repository.get(999999)
        assert user is None
    
    def test_get_all_users(self, user_repository):
        """Test getting all users."""
        user_repository.create(telegram_id=111, username="user1")
        user_repository.create(telegram_id=222, username="user2")
        user_repository.create(telegram_id=333, username="user3")
        
        all_users = user_repository.get_all()
        assert len(all_users) == 3
    
    def test_update_user(self, user_repository):
        """Test updating a user."""
        user = user_repository.create(
            telegram_id=123456,
            username="testuser",
            first_name="Test"
        )
        
        updated_user = user_repository.update(user.id, balance=100, first_name="Updated")
        
        assert updated_user is not None
        assert updated_user.balance == 100
        assert updated_user.first_name == "Updated"
    
    def test_update_user_not_found(self, user_repository):
        """Test updating a non-existent user."""
        updated_user = user_repository.update(999999, balance=100)
        assert updated_user is None
    
    def test_delete_user(self, user_repository):
        """Test deleting a user."""
        user = user_repository.create(
            telegram_id=123456,
            username="testuser",
            first_name="Test"
        )
        
        result = user_repository.delete(user.id)
        assert result is True
        
        deleted_user = user_repository.get(user.id)
        assert deleted_user is None
    
    def test_delete_user_not_found(self, user_repository):
        """Test deleting a non-existent user."""
        result = user_repository.delete(999999)
        assert result is False


class TestUserRepositoryCustomMethods:
    """Test custom methods specific to UserRepository."""
    
    def test_get_by_telegram_id(self, user_repository):
        """Test getting a user by Telegram ID."""
        user = user_repository.create(
            telegram_id=123456,
            username="testuser",
            first_name="Test"
        )
        
        retrieved_user = user_repository.get_by_telegram_id(123456)
        assert retrieved_user is not None
        assert retrieved_user.id == user.id
        assert retrieved_user.telegram_id == 123456
    
    def test_get_by_telegram_id_not_found(self, user_repository):
        """Test getting a non-existent user by Telegram ID."""
        user = user_repository.get_by_telegram_id(999999)
        assert user is None
    
    def test_get_by_username(self, user_repository):
        """Test getting a user by username."""
        user = user_repository.create(
            telegram_id=123456,
            username="testuser",
            first_name="Test"
        )
        
        retrieved_user = user_repository.get_by_username("testuser")
        assert retrieved_user is not None
        assert retrieved_user.id == user.id
        assert retrieved_user.username == "testuser"
    
    def test_get_by_username_not_found(self, user_repository):
        """Test getting a non-existent user by username."""
        user = user_repository.get_by_username("nonexistent")
        assert user is None
    
    def test_get_or_create_new_user(self, user_repository):
        """Test creating a new user with get_or_create."""
        user = user_repository.get_or_create(telegram_id=123456, username="newuser")
        
        assert user.id is not None
        assert user.telegram_id == 123456
        assert user.username == "newuser"
    
    def test_get_or_create_existing_user(self, user_repository):
        """Test retrieving an existing user with get_or_create."""
        user1 = user_repository.create(
            telegram_id=123456,
            username="existinguser",
            first_name="Existing"
        )
        
        user2 = user_repository.get_or_create(telegram_id=123456)
        
        assert user1.id == user2.id
        assert user1.telegram_id == user2.telegram_id
        assert user1.username == user2.username
    
    def test_get_all_by_balance(self, user_repository):
        """Test getting users by minimum balance."""
        user_repository.create(telegram_id=111, username="user1", balance=50)
        user_repository.create(telegram_id=222, username="user2", balance=100)
        user_repository.create(telegram_id=333, username="user3", balance=150)
        user_repository.create(telegram_id=444, username="user4", balance=200)
        
        users_min_100 = user_repository.get_all_by_balance(100)
        assert len(users_min_100) == 3
        
        users_min_150 = user_repository.get_all_by_balance(150)
        assert len(users_min_150) == 2
        
        users_min_250 = user_repository.get_all_by_balance(250)
        assert len(users_min_250) == 0
    
    def test_search_by_name(self, user_repository):
        """Test searching users by name."""
        user_repository.create(telegram_id=111, username="testuser1", first_name="John")
        user_repository.create(telegram_id=222, username="testuser2", first_name="Jane")
        user_repository.create(telegram_id=333, username="testuser3", first_name="Alice")
        user_repository.create(telegram_id=444, username="testuser4", first_name="Bob")
        
        users_j = user_repository.search_by_name("J")
        assert len(users_j) == 2
        
        users_oh = user_repository.search_by_name("oh")
        assert len(users_oh) == 1
        assert users_oh[0].first_name == "John"
    
    def test_search_by_username(self, user_repository):
        """Test searching users by username."""
        user_repository.create(telegram_id=111, username="user_test1", first_name="User1")
        user_repository.create(telegram_id=222, username="user_test2", first_name="User2")
        user_repository.create(telegram_id=333, username="other_user", first_name="Other")
        
        users_test = user_repository.search_by_name("test")
        assert len(users_test) == 2
    
    def test_search_no_results(self, user_repository):
        """Test searching with no matching results."""
        user_repository.create(telegram_id=111, username="user1", first_name="John")
        
        users = user_repository.search_by_name("xyz")
        assert len(users) == 0


class TestUserRepositoryEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_user_with_none_values(self, user_repository):
        """Test creating a user with None values for optional fields."""
        user = user_repository.create(telegram_id=123456)
        
        assert user.id is not None
        assert user.telegram_id == 123456
        assert user.username is None
        assert user.first_name is None
    
    def test_user_with_empty_strings(self, user_repository):
        """Test creating a user with empty strings."""
        user = user_repository.create(
            telegram_id=123456,
            username="",
            first_name=""
        )
        
        assert user.username == ""
        assert user.first_name == ""
    
    def test_user_with_special_characters(self, user_repository):
        """Test creating a user with special characters in names."""
        user = user_repository.create(
            telegram_id=123456,
            username="user@123_test",
            first_name="Иван",
            last_name="О'Коннор"
        )
        
        assert user.username == "user@123_test"
        assert user.first_name == "Иван"
        assert user.last_name == "О'Коннор"
    
    def test_user_with_zero_balance(self, user_repository):
        """Test creating a user with explicit zero balance."""
        user = user_repository.create(
            telegram_id=123456,
            username="testuser",
            balance=0
        )
        
        assert user.balance == 0
    
    def test_user_with_negative_balance(self, user_repository):
        """Test creating a user with negative balance."""
        user = user_repository.create(
            telegram_id=123456,
            username="testuser",
            balance=-50
        )
        
        assert user.balance == -50
    
    def test_user_with_large_balance(self, user_repository):
        """Test creating a user with large balance."""
        large_balance = 999999999
        user = user_repository.create(
            telegram_id=123456,
            username="testuser",
            balance=large_balance
        )
        
        assert user.balance == large_balance
    
    def test_duplicate_telegram_id(self, in_memory_db):
        """Test that duplicate telegram_id raises an error."""
        repo = UserRepository(in_memory_db)
        
        repo.create(telegram_id=123456, username="user1")
        
        with pytest.raises(Exception):
            repo.create(telegram_id=123456, username="user2")
    
    def test_duplicate_username(self, user_repository):
        """Test that duplicate username is allowed (not unique)."""
        user1 = user_repository.create(telegram_id=111, username="sameuser")
        user2 = user_repository.create(telegram_id=222, username="sameuser")
        
        assert user1.id != user2.id
        assert user1.username == user2.username == "sameuser"


class TestUserRepositoryTransactionIsolation:
    """Test transaction isolation and atomicity."""
    
    def test_multiple_operations_atomic(self, user_repository):
        """Test that multiple operations are atomic."""
        user1 = user_repository.create(telegram_id=111, username="user1", balance=50)
        user2 = user_repository.create(telegram_id=222, username="user2", balance=100)
        
        user_repository.update(user1.id, balance=150)
        user_repository.update(user2.id, balance=200)
        
        refreshed_user1 = user_repository.get(user1.id)
        refreshed_user2 = user_repository.get(user2.id)
        
        assert refreshed_user1.balance == 150
        assert refreshed_user2.balance == 200


class TestUserRepositoryPerformance:
    """Test performance with multiple users."""
    
    def test_create_many_users(self, user_repository):
        """Test creating many users efficiently."""
        num_users = 100
        
        for i in range(num_users):
            user_repository.create(telegram_id=1000 + i, username=f"user{i}")
        
        all_users = user_repository.get_all()
        assert len(all_users) == num_users
    
    def test_search_performance(self, user_repository):
        """Test search performance with many users."""
        # Create users
        for i in range(50):
            user_repository.create(
                telegram_id=1000 + i,
                username=f"user{i}",
                first_name=f"User{i}"
            )
        
        # Search should be fast
        results = user_repository.search_by_name("User")
        assert len(results) == 50
>>>>>>> f1369b8 (chore: minor update, possibly buggy)
