# Feature: telegram-bot-advanced-features, Property 14: Parsing Error Handling
"""
Property-based test for parsing error handling consistency.

**Property 14: Parsing Error Handling**
**Validates: Requirements 6.5**

For any message parsing attempt, parsing errors should be handled gracefully 
with failed attempts logged, and the system should continue processing other messages.
"""

import unittest
import sys
import os
import tempfile
import asyncio
import re
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, AsyncMock, patch

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from hypothesis import given, strategies as st, settings, assume
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    print("Warning: Hypothesis not available. Installing...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "hypothesis"])
        from hypothesis import given, strategies as st, settings, assume
        HYPOTHESIS_AVAILABLE = True
    except Exception as e:
        print(f"Failed to install Hypothesis: {e}")
        HYPOTHESIS_AVAILABLE = False

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database import Base, User, ParsingRule, ParsedTransaction
from core.message_parser import MessageParser
from core.advanced_models import ParsingRule as AdvancedParsingRule, ParsedTransaction as AdvancedParsedTransaction


class MockMessage:
    """Mock message object for testing"""
    def __init__(self, text: str, user_id: int = None, chat_username: str = None):
        self.text = text
        self.from_user = MockUser(user_id) if user_id else None
        self.chat = MockChat(chat_username) if chat_username else None


class MockUser:
    """Mock user object for testing"""
    def __init__(self, user_id: int):
        self.id = user_id
        self.username = f"user_{user_id}"


class MockChat:
    """Mock chat object for testing"""
    def __init__(self, username: str):
        self.username = username


class TestParsingErrorHandlingProperty(unittest.TestCase):
    """Property-based tests for parsing error handling consistency."""
    
    def setUp(self):
        """Set up test database and fixtures."""
        # Create in-memory SQLite database for testing
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Create sample parsing rules
        self.sample_parsing_rules = [
            AdvancedParsingRule(
                id=1,
                bot_name="Shmalala",
                pattern=r"Монеты: \+(\d+)",
                multiplier=Decimal("1.0"),
                currency_type="coins",
                is_active=True
            ),
            AdvancedParsingRule(
                id=2,
                bot_name="GDcards",
                pattern=r"Очки: \+(\d+)",
                multiplier=Decimal("0.5"),
                currency_type="points",
                is_active=True
            )
        ]
    
    def tearDown(self):
        """Clean up test database."""
        self.session.close()
        Base.metadata.drop_all(self.engine)
    
    @unittest.skipUnless(HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        message_text=st.one_of(
            st.none(),
            st.text(),
            st.just(""),
            st.text(min_size=1, max_size=1000),
            # Malformed patterns that should not match
            st.sampled_from([
                "Монеты: +abc",  # Non-numeric amount
                "Очки: +",       # Missing amount
                "Random text",   # No pattern match
                "Монеты: -100",  # Negative amount (not matching pattern)
                "Очки: +100.5",  # Decimal in integer pattern
                "Монеты: +999999999999999999999",  # Extremely large number
            ])
        ),
        user_id=st.integers(min_value=1, max_value=999999),
        bot_username=st.one_of(
            st.none(),
            st.text(min_size=1, max_size=50),
            st.sampled_from(["Shmalala", "GDcards", "UnknownBot", ""])
        )
    )
    @settings(max_examples=100)
    def test_parsing_error_handling_property(self, message_text, user_id, bot_username):
        """
        Property: For any message parsing attempt, parsing errors should be 
        handled gracefully with failed attempts logged, and the system should 
        continue processing other messages.
        """
        async def run_test():
            # Create MessageParser instance
            parser = MessageParser(self.session)
            
            # Mock the parsing rules loading
            with patch.object(parser, 'load_parsing_rules', return_value=self.sample_parsing_rules):
                # Create mock message
                mock_message = MockMessage(message_text, user_id, bot_username)
                
                try:
                    # Attempt to parse the message
                    result = await parser.parse_message(mock_message)
                    
                    # Property 1: Parser should never crash on invalid input
                    # If we reach this point, the parser handled the error gracefully
                    
                    # Property 2: Invalid messages should return None
                    if (not message_text or 
                        not isinstance(message_text, str) or 
                        not any(rule.bot_name == bot_username for rule in self.sample_parsing_rules if bot_username)):
                        self.assertIsNone(result, f"Expected None for invalid message, got {result}")
                    
                    # Property 3: Valid pattern matches should return ParsedTransaction or None
                    if result is not None:
                        self.assertIsInstance(result, AdvancedParsedTransaction, f"Expected ParsedTransaction or None, got {type(result)}")
                        self.assertEqual(result.user_id, user_id)
                        self.assertEqual(result.source_bot, bot_username)
                        self.assertIsInstance(result.original_amount, Decimal)
                        self.assertIsInstance(result.converted_amount, Decimal)
                        self.assertGreaterEqual(result.original_amount, 0)
                        self.assertGreaterEqual(result.converted_amount, 0)
                    
                except Exception as e:
                    # Property 4: Any exception should be a controlled error type
                    # The parser should not raise unexpected exceptions
                    self.fail(f"Parser raised unexpected exception: {type(e).__name__}: {e}")
        
        # Run the async test
        asyncio.run(run_test())
    
    @unittest.skipUnless(HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        parsing_rules=st.lists(
            st.builds(
                AdvancedParsingRule,
                id=st.integers(min_value=1, max_value=100),
                bot_name=st.text(min_size=1, max_size=50),
                pattern=st.one_of(
                    st.just(r"Монеты: \+(\d+)"),  # Valid pattern
                    st.just(r"Очки: \+(\d+)"),    # Valid pattern
                    st.text(min_size=1, max_size=100),  # Potentially invalid regex
                    st.just("(invalid regex"),     # Definitely invalid regex
                    st.just(""),                   # Empty pattern
                ),
                multiplier=st.decimals(min_value=0, max_value=100, places=4),
                currency_type=st.text(min_size=1, max_size=20),
                is_active=st.booleans()
            ),
            min_size=0,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_parsing_rules_error_handling_property(self, parsing_rules):
        """
        Property: For any set of parsing rules (including invalid ones), 
        the parser should handle rule loading errors gracefully.
        """
        async def run_test():
            parser = MessageParser(self.session)
            
            try:
                # Mock the database query to return our test rules
                with patch.object(parser, 'load_parsing_rules', return_value=parsing_rules):
                    # Create a valid test message
                    mock_message = MockMessage("Монеты: +100", 12345, "TestBot")
                    
                    # Attempt to parse with potentially invalid rules
                    result = await parser.parse_message(mock_message)
                    
                    # Property: Parser should handle invalid rules gracefully
                    # Either return None (no match) or valid ParsedTransaction
                    if result is not None:
                        self.assertIsInstance(result, AdvancedParsedTransaction)
                    
            except Exception as e:
                # Property: Should not crash on invalid parsing rules
                # Log the error but continue processing
                self.fail(f"Parser crashed on invalid rules: {type(e).__name__}: {e}")
        
        # Run the async test
        asyncio.run(run_test())
    
    @unittest.skipUnless(HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        database_error=st.sampled_from([
            "connection_lost",
            "transaction_rollback", 
            "constraint_violation",
            "timeout"
        ])
    )
    @settings(max_examples=20)
    def test_database_error_handling_property(self, database_error):
        """
        Property: For any database error during parsing, the system should 
        handle it gracefully and continue processing other messages.
        """
        async def run_test():
            parser = MessageParser(self.session)
            
            # Create valid test message
            mock_message = MockMessage("Монеты: +100", 12345, "Shmalala")
            
            # Mock database operations to simulate errors
            with patch.object(parser, 'load_parsing_rules', return_value=self.sample_parsing_rules):
                if database_error == "connection_lost":
                    with patch.object(parser, 'log_transaction', side_effect=ConnectionError("Database connection lost")):
                        result = await parser.parse_message(mock_message)
                        # Should handle connection error gracefully
                        self.assertTrue(result is None or isinstance(result, AdvancedParsedTransaction))
                
                elif database_error == "transaction_rollback":
                    with patch.object(parser, 'log_transaction', side_effect=Exception("Transaction rollback")):
                        result = await parser.parse_message(mock_message)
                        # Should handle transaction errors gracefully
                        self.assertTrue(result is None or isinstance(result, AdvancedParsedTransaction))
                
                elif database_error == "constraint_violation":
                    with patch.object(parser, 'log_transaction', side_effect=ValueError("Constraint violation")):
                        result = await parser.parse_message(mock_message)
                        # Should handle constraint violations gracefully
                        self.assertTrue(result is None or isinstance(result, AdvancedParsedTransaction))
                
                elif database_error == "timeout":
                    with patch.object(parser, 'log_transaction', side_effect=TimeoutError("Database timeout")):
                        result = await parser.parse_message(mock_message)
                        # Should handle timeouts gracefully
                        self.assertTrue(result is None or isinstance(result, AdvancedParsedTransaction))
        
        # Run the async test
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()