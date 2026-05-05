"""Integration tests for ParsingConfigManager with real database."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database import Base
from src.models.parsing_rule import ParsingRule
from src.repository.base import BaseRepository
from core.managers.parsing_config_manager import ParsingConfigManager


@pytest.fixture
def engine():
    """Create an in-memory SQLite database engine."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a database session."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def repository(session):
    """Create a BaseRepository for ParsingRule."""
    return BaseRepository(ParsingRule, session)


@pytest.fixture
def manager(repository):
    """Create a ParsingConfigManager instance."""
    return ParsingConfigManager(repository)


class TestParsingConfigManagerIntegration:
    """Integration tests for ParsingConfigManager."""

    def test_create_and_get_rule(self, manager):
        """Test creating and retrieving a parsing rule."""
        # Create a rule
        rule = manager.create_rule(
            game_name="gdcards",
            parser_class="GDCardsParser",
            coefficient=1.5,
            enabled=True,
            config={"test": "value"}
        )

        assert rule.id is not None
        assert rule.game_name == "gdcards"
        assert rule.parser_class == "GDCardsParser"
        assert rule.coefficient == 1.5
        assert rule.enabled is True
        assert rule.config == {"test": "value"}

        # Retrieve the rule
        retrieved = manager.get_rule("gdcards")
        assert retrieved is not None
        assert retrieved.id == rule.id
        assert retrieved.game_name == "gdcards"

    def test_update_coefficient(self, manager):
        """Test updating a rule's coefficient."""
        # Create a rule
        manager.create_rule(
            game_name="shmalala",
            parser_class="ShmalalaParser",
            coefficient=1.0
        )

        # Update coefficient
        result = manager.update_coefficient("shmalala", 2.5)
        assert result is True

        # Verify update
        rule = manager.get_rule("shmalala")
        assert rule.coefficient == 2.5

    def test_get_all_active_rules(self, manager):
        """Test retrieving all active rules."""
        # Create multiple rules
        manager.create_rule("gdcards", "GDCardsParser", enabled=True)
        manager.create_rule("shmalala", "ShmalalaParser", enabled=True)
        manager.create_rule("bunkerrp", "BunkerParser", enabled=False)

        # Get active rules
        active_rules = manager.get_all_active_rules()

        assert len(active_rules) == 2
        assert "gdcards" in active_rules
        assert "shmalala" in active_rules
        assert "bunkerrp" not in active_rules

    def test_get_all_rules(self, manager):
        """Test retrieving all rules including inactive."""
        # Create multiple rules
        manager.create_rule("gdcards", "GDCardsParser", enabled=True)
        manager.create_rule("shmalala", "ShmalalaParser", enabled=False)

        # Get all rules
        all_rules = manager.get_all_rules()

        assert len(all_rules) == 2
        assert "gdcards" in all_rules
        assert "shmalala" in all_rules

    def test_enable_and_disable_rule(self, manager):
        """Test enabling and disabling a rule."""
        # Create a disabled rule
        manager.create_rule("gdcards", "GDCardsParser", enabled=False)

        # Enable it
        result = manager.enable_rule("gdcards")
        assert result is True
        assert manager.is_enabled("gdcards") is True

        # Disable it
        result = manager.disable_rule("gdcards")
        assert result is True
        assert manager.is_enabled("gdcards") is False

    def test_update_rule_multiple_fields(self, manager):
        """Test updating multiple fields of a rule."""
        # Create a rule
        manager.create_rule(
            game_name="gdcards",
            parser_class="OldParser",
            coefficient=1.0,
            enabled=True,
            config={"old": "config"}
        )

        # Update multiple fields
        result = manager.update_rule(
            game_name="gdcards",
            parser_class="NewParser",
            coefficient=2.0,
            enabled=False,
            config={"new": "config"}
        )
        assert result is True

        # Verify updates
        rule = manager.get_rule("gdcards")
        assert rule.parser_class == "NewParser"
        assert rule.coefficient == 2.0
        assert rule.enabled is False
        assert rule.config == {"new": "config"}

    def test_delete_rule(self, manager):
        """Test deleting a rule."""
        # Create a rule
        manager.create_rule("gdcards", "GDCardsParser")

        # Verify it exists
        assert manager.get_rule("gdcards") is not None

        # Delete it
        result = manager.delete_rule("gdcards")
        assert result is True

        # Verify it's gone
        assert manager.get_rule("gdcards") is None

    def test_get_coefficient(self, manager):
        """Test getting coefficient value."""
        # Create a rule
        manager.create_rule("gdcards", "GDCardsParser", coefficient=1.8)

        # Get coefficient
        coef = manager.get_coefficient("gdcards")
        assert coef == 1.8

        # Non-existent rule
        coef = manager.get_coefficient("nonexistent")
        assert coef is None

    def test_is_enabled(self, manager):
        """Test checking if rule is enabled."""
        # Create enabled rule
        manager.create_rule("gdcards", "GDCardsParser", enabled=True)
        assert manager.is_enabled("gdcards") is True

        # Create disabled rule
        manager.create_rule("shmalala", "ShmalalaParser", enabled=False)
        assert manager.is_enabled("shmalala") is False

        # Non-existent rule
        assert manager.is_enabled("nonexistent") is False

    def test_create_rule_with_defaults(self, manager):
        """Test creating a rule with default values."""
        rule = manager.create_rule(
            game_name="gdcards",
            parser_class="GDCardsParser"
        )

        assert rule.coefficient == 1.0
        assert rule.enabled is True
        assert rule.config == {}

    def test_update_rule_partial(self, manager):
        """Test updating only some fields of a rule."""
        # Create a rule
        manager.create_rule(
            game_name="gdcards",
            parser_class="GDCardsParser",
            coefficient=1.0,
            enabled=True
        )

        # Update only coefficient
        result = manager.update_rule(
            game_name="gdcards",
            coefficient=2.5
        )
        assert result is True

        # Verify only coefficient changed
        rule = manager.get_rule("gdcards")
        assert rule.coefficient == 2.5
        assert rule.parser_class == "GDCardsParser"
        assert rule.enabled is True

    def test_operations_on_nonexistent_rule(self, manager):
        """Test that operations on non-existent rules return False."""
        assert manager.update_coefficient("nonexistent", 2.0) is False
        assert manager.enable_rule("nonexistent") is False
        assert manager.disable_rule("nonexistent") is False
        assert manager.update_rule("nonexistent", coefficient=2.0) is False
        assert manager.delete_rule("nonexistent") is False

    def test_multiple_rules_management(self, manager):
        """Test managing multiple rules simultaneously."""
        # Create multiple rules
        games = ["gdcards", "shmalala", "bunkerrp", "truemafia"]
        for game in games:
            manager.create_rule(
                game_name=game,
                parser_class=f"{game.capitalize()}Parser",
                coefficient=1.0 + games.index(game) * 0.5,
                enabled=games.index(game) % 2 == 0
            )

        # Verify all created
        all_rules = manager.get_all_rules()
        assert len(all_rules) == 4

        # Verify active rules
        active_rules = manager.get_all_active_rules()
        assert len(active_rules) == 2
        assert "gdcards" in active_rules
        assert "bunkerrp" in active_rules

        # Update coefficients
        for game in games:
            manager.update_coefficient(game, 2.0)

        # Verify all updated
        for game in games:
            assert manager.get_coefficient(game) == 2.0

    def test_config_field_persistence(self, manager):
        """Test that JSON config field persists correctly."""
        complex_config = {
            "nested": {
                "value": 123,
                "list": [1, 2, 3]
            },
            "string": "test",
            "boolean": True
        }

        # Create rule with complex config
        manager.create_rule(
            game_name="gdcards",
            parser_class="GDCardsParser",
            config=complex_config
        )

        # Retrieve and verify
        rule = manager.get_rule("gdcards")
        assert rule.config == complex_config
        assert rule.config["nested"]["value"] == 123
        assert rule.config["nested"]["list"] == [1, 2, 3]
