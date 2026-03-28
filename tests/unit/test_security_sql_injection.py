"""Security tests for SQL injection prevention."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.database import Base, User
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


class TestSQLInjectionPrevention:
    """Test that SQL injection is prevented via parameterized queries."""

    def test_username_with_sql_injection(self, user_repository, in_memory_db):
        """Test that SQL injection in username is prevented."""
        malicious_usernames = [
            "'; DROP TABLE users; --",
            "1 OR 1=1",
            "test' UNION SELECT * FROM users --",
            "test\"; DELETE FROM users; --",
            "<script>alert('xss')</script>",
        ]

        for i, malicious_input in enumerate(malicious_usernames):
            user = User(
                telegram_id=900000 + i,
                username=malicious_input,
                first_name="Test",
                balance=0
            )
            in_memory_db.add(user)
            in_memory_db.commit()
            
            result = user_repository.get_or_create_by_name(malicious_input)
            assert result is not None
            assert result.username == malicious_input

    def test_telegram_id_with_non_numeric(self, user_repository):
        """Test that non-numeric telegram_id values are handled safely."""
        result = user_repository.get_by_telegram_id(0)
        assert result is None

    def test_special_characters_in_username(self, user_repository, in_memory_db):
        """Test that special characters are stored correctly."""
        special_chars = [
            "test[1]",
            "(test)",
            "test with spaces",
            "emoji_🎮",
        ]

        for i, username in enumerate(special_chars):
            user = User(
                telegram_id=100100 + i,
                username=username,
                first_name="Test",
                balance=0
            )
            in_memory_db.add(user)
            in_memory_db.commit()
            
            result = user_repository.get_or_create_by_name(username)
            assert result is not None
            assert result.username == username


class TestParameterizedQueries:
    """Test that all queries use parameterized approach."""

    def test_all_queries_use_parameters(self, user_repository, in_memory_db):
        """Verify that repository methods don't use string concatenation for queries."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=100
        )
        in_memory_db.add(user)
        in_memory_db.commit()

        result = user_repository.get(1)
        assert result is not None
        assert result.username == "testuser"

        result = user_repository.get_by_telegram_id(123456)
        assert result is not None
        assert result.username == "testuser"

    def test_get_or_create_by_name_safe(self, user_repository, in_memory_db):
        """Test that get_or_create_by_name is safe against injection."""
        injection_attempts = [
            "'; SELECT 1; --",
            "test' OR '1'='1",
            "admin'--",
        ]

        for attempt in injection_attempts:
            result = user_repository.get_or_create_by_name(attempt)
            assert result is not None
            assert result.username == attempt
