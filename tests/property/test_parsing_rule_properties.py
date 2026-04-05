"""Property-based tests for ParsingRule model."""

import pytest
from contextlib import contextmanager
from hypothesis import given, strategies as st, assume
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database import Base
from src.models.parsing_rule import ParsingRule


@contextmanager
def get_test_session():
    """Context manager for creating test database sessions."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Strategy for generating valid game names
game_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), min_codepoint=97, max_codepoint=122),
    min_size=1,
    max_size=50
).filter(lambda x: x.strip() != '')

# Strategy for generating valid parser class names
parser_class_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), min_codepoint=65, max_codepoint=122),
    min_size=1,
    max_size=100
).filter(lambda x: x.strip() != '' and x[0].isupper())

# Strategy for generating valid coefficients
coefficient_strategy = st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False)


class TestParsingRuleProperties:
    """Property-based tests for ParsingRule model."""

    @given(
        game_name=game_name_strategy,
        parser_class=parser_class_strategy,
        coefficient=coefficient_strategy,
        enabled=st.booleans()
    )
    def test_parsing_rule_creation_always_succeeds(
        self, game_name, parser_class, coefficient, enabled
    ):
        """
        Property: Creating a ParsingRule with valid data always succeeds.
        
        **Validates: Requirements 7.1**
        """
        with get_test_session() as session:
            rule = ParsingRule(
                game_name=game_name,
                parser_class=parser_class,
                coefficient=coefficient,
                enabled=enabled
            )
            session.add(rule)
            session.commit()

            # Verify the rule was created
            assert rule.id is not None
            assert rule.game_name == game_name
            assert rule.parser_class == parser_class
            assert rule.coefficient == coefficient
            assert rule.enabled == enabled

    @given(
        game_name=game_name_strategy,
        parser_class=parser_class_strategy,
        coefficient=coefficient_strategy
    )
    def test_parsing_rule_defaults_are_consistent(
        self, game_name, parser_class, coefficient
    ):
        """
        Property: ParsingRule defaults are always applied consistently.
        
        **Validates: Requirements 7.1**
        """
        with get_test_session() as session:
            rule = ParsingRule(
                game_name=game_name,
                parser_class=parser_class,
                coefficient=coefficient
            )
            session.add(rule)
            session.commit()

            # Default values should always be applied
            assert rule.enabled is True
            assert rule.config == {}

    @given(
        game_name=game_name_strategy,
        parser_class=parser_class_strategy,
        new_coefficient=coefficient_strategy
    )
    def test_parsing_rule_update_preserves_identity(
        self, game_name, parser_class, new_coefficient
    ):
        """
        Property: Updating a ParsingRule preserves its identity (ID and game_name).
        
        **Validates: Requirements 7.1**
        """
        with get_test_session() as session:
            # Create initial rule
            rule = ParsingRule(
                game_name=game_name,
                parser_class=parser_class,
                coefficient=1.0
            )
            session.add(rule)
            session.commit()

            original_id = rule.id
            original_game_name = rule.game_name

            # Update the rule
            rule.coefficient = new_coefficient
            session.commit()

            # Identity should be preserved
            assert rule.id == original_id
            assert rule.game_name == original_game_name
            assert rule.coefficient == new_coefficient

    @given(
        game_name=game_name_strategy,
        parser_class=parser_class_strategy,
        coefficient=coefficient_strategy
    )
    def test_parsing_rule_query_by_game_name_is_consistent(
        self, game_name, parser_class, coefficient
    ):
        """
        Property: Querying by game_name always returns the same rule.
        
        **Validates: Requirements 7.1**
        """
        with get_test_session() as session:
            # Create rule
            rule = ParsingRule(
                game_name=game_name,
                parser_class=parser_class,
                coefficient=coefficient
            )
            session.add(rule)
            session.commit()

            # Query multiple times
            found_rule_1 = session.query(ParsingRule).filter_by(game_name=game_name).first()
            found_rule_2 = session.query(ParsingRule).filter_by(game_name=game_name).first()

            # Should always return the same rule
            assert found_rule_1 is not None
            assert found_rule_2 is not None
            assert found_rule_1.id == found_rule_2.id
            assert found_rule_1.game_name == found_rule_2.game_name

    @given(
        rules_data=st.lists(
            st.tuples(
                game_name_strategy,
                parser_class_strategy,
                coefficient_strategy,
                st.booleans()
            ),
            min_size=1,
            max_size=10,
            unique_by=lambda x: x[0]  # Unique by game_name
        )
    )
    def test_enabled_filter_returns_only_enabled_rules(self, rules_data):
        """
        Property: Filtering by enabled=True returns only enabled rules.
        
        **Validates: Requirements 7.1**
        """
        with get_test_session() as session:
            # Create rules
            for game_name, parser_class, coefficient, enabled in rules_data:
                rule = ParsingRule(
                    game_name=game_name,
                    parser_class=parser_class,
                    coefficient=coefficient,
                    enabled=enabled
                )
                session.add(rule)
            session.commit()

            # Query enabled rules
            enabled_rules = session.query(ParsingRule).filter_by(enabled=True).all()

            # All returned rules should be enabled
            assert all(rule.enabled for rule in enabled_rules)

            # Count should match
            expected_count = sum(1 for _, _, _, enabled in rules_data if enabled)
            assert len(enabled_rules) == expected_count

    @given(
        game_name=game_name_strategy,
        parser_class=parser_class_strategy
    )
    def test_parsing_rule_deletion_is_complete(self, game_name, parser_class):
        """
        Property: Deleting a ParsingRule removes it completely from the database.
        
        **Validates: Requirements 7.1**
        """
        with get_test_session() as session:
            # Create rule
            rule = ParsingRule(
                game_name=game_name,
                parser_class=parser_class
            )
            session.add(rule)
            session.commit()

            rule_id = rule.id

            # Delete rule
            session.delete(rule)
            session.commit()

            # Rule should not exist
            deleted_rule = session.query(ParsingRule).filter_by(id=rule_id).first()
            assert deleted_rule is None

            # Also verify by game_name
            deleted_by_name = session.query(ParsingRule).filter_by(game_name=game_name).first()
            assert deleted_by_name is None

    @given(
        game_name=game_name_strategy,
        parser_class=parser_class_strategy,
        coefficient=coefficient_strategy
    )
    def test_parsing_rule_repr_contains_key_info(
        self, game_name, parser_class, coefficient
    ):
        """
        Property: ParsingRule repr always contains key identifying information.
        
        **Validates: Requirements 7.1**
        """
        with get_test_session() as session:
            rule = ParsingRule(
                game_name=game_name,
                parser_class=parser_class,
                coefficient=coefficient
            )
            session.add(rule)
            session.commit()

            repr_str = repr(rule)

            # Repr should contain key information
            assert "ParsingRule" in repr_str
            assert game_name in repr_str
            assert parser_class in repr_str
