"""Unit tests for database-backed CoefficientProvider."""

import pytest
import tempfile
import os
from unittest.mock import Mock, MagicMock
from src.coefficient_provider import CoefficientProvider
from core.managers.parsing_config_manager import ParsingConfigManager


class TestCoefficientProviderDatabase:
    """Test suite for database-backed CoefficientProvider."""
    
    def test_from_database_creates_provider(self):
        """Test that from_database creates a provider with ParsingConfigManager."""
        # Arrange
        mock_manager = Mock(spec=ParsingConfigManager)
        
        # Act
        provider = CoefficientProvider.from_database(mock_manager)
        
        # Assert
        assert provider is not None
        assert provider.parsing_config_manager == mock_manager
        assert provider._use_database is True
    
    def test_get_coefficient_from_database(self):
        """Test retrieving coefficient from database-backed provider."""
        # Arrange
        mock_manager = Mock(spec=ParsingConfigManager)
        mock_manager.get_coefficient.return_value = 2.5
        provider = CoefficientProvider.from_database(mock_manager)
        
        # Act
        coefficient = provider.get_coefficient("gdcards")
        
        # Assert
        assert coefficient == 2
        mock_manager.get_coefficient.assert_called_once_with("gdcards")
    
    def test_get_coefficient_from_database_raises_when_not_found(self):
        """Test that missing game raises ValueError with database provider."""
        # Arrange
        mock_manager = Mock(spec=ParsingConfigManager)
        mock_manager.get_coefficient.return_value = None
        provider = CoefficientProvider.from_database(mock_manager)
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            provider.get_coefficient("nonexistent")
        
        assert "No coefficient configured for game: nonexistent" in str(exc_info.value)
    
    def test_database_provider_takes_precedence_over_dict(self):
        """Test that database provider takes precedence when both are provided."""
        # Arrange
        mock_manager = Mock(spec=ParsingConfigManager)
        mock_manager.get_coefficient.return_value = 5.0
        coefficients_dict = {"gdcards": 2}
        
        # Act
        provider = CoefficientProvider(
            coefficients=coefficients_dict,
            parsing_config_manager=mock_manager
        )
        coefficient = provider.get_coefficient("gdcards")
        
        # Assert
        assert coefficient == 5  # From database, not dict
        assert provider._use_database is True
    
    def test_init_without_either_raises_error(self):
        """Test that initialization without coefficients or manager raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            CoefficientProvider()
        
        assert "Either coefficients dict or parsing_config_manager must be provided" in str(exc_info.value)
    
    def test_legacy_dict_mode_shows_deprecation_warning(self):
        """Test that using dictionary mode shows deprecation warning."""
        # Arrange
        coefficients = {"gdcards": 2}
        
        # Act & Assert
        with pytest.warns(DeprecationWarning, match="Using dictionary-based CoefficientProvider is deprecated"):
            provider = CoefficientProvider(coefficients=coefficients)
        
        assert provider._use_database is False
    
    def test_from_config_shows_deprecation_warning(self):
        """Test that from_config method shows deprecation warning."""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"GD Cards": 2}')
            temp_path = f.name
        
        try:
            # Act & Assert
            with pytest.warns(DeprecationWarning, match="CoefficientProvider.from_config\\(\\) is deprecated"):
                provider = CoefficientProvider.from_config(temp_path)
            
            assert provider._use_database is False
        finally:
            os.unlink(temp_path)
    
    def test_database_provider_converts_float_to_int(self):
        """Test that database provider converts float coefficients to int."""
        # Arrange
        mock_manager = Mock(spec=ParsingConfigManager)
        mock_manager.get_coefficient.return_value = 2.7
        provider = CoefficientProvider.from_database(mock_manager)
        
        # Act
        coefficient = provider.get_coefficient("gdcards")
        
        # Assert
        assert coefficient == 2
        assert isinstance(coefficient, int)
