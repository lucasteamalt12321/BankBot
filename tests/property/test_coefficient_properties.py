"""Property-based tests for CoefficientProvider."""

import pytest
import json
import tempfile
import os
from hypothesis import given, strategies as st
from src.coefficient_provider import CoefficientProvider


# Strategy for generating valid game names
game_names = st.text(min_size=1, max_size=50, alphabet=st.characters(
    whitelist_categories=('Lu', 'Ll', 'Nd'),
    whitelist_characters=' '
))

# Strategy for generating valid coefficients (positive integers)
coefficients = st.integers(min_value=1, max_value=1000)


@given(
    game_name=game_names,
    coefficient_value=coefficients
)
def test_coefficient_retrieval(game_name, coefficient_value):
    """
    Feature: message-parsing-system, Property 17: Coefficient Retrieval
    
    For any configured game name, the coefficient provider should return 
    the correct coefficient value.
    
    Validates: Requirements 14.1
    """
    # Arrange
    coefficients_dict = {game_name: coefficient_value}
    provider = CoefficientProvider(coefficients_dict)
    
    # Act
    result = provider.get_coefficient(game_name)
    
    # Assert
    assert result == coefficient_value


@given(
    configured_game=game_names,
    configured_coefficient=coefficients,
    missing_game=game_names
)
def test_missing_coefficient_error(configured_game, configured_coefficient, missing_game):
    """
    Feature: message-parsing-system, Property 18: Missing Coefficient Error
    
    For any game name not in the configuration, attempting to get its 
    coefficient should raise a ValueError indicating the missing configuration.
    
    Validates: Requirements 14.3, 19.4
    """
    # Skip if the missing game is the same as the configured game
    if missing_game == configured_game:
        return
    
    # Arrange
    coefficients_dict = {configured_game: configured_coefficient}
    provider = CoefficientProvider(coefficients_dict)
    
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        provider.get_coefficient(missing_game)
    
    # Verify error message contains the missing game name
    assert "No coefficient configured for game:" in str(exc_info.value)
    assert missing_game in str(exc_info.value)


@given(
    coefficients_dict=st.dictionaries(
        keys=game_names,
        values=coefficients,
        min_size=1,
        max_size=10
    )
)
def test_from_config_preserves_all_coefficients(coefficients_dict):
    """
    Feature: message-parsing-system, Property 17: Coefficient Retrieval
    
    For any valid coefficients configuration loaded from a JSON file,
    all game coefficients should be retrievable and match the original values.
    
    Validates: Requirements 14.1, 14.4
    """
    # Create temporary JSON file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(coefficients_dict, f)
        temp_path = f.name
    
    try:
        # Act
        provider = CoefficientProvider.from_config(temp_path)
        
        # Assert - all coefficients should be retrievable
        for game_name, expected_coefficient in coefficients_dict.items():
            actual_coefficient = provider.get_coefficient(game_name)
            assert actual_coefficient == expected_coefficient
    finally:
        os.unlink(temp_path)


@given(
    game_name=game_names,
    coefficient_value=coefficients
)
def test_coefficient_retrieval_idempotent(game_name, coefficient_value):
    """
    Feature: message-parsing-system, Property 17: Coefficient Retrieval
    
    For any configured game, retrieving its coefficient multiple times
    should always return the same value (idempotent operation).
    
    Validates: Requirements 14.1
    """
    # Arrange
    coefficients_dict = {game_name: coefficient_value}
    provider = CoefficientProvider(coefficients_dict)
    
    # Act - retrieve coefficient multiple times
    result1 = provider.get_coefficient(game_name)
    result2 = provider.get_coefficient(game_name)
    result3 = provider.get_coefficient(game_name)
    
    # Assert - all results should be identical
    assert result1 == result2 == result3 == coefficient_value
