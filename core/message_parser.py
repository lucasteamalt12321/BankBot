"""
MessageParser class for Advanced Telegram Bot Features
Implements regex-based parsing for external bot messages with currency conversion and logging
"""

import os
import sys
import re
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import User, ParsingRule, ParsedTransaction
from core.advanced_models import (
    ParsingResult, ParsedTransaction as AdvancedParsedTransaction,
    ParsingRule as AdvancedParsingRule, ParsingError
)
from core.config_manager import get_config_manager
import structlog

logger = structlog.get_logger()


class MessageParser:
    """
    Message parser for extracting currency data from external bot messages
    Implements Requirements 5.1, 5.2, 5.3, 6.1, 6.2 from the advanced features specification
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize MessageParser with database session
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        self.config_manager = get_config_manager()
        self.parsing_rules: List[AdvancedParsingRule] = []
        self.load_parsing_rules()
    
    async def parse_message(self, message: Any) -> Optional[AdvancedParsedTransaction]:
        """
        Parse a message for currency patterns from configured external bots
        
        Args:
            message: Telegram message object or message text
            
        Returns:
            ParsedTransaction if parsing successful, None otherwise
            
        Validates: Requirements 5.1, 5.2, 5.3
        """
        try:
            # Extract message text and metadata
            if hasattr(message, 'text'):
                message_text = message.text
                user_id = getattr(message.from_user, 'id', None) if hasattr(message, 'from_user') else None
                chat_id = getattr(message.chat, 'id', None) if hasattr(message, 'chat') else None
            elif isinstance(message, str):
                message_text = message
                user_id = None
                chat_id = None
            else:
                logger.warning("Invalid message format", message_type=type(message))
                return None
            
            if not message_text:
                return None
            
            logger.debug("Parsing message", message_text=message_text[:100])
            
            # Try each parsing rule
            for rule in self.parsing_rules:
                if not rule.is_active:
                    continue
                
                try:
                    # Check if message matches the bot pattern
                    if not self._is_from_bot(message_text, rule.bot_name):
                        continue
                    
                    # Apply regex pattern to extract currency amount
                    pattern_match = re.search(rule.pattern, message_text, re.IGNORECASE | re.MULTILINE)
                    if pattern_match:
                        # Extract the numeric value (assuming first capture group)
                        amount_str = pattern_match.group(1)
                        original_amount = Decimal(amount_str)
                        
                        logger.info(
                            "Currency pattern matched",
                            bot_name=rule.bot_name,
                            original_amount=original_amount,
                            pattern=rule.pattern
                        )
                        
                        # Apply currency conversion
                        converted_amount = await self.apply_currency_conversion(original_amount, rule.bot_name)
                        
                        # Create parsed transaction object
                        parsed_transaction = AdvancedParsedTransaction(
                            id=0,  # Will be set by database
                            user_id=user_id or 0,  # Default to 0 if no user context
                            source_bot=rule.bot_name,
                            original_amount=original_amount,
                            converted_amount=converted_amount,
                            currency_type=rule.currency_type,
                            parsed_at=datetime.utcnow(),
                            message_text=message_text
                        )
                        
                        # Log the transaction
                        await self.log_transaction(parsed_transaction)
                        
                        return parsed_transaction
                        
                except (ValueError, IndexError, AttributeError) as e:
                    logger.warning(
                        "Failed to parse with rule",
                        bot_name=rule.bot_name,
                        pattern=rule.pattern,
                        error=str(e)
                    )
                    continue
            
            # No patterns matched
            logger.debug("No parsing rules matched", message_text=message_text[:50])
            return None
            
        except Exception as e:
            logger.error("Error parsing message", error=str(e), message_text=message_text[:100] if 'message_text' in locals() else "unknown")
            raise ParsingError(f"Failed to parse message: {str(e)}")
    
    def load_parsing_rules(self) -> List[AdvancedParsingRule]:
        """
        Load parsing rules from configuration system
        
        Returns:
            List of active parsing rules
            
        Validates: Requirements 5.4, 5.5, 11.1
        """
        try:
            logger.info("Loading parsing rules from configuration system")
            
            # Get parsing rules from configuration manager
            config = self.config_manager.get_configuration()
            self.parsing_rules = config.parsing_rules
            
            logger.info(f"Loaded {len(self.parsing_rules)} parsing rules from configuration")
            
            # Add default rules if none exist
            if not self.parsing_rules:
                self._create_default_rules()
            
            return self.parsing_rules
            
        except Exception as e:
            logger.error("Error loading parsing rules from configuration", error=str(e))
            # Return empty list on error, don't crash
            self.parsing_rules = []
            return self.parsing_rules
    
    async def apply_currency_conversion(self, amount: Decimal, source_bot: str) -> Decimal:
        """
        Apply configured multiplier rates to convert currency amounts
        
        Args:
            amount: Original currency amount
            source_bot: Source bot name for multiplier lookup
            
        Returns:
            Converted currency amount
            
        Validates: Requirements 6.1
        """
        try:
            # Find the parsing rule for this bot
            rule = next((r for r in self.parsing_rules if r.bot_name == source_bot), None)
            
            if not rule:
                logger.warning("No parsing rule found for bot", source_bot=source_bot)
                return amount  # Return original amount if no rule found
            
            # Apply multiplier conversion
            converted_amount = amount * rule.multiplier
            
            logger.info(
                "Currency conversion applied",
                source_bot=source_bot,
                original_amount=amount,
                multiplier=rule.multiplier,
                converted_amount=converted_amount
            )
            
            return converted_amount
            
        except Exception as e:
            logger.error("Error applying currency conversion", error=str(e), source_bot=source_bot, amount=amount)
            return amount  # Return original amount on error
    
    async def log_transaction(self, transaction: AdvancedParsedTransaction) -> None:
        """
        Log parsed transaction to database with complete audit trail
        
        Args:
            transaction: Parsed transaction to log
            
        Validates: Requirements 6.2, 6.4
        """
        try:
            logger.info(
                "Logging parsed transaction",
                user_id=transaction.user_id,
                source_bot=transaction.source_bot,
                original_amount=transaction.original_amount,
                converted_amount=transaction.converted_amount
            )
            
            # Create database record
            db_transaction = ParsedTransaction(
                user_id=transaction.user_id if transaction.user_id > 0 else None,
                source_bot=transaction.source_bot,
                original_amount=transaction.original_amount,
                converted_amount=transaction.converted_amount,
                currency_type=transaction.currency_type,
                parsed_at=transaction.parsed_at,
                message_text=transaction.message_text
            )
            
            self.db.add(db_transaction)
            
            # Update user balance if user is identified
            if transaction.user_id and transaction.user_id > 0:
                user = self.db.query(User).filter(User.telegram_id == transaction.user_id).first()
                if user:
                    # Add converted amount to user balance
                    user.balance += int(transaction.converted_amount)
                    user.last_activity = datetime.utcnow()
                    
                    logger.info(
                        "User balance updated",
                        user_id=transaction.user_id,
                        balance_increase=transaction.converted_amount,
                        new_balance=user.balance
                    )
                else:
                    logger.warning("User not found for balance update", user_id=transaction.user_id)
            
            # Commit the transaction
            self.db.commit()
            self.db.refresh(db_transaction)
            
            # Update the transaction ID
            transaction.id = db_transaction.id
            
            logger.info("Transaction logged successfully", transaction_id=db_transaction.id)
            
        except Exception as e:
            logger.error("Error logging transaction", error=str(e), transaction=transaction)
            self.db.rollback()
            raise ParsingError(f"Failed to log transaction: {str(e)}", transaction.source_bot)
    
    def _is_from_bot(self, message_text: str, bot_name: str) -> bool:
        """
        Check if message is from the specified bot based on content patterns
        
        Args:
            message_text: Message text to check
            bot_name: Bot name to check for
            
        Returns:
            True if message appears to be from the specified bot
        """
        # Define bot identification patterns
        bot_patterns = {
            'Shmalala': [
                r'Shmalala',
                r'Шмалала',
                r'Монеты:\s*\+\d+',
                r'💰\s*монетки?',
                r'🎣.*Рыбалка.*🎣',
                r'Победил\(а\).*и забрал\(а\).*💰'
            ],
            'GDcards': [
                r'GDcards',
                r'🃏.*НОВАЯ КАРТА.*🃏',
                r'🖼.*НОВАЯ КАРТА',
                r'Очки:\s*\+\d+',
                r'Игрок:.*\n.*Карта:',
                r'Редкость:.*\(.*\)'
            ]
        }
        
        # Get patterns for the specified bot (case-insensitive)
        patterns = bot_patterns.get(bot_name, [])
        if not patterns:
            # If no specific patterns, check if bot name appears in message
            return bot_name.lower() in message_text.lower()
        
        # Check if any pattern matches
        for pattern in patterns:
            if re.search(pattern, message_text, re.IGNORECASE | re.MULTILINE):
                return True
        
        return False
    
    def _create_default_rules(self) -> None:
        """
        Create default parsing rules if none exist in database
        """
        try:
            logger.info("Creating default parsing rules")
            
            default_rules = [
                {
                    'bot_name': 'Shmalala',
                    'pattern': r'Монеты:\s*\+(\d+)',
                    'multiplier': Decimal('1.0'),
                    'currency_type': 'coins'
                },
                {
                    'bot_name': 'GDcards',
                    'pattern': r'Очки:\s*\+(\d+)',
                    'multiplier': Decimal('1.0'),
                    'currency_type': 'points'
                }
            ]
            
            for rule_data in default_rules:
                # Check if rule already exists
                existing = self.db.query(ParsingRule).filter(
                    ParsingRule.bot_name == rule_data['bot_name']
                ).first()
                
                if not existing:
                    db_rule = ParsingRule(
                        bot_name=rule_data['bot_name'],
                        pattern=rule_data['pattern'],
                        multiplier=rule_data['multiplier'],
                        currency_type=rule_data['currency_type'],
                        is_active=True
                    )
                    self.db.add(db_rule)
                    
                    # Add to in-memory rules
                    rule = AdvancedParsingRule(
                        id=0,  # Will be set after commit
                        bot_name=rule_data['bot_name'],
                        pattern=rule_data['pattern'],
                        multiplier=rule_data['multiplier'],
                        currency_type=rule_data['currency_type'],
                        is_active=True
                    )
                    self.parsing_rules.append(rule)
            
            self.db.commit()
            logger.info(f"Created {len(default_rules)} default parsing rules")
            
        except Exception as e:
            logger.error("Error creating default parsing rules", error=str(e))
            self.db.rollback()
    
    def reload_configuration(self) -> bool:
        """
        Reload parsing rules from configuration system (hot reload)
        
        Returns:
            True if successful, False otherwise
            
        Validates: Requirements 11.3
        """
        try:
            logger.info("Hot reloading parsing configuration")
            
            # Reload configuration manager
            success = self.config_manager.reload_configuration()
            
            if success:
                # Reload parsing rules
                self.load_parsing_rules()
                logger.info("Parsing configuration hot reloaded successfully")
            else:
                logger.warning("Configuration reload had validation errors, keeping current rules")
            
            return success
            
        except Exception as e:
            logger.error("Error during configuration hot reload", error=str(e))
            return False