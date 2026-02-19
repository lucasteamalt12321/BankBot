"""Unit tests for BaseRepository."""

import pytest
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
from src.repository.base import BaseRepository

# Create test base and model
Base = declarative_base()


class UserModel(Base):
    """Test model for repository testing."""
    __tablename__ = "test_users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False)
    email = Column(String(100))
    is_active = Column(Boolean, default=True)
    balance = Column(Integer, default=0)


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
def repository(session):
    """Create repository instance for testing."""
    return BaseRepository(UserModel, session)


class TestBaseRepositoryCreate:
    """Tests for create operation."""
    
    def test_create_simple_record(self, repository):
        """Test creating a simple record."""
        user = repository.create(username="john_doe", email="john@example.com")
        
        assert user.id is not None
        assert user.username == "john_doe"
        assert user.email == "john@example.com"
        assert user.is_active is True
        assert user.balance == 0
    
    def test_create_with_defaults(self, repository):
        """Test that default values are applied."""
        user = repository.create(username="jane_doe")
        
        assert user.is_active is True
        assert user.balance == 0
    
    def test_create_override_defaults(self, repository):
        """Test overriding default values."""
        user = repository.create(
            username="admin",
            is_active=False,
            balance=100
        )
        
        assert user.is_active is False
        assert user.balance == 100


