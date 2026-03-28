"""Unit tests for ParsingRule model."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database import Base
from src.models.parsing_rule import ParsingRule


@pytest.fixture
def engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a test database session."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestParsingRuleModel:
    """Test suite for ParsingRule model."""
    
    def test_create_parsing_rule(self, session):
        """Test creating a ParsingRule instance."""
        rule = ParsingRule(
            game_name="gdcards",
            parser_class="GDCardsParser",
            coefficient=1.5,
            enabled=True,
            config={"max_retries": 3}
        )
        session.add(rule)
        session.commit()
        
        assert rule.id is not None
        assert rule.game_name == "gdcards"
        assert rule.parser_class == "GDCardsParser"
        assert rule.coefficient == 1.5
        assert rule.enabled is True
        assert rule.config == {"max_retries": 3}
    
    def test_parsing_rule_defaults(self, session):
        """Test ParsingRule default values."""
        rule = ParsingRule(
            game_name="shmalala",
            parser_class="ShmalalaParser"
        )
        session.add(rule)
        session.commit()
        
        assert rule.coefficient == 1.0
        assert rule.enabled is True
        assert rule.config == {}
    
    def test_parsing_rule_unique_game_name(self, session):
        """Test that game_name must be unique."""
        rule1 = ParsingRule(
            game_name="truemafia",
            parser_class="TrueMafiaParser"
        )
        session.add(rule1)
        session.commit()
        
        # Try to create another rule with the same game_name
        rule2 = ParsingRule(
            game_name="truemafia",
            parser_class="AnotherParser"
        )
        session.add(rule2)
        
        with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
            session.commit()
    
    def test_parsing_rule_repr(self, session):
        """Test ParsingRule string representation."""
        rule = ParsingRule(
            game_name="bunkerrp",
            parser_class="BunkerRPParser",
            coefficient=2.0,
            enabled=False
        )
        session.add(rule)
        session.commit()
        
        repr_str = repr(rule)
        assert "ParsingRule" in repr_str
        assert "bunkerrp" in repr_str
        assert "BunkerRPParser" in repr_str
        assert "2.0" in repr_str
        assert "False" in repr_str
    
    def test_query_parsing_rule_by_game_name(self, session):
        """Test querying ParsingRule by game_name."""
        rule = ParsingRule(
            game_name="gdcards",
            parser_class="GDCardsParser",
            coefficient=1.5
        )
        session.add(rule)
        session.commit()
        
        found_rule = session.query(ParsingRule).filter_by(game_name="gdcards").first()
        assert found_rule is not None
        assert found_rule.game_name == "gdcards"
        assert found_rule.parser_class == "GDCardsParser"
        assert found_rule.coefficient == 1.5
    
    def test_query_enabled_rules(self, session):
        """Test querying only enabled ParsingRules."""
        rules = [
            ParsingRule(game_name="game1", parser_class="Parser1", enabled=True),
            ParsingRule(game_name="game2", parser_class="Parser2", enabled=False),
            ParsingRule(game_name="game3", parser_class="Parser3", enabled=True),
        ]
        for rule in rules:
            session.add(rule)
        session.commit()
        
        enabled_rules = session.query(ParsingRule).filter_by(enabled=True).all()
        assert len(enabled_rules) == 2
        assert all(rule.enabled for rule in enabled_rules)
    
    def test_update_parsing_rule(self, session):
        """Test updating a ParsingRule."""
        rule = ParsingRule(
            game_name="gdcards",
            parser_class="GDCardsParser",
            coefficient=1.0
        )
        session.add(rule)
        session.commit()
        
        # Update the rule
        rule.coefficient = 2.5
        rule.enabled = False
        session.commit()
        
        # Verify the update
        updated_rule = session.query(ParsingRule).filter_by(game_name="gdcards").first()
        assert updated_rule.coefficient == 2.5
        assert updated_rule.enabled is False
    
    def test_delete_parsing_rule(self, session):
        """Test deleting a ParsingRule."""
        rule = ParsingRule(
            game_name="gdcards",
            parser_class="GDCardsParser"
        )
        session.add(rule)
        session.commit()
        
        rule_id = rule.id
        
        # Delete the rule
        session.delete(rule)
        session.commit()
        
        # Verify deletion
        deleted_rule = session.query(ParsingRule).filter_by(id=rule_id).first()
        assert deleted_rule is None
