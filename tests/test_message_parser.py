"""
Unit tests for the MessageParser class
Tests regex-based parsing, currency conversion, and transaction logging
"""

import unittest
import os
import sys
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.message_parser import MessageParser
from core.advanced_models import (
    ParsedTransaction, ParsingRule, ParsingError
)
from database.database import User, ParsingRule as DBParsingRule, ParsedTransaction as DBParsedTransaction


class TestMessageParser(unittest.TestCase):
    """Unit tests for MessageParser functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.parser = MessageParser(self.mock_db)
        
        # Mock parsing rules
        self.mock_rules = [
            ParsingRule(
                id=1,
                bot_name='Shmalala',
                pattern=r'Монеты:\s*\+(\d+)',
                multiplier=Decimal('1.5'),
                currency_type='coins',
                is_active=True
            ),
            ParsingRule(
                id=2,
                bot_name='GDcards',
                pattern=r'Очки:\s*\+(\d+)',
                multiplier=Decimal('2.0'),
                currency_type='points',
                is_active=True
            )
        ]
        self.parser.parsing_rules = self.mock_rules
    
    def test_parse_shmalala_message_success(self):
        """Test successful parsing of Shmalala bot message"""
        message_text = """Shmalala
        
Рыбак: TestUser
Место: Озеро
Монеты: +15 (100)💰
Опыт: +5 (50 / 100)🔋"""
        
        # Mock database operations
        self.mock_db.add = Mock()
        self.mock_db.commit = Mock()
        self.mock_db.refresh = Mock()
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Create mock transaction with ID
        mock_transaction = Mock()
        mock_transaction.id = 123
        self.mock_db.refresh.side_effect = lambda obj: setattr(obj, 'id', 123)
        
        # Test parsing
        result = unittest.TestCase.run_async(self.parser.parse_message(message_text))
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result.source_bot, 'Shmalala')
        self.assertEqual(result.original_amount, Decimal('15'))
        self.assertEqual(result.converted_amount, Decimal('22.5'))  # 15 * 1.5
        self.assertEqual(result.currency_type, 'coins')
        self.assertEqual(result.message_text, message_text)
    
    def test_parse_gdcards_message_success(self):
        """Test successful parsing of GDcards bot message"""
        message_text = """🃏 НОВАЯ КАРТА 🃏

