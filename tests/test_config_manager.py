"""
Unit tests for Configuration Management System
Tests configuration loading, validation, hot reload, and error handling
"""

import os
import sys
import tempfile
import pytest
import yaml
import json
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, mock_open

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config_manager import ConfigurationManager, get_config_manager, reload_global_configuration
from core.advanced_models import BotConfig, ParsingRule, ConfigurationError
from database.database import ParsingRule as DBParsingRule


class TestConfigurationManager:
    """Test cases for ConfigurationManager class"""
    
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
    
    def test_default_configuration_creation(self):
        """Test creation of default configuration with all required settings"""
        with patch('core.config_manager.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = iter([mock_db])
            mock_db.query.return_value.filter.return_value.all.return_value = []
            mock_db.close = Mock()
            
            config = self.config_manager.get_default_configuration()
            
            assert isinstance(config, BotConfig)
            assert isinstance(config.parsing_rules, list)
            assert isinstance(config.admin_user_ids, list)
            assert config.sticker_cleanup_interval == 300
            assert config.sticker_auto_delete_delay == 120
            assert config.broadcast_batch_size == 50
            assert config.max_parsing_retries == 3
    
    def test_parsing_rules_loading_from_database(self):
        """Test loading parsing rules from database configuration table"""
        # Create mock database rules
        mock_rule1 = Mock()
        mock_rule1.id = 1
        mock_rule1.bot_name = 'TestBot1'
        mock_rule1.pattern = r'Coins: \+(\d+)'
        mock_rule1.multiplier = Decimal('1.5')
        mock_rule1.currency_type = 'coins'
        mock_rule1.is_active = True
        
        mock_rule2 = Mock()
        mock_rule2.id = 2
        mock_rule2.bot_name = 'TestBot2'
        mock_rule2.pattern = r'Points: \+(\d+)'
        mock_rule2.multiplier = Decimal('2.0')
        mock_rule2.currency_type = 'points'
        mock_rule2.is_active = True
        
        with patch('core.config_manager.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = iter([mock_db])  # Make it an iterator
            mock_db.query.return_value.filter.return_value.all.return_value = [mock_rule1, mock_rule2]
            mock_db.close = Mock()
            
            rules = self.config_manager.load_parsing_rules_from_database()
            
            assert len(rules) == 2
            assert rules[0].bot_name == 'TestBot1'
            assert rules[0].pattern == r'Coins: \+(\d+)'
            assert rules[0].multiplier == Decimal('1.5')
            assert rules[1].bot_name == 'TestBot2'
            assert rules[1].multiplier == Decimal('2.0')
    
    def test_configuration_validation_success(self):
        """Test successful configuration validation"""
        # Create valid configuration
        parsing_rules = [
            ParsingRule(
                id=1,
                bot_name='TestBot',
                pattern=r'Test: \+(\d+)',
                multiplier=Decimal('1.0'),
                currency_type='test',
                is_active=True
            )
        ]
        
        config = BotConfig(
            parsing_rules=parsing_rules,
            admin_user_ids=[123456789],
            sticker_cleanup_interval=300,
            sticker_auto_delete_delay=120,
            broadcast_batch_size=50,
            max_parsing_retries=3
        )
        
        errors = self.config_manager.validate_configuration(config)
        assert len(errors) == 0
    
    def test_configuration_validation_errors(self):
        """Test configuration validation with various error conditions"""
        # Create invalid configuration
        parsing_rules = [
            ParsingRule(
                id=1,
                bot_name='',  # Empty bot name
                pattern='[invalid regex',  # Invalid regex
                multiplier=Decimal('-1.0'),  # Negative multiplier
                currency_type='',  # Empty currency type
                is_active=True
            )
        ]
        
        config = BotConfig(
            parsing_rules=parsing_rules,
            admin_user_ids=[],  # Empty admin list
            sticker_cleanup_interval=-1,  # Invalid interval
            sticker_auto_delete_delay=0,  # Invalid delay
            broadcast_batch_size=-10,  # Invalid batch size
            max_parsing_retries=0  # Invalid retries
        )
        
        errors = self.config_manager.validate_configuration(config)
        
        # Should have multiple validation errors
        assert len(errors) > 0
        
        # Check for specific error types
        error_text = ' '.join(errors)
        assert 'Empty bot name' in error_text
        assert 'Invalid regex pattern' in error_text
        assert 'Invalid multiplier' in error_text
        assert 'Empty currency type' in error_text
        assert 'No admin user IDs configured' in error_text
    
    def test_yaml_configuration_file_loading(self):
        """Test loading configuration from YAML file"""
        # Create test YAML configuration
        config_data = {
            'admin_user_ids': [123456789, 987654321],
            'sticker_cleanup_interval': 600,
            'sticker_auto_delete_delay': 180,
            'broadcast_batch_size': 100,
            'max_parsing_retries': 5
        }
        
        with open(self.config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        with patch('core.config_manager.get_db') as mock_get_db:
            mock_get_db.return_value = [self.mock_db]
            self.mock_db.query.return_value.filter.return_value.all.return_value = []
            
            # Reload configuration
            success = self.config_manager.reload_configuration()
            
            assert success
            config = self.config_manager.get_configuration()
            assert config.admin_user_ids == [123456789, 987654321]
            assert config.sticker_cleanup_interval == 600
            assert config.broadcast_batch_size == 100
    
    def test_json_configuration_file_loading(self):
        """Test loading configuration from JSON file"""
        # Change to JSON file
        json_file = os.path.join(self.temp_dir, 'test_config.json')
        self.config_manager.config_file_path = json_file
        
        # Create test JSON configuration
        config_data = {
            'admin_user_ids': [111111111],
            'sticker_cleanup_interval': 450,
            'max_parsing_retries': 2
        }
        
        with open(json_file, 'w') as f:
            json.dump(config_data, f)
        
        with patch('core.config_manager.get_db') as mock_get_db:
            mock_get_db.return_value = [self.mock_db]
            self.mock_db.query.return_value.filter.return_value.all.return_value = []
            
            # Reload configuration
            success = self.config_manager.reload_configuration()
            
            assert success
            config = self.config_manager.get_configuration()
            assert config.admin_user_ids == [111111111]
            assert config.sticker_cleanup_interval == 450
            assert config.max_parsing_retries == 2
    
    def test_hot_reload_capability(self):
        """Test hot reload capability for configuration changes"""
        # Create initial configuration
        initial_config = {
            'admin_user_ids': [123456789],
            'broadcast_batch_size': 50
        }
        
        with open(self.config_file, 'w') as f:
            yaml.dump(initial_config, f)
        
        with patch('core.config_manager.get_db') as mock_get_db:
            mock_get_db.return_value = [self.mock_db]
            self.mock_db.query.return_value.filter.return_value.all.return_value = []
            
            # Initial load
            self.config_manager.reload_configuration()
            config1 = self.config_manager.get_configuration()
            assert config1.broadcast_batch_size == 50
            
            # Update configuration file
            updated_config = {
                'admin_user_ids': [123456789],
                'broadcast_batch_size': 100
            }
            
            with open(self.config_file, 'w') as f:
                yaml.dump(updated_config, f)
            
            # Hot reload
            success = self.config_manager.reload_configuration()
            assert success
            
            config2 = self.config_manager.get_configuration()
            assert config2.broadcast_batch_size == 100
            assert self.config_manager.last_reload_time is not None
    
    def test_invalid_file_format_handling(self):
        """Test handling of invalid configuration file formats"""
        # Create invalid YAML file
        with open(self.config_file, 'w') as f:
            f.write("invalid: yaml: content: [unclosed")
        
        with patch('core.config_manager.get_db') as mock_get_db:
            mock_get_db.return_value = [self.mock_db]
            self.mock_db.query.return_value.filter.return_value.all.return_value = []
            
            # Should fall back to defaults
            success = self.config_manager.reload_configuration()
            
            # Should still have configuration (defaults)
            config = self.config_manager.get_configuration()
            assert config is not None
            
            # Should have validation errors
            errors = self.config_manager.get_validation_errors()
            assert len(errors) > 0
    
    def test_missing_configuration_file_handling(self):
        """Test handling when configuration file doesn't exist"""
        # Use non-existent file path
        non_existent_file = os.path.join(self.temp_dir, 'non_existent.yaml')
        self.config_manager.config_file_path = non_existent_file
        
        with patch('core.config_manager.get_db') as mock_get_db:
            mock_get_db.return_value = [self.mock_db]
            self.mock_db.query.return_value.filter.return_value.all.return_value = []
            
            # Should use defaults when file doesn't exist
            success = self.config_manager.reload_configuration()
            assert success
            
            config = self.config_manager.get_configuration()
            assert config is not None
            assert isinstance(config.admin_user_ids, list)
    
    def test_database_error_handling(self):
        """Test handling of database connection errors"""
        with patch('core.config_manager.get_db') as mock_get_db:
            # Simulate database error
            mock_get_db.side_effect = Exception("Database connection failed")
            
            # Should fall back to default rules
            rules = self.config_manager.load_parsing_rules_from_database()
            
            # Should return default rules
            assert len(rules) >= 2  # Default Shmalala and GDcards rules
            assert any(rule.bot_name == 'Shmalala' for rule in rules)
            assert any(rule.bot_name == 'GDcards' for rule in rules)
    
    def test_health_status_reporting(self):
        """Test configuration system health status reporting"""
        with patch('core.config_manager.get_db') as mock_get_db:
            mock_get_db.return_value = [self.mock_db]
            self.mock_db.execute.return_value = None  # Simulate successful DB query
            
            health = self.config_manager.get_health_status()
            
            assert hasattr(health, 'is_healthy')
            assert hasattr(health, 'database_connected')
            assert hasattr(health, 'parsing_active')
            assert hasattr(health, 'last_check')
            assert isinstance(health.errors, list)
    
    def test_parsing_rule_addition(self):
        """Test adding new parsing rules to database"""
        with patch('core.config_manager.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = iter([mock_db])  # Make it an iterator
            
            # Mock database operations
            mock_db.query.return_value.filter.return_value.first.return_value = None  # No existing rule
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.close = Mock()
            
            # Mock reload_configuration to avoid recursive calls
            with patch.object(self.config_manager, 'reload_configuration', return_value=True):
                # Add new parsing rule
                success = self.config_manager.add_parsing_rule(
                    bot_name='NewBot',
                    pattern=r'Credits: \+(\d+)',
                    multiplier=Decimal('1.2'),
                    currency_type='credits'
                )
            
            assert success
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
    
    def test_parsing_rule_update(self):
        """Test updating existing parsing rules"""
        with patch('core.config_manager.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = iter([mock_db])  # Make it an iterator
            
            # Mock existing rule
            mock_rule = Mock()
            mock_rule.id = 1
            mock_rule.multiplier = Decimal('1.0')
            
            mock_db.query.return_value.filter.return_value.first.return_value = mock_rule
            mock_db.commit = Mock()
            mock_db.close = Mock()
            
            # Mock reload_configuration to avoid recursive calls
            with patch.object(self.config_manager, 'reload_configuration', return_value=True):
                # Update parsing rule
                success = self.config_manager.update_parsing_rule(
                    rule_id=1,
                    multiplier=Decimal('2.0')
                )
            
            assert success
            assert mock_rule.multiplier == Decimal('2.0')
            mock_db.commit.assert_called_once()
    
    def test_configuration_template_saving(self):
        """Test saving configuration template file"""
        template_file = os.path.join(self.temp_dir, 'template.yaml')
        self.config_manager.config_file_path = template_file
        
        success = self.config_manager.save_configuration_template()
        
        assert success
        assert os.path.exists(template_file)
        
        # Verify template content
        with open(template_file, 'r') as f:
            template_data = yaml.safe_load(f)
        
        assert 'admin_user_ids' in template_data
        assert 'sticker_cleanup_interval' in template_data
        assert 'broadcast_batch_size' in template_data
    
    def test_botconfig_to_dict_conversion(self):
        """Test BotConfig to_dict method for serialization"""
        from core.advanced_models import BotConfig, ParsingRule
        from decimal import Decimal
        
        # Create test configuration
        parsing_rules = [
            ParsingRule(
                id=1,
                bot_name='TestBot',
                pattern=r'Test: \+(\d+)',
                multiplier=Decimal('1.5'),
                currency_type='test',
                is_active=True
            )
        ]
        
        config = BotConfig(
            parsing_rules=parsing_rules,
            admin_user_ids=[123456789],
            sticker_cleanup_interval=300,
            sticker_auto_delete_delay=120,
            broadcast_batch_size=50,
            max_parsing_retries=3
        )
        
        # Convert to dictionary
        config_dict = config.to_dict()
        
        # Verify structure
        assert 'parsing_rules' in config_dict
        assert 'admin_user_ids' in config_dict
        assert len(config_dict['parsing_rules']) == 1
        assert config_dict['parsing_rules'][0]['bot_name'] == 'TestBot'
        assert config_dict['parsing_rules'][0]['multiplier'] == 1.5
        assert config_dict['admin_user_ids'] == [123456789]
    
    def test_botconfig_from_dict_creation(self):
        """Test BotConfig from_dict method for deserialization"""
        from core.advanced_models import BotConfig
        
        # Create test data
        config_data = {
            'parsing_rules': [
                {
                    'id': 1,
                    'bot_name': 'TestBot',
                    'pattern': r'Test: \+(\d+)',
                    'multiplier': 1.5,
                    'currency_type': 'test',
                    'is_active': True
                }
            ],
            'admin_user_ids': [123456789],
            'sticker_cleanup_interval': 300,
            'sticker_auto_delete_delay': 120,
            'broadcast_batch_size': 50,
            'max_parsing_retries': 3
        }
        
        # Create configuration from dictionary
        config = BotConfig.from_dict(config_data)
        
        # Verify configuration
        assert len(config.parsing_rules) == 1
        assert config.parsing_rules[0].bot_name == 'TestBot'
        assert config.parsing_rules[0].multiplier == Decimal('1.5')
        assert config.admin_user_ids == [123456789]
        assert config.sticker_cleanup_interval == 300
    
    def test_botconfig_schema_validation(self):
        """Test BotConfig schema validation method"""
        from core.advanced_models import BotConfig, ParsingRule
        from decimal import Decimal
        
        # Create valid configuration
        valid_config = BotConfig(
            parsing_rules=[],
            admin_user_ids=[123456789],
            sticker_cleanup_interval=300,
            sticker_auto_delete_delay=120,
            broadcast_batch_size=50,
            max_parsing_retries=3
        )
        
        # Test valid configuration
        errors = valid_config.validate_schema()
        assert len(errors) == 0
        
        # Create invalid configuration
        invalid_config = BotConfig(
            parsing_rules="not a list",  # Invalid type
            admin_user_ids=[-1, "invalid"],  # Invalid values
            sticker_cleanup_interval=-1,  # Invalid value
            sticker_auto_delete_delay=0,  # Invalid value
            broadcast_batch_size=-10,  # Invalid value
            max_parsing_retries=0  # Invalid value
        )
        
        # Test invalid configuration
        errors = invalid_config.validate_schema()
        assert len(errors) > 0
        
        # Check for specific error types
        error_text = ' '.join(errors)
        assert 'parsing_rules must be a list' in error_text
        assert 'admin_user_ids must contain positive integers' in error_text
        assert 'sticker_cleanup_interval must be a positive integer' in error_text
    
    def test_configuration_export_functionality(self):
        """Test configuration export functionality"""
        with patch('core.config_manager.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = iter([mock_db])
            mock_db.query.return_value.filter.return_value.all.return_value = []
            mock_db.close = Mock()
            
            # Export configuration
            export_data = self.config_manager.export_configuration(include_parsing_rules=True)
            
            # Verify export structure
            assert 'export_timestamp' in export_data
            assert 'export_version' in export_data
            assert 'configuration' in export_data
            assert 'parsing_rules' in export_data
            
            # Verify configuration section
            config_section = export_data['configuration']
            assert 'admin_user_ids' in config_section
            assert 'sticker_cleanup_interval' in config_section
            assert 'broadcast_batch_size' in config_section
    
    def test_configuration_import_functionality(self):
        """Test configuration import functionality"""
        with patch('core.config_manager.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = iter([mock_db])
            mock_db.query.return_value.filter.return_value.all.return_value = []
            mock_db.close = Mock()
            
            # Create test import data
            import_data = {
                'export_timestamp': '2024-01-01T00:00:00',
                'export_version': '1.0',
                'configuration': {
                    'admin_user_ids': [987654321],
                    'sticker_cleanup_interval': 600,
                    'sticker_auto_delete_delay': 180,
                    'broadcast_batch_size': 100,
                    'max_parsing_retries': 5
                }
            }
            
            # Mock file operations
            with patch('builtins.open', mock_open()) as mock_file:
                with patch('yaml.dump') as mock_yaml_dump:
                    # Import configuration
                    success = self.config_manager.import_configuration(import_data, import_parsing_rules=False)
                    
                    # Verify import was attempted
                    assert mock_file.called
                    assert mock_yaml_dump.called
    
    def test_configuration_backup_creation(self):
        """Test configuration backup creation"""
        with patch('core.config_manager.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = iter([mock_db])
            mock_db.query.return_value.filter.return_value.all.return_value = []
            mock_db.close = Mock()
            
            # Mock file operations
            with patch('builtins.open', mock_open()) as mock_file:
                with patch('os.makedirs') as mock_makedirs:
                    # Create backup
                    backup_id = self.config_manager.create_configuration_backup(
                        description="Test backup",
                        created_by=123456789
                    )
                    
                    # Verify backup was created
                    assert backup_id is not None
                    assert isinstance(backup_id, str)
                    assert len(backup_id) > 0
                    
                    # Verify file operations were called
                    assert mock_makedirs.called
                    assert mock_file.called
    
    def test_configuration_backup_listing(self):
        """Test configuration backup listing"""
        # Mock backup directory with test files
        backup_dir = os.path.join(self.temp_dir, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Create test backup files
        test_backup_data = {
            'backup_id': 'test-backup-123',
            'created_at': '2024-01-01T00:00:00',
            'description': 'Test backup',
            'created_by': 123456789,
            'config_data': {}
        }
        
        backup_file = os.path.join(backup_dir, 'config_backup_test-backup-123.json')
        with open(backup_file, 'w') as f:
            json.dump(test_backup_data, f)
        
        # Update config manager to use test directory
        self.config_manager.config_file_path = os.path.join(self.temp_dir, 'test_config.yaml')
        
        # List backups
        backups = self.config_manager.list_configuration_backups()
        
        # Verify backup listing
        assert len(backups) == 1
        assert backups[0]['backup_id'] == 'test-backup-123'
        assert backups[0]['description'] == 'Test backup'
        assert backups[0]['created_by'] == 123456789
    
    def test_enhanced_configuration_validation(self):
        """Test enhanced configuration validation with business rules"""
        from core.advanced_models import BotConfig, ParsingRule
        from decimal import Decimal
        
        # Create configuration with business rule violations
        config = BotConfig(
            parsing_rules=[],
            admin_user_ids=[123456789],
            sticker_cleanup_interval=30,  # Too short (< 60)
            sticker_auto_delete_delay=15,  # Too short (< 30)
            broadcast_batch_size=150,  # Too large (> 100)
            max_parsing_retries=15  # Too many (> 10)
        )
        
        # Test enhanced validation
        errors = self.config_manager.validate_configuration_schema(config)
        
        # Verify business rule validation
        error_text = ' '.join(errors)
        assert 'should be at least 60 seconds' in error_text
        assert 'should be at least 30 seconds' in error_text
        assert 'should not exceed 100' in error_text
        assert 'should not exceed 10' in error_text


class TestGlobalConfigurationFunctions:
    """Test cases for global configuration functions"""
    
    def test_get_config_manager_singleton(self):
        """Test that get_config_manager returns singleton instance"""
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, ConfigurationManager)
    
    def test_reload_global_configuration(self):
        """Test global configuration reload function"""
        with patch.object(get_config_manager(), 'reload_configuration') as mock_reload:
            mock_reload.return_value = True
            
            success = reload_global_configuration()
            
            assert success
            mock_reload.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__])