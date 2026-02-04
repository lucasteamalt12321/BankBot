"""
Integration tests for MessageParser class
Tests complete parsing workflow with real database interactions
"""

import unittest
import os
import sys
import tempfile
from datetime import datetime
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.message_parser import MessageParser
from database.database import Base, User, ParsingRule, ParsedTransaction
from core.advanced_models import ParsingError


class TestMessageParserIntegration(unittest.TestCase):
    """Integration tests for MessageParser with real database"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database"""
        # Create temporary database
        cls.db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        cls.db_file.close()
        
        # Create engine and session
        cls.engine = create_engine(f'sqlite:///{cls.db_file.name}', echo=False)
        Base.metadata.create_all(cls.engine)
        
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test database"""
        cls.engine.dispose()
        os.unlink(cls.db_file.name)
    
    def setUp(self):
        """Set up test session and parser"""
        self.db = self.SessionLocal()
        self.parser = MessageParser(self.db)
        
        # Create test user
        self.test_user = User(
            telegram_id=12345,
            username='testuser',
            first_name='Test',
            last_name='User',
            balance=100,
            is_admin=False
        )
        self.db.add(self.test_user)
        
        # Create test parsing rules
        self.shmalala_rule = ParsingRule(
            bot_name='Shmalala',
            pattern=r'Монеты:\s*\+(\d+)',
            multiplier=Decimal('1.5'),
            currency_type='coins',
            is_active=True
        )
        
        self.gdcards_rule = ParsingRule(
            bot_name='GDcards',
            pattern=r'Очки:\s*\+(\d+)',
            multiplier=Decimal('2.0'),
            currency_type='points',
            is_active=True
        )
        
        self.db.add(self.shmalala_rule)
        self.db.add(self.gdcards_rule)
        self.db.commit()
        
        # Reload parsing rules
        self.parser.load_parsing_rules()
    
    def tearDown(self):
        """Clean up test session"""
        self.db.rollback()
        self.db.close()
    
    def test_complete_shmalala_parsing_workflow(self):
        """Test complete parsing workflow for Shmalala message"""
        message_text = """Shmalala

🎣 [Рыбалка] 🎣

Рыбак: testuser
Место: Тихое озеро
На крючке: Карп (2.5 кг)
Погода: Солнечно
Энергии осталось: 85 ⚡️

Монеты: +20 (120)💰
Опыт: +8 (45 / 100)🔋"""
        
        # Create mock message object
        class MockMessage:
            def __init__(self, text, user_id):
                self.text = text
                self.from_user = MockUser(user_id)
                self.chat = MockChat(67890)
        
        class MockUser:
            def __init__(self, user_id):
                self.id = user_id
        
        class MockChat:
            def __init__(self, chat_id):
                self.id = chat_id
        
        mock_message = MockMessage(message_text, 12345)
        
        # Parse the message
        result = self.run_async(self.parser.parse_message(mock_message))
        
        # Verify parsing result
        self.assertIsNotNone(result)
        self.assertEqual(result.user_id, 12345)
        self.assertEqual(result.source_bot, 'Shmalala')
        self.assertEqual(result.original_amount, Decimal('20'))
        self.assertEqual(result.converted_amount, Decimal('30'))  # 20 * 1.5
        self.assertEqual(result.currency_type, 'coins')
        self.assertEqual(result.message_text, message_text)
        
        # Verify database transaction was created
        db_transaction = self.db.query(ParsedTransaction).filter(
            ParsedTransaction.user_id == self.test_user.id
        ).first()
        
        self.assertIsNotNone(db_transaction)
        self.assertEqual(db_transaction.source_bot, 'Shmalala')
        self.assertEqual(db_transaction.original_amount, Decimal('20'))
        self.assertEqual(db_transaction.converted_amount, Decimal('30'))
        
        # Verify user balance was updated
        self.db.refresh(self.test_user)
        self.assertEqual(self.test_user.balance, 130)  # 100 + 30
        self.assertIsNotNone(self.test_user.last_activity)
    
    def test_complete_gdcards_parsing_workflow(self):
        """Test complete parsing workflow for GDcards message"""
        message_text = """🃏 НОВАЯ КАРТА 🃏

