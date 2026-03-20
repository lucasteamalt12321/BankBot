"""Unit tests for UserService implementation."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.services.user_service import UserService
from src.repository.user_repository import UserRepository
from database.database import Base, User, UserAlias


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
def user_service(user_repository):
    """Create a UserService instance."""
    return UserService(user_repository)


class TestUserServiceInitialization:
    """Test UserService initialization."""
    
    def test_init_creates_service(self, user_repository):
        """Test that UserService is created successfully."""
        service = UserService(user_repository)
        assert service is not None
        assert service.user_repo == user_repository


class TestUserServiceGetUserMethods:
    """Test user retrieval methods."""
    
    def test_get_user_by_telegram_id(self, user_service, in_memory_db):
        """Test getting a user by Telegram ID."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test"
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        retrieved_user = user_service.get_user_by_telegram_id(123456)
        assert retrieved_user is not None
        assert retrieved_user.telegram_id == 123456
    
    def test_get_user_by_telegram_id_not_found(self, user_service):
        """Test getting a non-existent user by Telegram ID."""
        user = user_service.get_user_by_telegram_id(999999)
        assert user is None
    
    def test_get_user_by_username(self, user_service, in_memory_db):
        """Test getting a user by username."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test"
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        retrieved_user = user_service.get_user_by_username("testuser")
        assert retrieved_user is not None
        assert retrieved_user.username == "testuser"
    
    def test_get_user_by_username_not_found(self, user_service):
        """Test getting a non-existent user by username."""
        user = user_service.get_user_by_username("nonexistent")
        assert user is None
    
    def test_get_or_create_user_new(self, user_service):
        """Test creating a new user with get_or_create."""
        user = user_service.get_or_create_user(telegram_id=123456, username="newuser")
        assert user is not None
        assert user.telegram_id == 123456
        assert user.username == "newuser"
    
    def test_get_or_create_user_existing(self, user_service, in_memory_db):
        """Test retrieving an existing user with get_or_create."""
        user1 = user_service.get_or_create_user(telegram_id=123456, username="existing")
        user2 = user_service.get_or_create_user(telegram_id=123456, username="existing")
        
        assert user1.id == user2.id
        assert user1.telegram_id == user2.telegram_id


class TestUserServiceAliasMethods:
    """Test alias management methods."""
    
    def test_add_alias(self, user_service, in_memory_db):
        """Test adding an alias to a user."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test"
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        alias = user_service.add_alias(
            user=user,
            alias_type="game_nickname",
            alias_value="GameUser",
            game_source="gdcards"
        )
        
        assert alias is not None
        assert alias.alias_type == "game_nickname"
        assert alias.alias_value == "GameUser"
        assert alias.game_source == "gdcards"
        assert alias.user_id == user.id
    
    def test_find_user_by_alias(self, user_service, in_memory_db):
        """Test finding a user by alias."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test"
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        alias = UserAlias(
            user_id=user.id,
            alias_type="game_nickname",
            alias_value="GameUser",
            game_source="gdcards"
        )
        in_memory_db.add(alias)
        in_memory_db.commit()
        
        found_user = user_service.find_user_by_alias("GameUser")
        assert found_user is not None
        assert found_user.id == user.id
    
    def test_find_user_by_alias_not_found(self, user_service):
        """Test finding a user by non-existent alias."""
        user = user_service.find_user_by_alias("nonexistent")
        assert user is None
    
    def test_get_user_aliases(self, user_service, in_memory_db):
        """Test getting all aliases for a user."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test"
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        alias1 = UserAlias(
            user_id=user.id,
            alias_type="game_nickname",
            alias_value="GameUser1",
            game_source="gdcards"
        )
        alias2 = UserAlias(
            user_id=user.id,
            alias_type="game_nickname",
            alias_value="GameUser2",
            game_source="shmalala"
        )
        in_memory_db.add_all([alias1, alias2])
        in_memory_db.commit()
        
        aliases = user_service.get_user_aliases(user.id)
        assert len(aliases) == 2
        assert aliases[0].alias_value in ["GameUser1", "GameUser2"]
        assert aliases[1].alias_value in ["GameUser1", "GameUser2"]
    
    def test_get_user_aliases_empty(self, user_service, in_memory_db):
        """Test getting aliases for user with no aliases."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test"
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        aliases = user_service.get_user_aliases(user.id)
        assert len(aliases) == 0


class TestUserServiceSearchMethods:
    """Test search methods."""
    
    def test_search_users_by_name(self, user_service, in_memory_db):
        """Test searching users by name."""
        users = [
            User(telegram_id=111, username="user1", first_name="John"),
            User(telegram_id=222, username="user2", first_name="Johnny"),
            User(telegram_id=333, username="user3", first_name="Jane"),
        ]
        in_memory_db.add_all(users)
        in_memory_db.commit()
        
        found_users = user_service.search_users_by_name("John")
        assert len(found_users) == 2
        assert all(u.first_name in ["John", "Johnny"] for u in found_users)
    
    def test_search_users_by_name_no_results(self, user_service, in_memory_db):
        """Test searching with no matching results."""
        users = [
            User(telegram_id=111, username="user1", first_name="John"),
            User(telegram_id=222, username="user2", first_name="Jane"),
        ]
        in_memory_db.add_all(users)
        in_memory_db.commit()
        
        found_users = user_service.search_users_by_name("NonExistent")
        assert len(found_users) == 0


class TestUserServiceBalanceMethods:
    """Test balance management methods."""
    
    def test_update_user_balance(self, user_service, in_memory_db):
        """Test updating user balance."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=100
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        updated_user = user_service.update_user_balance(user.id, 200)
        assert updated_user is not None
        assert updated_user.balance == 200
    
    def test_update_user_balance_not_found(self, user_service):
        """Test updating balance for non-existent user."""
        updated_user = user_service.update_user_balance(999999, 200)
        assert updated_user is None
    
    def test_increase_user_balance(self, user_service, in_memory_db):
        """Test increasing user balance."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=100
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        updated_user = user_service.increase_user_balance(user.id, 50)
        assert updated_user is not None
        assert updated_user.balance == 150
    
    def test_decrease_user_balance(self, user_service, in_memory_db):
        """Test decreasing user balance."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=100
        )
        in_memory_db.add(user)
        in_memory_db.commit()
        
        updated_user = user_service.decrease_user_balance(user.id, 30)
        assert updated_user is not None
        assert updated_user.balance == 70
