"""Unit tests for CoefficientProvider class."""

import pytest
import json
import tempfile
import os
from src.coefficient_provider import CoefficientProvider


class TestCoefficientProvider:
    """Test suite for CoefficientProvider."""
    
    def test_init_with_coefficients(self):
        """Test initialization with coefficient dictionary."""
        coefficients = {"Game1": 5, "Game2": 10}
        provider = CoefficientProvider(coefficients)
        
        assert provider.coefficients == coefficients
    
    def test_get_coefficient_existing_game(self):
        """Test retrieving coefficient for an existing game."""
        coefficients = {"GD Cards": 2, "True Mafia": 15}
        provider = CoefficientProvider(coefficients)
        
        assert provider.get_coefficient("GD Cards") == 2
        assert provider.get_coefficient("True Mafia") == 15
    
    def test_get_coefficient_missing_game_raises_error(self):
        """Test that missing game raises ValueError with descriptive message."""
        coefficients = {"GD Cards": 2}
        provider = CoefficientProvider(coefficients)
        
        with pytest.raises(ValueError) as exc_info:
            provider.get_coefficient("Unknown Game")
        
        assert "No coefficient configured for game: Unknown Game" in str(exc_info.value)
    
    def test_get_coefficient_initial_games(self):
        """Test that initial coefficients match requirements: Shmalala=1, GD Cards=2, True Mafia=15, Bunker RP=20."""
        coefficients = {
            "Shmalala": 1,
            "GD Cards": 2,
            "True Mafia": 15,
            "Bunker RP": 20
        }
        provider = CoefficientProvider(coefficients)
        
        assert provider.get_coefficient("Shmalala") == 1
        assert provider.get_coefficient("GD Cards") == 2
        assert provider.get_coefficient("True Mafia") == 15
        assert provider.get_coefficient("Bunker RP") == 20
    
    def test_from_config_loads_json_file(self):
        """Test loading coefficients from JSON config file."""
        coefficients = {
            "Shmalala": 1,
            "GD Cards": 2,
            "True Mafia": 15,
            "Bunker RP": 20
        }
        
        # Create temporary JSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(coefficients, f)
            temp_path = f.name
        
        try:
            provider = CoefficientProvider.from_config(temp_path)
            
            assert provider.get_coefficient("Shmalala") == 1
            assert provider.get_coefficient("GD Cards") == 2
            assert provider.get_coefficient("True Mafia") == 15
            assert provider.get_coefficient("Bunker RP") == 20
        finally:
            os.unlink(temp_path)
    
    def test_from_config_with_empty_dict(self):
        """Test loading empty coefficient dictionary from config."""
        coefficients = {}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(coefficients, f)
            temp_path = f.name
        
        try:
            provider = CoefficientProvider.from_config(temp_path)
            
            with pytest.raises(ValueError):
                provider.get_coefficient("Any Game")
        finally:
            os.unlink(temp_path)
    
    def test_from_config_file_not_found(self):
        """Test that from_config raises error when file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            CoefficientProvider.from_config("nonexistent_file.json")
