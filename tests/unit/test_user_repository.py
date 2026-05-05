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

    session.close()


@pytest.fixture
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

        users_min_100 = user_repository.get_users_with_balance_above(100)
        assert len(users_min_100) == 3

        users_min_150 = user_repository.get_users_with_balance_above(150)
        assert len(users_min_150) == 2

        users_min_250 = user_repository.get_users_with_balance_above(250)
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

    def test_duplicate_telegram_id(self, in_memory_db):
        """Test that duplicate telegram_id raises an error."""
        repo = UserRepository(in_memory_db)

        repo.create(telegram_id=123456, username="user1")

        with pytest.raises(Exception):
            repo.create(telegram_id=123456, username="user2")
