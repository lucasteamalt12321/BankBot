#!/usr/bin/env python3
"""
End-to-end integration test for Shmalala karma flow.

Validates Requirements: 1.4, 5.1-5.4, 6.1-6.4, 7.1, 14.1-14.2
"""

import os
import sys
import tempfile
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.classifier import MessageClassifier, MessageType
from src.parsers import KarmaParser
from src.balance_manager import BalanceManager
from src.repository import SQLiteRepository
from src.coefficient_provider import CoefficientProvider
from src.audit_logger import AuditLogger
import logging


class TestShmalaKarmaE2E(unittest.TestCase):
    """End-to-end integration tests for Shmalala karma flow."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        self.repository = SQLiteRepository(self.db_path)
        self.coefficient_provider = CoefficientProvider({
            "GD Cards": 2,
            "Shmalala": 1,
            "Shmalala Karma": 10,
            "True Mafia": 15,
            "Bunker RP": 20
        })
        
        logger = logging.getLogger("test_logger")
        logger.setLevel(logging.INFO)
        self.audit_logger = AuditLogger(logger)
        
        self.balance_manager = BalanceManager(
            self.repository,
            self.coefficient_provider,
            self.audit_logger
        )
        
        self.classifier = MessageClassifier()
        self.karma_parser = KarmaParser()
        
        self.karma_message = """Лайк! Вы повысили рейтинг пользователя KarmaPlayer.
Теперь его рейтинг: 25"""
    
    def tearDown(self):
        """Clean up test environment."""
        try:
            os.unlink(self.db_path)
        except:
            pass
    
    def test_first_time_karma_accrual(self):
        """Test first-time karma accrual (always +1)."""
        print("\n🔄 Testing first-time Shmalala karma accrual...")
        
        # Classification
        message_type = self.classifier.classify(self.karma_message)
        self.assertEqual(message_type, MessageType.SHMALALA_KARMA)
        print("    ✅ Message classified as SHMALALA_KARMA")
        
        # Parsing
        parsed = self.karma_parser.parse(self.karma_message)
        self.assertEqual(parsed.player_name, "KarmaPlayer")
        self.assertEqual(parsed.karma, Decimal("1"))  # Always 1
        self.assertEqual(parsed.game, "Shmalala Karma")
        print(f"    ✅ Parsed: player={parsed.player_name}, karma={parsed.karma}")
        
        # Balance processing
        self.balance_manager.process_karma(parsed)
        
        user = self.repository.get_or_create_user("KarmaPlayer")
        bot_balance = self.repository.get_bot_balance(user.user_id, "Shmalala Karma")
        
        self.assertIsNotNone(bot_balance)
        self.assertEqual(bot_balance.current_bot_balance, Decimal("1"))
        
        # Coefficient = 10, so bank_balance = 1 * 10 = 10
        self.assertEqual(user.bank_balance, Decimal("10"))
        print(f"    ✅ Bot balance: {bot_balance.current_bot_balance}, Bank balance: {user.bank_balance}")
        
        print("✅ First-time karma accrual test completed!")
    
    def test_multiple_karma_accruals(self):
        """Test multiple karma accruals (each +1)."""
        print("\n🔄 Testing multiple karma accruals...")
        
        # First karma
        parsed_first = self.karma_parser.parse(self.karma_message)
        self.balance_manager.process_karma(parsed_first)
        
        # Second karma
        parsed_second = self.karma_parser.parse(self.karma_message)
        self.balance_manager.process_karma(parsed_second)
        
        # Third karma
        parsed_third = self.karma_parser.parse(self.karma_message)
        self.balance_manager.process_karma(parsed_third)
        
        user = self.repository.get_or_create_user("KarmaPlayer")
        bot_balance = self.repository.get_bot_balance(user.user_id, "Shmalala Karma")
        
        # Should accumulate: 1 + 1 + 1 = 3
        self.assertEqual(bot_balance.current_bot_balance, Decimal("3"))
        # Bank balance: 3 * 10 = 30
        self.assertEqual(user.bank_balance, Decimal("30"))
        
        print(f"    ✅ Accumulated: bot_balance={bot_balance.current_bot_balance}, bank_balance={user.bank_balance}")
        print("✅ Multiple karma accruals test completed!")
    
    def test_coefficient_application(self):
        """Test Shmalala Karma coefficient (10) is applied correctly."""
        print("\n🔄 Testing Shmalala Karma coefficient application (coefficient=10)...")
        
        parsed = self.karma_parser.parse(self.karma_message)
        self.balance_manager.process_karma(parsed)
        
        user = self.repository.get_or_create_user("KarmaPlayer")
        
        # Karma = 1, coefficient = 10, bank_balance = 10
        self.assertEqual(user.bank_balance, Decimal("10"))
        print(f"    ✅ Karma: 1, Coefficient: 10, Bank balance: {user.bank_balance}")
        
        print("✅ Coefficient application test completed!")


if __name__ == "__main__":
    unittest.main(verbosity=2)
