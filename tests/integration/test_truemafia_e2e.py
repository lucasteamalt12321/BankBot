#!/usr/bin/env python3
"""
End-to-end integration tests for True Mafia game flows.

Validates Requirements: 1.5, 1.6, 6.1-6.5, 7.1-7.3, 8.1-8.3, 13.1-13.5, 14.1-14.2
"""

import os
import sys
import tempfile
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.classifier import MessageClassifier, MessageType
from src.parsers import MafiaGameEndParser, MafiaProfileParser
from src.balance_manager import BalanceManager
from src.repository import SQLiteRepository
from src.coefficient_provider import CoefficientProvider
from src.audit_logger import AuditLogger
import logging


class TestTrueMafiaE2E(unittest.TestCase):
    """End-to-end integration tests for True Mafia flows."""
    
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
        self.game_end_parser = MafiaGameEndParser()
        self.profile_parser = MafiaProfileParser()
        
        self.game_end_message = """Игра окончена!
───────────────
Победители:
Player1 - Мафия
Player2 - Мирный житель
Player3 - Доктор
───────────────
Остальные участники:
Player4 - Мирный житель
───────────────"""
        
        self.profile_message = """👤 MafiaPlayer
───────────────
💎 Камни: 100
🎎 Активная роль: Мафия
💵 Деньги: 50
───────────────"""
    
    def tearDown(self):
        """Clean up test environment."""
        try:
            os.unlink(self.db_path)
        except:
            pass
    
    def test_game_end_winners(self):
        """Test True Mafia game end with multiple winners (each gets 10 money)."""
        print("\n🔄 Testing True Mafia game end flow...")
        
        # Classification
        message_type = self.classifier.classify(self.game_end_message)
        self.assertEqual(message_type, MessageType.TRUEMAFIA_GAME_END)
        print("    ✅ Message classified as TRUEMAFIA_GAME_END")
        
        # Parsing
        parsed = self.game_end_parser.parse(self.game_end_message)
        self.assertEqual(len(parsed.winners), 3)
        self.assertIn("Player1", parsed.winners)
        self.assertIn("Player2", parsed.winners)
        self.assertIn("Player3", parsed.winners)
        print(f"    ✅ Parsed {len(parsed.winners)} winners: {parsed.winners}")
        
        # Balance processing
        self.balance_manager.process_game_winners(
            winners=parsed.winners,
            game=parsed.game,
            fixed_amount=Decimal("10")
        )
        
        # Verify each winner got 10 money
        for winner_name in parsed.winners:
            user = self.repository.get_or_create_user(winner_name)
            bot_balance = self.repository.get_bot_balance(user.user_id, "True Mafia")
            
            self.assertEqual(bot_balance.current_bot_balance, Decimal("10"))
            # Bank balance: 10 * 15 = 150
            self.assertEqual(user.bank_balance, Decimal("150"))
            print(f"    ✅ {winner_name}: money=10, bank_balance=150")
        
        print("✅ Game end winners test completed!")
    
    def test_profile_first_time(self):
        """Test first-time True Mafia profile initialization."""
        print("\n🔄 Testing first-time True Mafia profile...")
        
        # Classification
        message_type = self.classifier.classify(self.profile_message)
        self.assertEqual(message_type, MessageType.TRUEMAFIA_PROFILE)
        print("    ✅ Message classified as TRUEMAFIA_PROFILE")
        
        # Parsing
        parsed = self.profile_parser.parse(self.profile_message)
        self.assertEqual(parsed.player_name, "MafiaPlayer")
        self.assertEqual(parsed.money, Decimal("50"))
        print(f"    ✅ Parsed: player={parsed.player_name}, money={parsed.money}")
        
        # Balance processing
        self.balance_manager.process_mafia_profile(parsed)
        
        user = self.repository.get_or_create_user("MafiaPlayer")
        bot_balance = self.repository.get_bot_balance(user.user_id, "True Mafia")
        
        self.assertEqual(bot_balance.last_balance, Decimal("50"))
        self.assertEqual(bot_balance.current_bot_balance, Decimal("0"))
        self.assertEqual(user.bank_balance, Decimal("0"))  # No change on first profile
        print(f"    ✅ Initialized: last_balance=50, bank_balance=0")
        
        print("✅ First-time profile test completed!")
    
    def test_profile_positive_delta(self):
        """Test True Mafia profile update with positive delta."""
        print("\n🔄 Testing True Mafia profile with positive delta...")
        
        # Initialize with first profile
        parsed_first = self.profile_parser.parse(self.profile_message)
        self.balance_manager.process_mafia_profile(parsed_first)
        
        # Update with increased money
        updated_message = self.profile_message.replace("💵 Деньги: 50", "💵 Деньги: 80")
        parsed_updated = self.profile_parser.parse(updated_message)
        self.balance_manager.process_mafia_profile(parsed_updated)
        
        user = self.repository.get_or_create_user("MafiaPlayer")
        bot_balance = self.repository.get_bot_balance(user.user_id, "True Mafia")
        
        # Delta = 80 - 50 = 30
        # Bank change = 30 * 15 = 450
        self.assertEqual(bot_balance.last_balance, Decimal("80"))
        self.assertEqual(user.bank_balance, Decimal("450"))
        print(f"    ✅ Delta: 30, Bank change: 450, New balance: {user.bank_balance}")
        
        print("✅ Profile positive delta test completed!")
    
    def test_coefficient_application(self):
        """Test True Mafia coefficient (15) is applied correctly."""
        print("\n🔄 Testing True Mafia coefficient application (coefficient=15)...")
        
        # Game end: 10 money * 15 = 150 bank coins
        parsed_game = self.game_end_parser.parse(self.game_end_message)
        self.balance_manager.process_game_winners(
            winners=["TestWinner"],
            game="True Mafia",
            fixed_amount=Decimal("10")
        )
        
        user = self.repository.get_or_create_user("TestWinner")
        self.assertEqual(user.bank_balance, Decimal("150"))
        print(f"    ✅ Game end: 10 money * 15 = {user.bank_balance} bank coins")
        
        print("✅ Coefficient application test completed!")


if __name__ == "__main__":
    unittest.main(verbosity=2)
