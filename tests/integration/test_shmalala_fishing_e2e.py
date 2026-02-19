#!/usr/bin/env python3
"""
End-to-end integration test for Shmalala fishing flow.

Validates Requirements: 1.3, 4.1-4.4, 6.1-6.4, 7.1, 14.1-14.2
"""

import os
import sys
import tempfile
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.classifier import MessageClassifier, MessageType
from src.parsers import FishingParser
from src.balance_manager import BalanceManager
from src.repository import SQLiteRepository
from src.coefficient_provider import CoefficientProvider
from src.audit_logger import AuditLogger
import logging


class TestShmalaFishingE2E(unittest.TestCase):
    """End-to-end integration tests for Shmalala fishing flow."""
    
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
        self.fishing_parser = FishingParser()
        
        self.fishing_message = """🎣 [Рыбалка] 🎣
───────────────
Рыбак: FisherPlayer
Рыба: Золотая рыбка
Монеты: +50 (Всего: 150)
───────────────"""
    
    def tearDown(self):
        """Clean up test environment."""
        try:
            os.unlink(self.db_path)
        except:
            pass
    
    def test_first_time_fishing_accrual(self):
        """Test first-time fishing accrual."""
        print("\n🔄 Testing first-time Shmalala fishing accrual...")
        
        # Classification
        message_type = self.classifier.classify(self.fishing_message)
        self.assertEqual(message_type, MessageType.SHMALALA_FISHING)
        print("    ✅ Message classified as SHMALALA_FISHING")
        
        # Parsing
        parsed = self.fishing_parser.parse(self.fishing_message)
        self.assertEqual(parsed.player_name, "FisherPlayer")
        self.assertEqual(parsed.coins, Decimal("50"))
        self.assertEqual(parsed.game, "Shmalala")
        print(f"    ✅ Parsed: player={parsed.player_name}, coins={parsed.coins}")
        
        # Balance processing
        self.balance_manager.process_fishing(parsed)
        
        user = self.repository.get_or_create_user("FisherPlayer")
        bot_balance = self.repository.get_bot_balance(user.user_id, "Shmalala")
        
        self.assertIsNotNone(bot_balance)
        self.assertEqual(bot_balance.current_bot_balance, Decimal("50"))
        self.assertEqual(bot_balance.last_balance, Decimal("0"))
        
        # Coefficient = 1, so bank_balance = 50 * 1 = 50
        self.assertEqual(user.bank_balance, Decimal("50"))
        print(f"    ✅ Bot balance: {bot_balance.current_bot_balance}, Bank balance: {user.bank_balance}")
        
        print("✅ First-time fishing accrual test completed!")
    
    def test_subsequent_fishing_accruals(self):
        """Test multiple fishing accruals accumulate correctly."""
        print("\n🔄 Testing subsequent fishing accruals...")
        
        # First accrual
        parsed_first = self.fishing_parser.parse(self.fishing_message)
        self.balance_manager.process_fishing(parsed_first)
        
        # Second accrual
        fishing_message_2 = self.fishing_message.replace("Монеты: +50", "Монеты: +30")
        parsed_second = self.fishing_parser.parse(fishing_message_2)
        self.balance_manager.process_fishing(parsed_second)
        
        user = self.repository.get_or_create_user("FisherPlayer")
        bot_balance = self.repository.get_bot_balance(user.user_id, "Shmalala")
        
        # Should accumulate: 50 + 30 = 80
        self.assertEqual(bot_balance.current_bot_balance, Decimal("80"))
        self.assertEqual(user.bank_balance, Decimal("80"))  # coefficient = 1
        
        print(f"    ✅ Accumulated: bot_balance={bot_balance.current_bot_balance}, bank_balance={user.bank_balance}")
        print("✅ Subsequent fishing accruals test completed!")
    
    def test_coefficient_application(self):
        """Test Shmalala coefficient (1) is applied correctly."""
        print("\n🔄 Testing Shmalala coefficient application (coefficient=1)...")
        
        parsed = self.fishing_parser.parse(self.fishing_message)
        self.balance_manager.process_fishing(parsed)
        
        user = self.repository.get_or_create_user("FisherPlayer")
        
        # Coins = 50, coefficient = 1, bank_balance = 50
        self.assertEqual(user.bank_balance, Decimal("50"))
        print(f"    ✅ Coins: 50, Coefficient: 1, Bank balance: {user.bank_balance}")
        
        print("✅ Coefficient application test completed!")


if __name__ == "__main__":
    unittest.main(verbosity=2)
