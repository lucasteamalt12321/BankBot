#!/usr/bin/env python3
"""
End-to-end integration tests for BunkerRP game flows.

Validates Requirements: 1.7, 1.8, 8.1-8.3, 9.1-9.3, 13.1-13.5, 14.1-14.2
"""

import os
import sys
import tempfile
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.classifier import MessageClassifier, MessageType
from src.parsers import BunkerGameEndParser, BunkerProfileParser
from src.balance_manager import BalanceManager
from src.repository import SQLiteRepository
from src.coefficient_provider import CoefficientProvider
from src.audit_logger import AuditLogger
import logging


class TestBunkerRPE2E(unittest.TestCase):
    """End-to-end integration tests for BunkerRP flows."""
    
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
        self.game_end_parser = BunkerGameEndParser()
        self.profile_parser = BunkerProfileParser()
        
        self.game_end_message = """Прошли в бункер:
1. BunkerPlayer1
2. BunkerPlayer2
───────────────
Не прошли в бункер:
3. BunkerPlayer3
───────────────"""
        
        self.profile_message = """👤 BunkerPlayer
───────────────
💎 Кристаллики: 200
🎯 Побед: 5
💵 Деньги: 100
───────────────"""
    
    def tearDown(self):
        """Clean up test environment."""
        try:
            os.unlink(self.db_path)
        except:
            pass
    
    def test_game_end_winners(self):
        """Test BunkerRP game end with multiple winners (each gets 30 money)."""
        print("\n🔄 Testing BunkerRP game end flow...")
        
        # Classification
        message_type = self.classifier.classify(self.game_end_message)
        self.assertEqual(message_type, MessageType.BUNKERRP_GAME_END)
        print("    ✅ Message classified as BUNKERRP_GAME_END")
        
        # Parsing
        parsed = self.game_end_parser.parse(self.game_end_message)
        self.assertEqual(len(parsed.winners), 2)
        self.assertIn("BunkerPlayer1", parsed.winners)
        self.assertIn("BunkerPlayer2", parsed.winners)
        print(f"    ✅ Parsed {len(parsed.winners)} winners: {parsed.winners}")
        
        # Balance processing
        self.balance_manager.process_game_winners(
            winners=parsed.winners,
            game=parsed.game,
            fixed_amount=Decimal("30")
        )
        
        # Verify each winner got 30 money
        for winner_name in parsed.winners:
            user = self.repository.get_or_create_user(winner_name)
            bot_balance = self.repository.get_bot_balance(user.user_id, "Bunker RP")
            
            self.assertEqual(bot_balance.current_bot_balance, Decimal("30"))
            # Bank balance: 30 * 20 = 600
            self.assertEqual(user.bank_balance, Decimal("600"))
            print(f"    ✅ {winner_name}: money=30, bank_balance=600")
        
        print("✅ Game end winners test completed!")
    
    def test_profile_first_time(self):
        """Test first-time BunkerRP profile initialization."""
        print("\n🔄 Testing first-time BunkerRP profile...")
        
        # Classification
        message_type = self.classifier.classify(self.profile_message)
        self.assertEqual(message_type, MessageType.BUNKERRP_PROFILE)
        print("    ✅ Message classified as BUNKERRP_PROFILE")
        
        # Parsing
        parsed = self.profile_parser.parse(self.profile_message)
        self.assertEqual(parsed.player_name, "BunkerPlayer")
        self.assertEqual(parsed.money, Decimal("100"))
        print(f"    ✅ Parsed: player={parsed.player_name}, money={parsed.money}")
        
        # Balance processing
        self.balance_manager.process_bunker_profile(parsed)
        
        user = self.repository.get_or_create_user("BunkerPlayer")
        bot_balance = self.repository.get_bot_balance(user.user_id, "Bunker RP")
        
        self.assertEqual(bot_balance.last_balance, Decimal("100"))
        self.assertEqual(bot_balance.current_bot_balance, Decimal("0"))
        self.assertEqual(user.bank_balance, Decimal("0"))  # No change on first profile
        print(f"    ✅ Initialized: last_balance=100, bank_balance=0")
        
        print("✅ First-time profile test completed!")
    
    def test_profile_positive_delta(self):
        """Test BunkerRP profile update with positive delta."""
        print("\n🔄 Testing BunkerRP profile with positive delta...")
        
        # Initialize with first profile
        parsed_first = self.profile_parser.parse(self.profile_message)
        self.balance_manager.process_bunker_profile(parsed_first)
        
        # Update with increased money
        updated_message = self.profile_message.replace("💵 Деньги: 100", "💵 Деньги: 150")
        parsed_updated = self.profile_parser.parse(updated_message)
        self.balance_manager.process_bunker_profile(parsed_updated)
        
        user = self.repository.get_or_create_user("BunkerPlayer")
        bot_balance = self.repository.get_bot_balance(user.user_id, "Bunker RP")
        
        # Delta = 150 - 100 = 50
        # Bank change = 50 * 20 = 1000
        self.assertEqual(bot_balance.last_balance, Decimal("150"))
        self.assertEqual(user.bank_balance, Decimal("1000"))
        print(f"    ✅ Delta: 50, Bank change: 1000, New balance: {user.bank_balance}")
        
        print("✅ Profile positive delta test completed!")
    
    def test_coefficient_application(self):
        """Test BunkerRP coefficient (20) is applied correctly."""
        print("\n🔄 Testing BunkerRP coefficient application (coefficient=20)...")
        
        # Game end: 30 money * 20 = 600 bank coins
        parsed_game = self.game_end_parser.parse(self.game_end_message)
        self.balance_manager.process_game_winners(
            winners=["TestWinner"],
            game="Bunker RP",
            fixed_amount=Decimal("30")
        )
        
        user = self.repository.get_or_create_user("TestWinner")
        self.assertEqual(user.bank_balance, Decimal("600"))
        print(f"    ✅ Game end: 30 money * 20 = {user.bank_balance} bank coins")
        
        print("✅ Coefficient application test completed!")


if __name__ == "__main__":
    unittest.main(verbosity=2)