class TestBaseRepositoryGet:
    """Tests for get operations."""
    
    def test_get_existing_record(self, repository):
        """Test getting an existing record by ID."""
        created = repository.create(username="test_user")
        retrieved = repository.get(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.username == "test_user"
    
    def test_get_nonexistent_record(self, repository):
        """Test getting a non-existent record returns None."""
        result = repository.get(999)
        assert result is None
    
    def test_get_by_single_field(self, repository):
        """Test getting record by a single field."""
        repository.create(username="user1", email="user1@example.com")
        
        result = repository.get_by(username="user1")
        assert result is not None
        assert result.username == "user1"
    
    def test_get_by_multiple_fields(self, repository):
        """Test getting record by multiple fields."""
        repository.create(username="user1", email="user1@example.com", is_active=True)
        repository.create(username="user2", email="user2@example.com", is_active=False)
        
        result = repository.get_by(username="user2", is_active=False)
        assert result is not None
        assert result.username == "user2"
    
    def test_get_by_nonexistent(self, repository):
        """Test get_by returns None for non-existent record."""
        result = repository.get_by(username="nonexistent")
        assert result is None


class TestBaseRepositoryGetAll:
    """Tests for get_all operation."""
    
    def test_get_all_empty(self, repository):
        """Test get_all on empty table."""
        result = repository.get_all()
        assert result == []
    
    def test_get_all_multiple_records(self, repository):
        """Test get_all returns all records."""
        repository.create(username="user1")
        repository.create(username="user2")
        repository.create(username="user3")
        
        result = repository.get_all()
        assert len(result) == 3
    
    def test_get_all_with_limit(self, repository):
        """Test get_all with limit."""
        for i in range(5):
            repository.create(username=f"user{i}")
        
        result = repository.get_all(limit=3)
        assert len(result) == 3
    
    def test_get_all_with_offset(self, repository):
        """Test get_all with offset."""
        for i in range(5):
            repository.create(username=f"user{i}")
        
        result = repository.get_all(offset=2)
        assert len(result) == 3
    
    def test_get_all_with_limit_and_offset(self, repository):
        """Test get_all with both limit and offset."""
        for i in range(10):
            repository.create(username=f"user{i}")
        
        result = repository.get_all(limit=3, offset=5)
        assert len(result) == 3


class TestBaseRepositoryFilter:
    """Tests for filter operation."""
    
    def test_filter_single_field(self, repository):
        """Test filtering by single field."""
        repository.create(username="user1", is_active=True)
        repository.create(username="user2", is_active=False)
        repository.create(username="user3", is_active=True)
        
        result = repository.filter(is_active=True)
        assert len(result) == 2
    
    def test_filter_multiple_fields(self, repository):
        """Test filtering by multiple fields."""
        repository.create(username="user1", is_active=True, balance=100)
        repository.create(username="user2", is_active=True, balance=0)
        repository.create(username="user3", is_active=False, balance=100)
        
        result = repository.filter(is_active=True, balance=100)
        assert len(result) == 1
        assert result[0].username == "user1"
    
    def test_filter_no_matches(self, repository):
        """Test filter returns empty list when no matches."""
        repository.create(username="user1", is_active=True)
        
        result = repository.filter(is_active=False)
        assert result == []


class TestBaseRepositoryUpdate:
    """Tests for update operation."""
    
    def test_update_single_field(self, repository):
        """Test updating a single field."""
        user = repository.create(username="user1", balance=0)
        
        updated = repository.update(user.id, balance=100)
        assert updated is not None
        assert updated.balance == 100
        assert updated.username == "user1"
    
    def test_update_multiple_fields(self, repository):
        """Test updating multiple fields."""
        user = repository.create(username="user1", balance=0, is_active=True)
        
        updated = repository.update(
            user.id,
            balance=200,
            is_active=False,
            email="new@example.com"
        )
        assert updated.balance == 200
        assert updated.is_active is False
        assert updated.email == "new@example.com"
    
    def test_update_nonexistent_record(self, repository):
        """Test updating non-existent record returns None."""
        result = repository.update(999, balance=100)
        assert result is None
    
    def test_update_persists(self, repository):
        """Test that updates are persisted to database."""
        user = repository.create(username="user1", balance=0)
        repository.update(user.id, balance=100)
        
        retrieved = repository.get(user.id)
        assert retrieved.balance == 100


class TestBaseRepositoryDelete:
    """Tests for delete operation."""
    
    def test_delete_existing_record(self, repository):
        """Test deleting an existing record."""
        user = repository.create(username="user1")
        
        result = repository.delete(user.id)
        assert result is True
        
        # Verify it's deleted
        assert repository.get(user.id) is None
    
    def test_delete_nonexistent_record(self, repository):
        """Test deleting non-existent record returns False."""
        result = repository.delete(999)
        assert result is False
    
    def test_delete_reduces_count(self, repository):
        """Test that delete reduces record count."""
        repository.create(username="user1")
        repository.create(username="user2")
        user3 = repository.create(username="user3")
        
        assert repository.count() == 3
        repository.delete(user3.id)
        assert repository.count() == 2


class TestBaseRepositoryCount:
    """Tests for count operation."""
    
    def test_count_empty(self, repository):
        """Test count on empty table."""
        assert repository.count() == 0
    
    def test_count_all(self, repository):
        """Test counting all records."""
        repository.create(username="user1")
        repository.create(username="user2")
        repository.create(username="user3")
        
        assert repository.count() == 3
    
    def test_count_with_filter(self, repository):
        """Test counting with filter."""
        repository.create(username="user1", is_active=True)
        repository.create(username="user2", is_active=False)
        repository.create(username="user3", is_active=True)
        
        assert repository.count(is_active=True) == 2
        assert repository.count(is_active=False) == 1


class TestBaseRepositoryExists:
    """Tests for exists operation."""
    
    def test_exists_true(self, repository):
        """Test exists returns True when record exists."""
        repository.create(username="user1")
        
        assert repository.exists(username="user1") is True
    
    def test_exists_false(self, repository):
        """Test exists returns False when record doesn't exist."""
        assert repository.exists(username="nonexistent") is False
    
    def test_exists_with_multiple_filters(self, repository):
        """Test exists with multiple filters."""
        repository.create(username="user1", is_active=True)
        
        assert repository.exists(username="user1", is_active=True) is True
        assert repository.exists(username="user1", is_active=False) is False


class TestBaseRepositoryBulkCreate:
    """Tests for bulk_create operation."""
    
    def test_bulk_create_multiple_records(self, repository):
        """Test creating multiple records at once."""
        items = [
            {"username": "user1", "balance": 10},
            {"username": "user2", "balance": 20},
            {"username": "user3", "balance": 30},
        ]
        
        result = repository.bulk_create(items)
        assert len(result) == 3
        assert repository.count() == 3
    
    def test_bulk_create_empty_list(self, repository):
        """Test bulk_create with empty list."""
        result = repository.bulk_create([])
        assert result == []
        assert repository.count() == 0
    
    def test_bulk_create_with_defaults(self, repository):
        """Test bulk_create applies default values."""
        items = [
            {"username": "user1"},
            {"username": "user2"},
        ]
        
        repository.bulk_create(items)
        users = repository.get_all()
        
        assert all(user.is_active is True for user in users)
        assert all(user.balance == 0 for user in users)
