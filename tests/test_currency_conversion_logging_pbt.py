#!/usr/bin/env python3
"""
Property-based tests for currency conversion and logging
Feature: telegram-bot-advanced-features, Property 9: Currency Conversion and Logging
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


class TestCurrencyConversionLoggingPBT(unittest.TestCase):
    """Property-based tests for currency conversion and logging"""
    
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
        
        # Create test parsing rules with different multipliers
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
        """Create test parsing rules in database with different multipliers"""
        # Clear existing rules first
        self.session.query(ParsingRule).delete()
        
        # Shmalala bot rule with 1.5x multiplier
        shmalala_rule = ParsingRule(
            bot_name='Shmalala',
            pattern=r'Монеты:\s*\+(\d+)',
            multiplier=Decimal('1.5'),
            currency_type='coins',
            is_active=True
        )
        self.session.add(shmalala_rule)
        
        # GDcards bot rule with 2.0x multiplier
        gdcards_rule = ParsingRule(
            bot_name='GDcards',
            pattern=r'Очки:\s*\+(\d+)',
            multiplier=Decimal('2.0'),
            currency_type='points',
            is_active=True
        )
        self.session.add(gdcards_rule)
        
        # TestBot rule with 0.5x multiplier for testing fractional multipliers
        testbot_rule = ParsingRule(
            bot_name='TestBot',
            pattern=r'Credits:\s*\+(\d+)',
            multiplier=Decimal('0.5'),
            currency_type='credits',
            is_active=True
        )
        self.session.add(testbot_rule)
        
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
        st.sampled_from(['Shmalala', 'GDcards', 'TestBot']),  # bot_name
        st.integers(min_value=1, max_value=2147483647),  # user_id
        st.integers(min_value=0, max_value=10000)  # initial_balance
    )
    @settings(max_examples=20, deadline=None)
    def test_currency_conversion_and_logging_property(self, amount, bot_name, user_id, initial_balance):
        """
        **Property 9: Currency Conversion and Logging**
        **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
        
        For any parsed currency amount, the system should apply the correct multiplier, 
        update user balance, and log complete transaction details with all required fields
        """
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # Create test user with specified initial balance
        user = self._create_test_user(user_id, balance=initial_balance)
        original_balance = user.balance
        
        # Define expected multipliers and patterns for each bot
        bot_config = {
            'Shmalala': {
                'multiplier': Decimal('1.5'),
                'currency_type': 'coins',
                'pattern': r'Монеты:\s*\+(\d+)',
                'message_template': f"🎣 [Рыбалка] 🎣\n\nРыбак: TestUser{user_id}\nОпыт: +5 (525 / 683)🔋\n\nВы читали новости о загрязнении воды, но эта рыба не читает новости.\nНа крючке: 🐊 Щука (2.63 кг)\n\nПогода: ❄️ Снег\nМесто: Городское озеро\n\nМонеты: +{amount} (2605)💰\nЭнергии осталось: 5 ⚡️"
            },
            'GDcards': {
                'multiplier': Decimal('2.0'),
                'currency_type': 'points',
                'pattern': r'Очки:\s*\+(\d+)',
                'message_template': f"🃏 НОВАЯ КАРТА 🃏\n───────────────\nИгрок: TestUser{user_id}\n───────────────\nКарта: \"Test Level\"\nОписание: Test level description\nКатегория: challenges\n───────────────\nРедкость: Обычная (15/33) (40.0%) ⚪️\nОчки: +{amount}\nКоллекция: 86/213 карт\n───────────────\nЭта карта есть у: 1065 игроков\nЛимит карт сегодня: 1 из 8"
            },
            'TestBot': {
                'multiplier': Decimal('0.5'),
                'currency_type': 'credits',
                'pattern': r'Credits:\s*\+(\d+)',
                'message_template': f"🤖 TestBot Reward 🤖\nUser: TestUser{user_id}\nCredits: +{amount}\nTotal Credits: 1000"
            }
        }
        
        config = bot_config[bot_name]
        expected_multiplier = config['multiplier']
        expected_currency_type = config['currency_type']
        message_text = config['message_template']
        
        # Create mock message object
        mock_message = MockMessage(message_text, user_id=user_id)
        
        # **Property Part 1: Currency should be parsed from external bot messages**
        # Verify the pattern matches manually first
        pattern_match = re.search(config['pattern'], message_text, re.IGNORECASE | re.MULTILINE)
        self.assertIsNotNone(
            pattern_match,
            f"Pattern {config['pattern']} should match in message for {bot_name}"
        )
        
        extracted_amount = int(pattern_match.group(1))
        self.assertEqual(
            extracted_amount, amount,
            f"Extracted amount should match original amount for {bot_name}"
        )
        
        # **Property Part 2: Currency_Converter should apply configured multiplier rates**
        parsed_result = asyncio.run(self.parser.parse_message(mock_message))
        
        self.assertIsNotNone(
            parsed_result,
            f"Message from {bot_name} with pattern should be parsed successfully"
        )
        
        # Verify original amount is correct
        self.assertEqual(
            parsed_result.original_amount, Decimal(str(amount)),
            f"Original amount should be extracted correctly for {bot_name}"
        )
        
        # Verify multiplier is applied correctly
        expected_converted_amount = Decimal(str(amount)) * expected_multiplier
        self.assertEqual(
            parsed_result.converted_amount, expected_converted_amount,
            f"Converted amount should apply correct multiplier ({expected_multiplier}) for {bot_name}"
        )
        
        # Verify source bot and currency type
        self.assertEqual(
            parsed_result.source_bot, bot_name,
            f"Source bot should be correctly identified as {bot_name}"
        )
        
        self.assertEqual(
            parsed_result.currency_type, expected_currency_type,
            f"Currency type should be correct for {bot_name}"
        )
        
        # **Property Part 3: Bot_System should update user balances based on converted currency amounts**
        self.session.refresh(user)
        expected_new_balance = original_balance + int(expected_converted_amount)
        self.assertEqual(
            user.balance, expected_new_balance,
            f"User balance should be updated with converted amount for {bot_name}. "
            f"Original: {original_balance}, Converted: {expected_converted_amount}, "
            f"Expected: {expected_new_balance}, Actual: {user.balance}"
        )
        
        # **Property Part 4: Transaction_Logger should record all parsed transactions with complete details**
        transaction = self.session.query(ParsedTransaction).filter(
            ParsedTransaction.user_id == user_id,
            ParsedTransaction.source_bot == bot_name
        ).order_by(ParsedTransaction.id.desc()).first()
        
        self.assertIsNotNone(
            transaction,
            f"Transaction should be logged for {bot_name} parsing"
        )
        
        # Verify all required transaction fields are present and correct
        self.assertEqual(
            transaction.user_id, user_id,
            f"Logged transaction should have correct user_id"
        )
        
        self.assertEqual(
            transaction.source_bot, bot_name,
            f"Logged transaction should have correct source_bot"
        )
        
        self.assertEqual(
            transaction.original_amount, Decimal(str(amount)),
            f"Logged transaction should have correct original_amount"
        )
        
        self.assertEqual(
            transaction.converted_amount, expected_converted_amount,
            f"Logged transaction should have correct converted_amount"
        )
        
        self.assertEqual(
            transaction.currency_type, expected_currency_type,
            f"Logged transaction should have correct currency_type"
        )
        
        self.assertIsNotNone(
            transaction.parsed_at,
            f"Logged transaction should have parsed_at timestamp"
        )
        
        self.assertEqual(
            transaction.message_text, message_text,
            f"Logged transaction should store complete message_text"
        )
        
        # **Property Part 5: Transaction_Logger should store transaction data in parsed_transactions table**
        # Verify the transaction was actually stored in the database
        transaction_count = self.session.query(ParsedTransaction).filter(
            ParsedTransaction.user_id == user_id,
            ParsedTransaction.source_bot == bot_name
        ).count()
        
        self.assertEqual(
            transaction_count, 1,
            f"Exactly one transaction should be stored in parsed_transactions table"
        )
        
        # Verify transaction ID was assigned (indicating successful database storage)
        self.assertIsNotNone(
            transaction.id,
            f"Transaction should have database-assigned ID"
        )
        
        self.assertGreater(
            transaction.id, 0,
            f"Transaction ID should be positive integer"
        )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.lists(
            st.tuples(
                st.integers(min_value=1, max_value=999),  # amount
                st.sampled_from(['Shmalala', 'GDcards', 'TestBot'])  # bot_name
            ),
            min_size=2,
            max_size=5
        ),
        st.integers(min_value=1, max_value=2147483647),  # user_id
        st.integers(min_value=0, max_value=5000)  # initial_balance
    )
    @settings(max_examples=10, deadline=None)
    def test_multiple_currency_conversions_property(self, amount_bot_pairs, user_id, initial_balance):
        """
        **Property 9: Currency Conversion and Logging**
        **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
        
        For any sequence of currency parsing operations, each should be converted and logged 
        independently with cumulative balance updates
        """
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # Create test user with specified initial balance
        user = self._create_test_user(user_id, balance=initial_balance)
        original_balance = user.balance
        
        total_expected_increase = 0
        expected_transactions = []
        
        # Define bot configurations
        bot_config = {
            'Shmalala': {'multiplier': Decimal('1.5'), 'currency_type': 'coins'},
            'GDcards': {'multiplier': Decimal('2.0'), 'currency_type': 'points'},
            'TestBot': {'multiplier': Decimal('0.5'), 'currency_type': 'credits'}
        }
        
        # Process each message
        for i, (amount, bot_name) in enumerate(amount_bot_pairs):
            config = bot_config[bot_name]
            expected_multiplier = config['multiplier']
            expected_currency_type = config['currency_type']
            
            # Create appropriate message for bot type
            if bot_name == 'Shmalala':
                message_text = f"🎣 Рыбалка 🎣\nМонеты: +{amount} (1000)💰"
            elif bot_name == 'GDcards':
                message_text = f"🃏 НОВАЯ КАРТА 🃏\nОчки: +{amount}\nКоллекция: 86/213 карт"
            elif bot_name == 'TestBot':
                message_text = f"🤖 TestBot Reward 🤖\nCredits: +{amount}\nTotal Credits: 1000"
            
            # Create mock message
            mock_message = MockMessage(message_text, user_id=user_id)
            
            # Parse message
            parsed_result = asyncio.run(self.parser.parse_message(mock_message))
            
            # **Property Part 1: Each conversion should be applied correctly**
            self.assertIsNotNone(
                parsed_result,
                f"Message {i} from {bot_name} should be parsed: {message_text[:50]}..."
            )
            
            expected_converted = Decimal(str(amount)) * expected_multiplier
            self.assertEqual(
                parsed_result.converted_amount, expected_converted,
                f"Message {i}: Converted amount should be correct for {bot_name}"
            )
            
            total_expected_increase += int(expected_converted)
            expected_transactions.append({
                'amount': amount,
                'bot_name': bot_name,
                'converted_amount': expected_converted,
                'currency_type': expected_currency_type
            })
        
        # **Property Part 2: Total balance should reflect all conversions cumulatively**
        self.session.refresh(user)
        expected_final_balance = original_balance + total_expected_increase
        self.assertEqual(
            user.balance, expected_final_balance,
            f"Final balance should reflect all converted amounts cumulatively. "
            f"Original: {original_balance}, Total increase: {total_expected_increase}, "
            f"Expected: {expected_final_balance}, Actual: {user.balance}"
        )
        
        # **Property Part 3: All transactions should be logged independently**
        logged_transactions = self.session.query(ParsedTransaction).filter(
            ParsedTransaction.user_id == user_id
        ).order_by(ParsedTransaction.id).all()
        
        self.assertEqual(
            len(logged_transactions), len(amount_bot_pairs),
            f"All transactions should be logged independently"
        )
        
        # **Property Part 4: Each logged transaction should have complete details**
        for i, expected_tx in enumerate(expected_transactions):
            logged_tx = logged_transactions[i]
            
            self.assertEqual(
                logged_tx.source_bot, expected_tx['bot_name'],
                f"Transaction {i} should have correct bot name"
            )
            
            self.assertEqual(
                logged_tx.original_amount, Decimal(str(expected_tx['amount'])),
                f"Transaction {i} should have correct original amount"
            )
            
            self.assertEqual(
                logged_tx.converted_amount, expected_tx['converted_amount'],
                f"Transaction {i} should have correct converted amount"
            )
            
            self.assertEqual(
                logged_tx.currency_type, expected_tx['currency_type'],
                f"Transaction {i} should have correct currency type"
            )
            
            self.assertIsNotNone(
                logged_tx.parsed_at,
                f"Transaction {i} should have timestamp"
            )
            
            self.assertIsNotNone(
                logged_tx.message_text,
                f"Transaction {i} should have message text"
            )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=999999),  # amount
        st.floats(min_value=0.1, max_value=10.0),  # multiplier
        st.integers(min_value=1, max_value=2147483647),  # user_id
        st.integers(min_value=0, max_value=10000)  # initial_balance
    )
    @settings(max_examples=15, deadline=None)
    def test_custom_multiplier_conversion_property(self, amount, multiplier, user_id, initial_balance):
        """
        **Property 9: Currency Conversion and Logging**
        **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
        
        For any custom multiplier configuration, the conversion should be applied correctly 
        and logged with accurate details
        """
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # Create custom parsing rule with the generated multiplier
        self.session.query(ParsingRule).filter(ParsingRule.bot_name == 'CustomBot').delete()
        
        custom_rule = ParsingRule(
            bot_name='CustomBot',
            pattern=r'Reward:\s*\+(\d+)',
            multiplier=Decimal(str(round(multiplier, 4))),  # Round to 4 decimal places
            currency_type='custom_currency',
            is_active=True
        )
        self.session.add(custom_rule)
        self.session.commit()
        
        # Reload parser rules to include the new custom rule
        self.parser.load_parsing_rules()
        
        # Create test user
        user = self._create_test_user(user_id, balance=initial_balance)
        original_balance = user.balance
        
        # Create message with custom pattern
        message_text = f"🎁 Custom Reward System 🎁\nUser: TestUser{user_id}\nReward: +{amount}\nType: Custom Currency"
        
        # Create mock message
        mock_message = MockMessage(message_text, user_id=user_id)
        
        # Parse message
        parsed_result = asyncio.run(self.parser.parse_message(mock_message))
        
        # **Property Part 1: Custom multiplier should be applied correctly**
        self.assertIsNotNone(
            parsed_result,
            f"Message with custom pattern should be parsed successfully"
        )
        
        expected_multiplier = Decimal(str(round(multiplier, 4)))
        expected_converted_amount = Decimal(str(amount)) * expected_multiplier
        
        self.assertEqual(
            parsed_result.converted_amount, expected_converted_amount,
            f"Custom multiplier ({expected_multiplier}) should be applied correctly. "
            f"Original: {amount}, Expected: {expected_converted_amount}, "
            f"Actual: {parsed_result.converted_amount}"
        )
        
        # **Property Part 2: Balance should be updated with converted amount**
        self.session.refresh(user)
        expected_new_balance = original_balance + int(expected_converted_amount)
        self.assertEqual(
            user.balance, expected_new_balance,
            f"Balance should be updated with custom converted amount"
        )
        
        # **Property Part 3: Transaction should be logged with custom details**
        transaction = self.session.query(ParsedTransaction).filter(
            ParsedTransaction.user_id == user_id,
            ParsedTransaction.source_bot == 'CustomBot'
        ).first()
        
        self.assertIsNotNone(
            transaction,
            f"Transaction should be logged for custom bot parsing"
        )
        
        self.assertEqual(
            transaction.converted_amount, expected_converted_amount,
            f"Logged transaction should have correct custom converted amount"
        )
        
        self.assertEqual(
            transaction.currency_type, 'custom_currency',
            f"Logged transaction should have correct custom currency type"
        )
    
    def test_currency_conversion_and_logging_without_hypothesis(self):
        """Fallback test when Hypothesis is not available"""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Test cases covering the currency conversion and logging property
        test_cases = [
            # (amount, bot_name, initial_balance, description)
            (100, 'Shmalala', 1000, "Shmalala with 1.5x multiplier"),
            (50, 'GDcards', 500, "GDcards with 2.0x multiplier"),
            (200, 'TestBot', 2000, "TestBot with 0.5x multiplier"),
            (1, 'Shmalala', 0, "Minimum amount with zero balance"),
            (999999, 'GDcards', 10000, "Maximum amount with high balance"),
        ]
        
        for amount, bot_name, initial_balance, description in test_cases:
            with self.subTest(amount=amount, bot_name=bot_name, description=description):
                # Clean up previous test data
                self._cleanup_test_data()
                
                # Create test user
                user_id = 12345 + hash(description) % 1000000
                user = self._create_test_user(user_id, balance=initial_balance)
                original_balance = user.balance
                
                # Define expected values
                multipliers = {'Shmalala': Decimal('1.5'), 'GDcards': Decimal('2.0'), 'TestBot': Decimal('0.5')}
                currency_types = {'Shmalala': 'coins', 'GDcards': 'points', 'TestBot': 'credits'}
                
                expected_multiplier = multipliers[bot_name]
                expected_currency_type = currency_types[bot_name]
                expected_converted = Decimal(str(amount)) * expected_multiplier
                
                # Create appropriate message
                if bot_name == 'Shmalala':
                    message_text = f"🎣 Рыбалка 🎣\nМонеты: +{amount} (1000)💰"
                elif bot_name == 'GDcards':
                    message_text = f"🃏 НОВАЯ КАРТА 🃏\nОчки: +{amount}\nКоллекция: 86/213 карт"
                elif bot_name == 'TestBot':
                    message_text = f"🤖 TestBot Reward 🤖\nCredits: +{amount}\nTotal Credits: 1000"
                
                # Create mock message and parse
                mock_message = MockMessage(message_text, user_id=user_id)
                parsed_result = asyncio.run(self.parser.parse_message(mock_message))
                
                # Verify parsing and conversion
                self.assertIsNotNone(parsed_result, f"Should parse {description}")
                self.assertEqual(parsed_result.converted_amount, expected_converted, f"Correct conversion for {description}")
                
                # Verify balance update
                self.session.refresh(user)
                expected_balance = original_balance + int(expected_converted)
                self.assertEqual(user.balance, expected_balance, f"Correct balance update for {description}")
                
                # Verify transaction logging
                transaction = self.session.query(ParsedTransaction).filter(
                    ParsedTransaction.user_id == user_id,
                    ParsedTransaction.source_bot == bot_name
                ).first()
                
                self.assertIsNotNone(transaction, f"Transaction logged for {description}")
                self.assertEqual(transaction.converted_amount, expected_converted, f"Correct logged amount for {description}")
                self.assertEqual(transaction.currency_type, expected_currency_type, f"Correct currency type for {description}")


if __name__ == '__main__':
    unittest.main()