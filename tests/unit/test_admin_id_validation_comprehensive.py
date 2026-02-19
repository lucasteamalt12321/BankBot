"""
Comprehensive validation tests for ADMIN_TELEGRAM_ID field.

This test file verifies that the validation for ADMIN_TELEGRAM_ID is:
1. Comprehensive - covers all edge cases
2. Clear - provides helpful error messages
3. Correct - works as expected

Validates: Requirements 2.2 - ADMIN_TELEGRAM_ID validation
"""

import os
import sys
import pytest
from pydantic import ValidationError

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAdminTelegramIdValidationComprehensive:
    """Comprehensive tests for ADMIN_TELEGRAM_ID validation"""
    
    def test_validation_exists(self):
        """Verify that ADMIN_TELEGRAM_ID has validation"""
        from src.config import Settings
        
        # Should reject negative values
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID=-1,
                DATABASE_URL="sqlite:///test.db"
            )
        
        assert "ADMIN_TELEGRAM_ID must be a positive integer" in str(exc_info.value)
    
    def test_validation_rejects_zero(self):
        """Verify that zero is rejected"""
        from src.config import Settings
        
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID=0,
                DATABASE_URL="sqlite:///test.db"
            )
        
        assert "ADMIN_TELEGRAM_ID must be a positive integer" in str(exc_info.value)
    
    def test_validation_rejects_negative(self):
        """Verify that negative values are rejected"""
        from src.config import Settings
        
        test_cases = [-1, -100, -999999999]
        
        for invalid_id in test_cases:
            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    BOT_TOKEN="test_token",
                    ADMIN_TELEGRAM_ID=invalid_id,
                    DATABASE_URL="sqlite:///test.db"
                )
            
            assert "ADMIN_TELEGRAM_ID must be a positive integer" in str(exc_info.value)
    
    def test_validation_accepts_small_positive(self):
        """Verify that small positive integers are accepted"""
        from src.config import Settings
        
        test_cases = [1, 10, 100, 1000]
        
        for valid_id in test_cases:
            settings = Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID=valid_id,
                DATABASE_URL="sqlite:///test.db"
            )
            
            assert settings.ADMIN_TELEGRAM_ID == valid_id
    
    def test_validation_accepts_typical_telegram_ids(self):
        """Verify that typical Telegram IDs are accepted"""
        from src.config import Settings
        
        # Typical Telegram IDs are 9-10 digits
        test_cases = [
            123456789,      # 9 digits
            987654321,      # 9 digits
            1234567890,     # 10 digits
            9999999999,     # 10 digits (max 10-digit)
        ]
        
        for valid_id in test_cases:
            settings = Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID=valid_id,
                DATABASE_URL="sqlite:///test.db"
            )
            
            assert settings.ADMIN_TELEGRAM_ID == valid_id
    
    def test_validation_accepts_large_telegram_ids(self):
        """Verify that large Telegram IDs are accepted"""
        from src.config import Settings
        
        # Telegram IDs can be up to 0xffffffffff (1,099,511,627,775)
        # Test some large values
        test_cases = [
            99999999999,        # 11 digits
            999999999999,       # 12 digits
            1099511627775,      # Max Telegram ID (0xffffffffff)
        ]
        
        for valid_id in test_cases:
            settings = Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID=valid_id,
                DATABASE_URL="sqlite:///test.db"
            )
            
            assert settings.ADMIN_TELEGRAM_ID == valid_id
    
    def test_validation_is_required(self):
        """Verify that ADMIN_TELEGRAM_ID is required"""
        from src.config import Settings
        from unittest.mock import patch
        
        # Clear environment to test required field
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    BOT_TOKEN="test_token",
                    DATABASE_URL="sqlite:///test.db"
                )
            
            assert "ADMIN_TELEGRAM_ID" in str(exc_info.value)
            assert "Field required" in str(exc_info.value)
    
    def test_validation_type_checking(self):
        """Verify that ADMIN_TELEGRAM_ID must be an integer"""
        from src.config import Settings
        
        # String should be rejected (or converted if Pydantic does that)
        with pytest.raises(ValidationError):
            Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID="not_a_number",  # type: ignore
                DATABASE_URL="sqlite:///test.db"
            )
    
    def test_error_message_is_clear(self):
        """Verify that error messages are clear and helpful"""
        from src.config import Settings
        
        # Test negative value error message
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID=-1,
                DATABASE_URL="sqlite:///test.db"
            )
        
        error_message = str(exc_info.value)
        
        # Error message should be clear
        assert "ADMIN_TELEGRAM_ID" in error_message
        assert "positive integer" in error_message
        
        # Should not be a generic error
        assert "must be a positive integer" in error_message
    
    def test_validation_works_with_environment_variables(self):
        """Verify that validation works when loading from environment"""
        from src.config import Settings
        from unittest.mock import patch
        
        # Test with valid environment variable
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_token',
            'ADMIN_TELEGRAM_ID': '123456789',
            'DATABASE_URL': 'sqlite:///test.db'
        }):
            settings = Settings()
            assert settings.ADMIN_TELEGRAM_ID == 123456789
        
        # Test with invalid environment variable (negative)
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_token',
            'ADMIN_TELEGRAM_ID': '-1',
            'DATABASE_URL': 'sqlite:///test.db'
        }):
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            
            assert "ADMIN_TELEGRAM_ID must be a positive integer" in str(exc_info.value)
        
        # Test with invalid environment variable (zero)
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_token',
            'ADMIN_TELEGRAM_ID': '0',
            'DATABASE_URL': 'sqlite:///test.db'
        }):
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            
            assert "ADMIN_TELEGRAM_ID must be a positive integer" in str(exc_info.value)
    
    def test_validation_boundary_values(self):
        """Test boundary values for ADMIN_TELEGRAM_ID"""
        from src.config import Settings
        
        # Test minimum valid value (1)
        settings = Settings(
            BOT_TOKEN="test_token",
            ADMIN_TELEGRAM_ID=1,
            DATABASE_URL="sqlite:///test.db"
        )
        assert settings.ADMIN_TELEGRAM_ID == 1
        
        # Test just below minimum (0) - should fail
        with pytest.raises(ValidationError):
            Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID=0,
                DATABASE_URL="sqlite:///test.db"
            )
        
        # Test very large value (within Telegram's range)
        large_id = 1099511627775  # 0xffffffffff
        settings = Settings(
            BOT_TOKEN="test_token",
            ADMIN_TELEGRAM_ID=large_id,
            DATABASE_URL="sqlite:///test.db"
        )
        assert settings.ADMIN_TELEGRAM_ID == large_id
        
        # Test value exceeding Telegram's maximum - should fail
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID=1099511627776,  # 0xffffffffff + 1
                DATABASE_URL="sqlite:///test.db"
            )
        
        assert "exceeds Telegram's maximum user ID" in str(exc_info.value)


class TestAdminTelegramIdValidationDocumentation:
    """Test that validation is properly documented"""
    
    def test_validator_has_docstring(self):
        """Verify that the validator has documentation"""
        from src.config import Settings
        
        # Check that the validator has a docstring
        assert Settings.validate_admin_id.__doc__ is not None
        assert len(Settings.validate_admin_id.__doc__) > 0
        assert "positive integer" in Settings.validate_admin_id.__doc__.lower()
    
    def test_field_has_type_annotation(self):
        """Verify that ADMIN_TELEGRAM_ID has proper type annotation"""
        from src.config import Settings
        
        annotations = Settings.__annotations__
        assert 'ADMIN_TELEGRAM_ID' in annotations
        assert annotations['ADMIN_TELEGRAM_ID'] == int


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