Игрок: testuser
─────────────────
Карта: "Легендарный дракон"
Редкость: Легендарная (🟡)
─────────────────
Описание: Могучий дракон с огненным дыханием
Категория: Мифические существа
─────────────────
Очки: +50
Коллекция: 78/150 карт
Лимит карт сегодня: 3 из 10
Эта карта есть у: 12 игроков"""
        
        # Parse as string message (no user context)
        result = self.run_async(self.parser.parse_message(message_text))
        
        # Verify parsing result
        self.assertIsNotNone(result)
        self.assertEqual(result.user_id, 0)  # No user context
        self.assertEqual(result.source_bot, 'GDcards')
        self.assertEqual(result.original_amount, Decimal('50'))
        self.assertEqual(result.converted_amount, Decimal('100'))  # 50 * 2.0
        self.assertEqual(result.currency_type, 'points')
        
        # Verify database transaction was created
        db_transaction = self.db.query(ParsedTransaction).filter(
            ParsedTransaction.source_bot == 'GDcards'
        ).first()
        
        self.assertIsNotNone(db_transaction)
        self.assertIsNone(db_transaction.user_id)  # No user context
        self.assertEqual(db_transaction.original_amount, Decimal('50'))
        self.assertEqual(db_transaction.converted_amount, Decimal('100'))
        
        # User balance should not change (no user context)
        self.db.refresh(self.test_user)
        self.assertEqual(self.test_user.balance, 100)  # Unchanged
    
    def test_parsing_with_inactive_rule(self):
        """Test parsing when rule is deactivated"""
        # Deactivate Shmalala rule
        self.shmalala_rule.is_active = False
        self.db.commit()
        
        # Reload rules
        self.parser.load_parsing_rules()
        
        message_text = "Shmalala\nМонеты: +25"
        
        result = self.run_async(self.parser.parse_message(message_text))
        
        # Should return None because rule is inactive
        self.assertIsNone(result)
        
        # No transaction should be created
        transaction_count = self.db.query(ParsedTransaction).count()
        self.assertEqual(transaction_count, 0)
    
    def test_parsing_unknown_user(self):
        """Test parsing message from unknown user"""
        class MockMessage:
            def __init__(self, text, user_id):
                self.text = text
                self.from_user = MockUser(user_id)
                self.chat = MockChat(67890)
        
        class MockUser:
            def __init__(self, user_id):
                self.id = user_id
        
        class MockChat:
            def __init__(self, chat_id):
                self.id = chat_id
        
        # Use unknown user ID
        mock_message = MockMessage("Shmalala\nМонеты: +15", 99999)
        
        result = self.run_async(self.parser.parse_message(mock_message))
        
        # Should still parse successfully
        self.assertIsNotNone(result)
        self.assertEqual(result.user_id, 99999)
        self.assertEqual(result.original_amount, Decimal('15'))
        
        # Transaction should be logged
        db_transaction = self.db.query(ParsedTransaction).filter(
            ParsedTransaction.source_bot == 'Shmalala'
        ).first()
        self.assertIsNotNone(db_transaction)
        
        # But no user balance should be updated (user doesn't exist)
        self.db.refresh(self.test_user)
        self.assertEqual(self.test_user.balance, 100)  # Unchanged
    
    def test_multiple_transactions_same_user(self):
        """Test multiple transactions for the same user"""
        messages = [
            "Shmalala\nМонеты: +10",
            "Shmalala\nМонеты: +20",
            "GDcards\nОчки: +15"
        ]
        
        class MockMessage:
            def __init__(self, text, user_id):
                self.text = text
                self.from_user = MockUser(user_id)
                self.chat = MockChat(67890)
        
        class MockUser:
            def __init__(self, user_id):
                self.id = user_id
        
        class MockChat:
            def __init__(self, chat_id):
                self.id = chat_id
        
        # Process all messages
        for message_text in messages:
            mock_message = MockMessage(message_text, 12345)
            result = self.run_async(self.parser.parse_message(mock_message))
            self.assertIsNotNone(result)
        
        # Verify all transactions were created
        transaction_count = self.db.query(ParsedTransaction).count()
        self.assertEqual(transaction_count, 3)
        
        # Verify user balance accumulation
        # Shmalala: 10 * 1.5 = 15, 20 * 1.5 = 30
        # GDcards: 15 * 2.0 = 30
        # Total: 15 + 30 + 30 = 75
        self.db.refresh(self.test_user)
        self.assertEqual(self.test_user.balance, 175)  # 100 + 75
    
    def test_parsing_rules_reload(self):
        """Test reloading parsing rules from database"""
        # Add new rule to database
        new_rule = ParsingRule(
            bot_name='TestBot',
            pattern=r'Credits:\s*\+(\d+)',
            multiplier=Decimal('0.5'),
            currency_type='credits',
            is_active=True
        )
        self.db.add(new_rule)
        self.db.commit()
        
        # Reload rules
        rules = self.parser.load_parsing_rules()
        
        # Should now have 3 rules
        self.assertEqual(len(rules), 3)
        
        # Find the new rule
        test_rule = next((r for r in rules if r.bot_name == 'TestBot'), None)
        self.assertIsNotNone(test_rule)
        self.assertEqual(test_rule.pattern, r'Credits:\s*\+(\d+)')
        self.assertEqual(test_rule.multiplier, Decimal('0.5'))
    
    def test_database_error_handling(self):
        """Test handling of database errors"""
        # Close the database session to simulate error
        self.db.close()
        
        message_text = "Shmalala\nМонеты: +10"
        
        # Should raise ParsingError on database failure
        with self.assertRaises(ParsingError):
            self.run_async(self.parser.parse_message(message_text))
    
    def test_concurrent_parsing(self):
        """Test parsing multiple messages concurrently"""
        import asyncio
        
        messages = [
            ("Shmalala\nМонеты: +5", 12345),
            ("GDcards\nОчки: +10", 12345),
            ("Shmalala\nМонеты: +15", 12345)
        ]
        
        class MockMessage:
            def __init__(self, text, user_id):
                self.text = text
                self.from_user = MockUser(user_id)
                self.chat = MockChat(67890)
        
        class MockUser:
            def __init__(self, user_id):
                self.id = user_id
        
        class MockChat:
            def __init__(self, chat_id):
                self.id = chat_id
        
        async def parse_all():
            tasks = []
            for message_text, user_id in messages:
                mock_message = MockMessage(message_text, user_id)
                task = self.parser.parse_message(mock_message)
                tasks.append(task)
            
            return await asyncio.gather(*tasks)
        
        # Parse all messages concurrently
        results = self.run_async(parse_all())
        
        # All should succeed
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertIsNotNone(result)
        
        # Verify total balance update
        # Shmalala: 5 * 1.5 = 7.5, 15 * 1.5 = 22.5
        # GDcards: 10 * 2.0 = 20
        # Total: 7.5 + 22.5 + 20 = 50
        self.db.refresh(self.test_user)
        self.assertEqual(self.test_user.balance, 150)  # 100 + 50
    
    def test_edge_case_zero_amount(self):
        """Test parsing message with zero amount"""
        message_text = "Shmalala\nМонеты: +0"
        
        result = self.run_async(self.parser.parse_message(message_text))
        
        # Should parse successfully
        self.assertIsNotNone(result)
        self.assertEqual(result.original_amount, Decimal('0'))
        self.assertEqual(result.converted_amount, Decimal('0'))
        
        # User balance should not change
        self.db.refresh(self.test_user)
        self.assertEqual(self.test_user.balance, 100)
    
    def test_edge_case_decimal_multiplier(self):
        """Test parsing with decimal multiplier"""
        # Create rule with decimal multiplier
        decimal_rule = ParsingRule(
            bot_name='DecimalBot',
            pattern=r'Points:\s*\+(\d+)',
            multiplier=Decimal('0.75'),
            currency_type='decimal_points',
            is_active=True
        )
        self.db.add(decimal_rule)
        self.db.commit()
        
        # Reload rules
        self.parser.load_parsing_rules()
        
        message_text = "DecimalBot\nPoints: +100"
        
        result = self.run_async(self.parser.parse_message(message_text))
        
        # Should apply decimal multiplier correctly
        self.assertIsNotNone(result)
        self.assertEqual(result.original_amount, Decimal('100'))
        self.assertEqual(result.converted_amount, Decimal('75'))  # 100 * 0.75
    
    def run_async(self, coro):
        """Helper to run async methods"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(coro)


if __name__ == '__main__':
    unittest.main()