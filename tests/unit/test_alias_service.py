"""
Unit tests for AliasService.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database import Base, User, UserAlias
from core.services.alias_service import AliasService


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
        first_name="Test",
        balance=100
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def alias_service(session):
    """Create AliasService with test session."""
    return AliasService(session=session)


class TestAliasServiceBasics:
    """Test basic alias operations."""

    def test_add_alias(self, alias_service, test_user):
        """Test adding a new alias."""
        alias = alias_service.add_alias(
            user_id=test_user.id,
            alias_value="TestNick",
            alias_type="nickname",
            game_source="gdcards",
            confidence_score=1.0
        )

        assert alias.user_id == test_user.id
        assert alias.alias_value == "TestNick"
        assert alias.alias_type == "nickname"
        assert alias.game_source == "gdcards"
        assert alias.confidence_score == 1.0

    def test_add_duplicate_alias_updates_confidence(self, alias_service, test_user):
        """Test that adding duplicate alias updates confidence score."""
        # Add alias with low confidence
        alias_service.add_alias(
            user_id=test_user.id,
            alias_value="TestNick",
            confidence_score=0.5
        )

        # Add same alias with higher confidence
        alias = alias_service.add_alias(
            user_id=test_user.id,
            alias_value="TestNick",
            confidence_score=0.9
        )

        assert alias.confidence_score == 0.9

    def test_add_alias_invalid_user(self, alias_service):
        """Test adding alias for non-existent user raises error."""
        with pytest.raises(ValueError, match="User with id 999 not found"):
            alias_service.add_alias(
                user_id=999,
                alias_value="TestNick"
            )

    def test_remove_alias(self, alias_service, test_user):
        """Test removing an alias."""
        # Add alias
        alias_service.add_alias(
            user_id=test_user.id,
            alias_value="TestNick"
        )

        # Remove it
        result = alias_service.remove_alias(
            user_id=test_user.id,
            alias_value="TestNick"
        )

        assert result is True

        # Verify it's gone
        aliases = alias_service.get_user_aliases(test_user.id)
        assert len(aliases) == 0

    def test_remove_nonexistent_alias(self, alias_service, test_user):
        """Test removing non-existent alias returns False."""
        result = alias_service.remove_alias(
            user_id=test_user.id,
            alias_value="NonExistent"
        )

        assert result is False

    def test_get_user_aliases(self, alias_service, test_user):
        """Test getting all aliases for a user."""
        # Add multiple aliases
        alias_service.add_alias(test_user.id, "Nick1", confidence_score=1.0)
        alias_service.add_alias(test_user.id, "Nick2", confidence_score=0.8)
        alias_service.add_alias(test_user.id, "Nick3", confidence_score=0.9)

        aliases = alias_service.get_user_aliases(test_user.id)

        assert len(aliases) == 3
        # Should be ordered by confidence score descending
        assert aliases[0].alias_value == "Nick1"
        assert aliases[1].alias_value == "Nick3"
        assert aliases[2].alias_value == "Nick2"

    def test_get_user_aliases_filtered_by_game(self, alias_service, test_user):
        """Test filtering aliases by game source."""
        alias_service.add_alias(test_user.id, "Nick1", game_source="gdcards")
        alias_service.add_alias(test_user.id, "Nick2", game_source="shmalala")
        alias_service.add_alias(test_user.id, "Nick3", game_source="gdcards")

        gdcards_aliases = alias_service.get_user_aliases(
            test_user.id,
            game_source="gdcards"
        )

        assert len(gdcards_aliases) == 2
        assert all(a.game_source == "gdcards" for a in gdcards_aliases)


class TestAliasServiceSearch:
    """Test user search functionality."""

    def test_find_user_by_alias(self, alias_service, test_user):
        """Test finding user by alias."""
        alias_service.add_alias(
            test_user.id,
            "GameNick",
            game_source="gdcards"
        )

        found_user = alias_service.find_user_by_alias("GameNick")

        assert found_user is not None
        assert found_user.id == test_user.id

    def test_find_user_by_alias_with_game_filter(self, alias_service, test_user, session):
        """Test finding user by alias with game source filter."""
        # Create another user
        user2 = User(telegram_id=789, username="user2")
        session.add(user2)
        session.commit()

        # Add same alias for different games
        alias_service.add_alias(test_user.id, "Nick", game_source="gdcards")
        alias_service.add_alias(user2.id, "Nick", game_source="shmalala")

        # Find with game filter
        found = alias_service.find_user_by_alias("Nick", game_source="gdcards")
        assert found.id == test_user.id

        found = alias_service.find_user_by_alias("Nick", game_source="shmalala")
        assert found.id == user2.id

    def test_find_user_by_alias_respects_confidence(self, alias_service, test_user):
        """Test that low confidence aliases are not returned."""
        alias_service.add_alias(
            test_user.id,
            "LowConfidence",
            confidence_score=0.3
        )

        # Should not find with default min_confidence=0.5
        found = alias_service.find_user_by_alias("LowConfidence")
        assert found is None

        # Should find with lower threshold
        found = alias_service.find_user_by_alias("LowConfidence", min_confidence=0.2)
        assert found is not None

    def test_find_user_by_name_or_alias_via_alias(self, alias_service, test_user):
        """Test finding user via alias."""
        alias_service.add_alias(test_user.id, "GameNick")

        found = alias_service.find_user_by_name_or_alias("GameNick")
        assert found.id == test_user.id

    def test_find_user_by_name_or_alias_via_username(self, alias_service, test_user):
        """Test fallback to username."""
        found = alias_service.find_user_by_name_or_alias("testuser")
        assert found.id == test_user.id

        # Case insensitive
        found = alias_service.find_user_by_name_or_alias("TESTUSER")
        assert found.id == test_user.id

    def test_find_user_by_name_or_alias_via_first_name(self, alias_service, test_user):
        """Test fallback to first_name."""
        found = alias_service.find_user_by_name_or_alias("Test")
        assert found.id == test_user.id

        # Case insensitive
        found = alias_service.find_user_by_name_or_alias("test")
        assert found.id == test_user.id

    def test_find_user_by_name_or_alias_not_found(self, alias_service):
        """Test that None is returned when user not found."""
        found = alias_service.find_user_by_name_or_alias("NonExistent")
        assert found is None


class TestAliasServiceStats:
    """Test alias statistics."""

    def test_get_alias_stats(self, alias_service, test_user):
        """Test getting alias statistics."""
        alias_service.add_alias(test_user.id, "Nick1", game_source="gdcards", alias_type="nickname")
        alias_service.add_alias(test_user.id, "Nick2", game_source="gdcards", alias_type="game_name")
        alias_service.add_alias(test_user.id, "Nick3", game_source="shmalala", alias_type="nickname")

        stats = alias_service.get_alias_stats(test_user.id)

        assert stats["total"] == 3
        assert stats["by_game"]["gdcards"] == 2
        assert stats["by_game"]["shmalala"] == 1
        assert stats["by_type"]["nickname"] == 2
        assert stats["by_type"]["game_name"] == 1

    def test_get_alias_stats_empty(self, alias_service, test_user):
        """Test stats for user with no aliases."""
        stats = alias_service.get_alias_stats(test_user.id)

        assert stats["total"] == 0
        assert stats["by_game"] == {}
        assert stats["by_type"] == {}


class TestAliasServiceParserIntegration:
    """Test parser integration methods."""

    def test_sync_alias_from_parser(self, alias_service, test_user):
        """Test syncing alias from parser."""
        alias = alias_service.sync_alias_from_parser(
            telegram_id=test_user.telegram_id,
            game_name="ParserNick",
            game_source="gdcards",
            confidence_score=0.9
        )

        assert alias is not None
        assert alias.alias_value == "ParserNick"
        assert alias.game_source == "gdcards"
        assert alias.alias_type == "game_name"
        assert alias.confidence_score == 0.9

    def test_sync_alias_from_parser_user_not_found(self, alias_service):
        """Test sync with non-existent user returns None."""
        alias = alias_service.sync_alias_from_parser(
            telegram_id=999999,
            game_name="Nick",
            game_source="gdcards"
        )

        assert alias is None

    def test_sync_alias_from_parser_updates_existing(self, alias_service, test_user):
        """Test that sync updates existing alias."""
        # First sync
        alias_service.sync_alias_from_parser(
            telegram_id=test_user.telegram_id,
            game_name="Nick",
            game_source="gdcards",
            confidence_score=0.7
        )

        # Second sync with higher confidence
        alias = alias_service.sync_alias_from_parser(
            telegram_id=test_user.telegram_id,
            game_name="Nick",
            game_source="gdcards",
            confidence_score=0.95
        )

        assert alias.confidence_score == 0.95

        # Should still be only one alias
        aliases = alias_service.get_user_aliases(test_user.id)
        assert len(aliases) == 1


class TestAliasServiceContextManager:
    """Test context manager functionality."""

    def test_context_manager_with_own_session(self, engine):
        """Test that service can manage its own session."""
        # Create user first
        Session = sessionmaker(bind=engine)
        session = Session()
        user = User(telegram_id=123, username="test")
        session.add(user)
        session.commit()
        user_id = user.id
        session.close()

        # Use service as context manager
        with AliasService() as service:
            # Override session for testing
            Session = sessionmaker(bind=engine)
            service.session = Session()
            service._owns_session = True

            alias = service.add_alias(user_id, "TestNick")
            assert alias is not None

    def test_context_manager_with_provided_session(self, session, test_user):
        """Test that service doesn't close provided session."""
        with AliasService(session=session) as service:
            service.add_alias(test_user.id, "TestNick")

        # Session should still be usable
        user = session.query(User).filter_by(id=test_user.id).first()
        assert user is not None
