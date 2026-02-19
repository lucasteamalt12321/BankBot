#!/usr/bin/env python3
"""
End-to-end integration test for GD Cards accrual flow.

This test validates the complete flow from message input to database persistence:
- Classification → Parsing → Balance Processing → Database Updates

Tests:
1. First-time accrual (creates bot_balance with current_bot_balance = points)
2. Subsequent accruals (adds to current_bot_balance)
3. Bank balance updates with coefficient 2
4. Multiple accruals accumulation

Validates Requirements: 1.2, 3.1-3.5, 6.1-6.4, 7.1, 10.1-10.5, 14.1-14.2
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.classifier import MessageClassifier, MessageType
from src.parsers import AccrualParser
from src.balance_manager import BalanceManager
from src.repository import SQLiteRepository
from src.coefficient_provider import CoefficientProvider
from src.audit_logger import AuditLogger
import logging


class TestGDCardsAccrualE2E(unittest.TestCase):
    """End-to-end integration tests for GD Cards accrual flow."""
    
    def setUp(self):
        """Set up test environment with temporary database."""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        # Initialize components
        self.repository = SQLiteRepository(self.db_path)
        
        # Create coefficient provider with GD Cards coefficient = 2
        self.coefficient_provider = CoefficientProvider({
            "GD Cards": 2,
            "Shmalala": 1,
            "Shmalala Karma": 10,
            "True Mafia": 15,
            "Bunker RP": 20
        })
        
        # Create audit logger
        logger = logging.getLogger("test_logger")
        logger.setLevel(logging.INFO)
        self.audit_logger = AuditLogger(logger)
        
        # Create balance manager
        self.balance_manager = BalanceManager(
            self.repository,
            self.coefficient_provider,
            self.audit_logger
        )
        
        # Create parsers and classifier
        self.classifier = MessageClassifier()
        self.accrual_parser = AccrualParser()
        
        # Example accrual message
        self.accrual_message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: TestPlayer
Карта: Rare Card
Очки: +15
───────────────"""
    
    def tearDown(self):
        """Clean up test environment."""
        try:
            os.unlink(self.db_path)
        except:
            pass
    
    def test_first_time_accrual(self):
        """
        Test first-time accrual processing:
        - Message is classified as GDCARDS_ACCRUAL
        - Player name and points are parsed correctly
        - Bot balance is created with current_bot_balance = points
        - Bank balance is increased by (points * coefficient)
        
        **Validates: Requirements 1.2, 3.1-3.5, 6.3, 10.1-10.5**
        """
        print("\n🔄 Testing first-time GD Cards accrual...")
        
        # === PHASE 1: Classification ===
        print("  📋 Phase 1: Message classification...")
        message_type = self.classifier.classify(self.accrual_message)
        self.assertEqual(message_type, MessageType.GDCARDS_ACCRUAL, 
                        "Message should be classified as GDCARDS_ACCRUAL")
        print("    ✅ Message classified correctly as GDCARDS_ACCRUAL")
        
        # === PHASE 2: Parsing ===
        print("  🔍 Phase 2: Message parsing...")
        parsed = self.accrual_parser.parse(self.accrual_message)
        
        self.assertEqual(parsed.player_name, "TestPlayer", "Player name should be extracted correctly")
        self.assertEqual(parsed.points, Decimal("15"), "Points should be extracted correctly")
        self.assertEqual(parsed.game, "GD Cards", "Game should be GD Cards")
        print(f"    ✅ Parsed: player={parsed.player_name}, points={parsed.points}, game={parsed.game}")
        
        # === PHASE 3: Balance Processing ===
        print("  💰 Phase 3: Balance processing (first-time accrual)...")
        
        # Process the accrual
        self.balance_manager.process_accrual(parsed)
        
        # Verify bot balance was created
        user = self.repository.get_or_create_user("TestPlayer")
        bot_balance = self.repository.get_bot_balance(user.user_id, "GD Cards")
        
        self.assertIsNotNone(bot_balance, "Bot balance should be created")
        self.assertEqual(bot_balance.current_bot_balance, Decimal("15"), 
                        "current_bot_balance should be set to points value")
        self.assertEqual(bot_balance.last_balance, Decimal("0"), 
                        "last_balance should be initialized to 0")
        self.assertEqual(bot_balance.game, "GD Cards", "Game should be GD Cards")
        
        # Verify bank balance was updated with coefficient
        # Bank change = 15 * 2 = 30
        expected_bank_balance = Decimal("30")
        self.assertEqual(user.bank_balance, expected_bank_balance, 
                        "Bank balance should be increased by (points * coefficient)")
        
        print(f"    ✅ Bot balance created: current_bot_balance={bot_balance.current_bot_balance}, "
              f"last_balance={bot_balance.last_balance}")
        print(f"    ✅ Bank balance updated: {user.bank_balance} (15 * 2 = 30)")
        
        print("✅ First-time accrual test completed successfully!")
    
    def test_subsequent_accruals(self):
        """
        Test subsequent accrual processing:
        - First accrual: +15 points
        - Second accrual: +10 points
        - current_bot_balance should accumulate: 15 + 10 = 25
        - Bank balance should accumulate: (15 * 2) + (10 * 2) = 50
        
        **Validates: Requirements 6.1-6.2, 6.4, 14.1-14.2**
        """
        print("\n🔄 Testing subsequent accruals...")
        
        # === PHASE 1: First accrual ===
        print("  📝 Phase 1: Process first accrual (+15 points)...")
        parsed_first = self.accrual_parser.parse(self.accrual_message)
        self.balance_manager.process_accrual(parsed_first)
        
        user = self.repository.get_or_create_user("TestPlayer")
        bot_balance_first = self.repository.get_bot_balance(user.user_id, "GD Cards")
        
        self.assertEqual(bot_balance_first.current_bot_balance, Decimal("15"))
        self.assertEqual(user.bank_balance, Decimal("30"))
        print(f"    ✅ After first accrual: current_bot_balance=15, bank_balance=30")
        
        # === PHASE 2: Second accrual ===
        print("  📈 Phase 2: Process second accrual (+10 points)...")
        
        # Create second accrual message
        accrual_message_2 = self.accrual_message.replace("Очки: +15", "Очки: +10")
        parsed_second = self.accrual_parser.parse(accrual_message_2)
        self.balance_manager.process_accrual(parsed_second)
        
        # === PHASE 3: Verify accumulation ===
        print("  🧮 Phase 3: Verify accumulation...")
        
        user_after = self.repository.get_or_create_user("TestPlayer")
        bot_balance_after = self.repository.get_bot_balance(user_after.user_id, "GD Cards")
        
        # current_bot_balance should accumulate: 15 + 10 = 25
        expected_bot_balance = Decimal("25")
        self.assertEqual(bot_balance_after.current_bot_balance, expected_bot_balance,
                        "current_bot_balance should accumulate")
        
        # Bank balance should accumulate: 30 + (10 * 2) = 50
        expected_bank_balance = Decimal("50")
        self.assertEqual(user_after.bank_balance, expected_bank_balance,
                        "Bank balance should accumulate with coefficient")
        
        # last_balance should remain 0 (not modified by accruals)
        self.assertEqual(bot_balance_after.last_balance, Decimal("0"),
                        "last_balance should not be modified by accruals")
        
        print(f"    ✅ Accumulated current_bot_balance: {bot_balance_after.current_bot_balance}")
        print(f"    ✅ Accumulated bank_balance: {user_after.bank_balance}")
        print(f"    ✅ last_balance unchanged: {bot_balance_after.last_balance}")
        
        print("✅ Subsequent accruals test completed successfully!")
    
    def test_coefficient_application(self):
        """
        Test that GD Cards coefficient (2) is correctly applied:
        - Accrual of 20 points
        - Bank change should be 20 * 2 = 40
        
        **Validates: Requirements 14.1-14.2**
        """
        print("\n🔄 Testing GD Cards coefficient application (coefficient=2)...")
        
        # Create accrual with 20 points
        accrual_message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: CoefficientTest
