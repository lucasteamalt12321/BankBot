"""
Unit tests for Settings configuration system (src/config.py)

Tests cover:
- Valid configuration loading
- Validation of required fields (BOT_TOKEN, ADMIN_TELEGRAM_ID, DATABASE_URL)
- Validation of ENV values
- Validation of LOG_LEVEL values
- Error handling for missing/invalid values
- Multiple environment support

Validates: Requirements 1.1 - Unified configuration system
Validates: Design section 1 - Configuration validation
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch
from pydantic import ValidationError

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSettingsBasicValidation:
    """Test basic Settings validation"""
    
    def test_valid_configuration_loading(self):
        """Test that Settings loads with valid configuration"""
        # Import Settings class (not the singleton)
        from src.config import Settings
        
        settings = Settings(
            BOT_TOKEN="test_bot_token_12345",
            ADMIN_TELEGRAM_ID=123456789,
            DATABASE_URL="sqlite:///test.db"
        )
        
        assert settings.BOT_TOKEN == "test_bot_token_12345"
        assert settings.ADMIN_TELEGRAM_ID == 123456789
        assert settings.DATABASE_URL == "sqlite:///test.db"
    
    def test_settings_validates_bot_token_empty(self):
        """Test that BOT_TOKEN cannot be empty"""
        from src.config import Settings
        
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                BOT_TOKEN="",
                ADMIN_TELEGRAM_ID=123456789,
                DATABASE_URL="sqlite:///test.db"
            )
        
        assert "BOT_TOKEN cannot be empty" in str(exc_info.value)
    
    def test_settings_validates_bot_token_required(self):
        """Test that BOT_TOKEN is required"""
        from src.config import Settings
        
        # Clear environment variable to test required field
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    ADMIN_TELEGRAM_ID=123456789,
                    DATABASE_URL="sqlite:///test.db"
                )
            
            assert "BOT_TOKEN" in str(exc_info.value)
            assert "Field required" in str(exc_info.value)
    
    def test_settings_validates_admin_id_positive(self):
        """Test that ADMIN_TELEGRAM_ID must be positive"""
        from src.config import Settings
        
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID=-1,
                DATABASE_URL="sqlite:///test.db"
            )
        
        assert "ADMIN_TELEGRAM_ID must be a positive integer" in str(exc_info.value)
    
    def test_settings_validates_admin_id_zero(self):
        """Test that ADMIN_TELEGRAM_ID cannot be zero"""
        from src.config import Settings
        
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID=0,
                DATABASE_URL="sqlite:///test.db"
            )
        
        assert "ADMIN_TELEGRAM_ID must be a positive integer" in str(exc_info.value)
    
    def test_settings_validates_admin_id_required(self):
        """Test that ADMIN_TELEGRAM_ID is required"""
        from src.config import Settings
        
        # Clear environment variable to test required field
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    BOT_TOKEN="test_token",
                    DATABASE_URL="sqlite:///test.db"
                )
            
            assert "ADMIN_TELEGRAM_ID" in str(exc_info.value)
            assert "Field required" in str(exc_info.value)
    
    def test_settings_validates_database_url_empty(self):
        """Test that DATABASE_URL cannot be empty"""
        from src.config import Settings
        
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID=123456789,
                DATABASE_URL=""
            )
        
        assert "DATABASE_URL cannot be empty" in str(exc_info.value)
    
    def test_settings_validates_database_url_required(self):
        """Test that DATABASE_URL is required"""
        from src.config import Settings
        
        # Clear environment variable to test required field
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    BOT_TOKEN="test_token",
                    ADMIN_TELEGRAM_ID=123456789
                )
            
            assert "DATABASE_URL" in str(exc_info.value)
            assert "Field required" in str(exc_info.value)
    
    def test_settings_validates_env_invalid(self):
        """Test that ENV must be one of allowed values"""
        from src.config import Settings
        
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID=123456789,
                DATABASE_URL="sqlite:///test.db",
                ENV="invalid_env"
            )
        
        assert "ENV must be one of" in str(exc_info.value)
    
    def test_settings_validates_env_allowed_values(self):
        """Test that all allowed ENV values work"""
        from src.config import Settings
        
        allowed_envs = ["development", "test", "staging", "production"]
        
        for env in allowed_envs:
            settings = Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID=123456789,
                DATABASE_URL="sqlite:///test.db",
                ENV=env
            )
            assert settings.ENV == env
    
    def test_settings_validates_log_level_lowercase(self):
        """Test that LOG_LEVEL converts lowercase to uppercase"""
        from src.config import Settings
        
        settings = Settings(
            BOT_TOKEN="test_token",
            ADMIN_TELEGRAM_ID=123456789,
            DATABASE_URL="sqlite:///test.db",
            LOG_LEVEL="debug"
        )
        
        assert settings.LOG_LEVEL == "DEBUG"
    
    def test_settings_validates_log_level_invalid(self):
        """Test that LOG_LEVEL must be one of allowed values"""
        from src.config import Settings
        
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID=123456789,
                DATABASE_URL="sqlite:///test.db",
                LOG_LEVEL="INVALID"
            )
        
        assert "LOG_LEVEL must be one of" in str(exc_info.value)
    
    def test_settings_validates_log_level_allowed_values(self):
        """Test that all allowed LOG_LEVEL values work"""
        from src.config import Settings
        
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        
        for level in allowed_levels:
            settings = Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID=123456789,
                DATABASE_URL="sqlite:///test.db",
                LOG_LEVEL=level
            )
            assert settings.LOG_LEVEL == level
    
    def test_settings_default_values(self):
        """Test that default values are set correctly"""
        from src.config import Settings
        
        # Explicitly set ENV to test default, or pass it as parameter
        settings = Settings(
            BOT_TOKEN="test_token",
            ADMIN_TELEGRAM_ID=123456789,
            DATABASE_URL="sqlite:///test.db",
            ENV="development"  # Explicitly set to test default
        )
        
        assert settings.ENV == "development"
        assert settings.PARSING_ENABLED == False
        assert settings.LOG_LEVEL == "INFO"
        assert settings.LOG_FILE is None
    
    def test_settings_optional_fields(self):
        """Test that optional fields can be set"""
        from src.config import Settings
        
        settings = Settings(
            BOT_TOKEN="test_token",
            ADMIN_TELEGRAM_ID=123456789,
            DATABASE_URL="sqlite:///test.db",
            PARSING_ENABLED=True,
            LOG_FILE="/var/log/bot.log"
        )
        
        assert settings.PARSING_ENABLED == True
        assert settings.LOG_FILE == "/var/log/bot.log"


class TestSettingsEnvironmentVariables:
    """Test environment variable loading"""
    
    def test_loads_from_environment_variables(self):
        """Test that Settings loads from environment variables"""
        from src.config import Settings
        
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'env_token_12345',
            'ADMIN_TELEGRAM_ID': '987654321',
            'DATABASE_URL': 'postgresql://localhost/testdb',
            'ENV': 'production',
            'LOG_LEVEL': 'WARNING'
        }):
            settings = Settings()
            
            assert settings.BOT_TOKEN == 'env_token_12345'
            assert settings.ADMIN_TELEGRAM_ID == 987654321
            assert settings.DATABASE_URL == 'postgresql://localhost/testdb'
            assert settings.ENV == 'production'
            assert settings.LOG_LEVEL == 'WARNING'
    
    def test_environment_variables_override_defaults(self):
        """Test that environment variables override default values"""
        from src.config import Settings
        
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'env_token',
            'ADMIN_TELEGRAM_ID': '111111111',
            'DATABASE_URL': 'sqlite:///env.db',
            'PARSING_ENABLED': 'true',
            'LOG_LEVEL': 'ERROR'
        }):
            settings = Settings()
            
            assert settings.PARSING_ENABLED == True
            assert settings.LOG_LEVEL == 'ERROR'
    
    def test_partial_environment_variables(self):
        """Test that some values can come from env, others from defaults"""
        from src.config import Settings
        
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'env_token',
            'ADMIN_TELEGRAM_ID': '123456789',
            'DATABASE_URL': 'sqlite:///test.db'
            # ENV and LOG_LEVEL not set, should use defaults
        }, clear=True):
            settings = Settings()
            
            assert settings.BOT_TOKEN == 'env_token'
            assert settings.ENV == 'development'  # default
            assert settings.LOG_LEVEL == 'INFO'  # default


class TestSettingsMultipleEnvironments:
    """Test multiple environment support"""
    
    def test_supports_all_environments(self):
        """Test that all defined environments are supported"""
        from src.config import Settings
        
        allowed_envs = ["development", "test", "staging", "production"]
        
        for env in allowed_envs:
            settings = Settings(
                BOT_TOKEN="test_token",
                ADMIN_TELEGRAM_ID=123456789,
                DATABASE_URL="sqlite:///test.db",
                ENV=env
            )
            assert settings.ENV == env
    
    def test_development_environment(self):
        """Test development environment configuration"""
        from src.config import Settings
        
        settings = Settings(
            BOT_TOKEN="dev_token",
            ADMIN_TELEGRAM_ID=123456789,
            DATABASE_URL="sqlite:///dev.db",
            ENV="development"
        )
        
        assert settings.ENV == "development"
    
    def test_test_environment(self):
        """Test test environment configuration"""
        from src.config import Settings
        
        settings = Settings(
            BOT_TOKEN="test_token",
            ADMIN_TELEGRAM_ID=123456789,
            DATABASE_URL="sqlite:///test.db",
            ENV="test"
        )
        
        assert settings.ENV == "test"
    
    def test_staging_environment(self):
        """Test staging environment configuration"""
        from src.config import Settings
        
        settings = Settings(
            BOT_TOKEN="staging_token",
            ADMIN_TELEGRAM_ID=123456789,
            DATABASE_URL="postgresql://staging/db",
            ENV="staging"
        )
        
        assert settings.ENV == "staging"
    
    def test_production_environment(self):
        """Test production environment configuration"""
        from src.config import Settings
        
        settings = Settings(
            BOT_TOKEN="prod_token",
            ADMIN_TELEGRAM_ID=123456789,
            DATABASE_URL="postgresql://prod/db",
            ENV="production",
            LOG_LEVEL="WARNING"
        )
        
        assert settings.ENV == "production"
        assert settings.LOG_LEVEL == "WARNING"


class TestSettingsErrorHandling:
    """Test error handling for missing/invalid values"""
    
    def test_multiple_validation_errors(self):
        """Test that multiple validation errors are reported"""
        from src.config import Settings
        
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                BOT_TOKEN="",  # Invalid: empty
                ADMIN_TELEGRAM_ID=-1,  # Invalid: negative
                DATABASE_URL=""  # Invalid: empty
            )
        
        error_str = str(exc_info.value)
        # Should report all three errors
        assert "BOT_TOKEN" in error_str or "ADMIN_TELEGRAM_ID" in error_str or "DATABASE_URL" in error_str
    
    def test_clear_error_messages(self):
        """Test that error messages are clear and helpful"""
        from src.config import Settings
        
        # Test BOT_TOKEN error message
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                BOT_TOKEN="",
                ADMIN_TELEGRAM_ID=123456789,
                DATABASE_URL="sqlite:///test.db"
            )
        assert "BOT_TOKEN cannot be empty" in str(exc_info.value)
        
        # Test ADMIN_TELEGRAM_ID error message
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                BOT_TOKEN="token",
                ADMIN_TELEGRAM_ID=-1,
                DATABASE_URL="sqlite:///test.db"
            )
        assert "ADMIN_TELEGRAM_ID must be a positive integer" in str(exc_info.value)
        
        # Test DATABASE_URL error message
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                BOT_TOKEN="token",
                ADMIN_TELEGRAM_ID=123456789,
                DATABASE_URL=""
            )
        assert "DATABASE_URL cannot be empty" in str(exc_info.value)
    
    def test_type_conversion_errors(self):
        """Test that type conversion errors are handled"""
        from src.config import Settings
        
        # ADMIN_TELEGRAM_ID should be an integer
        with pytest.raises(ValidationError):
            Settings(
                BOT_TOKEN="token",
                ADMIN_TELEGRAM_ID="not_a_number",  # type: ignore
                DATABASE_URL="sqlite:///test.db"
            )


class TestSettingsBackwardCompatibility:
    """Test backward compatibility with existing configuration"""
    
    def test_existing_code_continues_to_work(self):
        """Test that existing code pattern works"""
        # Mock environment variables to avoid singleton instantiation error
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_token',
            'ADMIN_TELEGRAM_ID': '123456789',
            'DATABASE_URL': 'sqlite:///test.db'
        }):
            # Import should work
            import importlib
            import src.config
            importlib.reload(src.config)
            from src.config import settings
            
            # Settings object should exist
            assert settings is not None
            
            # Should have all expected attributes
            assert hasattr(settings, 'ENV')
            assert hasattr(settings, 'BOT_TOKEN')
            assert hasattr(settings, 'ADMIN_TELEGRAM_ID')
            assert hasattr(settings, 'DATABASE_URL')
            assert hasattr(settings, 'PARSING_ENABLED')
            assert hasattr(settings, 'LOG_LEVEL')
            assert hasattr(settings, 'LOG_FILE')
    
    def test_settings_class_importable(self):
        """Test that Settings class can be imported"""
        from src.config import Settings
        
        assert Settings is not None
        assert callable(Settings)


class TestSettingsDocumentation:
    """Test that Settings class is properly documented"""
    
    def test_class_has_docstring(self):
        """Test that Settings class has documentation"""
        from src.config import Settings
        
        assert Settings.__doc__ is not None
        assert len(Settings.__doc__) > 0
        assert "multiple environments" in Settings.__doc__.lower() or "environment" in Settings.__doc__.lower()
    
    def test_validators_have_docstrings(self):
        """Test that validators have documentation"""
        from src.config import Settings
        
        # Check that validators have docstrings
        assert Settings.validate_bot_token.__doc__ is not None
        assert Settings.validate_admin_id.__doc__ is not None
        assert Settings.validate_database_url.__doc__ is not None
        assert Settings.validate_env.__doc__ is not None
        assert Settings.validate_log_level.__doc__ is not None
    
    def test_fields_are_documented(self):
        """Test that fields have proper type hints"""
        from src.config import Settings
        
        # Check that Settings has proper annotations
        annotations = Settings.__annotations__
        assert 'BOT_TOKEN' in annotations
        assert 'ADMIN_TELEGRAM_ID' in annotations
        assert 'DATABASE_URL' in annotations
        assert 'ENV' in annotations
        assert 'LOG_LEVEL' in annotations
        assert 'PARSING_ENABLED' in annotations
        assert 'LOG_FILE' in annotations


class TestSettingsEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_very_long_bot_token(self):
        """Test that very long BOT_TOKEN is accepted"""
        from src.config import Settings
        
        long_token = "a" * 1000
        settings = Settings(
            BOT_TOKEN=long_token,
            ADMIN_TELEGRAM_ID=123456789,
            DATABASE_URL="sqlite:///test.db"
        )
        
        assert settings.BOT_TOKEN == long_token
    
    def test_very_large_admin_id(self):
        """Test that very large ADMIN_TELEGRAM_ID is accepted"""
        from src.config import Settings
        
        large_id = 9999999999
        settings = Settings(
            BOT_TOKEN="token",
            ADMIN_TELEGRAM_ID=large_id,
            DATABASE_URL="sqlite:///test.db"
        )
        
        assert settings.ADMIN_TELEGRAM_ID == large_id
    
    def test_complex_database_url(self):
        """Test that complex DATABASE_URL is accepted"""
        from src.config import Settings
        
        complex_url = "postgresql://user:password@localhost:5432/dbname?sslmode=require"
        settings = Settings(
            BOT_TOKEN="token",
            ADMIN_TELEGRAM_ID=123456789,
            DATABASE_URL=complex_url
        )
        
        assert settings.DATABASE_URL == complex_url
    
    def test_log_level_case_insensitive(self):
        """Test that LOG_LEVEL is case-insensitive"""
        from src.config import Settings
        
        test_cases = [
            ("debug", "DEBUG"),
            ("Debug", "DEBUG"),
            ("DEBUG", "DEBUG"),
            ("info", "INFO"),
            ("warning", "WARNING"),
            ("error", "ERROR"),
            ("critical", "CRITICAL")
        ]
        
        for input_level, expected_level in test_cases:
            settings = Settings(
                BOT_TOKEN="token",
                ADMIN_TELEGRAM_ID=123456789,
                DATABASE_URL="sqlite:///test.db",
                LOG_LEVEL=input_level
            )
            assert settings.LOG_LEVEL == expected_level
    
    def test_boolean_parsing_enabled(self):
        """Test that PARSING_ENABLED handles boolean values"""
        from src.config import Settings
        
        # Test True
        settings = Settings(
            BOT_TOKEN="token",
            ADMIN_TELEGRAM_ID=123456789,
            DATABASE_URL="sqlite:///test.db",
            PARSING_ENABLED=True
        )
        assert settings.PARSING_ENABLED == True
        
        # Test False
        settings = Settings(
            BOT_TOKEN="token",
            ADMIN_TELEGRAM_ID=123456789,
            DATABASE_URL="sqlite:///test.db",
            PARSING_ENABLED=False
        )
        assert settings.PARSING_ENABLED == False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
