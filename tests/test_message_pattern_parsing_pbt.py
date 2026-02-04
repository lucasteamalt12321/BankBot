#!/usr/bin/env python3
"""
Property-based tests for message pattern parsing
Feature: telegram-bot-advanced-features, Property 8: Message Pattern Parsing
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
    def __init__(self, text: str, user_id: int = None, chat_id: int = None):
        self.text = text
        self.from_user = MockUser(user_id) if user_id else None
        self.chat = MockChat(chat_id) if chat_id else None


class MockUser:
    """Mock user object for testing"""
    def __init__(self, user_id: int):
        self.id = user_id


class MockChat:
    """Mock chat object for testing"""
    def __init__(self, chat_id: int):
        self.id = chat_id


class TestMessagePatternParsingPBT(unittest.TestCase):
    """Property-based tests for message pattern parsing"""
    
    def setUp(self):
        """Setup test database and parser"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Create database engine and session
        self.engine = create_engine(f"sqlite:///{self.temp_db.name}")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Initialize message parser
        self.parser = MessageParser(self.session)
        
        # Create default parsing rules
        self._create_test_parsing_rules()
    
    def _cleanup_test_data(self):
        """Clean up test data between property test runs"""
        try:
            # Clean up transactions and users to avoid foreign key constraints
            self.session.query(ParsedTransaction).delete()
            self.session.query(User).delete()
            self.session.commit()
        except Exception:
            self.session.rollback()
    
    def tearDown(self):
        """Clean up after tests"""
        self.session.close()
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    def _create_test_parsing_rules(self):
        """Create test parsing rules in database"""
        # Clear existing rules first
        self.session.query(ParsingRule).delete()
        
        # Shmalala bot rule
        shmalala_rule = ParsingRule(
            bot_name='Shmalala',
            pattern=r'Монеты:\s*\+(\d+)',
            multiplier=Decimal('1.0'),
            currency_type='coins',
            is_active=True
        )
        self.session.add(shmalala_rule)
        
        # GDcards bot rule
        gdcards_rule = ParsingRule(
            bot_name='GDcards',
            pattern=r'Очки:\s*\+(\d+)',
            multiplier=Decimal('1.0'),
            currency_type='points',
            is_active=True
        )
        self.session.add(gdcards_rule)
        
        self.session.commit()
        
        # Reload parser rules
        self.parser.load_parsing_rules()
    
    def _create_test_user(self, user_id: int, balance: int = 1000) -> User:
        """Create a test user"""
        # Check if user already exists and delete it
        existing_user = self.session.query(User).filter(User.telegram_id == user_id).first()
        if existing_user:
            self.session.delete(existing_user)
            self.session.commit()
        
        # Create new user
        user = User(
            telegram_id=user_id,
            username=f"testuser_{user_id}",
            first_name=f"TestUser{user_id}",
            balance=balance,
            is_admin=False
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=999999),  # amount
        st.sampled_from(['Shmalala', 'GDcards']),  # bot_name (removed TestBot)
        st.integers(min_value=1, max_value=2147483647)  # user_id
    )
    @settings(max_examples=20, deadline=None)
    def test_message_pattern_parsing_property(self, amount, bot_name, user_id):
        """
        **Property 8: Message Pattern Parsing**
        **Validates: Requirements 5.2, 5.3**
        
        For any message from configured external bots matching defined regex patterns, 
        the numeric values should be extracted correctly regardless of the specific bot source
        """
        # Clean up any previous test data
        self._cleanup_test_data()
        # Create test user
        user = self._create_test_user(user_id, balance=1000)
        original_balance = user.balance
        
        # Create message text based on bot type
        if bot_name == 'Shmalala':
            # Create realistic Shmalala fishing message
            message_text = f"""🎣 [Рыбалка] 🎣

Рыбак: TestUser{user_id}
Опыт: +5 (525 / 683)🔋

Вы читали новости о загрязнении воды, но эта рыба не читает новости.
На крючке: 🐊 Щука (2.63 кг)

Погода: ❄️ Снег
Место: Городское озеро

Монеты: +{amount} (2605)💰
Энергии осталось: 5 ⚡️"""
            expected_pattern = r'Монеты:\s*\+(\d+)'
            expected_currency = 'coins'
            expected_multiplier = Decimal('1.0')
            
        elif bot_name == 'GDcards':
            # Create realistic GDcards message
            message_text = f"""🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: TestUser{user_id}
───────────────
Карта: "Test Level"
Описание: Test level description
Категория: challenges
───────────────
Редкость: Обычная (15/33) (40.0%) ⚪️
Очки: +{amount}
Коллекция: 86/213 карт
───────────────
Эта карта есть у: 1065 игроков
Лимит карт сегодня: 1 из 8"""
            expected_pattern = r'Очки:\s*\+(\d+)'
            expected_currency = 'points'
            expected_multiplier = Decimal('1.0')
        
        # Create mock message object
        mock_message = MockMessage(message_text, user_id=user_id)
        
        # **Property Part 1: Pattern should be detected correctly**
        # Verify the pattern matches manually first
        pattern_match = re.search(expected_pattern, message_text, re.IGNORECASE | re.MULTILINE)
        self.assertIsNotNone(
            pattern_match,
            f"Pattern {expected_pattern} should match in message for {bot_name}"
        )
        
        extracted_amount = int(pattern_match.group(1))
        self.assertEqual(
            extracted_amount, amount,
            f"Extracted amount should match original amount for {bot_name}"
        )
        
        # **Property Part 2: Message parsing should extract numeric values correctly**
        parsed_result = asyncio.run(self.parser.parse_message(mock_message))
        
        self.assertIsNotNone(
            parsed_result,
            f"Message from {bot_name} with pattern should be parsed successfully"
        )
        
        # **Property Part 3: Extracted values should match regardless of bot source**
        self.assertEqual(
            parsed_result.source_bot, bot_name,
            f"Source bot should be correctly identified as {bot_name}"
        )
        
        self.assertEqual(
            parsed_result.original_amount, Decimal(str(amount)),
            f"Original amount should be extracted correctly for {bot_name}"
        )
        
        self.assertEqual(
            parsed_result.currency_type, expected_currency,
            f"Currency type should be correct for {bot_name}"
        )
        
        # **Property Part 4: Currency conversion should be applied correctly**
        expected_converted_amount = Decimal(str(amount)) * expected_multiplier
        self.assertEqual(
            parsed_result.converted_amount, expected_converted_amount,
            f"Converted amount should apply correct multiplier for {bot_name}"
        )
        
        # **Property Part 5: User balance should be updated correctly**
        self.session.refresh(user)
        expected_new_balance = original_balance + int(expected_converted_amount)
        self.assertEqual(
            user.balance, expected_new_balance,
            f"User balance should be updated with converted amount for {bot_name}"
        )
        
        # **Property Part 6: Transaction should be logged correctly**
        transaction = self.session.query(ParsedTransaction).filter(
            ParsedTransaction.user_id == user_id,
            ParsedTransaction.source_bot == bot_name
        ).order_by(ParsedTransaction.id.desc()).first()
        
        self.assertIsNotNone(
            transaction,
            f"Transaction should be logged for {bot_name} parsing"
        )
        
        self.assertEqual(
            transaction.original_amount, Decimal(str(amount)),
            f"Logged original amount should match for {bot_name}"
        )
        
        self.assertEqual(
            transaction.converted_amount, expected_converted_amount,
            f"Logged converted amount should match for {bot_name}"
        )
        
        self.assertEqual(
            transaction.source_bot, bot_name,
            f"Logged source bot should match for {bot_name}"
        )
        
        self.assertEqual(
            transaction.currency_type, expected_currency,
            f"Logged currency type should match for {bot_name}"
        )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.text(min_size=10, max_size=500),  # random_text
        st.integers(min_value=1, max_value=2147483647)  # user_id
    )
    @settings(max_examples=20, deadline=None)
    def test_non_matching_message_property(self, random_text, user_id):
        """
        **Property 8: Message Pattern Parsing**
        **Validates: Requirements 5.2, 5.3**
        
        For any message that doesn't match configured patterns, 
        parsing should return None and not affect user balance
        """
        # Clean up any previous test data
        self._cleanup_test_data()
        # Skip if the random text accidentally contains our patterns
        patterns_to_avoid = [
            r'Монеты:\s*\+\d+',
            r'Очки:\s*\+\d+',
            r'Credits:\s*\+\d+'
        ]
        
        for pattern in patterns_to_avoid:
            if re.search(pattern, random_text, re.IGNORECASE):
                assume(False)  # Skip this test case
        
        # Create test user
        user = self._create_test_user(user_id, balance=1000)
        original_balance = user.balance
        
        # Create mock message with random text
        mock_message = MockMessage(random_text, user_id=user_id)
        
        # **Property Part 1: Non-matching messages should return None**
        parsed_result = asyncio.run(self.parser.parse_message(mock_message))
        
        self.assertIsNone(
            parsed_result,
            f"Random text should not match any parsing patterns: {random_text[:50]}..."
        )
        
        # **Property Part 2: User balance should remain unchanged**
        self.session.refresh(user)
        self.assertEqual(
            user.balance, original_balance,
            f"User balance should not change for non-matching message"
        )
        
        # **Property Part 3: No transaction should be logged**
        transaction_count = self.session.query(ParsedTransaction).filter(
            ParsedTransaction.user_id == user_id
        ).count()
        
        self.assertEqual(
            transaction_count, 0,
            f"No transaction should be logged for non-matching message"
        )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=999999),  # amount
        st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Pd', 'Zs'))),  # prefix
        st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Pd', 'Zs'))),  # suffix
        st.integers(min_value=1, max_value=2147483647)  # user_id
    )
    @settings(max_examples=20, deadline=None)
    def test_pattern_extraction_robustness_property(self, amount, prefix, suffix, user_id):
        """
        **Property 8: Message Pattern Parsing**
        **Validates: Requirements 5.2, 5.3**
        
        For any message containing the correct pattern with surrounding text, 
        the numeric value should be extracted correctly regardless of context
        """
        # Clean up any previous test data
        self._cleanup_test_data()
        # Create test user
        user = self._create_test_user(user_id, balance=1000)
        original_balance = user.balance
        
        # Create message with pattern embedded in random text
        message_text = f"{prefix} Монеты: +{amount} {suffix}"
        
        # Create mock message
        mock_message = MockMessage(message_text, user_id=user_id)
        
        # **Property Part 1: Pattern should be extracted from any context**
        parsed_result = asyncio.run(self.parser.parse_message(mock_message))
        
        self.assertIsNotNone(
            parsed_result,
            f"Pattern should be found in message with context: {message_text}"
        )
        
        # **Property Part 2: Extracted amount should be correct regardless of context**
        self.assertEqual(
            parsed_result.original_amount, Decimal(str(amount)),
            f"Amount should be extracted correctly from context: {message_text}"
        )
        
        self.assertEqual(
            parsed_result.source_bot, 'Shmalala',
            f"Bot should be identified correctly from pattern"
        )
        
        # **Property Part 3: Balance update should work correctly**
        self.session.refresh(user)
        expected_new_balance = original_balance + amount  # Multiplier is 1.0 for Shmalala
        self.assertEqual(
            user.balance, expected_new_balance,
            f"Balance should be updated correctly regardless of message context"
        )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.lists(
            st.tuples(
                st.integers(min_value=1, max_value=999),  # amount
                st.sampled_from(['Shmalala', 'GDcards'])  # bot_name (removed TestBot)
            ),
            min_size=1,
            max_size=5
        ),
        st.integers(min_value=1, max_value=2147483647)  # user_id
    )
    @settings(max_examples=10, deadline=None)
    def test_multiple_patterns_parsing_property(self, amount_bot_pairs, user_id):
        """
        **Property 8: Message Pattern Parsing**
        **Validates: Requirements 5.2, 5.3**
        
        For any sequence of messages from different bots, each should be parsed 
        independently and correctly regardless of the order or bot source
        """
        # Clean up any previous test data
        self._cleanup_test_data()
        # Create test user
        user = self._create_test_user(user_id, balance=1000)
        original_balance = user.balance
        
        total_expected_increase = 0
        parsed_transactions = []
        
        # Process each message
        for amount, bot_name in amount_bot_pairs:
            # Create appropriate message for bot type
            if bot_name == 'Shmalala':
                message_text = f"🎣 Рыбалка 🎣\nМонеты: +{amount} (1000)💰"
                expected_multiplier = Decimal('1.0')
            elif bot_name == 'GDcards':
                message_text = f"🃏 НОВАЯ КАРТА 🃏\nОчки: +{amount}\nКоллекция: 86/213 карт"
                expected_multiplier = Decimal('1.0')
            
            # Create mock message
            mock_message = MockMessage(message_text, user_id=user_id)
            
            # Parse message
            parsed_result = asyncio.run(self.parser.parse_message(mock_message))
            
            # **Property Part 1: Each message should be parsed correctly**
            self.assertIsNotNone(
                parsed_result,
                f"Message from {bot_name} should be parsed: {message_text[:50]}..."
            )
            
            self.assertEqual(
                parsed_result.source_bot, bot_name,
                f"Source bot should be identified correctly for {bot_name}"
            )
            
            self.assertEqual(
                parsed_result.original_amount, Decimal(str(amount)),
                f"Original amount should be correct for {bot_name}"
            )
            
            # **Property Part 2: Conversion should be applied correctly**
            expected_converted = Decimal(str(amount)) * expected_multiplier
            self.assertEqual(
                parsed_result.converted_amount, expected_converted,
                f"Converted amount should be correct for {bot_name}"
            )
            
            total_expected_increase += int(expected_converted)
            parsed_transactions.append(parsed_result)
        
        # **Property Part 3: Total balance should reflect all transactions**
        self.session.refresh(user)
        expected_final_balance = original_balance + total_expected_increase
        self.assertEqual(
            user.balance, expected_final_balance,
            f"Final balance should reflect all parsed transactions"
        )
        
        # **Property Part 4: All transactions should be logged independently**
        logged_transactions = self.session.query(ParsedTransaction).filter(
            ParsedTransaction.user_id == user_id
        ).order_by(ParsedTransaction.id).all()
        
        self.assertEqual(
            len(logged_transactions), len(amount_bot_pairs),
            f"All transactions should be logged independently"
        )
        
        # Verify each logged transaction
        for i, (amount, bot_name) in enumerate(amount_bot_pairs):
            logged_tx = logged_transactions[i]
            parsed_tx = parsed_transactions[i]
            
            self.assertEqual(
                logged_tx.source_bot, bot_name,
                f"Logged transaction {i} should have correct bot name"
            )
            
            self.assertEqual(
                logged_tx.original_amount, Decimal(str(amount)),
                f"Logged transaction {i} should have correct original amount"
            )
            
            self.assertEqual(
                logged_tx.converted_amount, parsed_tx.converted_amount,
                f"Logged transaction {i} should have correct converted amount"
            )
    
    def test_message_pattern_parsing_without_hypothesis(self):
        """Fallback test when Hypothesis is not available"""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Test cases covering the message pattern parsing property
        test_cases = [
            # (amount, bot_name, description)
            (100, 'Shmalala', "Shmalala fishing message"),
            (50, 'GDcards', "GDcards card message"),
            (1, 'Shmalala', "Minimum amount Shmalala"),
            (999999, 'GDcards', "Maximum amount GDcards"),
        ]
        
        for amount, bot_name, description in test_cases:
            with self.subTest(amount=amount, bot_name=bot_name, description=description):
                # Create test user
                user_id = 12345 + hash(description) % 1000000
                user = self._create_test_user(user_id, balance=1000)
                original_balance = user.balance
                
                # Create appropriate message
                if bot_name == 'Shmalala':
                    message_text = f"🎣 Рыбалка 🎣\nМонеты: +{amount} (1000)💰"
                    expected_multiplier = Decimal('1.0')
                elif bot_name == 'GDcards':
                    message_text = f"🃏 НОВАЯ КАРТА 🃏\nОчки: +{amount}\nКоллекция: 86/213 карт"
                    expected_multiplier = Decimal('1.0')
                
                # Create mock message and parse
                mock_message = MockMessage(message_text, user_id=user_id)
                parsed_result = asyncio.run(self.parser.parse_message(mock_message))
                
                # Verify parsing results
                self.assertIsNotNone(parsed_result, f"Should parse {description}")
                self.assertEqual(parsed_result.source_bot, bot_name, f"Correct bot for {description}")
                self.assertEqual(parsed_result.original_amount, Decimal(str(amount)), f"Correct amount for {description}")
                
                # Verify conversion and balance update
                expected_converted = Decimal(str(amount)) * expected_multiplier
                self.assertEqual(parsed_result.converted_amount, expected_converted, f"Correct conversion for {description}")
                
                self.session.refresh(user)
                expected_balance = original_balance + int(expected_converted)
                self.assertEqual(user.balance, expected_balance, f"Correct balance update for {description}")
                
                # Clean up for next test
                self.session.query(ParsedTransaction).filter(ParsedTransaction.user_id == user_id).delete()
                self.session.delete(user)
                self.session.commit()


if __name__ == '__main__':
    unittest.main()