Карта: Epic Card
Очки: +20
───────────────"""
        
        parsed = self.accrual_parser.parse(accrual_message)
        self.balance_manager.process_accrual(parsed)
        
        # Verify coefficient was applied
        user = self.repository.get_or_create_user("CoefficientTest")
        bot_balance = self.repository.get_bot_balance(user.user_id, "GD Cards")
        
        # Points = 20
        # Bank change = 20 * 2 = 40
        expected_bank_balance = Decimal("40")
        
        self.assertEqual(bot_balance.current_bot_balance, Decimal("20"),
                        "current_bot_balance should be 20 (without coefficient)")
        self.assertEqual(user.bank_balance, expected_bank_balance, 
                        "Coefficient 2 should be applied to bank balance")
        
        print(f"    ✅ Points: 20")
        print(f"    ✅ Coefficient: 2")
        print(f"    ✅ Bank change: 40")
        print(f"    ✅ current_bot_balance: {bot_balance.current_bot_balance}")
        print(f"    ✅ bank_balance: {user.bank_balance}")
        
        print("✅ Coefficient application test completed successfully!")
    
    def test_multiple_players_isolation(self):
        """
        Test that multiple players' accruals are isolated:
        - Process accruals for two different players
        - Verify each has independent bot_balance and bank_balance
        
        **Validates: Requirements 10.4**
        """
        print("\n🔄 Testing multiple players isolation...")
        
        # Process accrual for first player
        accrual_1 = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: Player1
Карта: Card A
Очки: +10
───────────────"""
        
        parsed_1 = self.accrual_parser.parse(accrual_1)
        self.balance_manager.process_accrual(parsed_1)
        
        # Process accrual for second player
        accrual_2 = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: Player2
