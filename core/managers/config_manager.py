"""
Configuration Management System for Advanced Telegram Bot Features
Implements parsing rules loading from database, validation, default values, and hot reload
"""

import os
import sys
import json
import yaml
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Union
from sqlalchemy.orm import Session
from pathlib import Path
import structlog

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import ParsingRule, get_db
from core.models.advanced_models import (
    BotConfig, ParsingRule as AdvancedParsingRule, 
    ConfigurationError, HealthStatus, ConfigurationBackup
)

logger = structlog.get_logger()


class ConfigurationManager:
    """
    Comprehensive configuration management system for the advanced bot features
    Implements Requirements 11.1, 11.2, 11.3, 11.4, 11.5
    """
    
    def __init__(self, config_file_path: Optional[str] = None):
        """
        Initialize ConfigurationManager
        
        Args:
            config_file_path: Optional path to configuration file
        """
        self.config_file_path = config_file_path or self._get_default_config_path()
        self.config: Optional[BotConfig] = None
        self.last_reload_time: Optional[datetime] = None
        self.file_watch_enabled = True
        self.validation_errors: List[str] = []
        
        # Load initial configuration
        self.reload_configuration()
    
    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(root_dir, 'config', 'bot_config.yaml')
    
    def load_parsing_rules_from_database(self) -> List[AdvancedParsingRule]:
        """
        Load parsing rules from database configuration table
        
        Returns:
            List of active parsing rules from database
            
        Validates: Requirements 11.1
        """
        try:
            logger.info("Loading parsing rules from database")
            
            db = next(get_db())
            try:
                # Query active parsing rules from database
                db_rules = db.query(ParsingRule).filter(ParsingRule.is_active == True).all()
                
                # Convert to advanced model objects
                parsing_rules = []
                for db_rule in db_rules:
                    rule = AdvancedParsingRule(
                        id=db_rule.id,
                        bot_name=db_rule.bot_name,
                        pattern=db_rule.pattern,
                        multiplier=db_rule.multiplier,
                        currency_type=db_rule.currency_type,
                        is_active=db_rule.is_active
                    )
                    parsing_rules.append(rule)
                
                logger.info(f"Successfully loaded {len(parsing_rules)} parsing rules from database")
                return parsing_rules
                
            finally:
                db.close()
                
        except Exception as e:
            error_msg = f"Failed to load parsing rules from database: {str(e)}"
            logger.error(error_msg)
            self.validation_errors.append(error_msg)
            
            # Return default rules on error
            return self._get_default_parsing_rules()
    
    def validate_configuration(self, config: BotConfig) -> List[str]:
        """
        Validate configuration with comprehensive error reporting
        
        Args:
            config: BotConfig object to validate
            
        Returns:
            List of validation error messages (empty if valid)
            
        Validates: Requirements 11.4
        """
        errors = []
        
        try:
            # Validate parsing rules
            if not config.parsing_rules:
                errors.append("No parsing rules configured")
            else:
                for i, rule in enumerate(config.parsing_rules):
                    rule_errors = self._validate_parsing_rule(rule, i)
                    errors.extend(rule_errors)
            
            # Validate admin user IDs
            if not config.admin_user_ids:
                errors.append("No admin user IDs configured")
            else:
                for i, admin_id in enumerate(config.admin_user_ids):
                    if not isinstance(admin_id, int) or admin_id <= 0:
                        errors.append(f"Invalid admin user ID at index {i}: {admin_id}")
            
            # Validate timing configurations
            if config.sticker_cleanup_interval <= 0:
                errors.append(f"Invalid sticker cleanup interval: {config.sticker_cleanup_interval}")
            
            if config.sticker_auto_delete_delay <= 0:
                errors.append(f"Invalid sticker auto delete delay: {config.sticker_auto_delete_delay}")
            
            if config.broadcast_batch_size <= 0:
                errors.append(f"Invalid broadcast batch size: {config.broadcast_batch_size}")
            
            if config.max_parsing_retries <= 0:
                errors.append(f"Invalid max parsing retries: {config.max_parsing_retries}")
            
            # Log validation results
            if errors:
                logger.warning(f"Configuration validation found {len(errors)} errors", errors=errors)
            else:
                logger.info("Configuration validation passed successfully")
            
            return errors
            
        except Exception as e:
            error_msg = f"Error during configuration validation: {str(e)}"
            logger.error(error_msg)
            return [error_msg]
    
    def _validate_parsing_rule(self, rule: AdvancedParsingRule, index: int) -> List[str]:
        """
        Validate a single parsing rule
        
        Args:
            rule: Parsing rule to validate
            index: Rule index for error reporting
            
        Returns:
            List of validation errors for this rule
        """
        errors = []
        
        # Validate bot name
        if not rule.bot_name or not rule.bot_name.strip():
            errors.append(f"Parsing rule {index}: Empty bot name")
        
        # Validate regex pattern
        if not rule.pattern or not rule.pattern.strip():
            errors.append(f"Parsing rule {index}: Empty pattern")
        else:
            try:
                import re
                re.compile(rule.pattern)
            except re.error as e:
                errors.append(f"Parsing rule {index}: Invalid regex pattern '{rule.pattern}': {str(e)}")
        
        # Validate multiplier
        if rule.multiplier <= 0:
            errors.append(f"Parsing rule {index}: Invalid multiplier {rule.multiplier} (must be > 0)")
        
        # Validate currency type
        if not rule.currency_type or not rule.currency_type.strip():
            errors.append(f"Parsing rule {index}: Empty currency type")
        
        return errors
    
    def get_default_configuration(self) -> BotConfig:
        """
        Create default configuration with all required settings
        
        Returns:
            BotConfig with default values
            
        Validates: Requirements 11.5
        """
        try:
            logger.info("Creating default configuration")
            
            # Load parsing rules from database or use defaults
            parsing_rules = self.load_parsing_rules_from_database()
            
            # Create default configuration
            default_config = BotConfig(
                parsing_rules=parsing_rules,
                admin_user_ids=self._get_default_admin_ids(),
                sticker_cleanup_interval=300,  # 5 minutes
                sticker_auto_delete_delay=120,  # 2 minutes
                broadcast_batch_size=50,
                max_parsing_retries=3
            )
            
            logger.info("Default configuration created successfully")
            return default_config
            
        except Exception as e:
            error_msg = f"Failed to create default configuration: {str(e)}"
            logger.error(error_msg)
            raise ConfigurationError(error_msg)
    
    def _get_default_parsing_rules(self) -> List[AdvancedParsingRule]:
        """Get default parsing rules if database is unavailable"""
        return [
            AdvancedParsingRule(
                id=1,
                bot_name='Shmalala',
                pattern=r'Монеты:\s*\+(\d+)',
                multiplier=Decimal('1.0'),
                currency_type='coins',
                is_active=True
            ),
            AdvancedParsingRule(
                id=2,
                bot_name='GDcards',
                pattern=r'Очки:\s*\+(\d+)',
                multiplier=Decimal('1.0'),
                currency_type='points',
                is_active=True
            )
        ]
    
    def _get_default_admin_ids(self) -> List[int]:
        """Get default admin user IDs from environment or config"""
        try:
            from src.config import settings
            return settings.admin_user_ids if settings.admin_user_ids else [settings.ADMIN_TELEGRAM_ID]
        except Exception:
            from src.config import settings
            return [settings.ADMIN_TELEGRAM_ID]  # Fallback admin ID
    
    def reload_configuration(self) -> bool:
        """
        Reload configuration without restart with hot reload capability
        
        Returns:
            True if reload successful, False otherwise
            
        Validates: Requirements 11.3
        """
        try:
            logger.info("Reloading configuration")
            self.validation_errors.clear()
            
            # Try to load from file first, then use defaults
            config = None
            
            if os.path.exists(self.config_file_path):
                config = self._load_from_file()
            
            if config is None:
                logger.info("Using default configuration")
                config = self.get_default_configuration()
            
            # Validate configuration
            validation_errors = self.validate_configuration(config)
            
            if validation_errors:
                self.validation_errors.extend(validation_errors)
                logger.error(f"Configuration validation failed with {len(validation_errors)} errors")
                
                # Use previous config if available, otherwise use defaults
                if self.config is None:
                    logger.warning("No previous valid configuration, using defaults despite errors")
                    self.config = config
                else:
                    logger.warning("Keeping previous valid configuration due to validation errors")
                    return False
            else:
                # Configuration is valid
                self.config = config
                self.last_reload_time = datetime.utcnow()
                logger.info("Configuration reloaded successfully")
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to reload configuration: {str(e)}"
            logger.error(error_msg)
            self.validation_errors.append(error_msg)
            
            # Ensure we have some configuration
            if self.config is None:
                try:
                    self.config = self.get_default_configuration()
                    logger.info("Fallback to default configuration due to reload error")
                except Exception as fallback_error:
                    logger.critical(f"Failed to create fallback configuration: {str(fallback_error)}")
                    raise ConfigurationError(f"Critical configuration error: {str(fallback_error)}")
            
            return False
    
    def _load_from_file(self) -> Optional[BotConfig]:
        """
        Load configuration from file (JSON or YAML)
        
        Returns:
            BotConfig if successful, None otherwise
        """
        try:
            logger.info(f"Loading configuration from file: {self.config_file_path}")
            
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                if self.config_file_path.endswith('.yaml') or self.config_file_path.endswith('.yml'):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            
            # Parse configuration data
            config = self._parse_config_data(data)
            logger.info("Configuration loaded from file successfully")
            return config
            
        except FileNotFoundError:
            logger.info(f"Configuration file not found: {self.config_file_path}")
            return None
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            error_msg = f"Invalid configuration file format: {str(e)}"
            logger.error(error_msg)
            self.validation_errors.append(error_msg)
            return None
        except Exception as e:
            error_msg = f"Error loading configuration file: {str(e)}"
            logger.error(error_msg)
            self.validation_errors.append(error_msg)
            return None
    
    def _parse_config_data(self, data: Dict[str, Any]) -> BotConfig:
        """
        Parse configuration data from file into BotConfig object
        
        Args:
            data: Configuration data dictionary
            
        Returns:
            BotConfig object
        """
        # Load parsing rules from database (file config doesn't override database rules)
        parsing_rules = self.load_parsing_rules_from_database()
        
        # Parse admin user IDs
        admin_user_ids = data.get('admin_user_ids', self._get_default_admin_ids())
        if isinstance(admin_user_ids, str):
            admin_user_ids = [int(x.strip()) for x in admin_user_ids.split(',') if x.strip().isdigit()]
        
        # Parse timing configurations with defaults
        sticker_cleanup_interval = data.get('sticker_cleanup_interval', 300)
        sticker_auto_delete_delay = data.get('sticker_auto_delete_delay', 120)
        broadcast_batch_size = data.get('broadcast_batch_size', 50)
        max_parsing_retries = data.get('max_parsing_retries', 3)
        
        return BotConfig(
            parsing_rules=parsing_rules,
            admin_user_ids=admin_user_ids,
            sticker_cleanup_interval=sticker_cleanup_interval,
            sticker_auto_delete_delay=sticker_auto_delete_delay,
            broadcast_batch_size=broadcast_batch_size,
            max_parsing_retries=max_parsing_retries
        )
    
    def save_configuration_template(self) -> bool:
        """
        Save a configuration template file with default values
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure config directory exists
            config_dir = os.path.dirname(self.config_file_path)
            os.makedirs(config_dir, exist_ok=True)
            
            # Create template configuration
            template_config = {
                'admin_user_ids': self._get_default_admin_ids(),
                'sticker_cleanup_interval': 300,
                'sticker_auto_delete_delay': 120,
                'broadcast_batch_size': 50,
                'max_parsing_retries': 3,
                '_note': 'Parsing rules are loaded from database, not from this file'
            }
            
            # Save as YAML for better readability
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                yaml.dump(template_config, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"Configuration template saved to: {self.config_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save configuration template: {str(e)}")
            return False
    
    def get_configuration(self) -> BotConfig:
        """
        Get current configuration
        
        Returns:
            Current BotConfig object
        """
        if self.config is None:
            logger.warning("No configuration loaded, creating default")
            self.config = self.get_default_configuration()
        
        return self.config
    
    def get_validation_errors(self) -> List[str]:
        """
        Get current validation errors
        
        Returns:
            List of validation error messages
        """
        return self.validation_errors.copy()
    
    def has_validation_errors(self) -> bool:
        """
        Check if there are any validation errors
        
        Returns:
            True if there are validation errors
        """
        return len(self.validation_errors) > 0
    
    def get_health_status(self) -> HealthStatus:
        """
        Get configuration system health status
        
        Returns:
            HealthStatus object with system health information
        """
        try:
            # Check database connectivity
            db_connected = True
            try:
                db = next(get_db())
                db.execute("SELECT 1")
                db.close()
            except Exception:
                db_connected = False
            
            # Check configuration validity
            config_valid = self.config is not None and not self.has_validation_errors()
            
            # Check file accessibility
            file_accessible = os.path.exists(self.config_file_path) or os.access(os.path.dirname(self.config_file_path), os.W_OK)
            
            is_healthy = db_connected and config_valid and file_accessible
            
            errors = []
            if not db_connected:
                errors.append("Database connection failed")
            if not config_valid:
                errors.append("Configuration validation failed")
                errors.extend(self.validation_errors)
            if not file_accessible:
                errors.append("Configuration file not accessible")
            
            return HealthStatus(
                is_healthy=is_healthy,
                parsing_active=config_valid and db_connected,
                background_tasks_running=True,  # Assume running if config is valid
                database_connected=db_connected,
                last_check=datetime.utcnow(),
                errors=errors
            )
            
        except Exception as e:
            return HealthStatus(
                is_healthy=False,
                parsing_active=False,
                background_tasks_running=False,
                database_connected=False,
                last_check=datetime.utcnow(),
                errors=[f"Health check failed: {str(e)}"]
            )
    
    def add_parsing_rule(self, bot_name: str, pattern: str, multiplier: Decimal, currency_type: str) -> bool:
        """
        Add a new parsing rule to the database
        
        Args:
            bot_name: Name of the bot
            pattern: Regex pattern for parsing
            multiplier: Currency conversion multiplier
            currency_type: Type of currency
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Adding new parsing rule for bot: {bot_name}")
            
            db = next(get_db())
            try:
                # Check if rule already exists
                existing = db.query(ParsingRule).filter(
                    ParsingRule.bot_name == bot_name,
                    ParsingRule.pattern == pattern
                ).first()
                
                if existing:
                    logger.warning(f"Parsing rule already exists for {bot_name} with pattern {pattern}")
                    return False
                
                # Create new rule
                new_rule = ParsingRule(
                    bot_name=bot_name,
                    pattern=pattern,
                    multiplier=multiplier,
                    currency_type=currency_type,
                    is_active=True
                )
                
                db.add(new_rule)
                db.commit()
                
                logger.info(f"Successfully added parsing rule for {bot_name}")
                
                # Reload configuration to include new rule
                self.reload_configuration()
                
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to add parsing rule: {str(e)}")
            return False
    
    def update_parsing_rule(self, rule_id: int, **kwargs) -> bool:
        """
        Update an existing parsing rule
        
        Args:
            rule_id: ID of the rule to update
            **kwargs: Fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Updating parsing rule ID: {rule_id}")
            
            db = next(get_db())
            try:
                rule = db.query(ParsingRule).filter(ParsingRule.id == rule_id).first()
                
                if not rule:
                    logger.warning(f"Parsing rule with ID {rule_id} not found")
                    return False
                
                # Update fields
                for field, value in kwargs.items():
                    if hasattr(rule, field):
                        setattr(rule, field, value)
                
                db.commit()
                
                logger.info(f"Successfully updated parsing rule ID: {rule_id}")
                
                # Reload configuration to reflect changes
                self.reload_configuration()
                
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to update parsing rule: {str(e)}")
            return False
    
    def export_configuration(self, include_parsing_rules: bool = True) -> Dict[str, Any]:
        """
        Export current configuration to dictionary format
        
        Args:
            include_parsing_rules: Whether to include parsing rules in export
            
        Returns:
            Dictionary containing configuration data
        """
        try:
            logger.info("Exporting configuration")
            
            config = self.get_configuration()
            export_data = {
                'export_timestamp': datetime.utcnow().isoformat(),
                'export_version': '1.0',
                'configuration': {
                    'admin_user_ids': config.admin_user_ids,
                    'sticker_cleanup_interval': config.sticker_cleanup_interval,
                    'sticker_auto_delete_delay': config.sticker_auto_delete_delay,
                    'broadcast_batch_size': config.broadcast_batch_size,
                    'max_parsing_retries': config.max_parsing_retries
                }
            }
            
            if include_parsing_rules:
                export_data['parsing_rules'] = [
                    {
                        'id': rule.id,
                        'bot_name': rule.bot_name,
                        'pattern': rule.pattern,
                        'multiplier': float(rule.multiplier),
                        'currency_type': rule.currency_type,
                        'is_active': rule.is_active
                    } for rule in config.parsing_rules
                ]
            
            logger.info("Configuration exported successfully")
            return export_data
            
        except Exception as e:
            logger.error(f"Failed to export configuration: {str(e)}")
            return {}
    
    def import_configuration(self, config_data: Dict[str, Any], 
                           import_parsing_rules: bool = False) -> bool:
        """
        Import configuration from dictionary format
        
        Args:
            config_data: Configuration data dictionary
            import_parsing_rules: Whether to import parsing rules
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Importing configuration")
            
            # Validate import data structure
            if 'configuration' not in config_data:
                logger.error("Invalid import data: missing 'configuration' key")
                return False
            
            config_section = config_data['configuration']
            
            # Create temporary configuration for validation
            temp_config = BotConfig(
                parsing_rules=self.config.parsing_rules if self.config else [],
                admin_user_ids=config_section.get('admin_user_ids', []),
                sticker_cleanup_interval=config_section.get('sticker_cleanup_interval', 300),
                sticker_auto_delete_delay=config_section.get('sticker_auto_delete_delay', 120),
                broadcast_batch_size=config_section.get('broadcast_batch_size', 50),
                max_parsing_retries=config_section.get('max_parsing_retries', 3)
            )
            
            # Validate imported configuration
            validation_errors = self.validate_configuration(temp_config)
            if validation_errors:
                logger.error(f"Import validation failed: {validation_errors}")
                return False
            
            # Import parsing rules if requested
            if import_parsing_rules and 'parsing_rules' in config_data:
                success = self._import_parsing_rules(config_data['parsing_rules'])
                if not success:
                    logger.warning("Failed to import parsing rules, continuing with configuration import")
            
            # Update configuration file
            config_file_data = {
                'admin_user_ids': temp_config.admin_user_ids,
                'sticker_cleanup_interval': temp_config.sticker_cleanup_interval,
                'sticker_auto_delete_delay': temp_config.sticker_auto_delete_delay,
                'broadcast_batch_size': temp_config.broadcast_batch_size,
                'max_parsing_retries': temp_config.max_parsing_retries,
                '_imported_at': datetime.utcnow().isoformat()
            }
            
            # Save to configuration file
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_file_data, f, default_flow_style=False, allow_unicode=True)
            
            # Reload configuration
            success = self.reload_configuration()
            
            if success:
                logger.info("Configuration imported successfully")
            else:
                logger.error("Configuration import completed but reload failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to import configuration: {str(e)}")
            return False
    
    def _import_parsing_rules(self, rules_data: List[Dict[str, Any]]) -> bool:
        """
        Import parsing rules to database
        
        Args:
            rules_data: List of parsing rule dictionaries
            
        Returns:
            True if successful, False otherwise
        """
        try:
            db = next(get_db())
            try:
                imported_count = 0
                
                for rule_data in rules_data:
                    # Check if rule already exists
                    existing = db.query(ParsingRule).filter(
                        ParsingRule.bot_name == rule_data['bot_name'],
                        ParsingRule.pattern == rule_data['pattern']
                    ).first()
                    
                    if existing:
                        logger.info(f"Parsing rule already exists: {rule_data['bot_name']}")
                        continue
                    
                    # Create new rule
                    new_rule = ParsingRule(
                        bot_name=rule_data['bot_name'],
                        pattern=rule_data['pattern'],
                        multiplier=Decimal(str(rule_data['multiplier'])),
                        currency_type=rule_data['currency_type'],
                        is_active=rule_data.get('is_active', True)
                    )
                    
                    db.add(new_rule)
                    imported_count += 1
                
                db.commit()
                logger.info(f"Successfully imported {imported_count} parsing rules")
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to import parsing rules: {str(e)}")
            return False
    
    def create_configuration_backup(self, description: str, 
                                  created_by: Optional[int] = None) -> Optional[str]:
        """
        Create a backup of current configuration
        
        Args:
            description: Description of the backup
            created_by: Admin user ID who created the backup
            
        Returns:
            Backup ID if successful, None otherwise
        """
        try:
            import uuid
            
            backup_id = str(uuid.uuid4())
            logger.info(f"Creating configuration backup: {backup_id}")
            
            # Export current configuration
            config_data = self.export_configuration(include_parsing_rules=True)
            
            if not config_data:
                logger.error("Failed to export configuration for backup")
                return None
            
            # Create backup metadata
            backup = {
                'backup_id': backup_id,
                'created_at': datetime.utcnow().isoformat(),
                'description': description,
                'created_by': created_by,
                'config_data': config_data
            }
            
            # Save backup to file
            backup_dir = os.path.join(os.path.dirname(self.config_file_path), 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            backup_file = os.path.join(backup_dir, f'config_backup_{backup_id}.json')
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuration backup created successfully: {backup_file}")
            return backup_id
            
        except Exception as e:
            logger.error(f"Failed to create configuration backup: {str(e)}")
            return None
    
    def restore_configuration_backup(self, backup_id: str) -> bool:
        """
        Restore configuration from backup
        
        Args:
            backup_id: ID of the backup to restore
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Restoring configuration backup: {backup_id}")
            
            # Find backup file
            backup_dir = os.path.join(os.path.dirname(self.config_file_path), 'backups')
            backup_file = os.path.join(backup_dir, f'config_backup_{backup_id}.json')
            
            if not os.path.exists(backup_file):
                logger.error(f"Backup file not found: {backup_file}")
                return False
            
            # Load backup data
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # Validate backup structure
            if 'config_data' not in backup_data:
                logger.error("Invalid backup file: missing config_data")
                return False
            
            # Import configuration from backup
            success = self.import_configuration(
                backup_data['config_data'], 
                import_parsing_rules=True
            )
            
            if success:
                logger.info(f"Configuration restored successfully from backup: {backup_id}")
            else:
                logger.error(f"Failed to restore configuration from backup: {backup_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to restore configuration backup: {str(e)}")
            return False
    
    def list_configuration_backups(self) -> List[Dict[str, Any]]:
        """
        List available configuration backups
        
        Returns:
            List of backup metadata dictionaries
        """
        try:
            backup_dir = os.path.join(os.path.dirname(self.config_file_path), 'backups')
            
            if not os.path.exists(backup_dir):
                return []
            
            backups = []
            
            for filename in os.listdir(backup_dir):
                if filename.startswith('config_backup_') and filename.endswith('.json'):
                    backup_file = os.path.join(backup_dir, filename)
                    
                    try:
                        with open(backup_file, 'r', encoding='utf-8') as f:
                            backup_data = json.load(f)
                        
                        backup_info = {
                            'backup_id': backup_data.get('backup_id'),
                            'created_at': backup_data.get('created_at'),
                            'description': backup_data.get('description'),
                            'created_by': backup_data.get('created_by'),
                            'file_size': os.path.getsize(backup_file)
                        }
                        
                        backups.append(backup_info)
                        
                    except Exception as e:
                        logger.warning(f"Failed to read backup file {filename}: {str(e)}")
                        continue
            
            # Sort by creation date (newest first)
            backups.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            return backups
            
        except Exception as e:
            logger.error(f"Failed to list configuration backups: {str(e)}")
            return []
    
    def validate_configuration_schema(self, config: BotConfig) -> List[str]:
        """
        Validate configuration against JSON schema
        
        Args:
            config: BotConfig object to validate
            
        Returns:
            List of schema validation errors
        """
        try:
            # Use the built-in schema validation from BotConfig
            schema_errors = config.validate_schema()
            
            # Additional business logic validation
            business_errors = []
            
            # Validate reasonable ranges
            if config.sticker_cleanup_interval < 60:  # Less than 1 minute
                business_errors.append("sticker_cleanup_interval should be at least 60 seconds")
            
            if config.sticker_auto_delete_delay < 30:  # Less than 30 seconds
                business_errors.append("sticker_auto_delete_delay should be at least 30 seconds")
            
            if config.broadcast_batch_size > 100:  # Too large batch size
                business_errors.append("broadcast_batch_size should not exceed 100 for rate limiting")
            
            if config.max_parsing_retries > 10:  # Too many retries
                business_errors.append("max_parsing_retries should not exceed 10")
            
            return schema_errors + business_errors
            
        except Exception as e:
            return [f"Schema validation error: {str(e)}"]


# Global configuration manager instance
_config_manager: Optional[ConfigurationManager] = None


def get_config_manager() -> ConfigurationManager:
    """
    Get the global configuration manager instance
    
    Returns:
        ConfigurationManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager


def reload_global_configuration() -> bool:
    """
    Reload the global configuration
    
    Returns:
        True if successful, False otherwise
    """
    return get_config_manager().reload_configuration()


def get_current_configuration() -> BotConfig:
    """
    Get the current global configuration
    
    Returns:
        Current BotConfig object
    """
    return get_config_manager().get_configuration()