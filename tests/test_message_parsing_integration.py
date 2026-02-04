"""
Integration tests for message parsing middleware (Task 11.2)
Tests the integration of MessageParser with bot message pipeline, 
parsing rules loading on startup, and currency conversion with user balance updates
"""

import pytest
import asyncio
import os
import sys
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal
from datetime import datetime

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import get_db, User, ParsingRule, ParsedTransaction
from core.message_parser import MessageParser
from core.message_monitoring_middleware import MessageMonitoringMiddleware
from core.config_manager import ConfigurationManager
from core.advanced_models import ParsedTransaction as AdvancedParsedTransaction


class TestMessageParsingIntegration:
    """Test message parsing middleware integration"""
    
    @pytest.fixture
    def db_session(self):
        """Create database session for testing"""
        db = next(get_db())
        try:
            yield db
        finally:
            db.close()
    
    @pytest.fixture
    def sample_user(self, db_session):
        """Create a sample user for testing"""
        user = User(
            telegram_id=12345,
            username="testuser",
            first_name="Test",
            balance=100
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    
    @pytest.fixture
    def sample_parsing_rules(self, db_session):
        """Create sample parsing rules"""
        rules = [
            ParsingRule(
                bot_name="Shmalala",
                pattern=r'Монеты:\s*\+(\d+)',
                multiplier=Decimal('1.0'),
                currency_type='coins',
                is_active=True
            ),
            ParsingRule(
                bot_name="GDcards",
                pattern=r'Очки:\s*\+(\d+)',
                multiplier=Decimal('2.0'),
                currency_type='points',
                is_active=True
            )
        ]
        
        for rule in rules:
            db_session.add(rule)
        
        db_session.commit()
        return rules
    
    def test_parsing_rules_loading_on_startup(self, db_session, sample_parsing_rules):
        """Test that parsing rules are loaded correctly on startup"""
        # Create MessageParser instance
        parser = MessageParser(db_session)
        
        # Verify rules are loaded
        assert len(parser.parsing_rules) >= 2
        
        # Check specific rules
        shmalala_rule = next((r for r in parser.parsing_rules if r.bot_name == "Shmalala"), None)
        assert shmalala_rule is not None
        assert shmalala_rule.pattern == r'Монеты:\s*\+(\d+)'
        assert shmalala_rule.multiplier == Decimal('1.0')
        
        gdcards_rule = next((r for r in parser.parsing_rules if r.bot_name == "GDcards"), None)
        assert gdcards_rule is not None
        assert gdcards_rule.pattern == r'Очки:\s*\+(\d+)'
        assert gdcards_rule.multiplier == Decimal('2.0')
    
    @pytest.mark.asyncio
    async def test_message_parsing_with_currency_conversion(self, db_session, sample_user, sample_parsing_rules):
        """Test message parsing with currency conversion"""
        # Create MessageParser instance
        parser = MessageParser(db_session)
        
        # Create mock message for Shmalala bot
        mock_message = Mock()
        mock_message.text = "🎣 [Рыбалка] 🎣\nРыбак: testuser\nПоймал рыбу и получил награду!\nМонеты: +50"
        mock_message.from_user = Mock()
        mock_message.from_user.id = sample_user.telegram_id
        mock_message.chat = Mock()
        mock_message.chat.id = -123456
        
        # Parse the message
        result = await parser.parse_message(mock_message)
        
        # Verify parsing result
        assert result is not None
        assert result.source_bot == "Shmalala"
        assert result.original_amount == Decimal('50')
        assert result.converted_amount == Decimal('50')  # 1.0 multiplier
        assert result.currency_type == "coins"
        assert result.user_id == sample_user.telegram_id
        
        # Verify user balance was updated
        db_session.refresh(sample_user)
        assert sample_user.balance == 150  # 100 + 50
        
        # Verify transaction was logged
        transaction = db_session.query(ParsedTransaction).filter(
            ParsedTransaction.user_id == sample_user.id
        ).first()
        assert transaction is not None
        assert transaction.source_bot == "Shmalala"
        assert transaction.original_amount == Decimal('50')
        assert transaction.converted_amount == Decimal('50')
    
    @pytest.mark.asyncio
    async def test_message_parsing_with_multiplier(self, db_session, sample_user, sample_parsing_rules):
        """Test message parsing with currency multiplier"""
        # Create MessageParser instance
        parser = MessageParser(db_session)
        
        # Create mock message for GDcards bot (has 2.0 multiplier)
        mock_message = Mock()
        mock_message.text = "🃏 НОВАЯ КАРТА 🃏\nИгрок: testuser\nКарта: Epic Dragon\nОчки: +25"
        mock_message.from_user = Mock()
        mock_message.from_user.id = sample_user.telegram_id
        mock_message.chat = Mock()
        mock_message.chat.id = -123456
        
        # Parse the message
        result = await parser.parse_message(mock_message)
        
        # Verify parsing result with multiplier applied
        assert result is not None
        assert result.source_bot == "GDcards"
        assert result.original_amount == Decimal('25')
        assert result.converted_amount == Decimal('50')  # 25 * 2.0 multiplier
        assert result.currency_type == "points"
        
        # Verify user balance was updated with converted amount
        db_session.refresh(sample_user)
        assert sample_user.balance == 150  # 100 + 50 (converted)
    
    @pytest.mark.asyncio
    async def test_middleware_integration(self, db_session, sample_user, sample_parsing_rules):
        """Test middleware integration with message processing"""
        # Create middleware instance
        middleware = MessageMonitoringMiddleware()
        
        # Create MessageParser and assign to middleware
        parser = MessageParser(db_session)
        middleware.message_parser = parser
        
        # Create mock update and context
        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.text = "Рыбак: testuser поймал рыбу!\nМонеты: +75"
        mock_update.message.from_user = Mock()
        mock_update.message.from_user.id = sample_user.telegram_id
        mock_update.message.from_user.is_bot = False
        mock_update.message.chat = Mock()
        mock_update.message.chat.id = -123456
        mock_update.message.chat.type = "group"
        mock_update.effective_user = mock_update.message.from_user
        mock_update.effective_chat = mock_update.message.chat
        mock_update.message.message_id = 12345
        mock_update.message.reply_text = AsyncMock()
        
        mock_context = Mock()
        
        # Process message through middleware
        result = await middleware.process_message(mock_update, mock_context)
        
        # Verify result
        assert result is not None
        assert result.source_bot == "Shmalala"
        assert result.original_amount == Decimal('75')
        assert result.converted_amount == Decimal('75')
        
        # Verify user balance was updated
        db_session.refresh(sample_user)
        assert sample_user.balance == 175  # 100 + 75
    
    def test_configuration_manager_integration(self, db_session, sample_parsing_rules):
        """Test configuration manager integration with parsing rules"""
        # Create configuration manager
        config_manager = ConfigurationManager()
        
        # Load configuration
        config = config_manager.get_configuration()
        
        # Verify parsing rules are loaded
        assert len(config.parsing_rules) >= 2
        
        # Verify specific rules exist
        bot_names = [rule.bot_name for rule in config.parsing_rules]
        assert "Shmalala" in bot_names
        assert "GDcards" in bot_names
        
        # Test configuration validation
        validation_errors = config_manager.validate_configuration(config)
        assert len(validation_errors) == 0  # Should have no validation errors
    
    @pytest.mark.asyncio
    async def test_parsing_error_handling(self, db_session, sample_user, sample_parsing_rules):
        """Test error handling in message parsing"""
        # Create MessageParser instance
        parser = MessageParser(db_session)
        
        # Test with invalid message format
        mock_message = Mock()
        mock_message.text = "Invalid message format"
        mock_message.from_user = Mock()
        mock_message.from_user.id = sample_user.telegram_id
        
        # Parse the message (should return None for non-matching message)
        result = await parser.parse_message(mock_message)
        assert result is None
        
        # Test with None message
        result = await parser.parse_message(None)
        assert result is None
        
        # Test with empty message text
        mock_message.text = ""
        result = await parser.parse_message(mock_message)
        assert result is None
    
    def test_hot_reload_configuration(self, db_session, sample_parsing_rules):
        """Test hot reload of parsing configuration"""
        # Create configuration manager
        config_manager = ConfigurationManager()
        
        # Get initial configuration
        initial_config = config_manager.get_configuration()
        initial_rule_count = len(initial_config.parsing_rules)
        
        # Add a new parsing rule to database
        new_rule = ParsingRule(
            bot_name="TestBot",
            pattern=r'Test:\s*\+(\d+)',
            multiplier=Decimal('3.0'),
            currency_type='test',
            is_active=True
        )
        db_session.add(new_rule)
        db_session.commit()
        
        # Reload configuration
        success = config_manager.reload_configuration()
        assert success
        
        # Verify new rule is loaded
        reloaded_config = config_manager.get_configuration()
        assert len(reloaded_config.parsing_rules) == initial_rule_count + 1
        
        # Find the new rule
        test_rule = next((r for r in reloaded_config.parsing_rules if r.bot_name == "TestBot"), None)
        assert test_rule is not None
        assert test_rule.multiplier == Decimal('3.0')
    
    @pytest.mark.asyncio
    async def test_user_balance_integration(self, db_session, sample_user, sample_parsing_rules):
        """Test integration with user balance updates"""
        initial_balance = sample_user.balance
        
        # Create MessageParser instance
        parser = MessageParser(db_session)
        
        # Create transaction object
        transaction = AdvancedParsedTransaction(
            id=0,
            user_id=sample_user.telegram_id,
            source_bot="Shmalala",
            original_amount=Decimal('100'),
            converted_amount=Decimal('100'),
            currency_type="coins",
            parsed_at=datetime.utcnow(),
            message_text="Test message"
        )
        
        # Log the transaction (should update user balance)
        await parser.log_transaction(transaction)
        
        # Verify user balance was updated
        db_session.refresh(sample_user)
        assert sample_user.balance == initial_balance + 100
        
        # Verify transaction was logged in database
        db_transaction = db_session.query(ParsedTransaction).filter(
            ParsedTransaction.user_id == sample_user.id
        ).first()
        assert db_transaction is not None
        assert db_transaction.converted_amount == Decimal('100')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])