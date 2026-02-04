"""
Integration tests for Configuration Management System
Tests integration between configuration system and message parser
"""

import os
import sys
import tempfile
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config_manager import ConfigurationManager
from core.message_parser import MessageParser
from core.advanced_models import ParsingRule


class TestConfigurationIntegration:
    """Integration tests for configuration system with message parser"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_config.yaml')
        
        # Create mock database session
        self.mock_db = Mock()
        
        # Create test configuration manager
        self.config_manager = ConfigurationManager(self.config_file)
    
    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_message_parser_uses_configuration_rules(self):
        """Test that MessageParser uses rules from configuration system"""
        # Create test parsing rules
        test_rules = [
            ParsingRule(
                id=1,
                bot_name='TestBot',
                pattern=r'Coins: \+(\d+)',
                multiplier=Decimal('1.5'),
                currency_type='coins',
                is_active=True
            ),
            ParsingRule(
                id=2,
                bot_name='AnotherBot',
                pattern=r'Points: \+(\d+)',
                multiplier=Decimal('2.0'),
                currency_type='points',
                is_active=True
            )
        ]
        
        with patch('core.message_parser.get_config_manager') as mock_get_config_manager:
            # Mock the config manager to return our test rules
            mock_config_manager = Mock()
            mock_config = Mock()
            mock_config.parsing_rules = test_rules
            mock_config_manager.get_configuration.return_value = mock_config
            mock_get_config_manager.return_value = mock_config_manager
            
            # Create message parser with mocked database
            message_parser = MessageParser(self.mock_db)
            
            # Verify parser loaded the rules from configuration
            assert len(message_parser.parsing_rules) == 2
            assert message_parser.parsing_rules[0].bot_name == 'TestBot'
            assert message_parser.parsing_rules[0].multiplier == Decimal('1.5')
            assert message_parser.parsing_rules[1].bot_name == 'AnotherBot'
            assert message_parser.parsing_rules[1].multiplier == Decimal('2.0')
    
    def test_configuration_hot_reload_updates_parser(self):
        """Test that configuration hot reload updates message parser rules"""
        # Initial rules
        initial_rules = [
            ParsingRule(
                id=1,
                bot_name='InitialBot',
                pattern=r'Initial: \+(\d+)',
                multiplier=Decimal('1.0'),
                currency_type='initial',
                is_active=True
            )
        ]
        
        # Updated rules after reload
        updated_rules = [
            ParsingRule(
                id=1,
                bot_name='InitialBot',
                pattern=r'Initial: \+(\d+)',
                multiplier=Decimal('2.0'),  # Changed multiplier
                currency_type='initial',
                is_active=True
            ),
            ParsingRule(
                id=2,
                bot_name='NewBot',
                pattern=r'New: \+(\d+)',
                multiplier=Decimal('1.5'),
                currency_type='new',
                is_active=True
            )
        ]
        
        with patch('core.message_parser.get_config_manager') as mock_get_config_manager:
            # Mock the config manager
            mock_config_manager = Mock()
            mock_get_config_manager.return_value = mock_config_manager
            
            # Create message parser
            message_parser = MessageParser(self.mock_db)
            
            # Mock initial configuration load
            mock_config = Mock()
            mock_config.parsing_rules = initial_rules
            mock_config_manager.get_configuration.return_value = mock_config
            
            message_parser.load_parsing_rules()
            
            # Verify initial state
            assert len(message_parser.parsing_rules) == 1
            assert message_parser.parsing_rules[0].multiplier == Decimal('1.0')
            
            # Mock configuration reload with updated rules
            mock_config.parsing_rules = updated_rules
            mock_config_manager.reload_configuration.return_value = True
            
            # Perform hot reload
            success = message_parser.reload_configuration()
            
            assert success
            # Verify updated state
            assert len(message_parser.parsing_rules) == 2
            assert message_parser.parsing_rules[0].multiplier == Decimal('2.0')
            assert message_parser.parsing_rules[1].bot_name == 'NewBot'
    
    def test_configuration_validation_prevents_invalid_rules(self):
        """Test that configuration validation prevents invalid parsing rules"""
        # Create invalid parsing rule
        invalid_rule = ParsingRule(
            id=1,
            bot_name='',  # Empty bot name
            pattern='[invalid regex',  # Invalid regex
            multiplier=Decimal('-1.0'),  # Negative multiplier
            currency_type='',  # Empty currency type
            is_active=True
        )
        
        # Create a valid config with invalid rule for testing
        from core.advanced_models import BotConfig
        invalid_config = BotConfig(
            parsing_rules=[invalid_rule],
            admin_user_ids=[123456789],
            sticker_cleanup_interval=300,
            sticker_auto_delete_delay=120,
            broadcast_batch_size=50,
            max_parsing_retries=3
        )
        
        # Test validation directly
        errors = self.config_manager.validate_configuration(invalid_config)
        assert len(errors) > 0
        
        # Verify specific validation errors
        error_text = ' '.join(errors)
        assert 'Empty bot name' in error_text
        assert 'Invalid regex pattern' in error_text
        assert 'Invalid multiplier' in error_text
    
    def test_configuration_fallback_on_database_error(self):
        """Test that configuration falls back to defaults on database errors"""
        with patch('core.config_manager.get_db') as mock_get_db:
            # Simulate database connection error
            mock_get_db.side_effect = Exception("Database connection failed")
            
            # Configuration should still work with defaults
            config = self.config_manager.get_configuration()
            
            assert config is not None
            assert isinstance(config.parsing_rules, list)
            assert len(config.parsing_rules) >= 2  # Should have default rules
            
            # Should have default Shmalala and GDcards rules
            bot_names = [rule.bot_name for rule in config.parsing_rules]
            assert 'Shmalala' in bot_names
            assert 'GDcards' in bot_names


if __name__ == '__main__':
    pytest.main([__file__])