Карта: Card B
Очки: +25
───────────────"""
        
        parsed_2 = self.accrual_parser.parse(accrual_2)
        self.balance_manager.process_accrual(parsed_2)
        
        # Verify both players exist independently
        user1 = self.repository.get_or_create_user("Player1")
        user2 = self.repository.get_or_create_user("Player2")
        
        bot_balance1 = self.repository.get_bot_balance(user1.user_id, "GD Cards")
        bot_balance2 = self.repository.get_bot_balance(user2.user_id, "GD Cards")
        
        self.assertNotEqual(user1.user_id, user2.user_id, "Players should have different user_ids")
        self.assertEqual(bot_balance1.current_bot_balance, Decimal("10"), "Player 1 should have 10 points")
        self.assertEqual(bot_balance2.current_bot_balance, Decimal("25"), "Player 2 should have 25 points")
        self.assertEqual(user1.bank_balance, Decimal("20"), "Player 1 bank balance should be 20")
        self.assertEqual(user2.bank_balance, Decimal("50"), "Player 2 bank balance should be 50")
        
        print(f"    ✅ Player 1: points=10, bank_balance=20")
        print(f"    ✅ Player 2: points=25, bank_balance=50")
        print("    ✅ Players are properly isolated")
        
        print("✅ Multiple players isolation test completed successfully!")
    
    def test_decimal_precision(self):
        """
        Test that decimal precision is preserved:
        - Accrual with decimal points (e.g., 12.5)
        - Verify precision is maintained in both bot_balance and bank_balance
        
        **Validates: Requirements 3.4**
        """
        print("\n🔄 Testing decimal precision preservation...")
        
        # Create accrual with decimal points
        accrual_message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: DecimalTest
Карта: Decimal Card
Очки: +12.5
───────────────"""
        
        parsed = self.accrual_parser.parse(accrual_message)
        self.balance_manager.process_accrual(parsed)
        
        # Verify precision is preserved
        user = self.repository.get_or_create_user("DecimalTest")
        bot_balance = self.repository.get_bot_balance(user.user_id, "GD Cards")
        
        self.assertEqual(bot_balance.current_bot_balance, Decimal("12.5"),
                        "Decimal precision should be preserved in bot_balance")
        self.assertEqual(user.bank_balance, Decimal("25"),
                        "Bank balance should be 12.5 * 2 = 25")
        
        print(f"    ✅ Points with decimal: 12.5")
        print(f"    ✅ current_bot_balance: {bot_balance.current_bot_balance}")
        print(f"    ✅ bank_balance: {user.bank_balance}")
        
        print("✅ Decimal precision test completed successfully!")


def run_e2e_tests():
    """Run all end-to-end tests."""
    print("🚀 Starting GD Cards Accrual End-to-End Integration Tests...")
    print("=" * 80)
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(TestGDCardsAccrualE2E('test_first_time_accrual'))
    suite.addTest(TestGDCardsAccrualE2E('test_subsequent_accruals'))
    suite.addTest(TestGDCardsAccrualE2E('test_coefficient_application'))
    suite.addTest(TestGDCardsAccrualE2E('test_multiple_players_isolation'))
    suite.addTest(TestGDCardsAccrualE2E('test_decimal_precision'))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("=" * 80)
    print(f"📊 Test Results: {result.testsRun - len(result.failures) - len(result.errors)}/{result.testsRun} tests passed")
    
    if result.failures:
        print(f"❌ Failures: {len(result.failures)}")
    
    if result.errors:
        print(f"💥 Errors: {len(result.errors)}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    
    if success:
        print("🎉 All GD Cards accrual E2E tests passed! Complete flow is working correctly.")
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
    
    return success


if __name__ == "__main__":
    success = run_e2e_tests()
    sys.exit(0 if success else 1)