Игрок: TestPlayer
─────────────────
Карта: "Эпическая карта"
Редкость: Эпическая (🟣)
─────────────────
Очки: +25
Коллекция: 45/100 карт"""
        
        # Mock database operations
        self.mock_db.add = Mock()
        self.mock_db.commit = Mock()
        self.mock_db.refresh = Mock()
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Test parsing
        result = unittest.TestCase.run_async(self.parser.parse_message(message_text))
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result.source_bot, 'GDcards')
        self.assertEqual(result.original_amount, Decimal('25'))
        self.assertEqual(result.converted_amount, Decimal('50'))  # 25 * 2.0
        self.assertEqual(result.currency_type, 'points')
    
    def test_parse_message_no_match(self):
        """Test parsing message that doesn't match any patterns"""
        message_text = "Just a regular message with no currency patterns"
        
        result = unittest.TestCase.run_async(self.parser.parse_message(message_text))
        
        # Should return None for no matches
        self.assertIsNone(result)
    
    def test_parse_message_inactive_rule(self):
        """Test parsing with inactive rule"""
        # Set rule as inactive
        self.parser.parsing_rules[0].is_active = False
        
        message_text = "Shmalala\nМонеты: +10"
        
        result = unittest.TestCase.run_async(self.parser.parse_message(message_text))
        
        # Should return None because rule is inactive
        self.assertIsNone(result)
    
    def test_parse_message_invalid_amount(self):
        """Test parsing message with invalid numeric amount"""
        message_text = "Shmalala\nМонеты: +invalid"
        
        result = unittest.TestCase.run_async(self.parser.parse_message(message_text))
        
        # Should return None for invalid amount
        self.assertIsNone(result)
    
    def test_parse_telegram_message_object(self):
        """Test parsing with Telegram message object"""
        # Create mock Telegram message
        mock_message = Mock()
        mock_message.text = "Shmalala\nМонеты: +20"
        mock_message.from_user = Mock()
        mock_message.from_user.id = 12345
        mock_message.chat = Mock()
        mock_message.chat.id = 67890
        
        # Mock database operations
        self.mock_db.add = Mock()
        self.mock_db.commit = Mock()
        self.mock_db.refresh = Mock()
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = unittest.TestCase.run_async(self.parser.parse_message(mock_message))
        
        # Verify result includes user context
        self.assertIsNotNone(result)
        self.assertEqual(result.user_id, 12345)
        self.assertEqual(result.original_amount, Decimal('20'))
    
    def test_load_parsing_rules_from_database(self):
        """Test loading parsing rules from database"""
        # Mock database rules
        mock_db_rules = [
            Mock(
                id=1,
                bot_name='TestBot',
                pattern=r'Points:\s*\+(\d+)',
                multiplier=Decimal('3.0'),
                currency_type='test_points',
                is_active=True
            )
        ]
        
        self.mock_db.query.return_value.filter.return_value.all.return_value = mock_db_rules
        
        # Load rules
        rules = self.parser.load_parsing_rules()
        
        # Verify rules loaded correctly
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].bot_name, 'TestBot')
        self.assertEqual(rules[0].pattern, r'Points:\s*\+(\d+)')
        self.assertEqual(rules[0].multiplier, Decimal('3.0'))
    
    def test_load_parsing_rules_creates_defaults(self):
        """Test that default rules are created when none exist"""
        # Mock empty database
        self.mock_db.query.return_value.filter.return_value.all.return_value = []
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        self.mock_db.add = Mock()
        self.mock_db.commit = Mock()
        
        # Load rules (should create defaults)
        rules = self.parser.load_parsing_rules()
        
        # Verify default rules were created
        self.assertEqual(len(rules), 2)
        bot_names = [rule.bot_name for rule in rules]
        self.assertIn('Shmalala', bot_names)
        self.assertIn('GDcards', bot_names)
    
    def test_apply_currency_conversion(self):
        """Test currency conversion with multipliers"""
        amount = Decimal('100')
        
        # Test Shmalala conversion (1.5x multiplier)
        result = unittest.TestCase.run_async(
            self.parser.apply_currency_conversion(amount, 'Shmalala')
        )
        self.assertEqual(result, Decimal('150'))
        
        # Test GDcards conversion (2.0x multiplier)
        result = unittest.TestCase.run_async(
            self.parser.apply_currency_conversion(amount, 'GDcards')
        )
        self.assertEqual(result, Decimal('200'))
    
    def test_apply_currency_conversion_unknown_bot(self):
        """Test currency conversion for unknown bot"""
        amount = Decimal('50')
        
        result = unittest.TestCase.run_async(
            self.parser.apply_currency_conversion(amount, 'UnknownBot')
        )
        
        # Should return original amount for unknown bot
        self.assertEqual(result, amount)
    
    def test_log_transaction_with_user_update(self):
        """Test transaction logging with user balance update"""
        # Create test transaction
        transaction = ParsedTransaction(
            id=0,
            user_id=12345,
            source_bot='Shmalala',
            original_amount=Decimal('10'),
            converted_amount=Decimal('15'),
            currency_type='coins',
            parsed_at=datetime.utcnow(),
            message_text='Test message'
        )
        
        # Mock user in database
        mock_user = Mock()
        mock_user.balance = 100
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        # Mock database operations
        self.mock_db.add = Mock()
        self.mock_db.commit = Mock()
        mock_db_transaction = Mock()
        mock_db_transaction.id = 456
        self.mock_db.refresh.side_effect = lambda obj: setattr(obj, 'id', 456)
        
        # Log transaction
        unittest.TestCase.run_async(self.parser.log_transaction(transaction))
        
        # Verify user balance was updated
        self.assertEqual(mock_user.balance, 115)  # 100 + 15
        self.assertIsNotNone(mock_user.last_activity)
        
        # Verify database operations
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
    
    def test_log_transaction_user_not_found(self):
        """Test transaction logging when user is not found"""
        transaction = ParsedTransaction(
            id=0,
            user_id=99999,  # Non-existent user
            source_bot='Shmalala',
            original_amount=Decimal('10'),
            converted_amount=Decimal('15'),
            currency_type='coins',
            parsed_at=datetime.utcnow(),
            message_text='Test message'
        )
        
        # Mock user not found
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        self.mock_db.add = Mock()
        self.mock_db.commit = Mock()
        self.mock_db.refresh = Mock()
        
        # Should not raise exception even if user not found
        unittest.TestCase.run_async(self.parser.log_transaction(transaction))
        
        # Verify transaction was still logged
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
    
    def test_log_transaction_database_error(self):
        """Test transaction logging with database error"""
        transaction = ParsedTransaction(
            id=0,
            user_id=12345,
            source_bot='Shmalala',
            original_amount=Decimal('10'),
            converted_amount=Decimal('15'),
            currency_type='coins',
            parsed_at=datetime.utcnow(),
            message_text='Test message'
        )
        
        # Mock database error
        self.mock_db.add.side_effect = Exception("Database error")
        self.mock_db.rollback = Mock()
        
        # Should raise ParsingError
        with self.assertRaises(ParsingError):
            unittest.TestCase.run_async(self.parser.log_transaction(transaction))
        
        # Verify rollback was called
        self.mock_db.rollback.assert_called_once()
    
    def test_is_from_bot_shmalala(self):
        """Test bot identification for Shmalala messages"""
        # Test various Shmalala patterns
        shmalala_messages = [
            "Shmalala\nМонеты: +10",
            "Шмалала\nРыбалка",
            "Победил(а) TestUser и забрал(а) 5 💰 монетки",
            "🎣 [Рыбалка] 🎣\nРыбак: TestUser"
        ]
        
        for message in shmalala_messages:
            result = self.parser._is_from_bot(message, 'Shmalala')
            self.assertTrue(result, f"Failed to identify Shmalala message: {message}")
    
    def test_is_from_bot_gdcards(self):
        """Test bot identification for GDcards messages"""
        # Test various GDcards patterns
        gdcards_messages = [
            "🃏 НОВАЯ КАРТА 🃏\nИгрок: TestUser",
            "GDcards\nОчки: +15",
            "🖼 НОВАЯ КАРТА\nКарта: Test",
            "Игрок: TestUser\nКарта: TestCard\nОчки: +5"
        ]
        
        for message in gdcards_messages:
            result = self.parser._is_from_bot(message, 'GDcards')
            self.assertTrue(result, f"Failed to identify GDcards message: {message}")
    
    def test_is_from_bot_unknown(self):
        """Test bot identification for unknown bot"""
        message = "Some random message"
        
        # Should return False for unknown bot with no matching patterns
        result = self.parser._is_from_bot(message, 'UnknownBot')
        self.assertFalse(result)
        
        # Should return True if bot name appears in message
        message_with_bot = "Message from UnknownBot"
        result = self.parser._is_from_bot(message_with_bot, 'UnknownBot')
        self.assertTrue(result)
    
    def test_parse_message_error_handling(self):
        """Test error handling in parse_message"""
        # Test with invalid message object
        invalid_message = object()
        
        result = unittest.TestCase.run_async(self.parser.parse_message(invalid_message))
        self.assertIsNone(result)
        
        # Test with None message
        result = unittest.TestCase.run_async(self.parser.parse_message(None))
        self.assertIsNone(result)
    
    def test_edge_case_empty_message(self):
        """Test parsing empty message"""
        result = unittest.TestCase.run_async(self.parser.parse_message(""))
        self.assertIsNone(result)
    
    def test_edge_case_very_large_amount(self):
        """Test parsing very large currency amount"""
        message_text = "Shmalala\nМонеты: +999999999"
        
        # Mock database operations
        self.mock_db.add = Mock()
        self.mock_db.commit = Mock()
        self.mock_db.refresh = Mock()
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = unittest.TestCase.run_async(self.parser.parse_message(message_text))
        
        # Should handle large amounts correctly
        self.assertIsNotNone(result)
        self.assertEqual(result.original_amount, Decimal('999999999'))
        self.assertEqual(result.converted_amount, Decimal('1499999998.5'))  # 999999999 * 1.5
    
    def test_multiple_pattern_matches(self):
        """Test message with multiple currency patterns"""
        message_text = """Shmalala
        
Рыбалка завершена!
Монеты: +10 (100)💰
Дополнительные монеты: +5
Очки: +3"""
        
        # Mock database operations
        self.mock_db.add = Mock()
        self.mock_db.commit = Mock()
        self.mock_db.refresh = Mock()
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = unittest.TestCase.run_async(self.parser.parse_message(message_text))
        
        # Should match the first pattern found (Shmalala rule)
        self.assertIsNotNone(result)
        self.assertEqual(result.source_bot, 'Shmalala')
        self.assertEqual(result.original_amount, Decimal('10'))  # First match


# Helper function to run async methods in tests
def run_async(coro):
    """Helper to run async methods in synchronous tests"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

# Monkey patch the run_async method to TestCase
unittest.TestCase.run_async = staticmethod(run_async)


if __name__ == '__main__':
    unittest.main()