#!/usr/bin/env python3
"""
End-to-end integration test for GD Cards profile flow.

This test validates the complete flow from message input to database persistence:
- Classification → Parsing → Balance Processing → Database Updates

Tests both:
1. First-time profile initialization (no bank balance change)
2. Subsequent profile updates with deltas (bank balance changes with coefficient 2)

Validates Requirements: 1.1, 2.1-2.5, 4.1-4.4, 5.1-5.5, 7.1, 10.1-10.5, 14.1-14.2
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.classifier import MessageClassifier
from src.parsers import ProfileParser
from src.balance_manager import BalanceManager
from src.repository import SQLiteRepository
from src.coefficient_provider import CoefficientProvider
from src.audit_logger import AuditLogger
from src.idempotency import IdempotencyChecker
from src.message_processor import MessageProcessor
import logging


class TestGDCardsProfileE2E(unittest.TestCase):
    """End-to-end integration tests for GD Cards profile flow."""
    
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
        
        # Create message processor with all parsers
        self.classifier = MessageClassifier()
        self.profile_parser = ProfileParser()
        self.idempotency_checker = IdempotencyChecker(self.repository)
        
        # Real example messages from for_programmer/messages_examples
        self.profile_message_1 = """ПРОФИЛЬ LucasTeam
───────────────
ID: 8685 (23.08.2025)
Ник: LucasTeam
Статусы: Игрок
Карт собрано: 124/213
Очки: 364 (#701)
Орбы: 10 (#342)
Клан: LucasTeamGD (#50)
Титулы: Продвинутый S2
Бейджи: Нет
Любимая карта: Нету
───────────────"""
        
        self.profile_message_2 = """ПРОФИЛЬ CrazyTimeI
───────────────
ID: 16525 (16.11.2025)
Ник: CrazyTimeI
Статусы: Игрок
Карт собрано: 6/213
Очки: 12 (#3909)
Орбы: 5 (#602)
Клан: Не в клане
Титулы: Нету
Бейджи: Нет
Любимая карта: Нету
───────────────"""
    
    def tearDown(self):
        """Clean up test environment."""
        try:
            os.unlink(self.db_path)
        except:
            pass
    
    def test_first_time_profile_initialization(self):
        """
        Test first-time profile processing:
        - Message is classified as GDCARDS_PROFILE
        - Player name and orbs are parsed correctly
        - Bot balance is initialized with last_balance = orbs, current_bot_balance = 0
        - Bank balance is NOT modified (remains 0)
        - Data is persisted to database
        
        **Validates: Requirements 1.1, 2.1-2.5, 4.1-4.4, 10.1-10.5**
        """
        print("\n🔄 Testing first-time GD Cards profile initialization...")
        
        # === PHASE 1: Classification ===
        print("  📋 Phase 1: Message classification...")
        message_type = self.classifier.classify(self.profile_message_1)
        from src.classifier import MessageType
        self.assertEqual(message_type, MessageType.GDCARDS_PROFILE, 
                        "Message should be classified as GDCARDS_PROFILE")
        print("    ✅ Message classified correctly as GDCARDS_PROFILE")
        
        # === PHASE 2: Parsing ===
        print("  🔍 Phase 2: Message parsing...")
        parsed = self.profile_parser.parse(self.profile_message_1)
        
        self.assertEqual(parsed.player_name, "LucasTeam", "Player name should be extracted correctly")
        self.assertEqual(parsed.orbs, Decimal("10"), "Orbs should be extracted correctly")
        self.assertEqual(parsed.game, "GD Cards", "Game should be GD Cards")
        print(f"    ✅ Parsed: player={parsed.player_name}, orbs={parsed.orbs}, game={parsed.game}")
        
        # === PHASE 3: Balance Processing ===
        print("  💰 Phase 3: Balance processing (first-time initialization)...")
        
        # Verify user doesn't exist yet
        user_before = self.repository.get_or_create_user("LucasTeam")
        initial_bank_balance = user_before.bank_balance
        self.assertEqual(initial_bank_balance, Decimal("0"), "Initial bank balance should be 0")
        
        # Process the profile
        self.balance_manager.process_profile(parsed)
        
        # Verify bot balance was created
        user_after = self.repository.get_or_create_user("LucasTeam")
        bot_balance = self.repository.get_bot_balance(user_after.user_id, "GD Cards")
        
        self.assertIsNotNone(bot_balance, "Bot balance should be created")
        self.assertEqual(bot_balance.last_balance, Decimal("10"), 
                        "last_balance should be set to current orbs value")
        self.assertEqual(bot_balance.current_bot_balance, Decimal("0"), 
                        "current_bot_balance should be initialized to 0")
        self.assertEqual(bot_balance.game, "GD Cards", "Game should be GD Cards")
        
        # Verify bank balance was NOT modified
        self.assertEqual(user_after.bank_balance, Decimal("0"), 
                        "Bank balance should NOT change on first profile parse")
        
        print(f"    ✅ Bot balance initialized: last_balance={bot_balance.last_balance}, "
              f"current_bot_balance={bot_balance.current_bot_balance}")
        print(f"    ✅ Bank balance unchanged: {user_after.bank_balance}")
        
        # === PHASE 4: Database Persistence ===
        print("  💾 Phase 4: Database persistence verification...")
        
        # Verify data persists across repository queries
        user_persisted = self.repository.get_or_create_user("LucasTeam")
        bot_balance_persisted = self.repository.get_bot_balance(user_persisted.user_id, "GD Cards")
        
        self.assertEqual(user_persisted.user_name, "LucasTeam")
        self.assertEqual(user_persisted.bank_balance, Decimal("0"))
        self.assertEqual(bot_balance_persisted.last_balance, Decimal("10"))
        self.assertEqual(bot_balance_persisted.current_bot_balance, Decimal("0"))
        
        print("    ✅ Data persisted correctly to database")
        print("✅ First-time profile initialization test completed successfully!")
    
    def test_subsequent_profile_update_positive_delta(self):
        """
        Test subsequent profile update with positive delta:
        - First profile initializes tracking (orbs = 10)
        - Second profile shows increased orbs (orbs = 25)
        - Delta = 15, bank_change = 15 * 2 = 30
        - Bank balance increases by 30
        - last_balance is updated to 25
        
        **Validates: Requirements 5.1-5.2, 5.5, 14.1-14.2**
        """
        print("\n🔄 Testing subsequent profile update with positive delta...")
        
        # === PHASE 1: Initialize with first profile ===
        print("  📝 Phase 1: Initialize with first profile (orbs=10)...")
        parsed_first = self.profile_parser.parse(self.profile_message_1)
        self.balance_manager.process_profile(parsed_first)
        
        user = self.repository.get_or_create_user("LucasTeam")
        bot_balance_initial = self.repository.get_bot_balance(user.user_id, "GD Cards")
        
        self.assertEqual(bot_balance_initial.last_balance, Decimal("10"))
        self.assertEqual(user.bank_balance, Decimal("0"))
        print(f"    ✅ Initial state: last_balance={bot_balance_initial.last_balance}, "
              f"bank_balance={user.bank_balance}")
        
        # === PHASE 2: Process second profile with increased orbs ===
        print("  📈 Phase 2: Process second profile with increased orbs (orbs=25)...")
        
        # Create a modified profile message with increased orbs
        profile_message_updated = self.profile_message_1.replace("Орбы: 10", "Орбы: 25")
        parsed_updated = self.profile_parser.parse(profile_message_updated)
        
        self.assertEqual(parsed_updated.orbs, Decimal("25"), "Updated orbs should be 25")
        
        # Process the updated profile
        self.balance_manager.process_profile(parsed_updated)
        
        # === PHASE 3: Verify delta calculation and balance updates ===
        print("  🧮 Phase 3: Verify delta calculation and balance updates...")
        
        user_after = self.repository.get_or_create_user("LucasTeam")
        bot_balance_after = self.repository.get_bot_balance(user_after.user_id, "GD Cards")
        
        # Delta = 25 - 10 = 15
        expected_delta = Decimal("15")
        # Bank change = delta * coefficient = 15 * 2 = 30
        expected_bank_change = expected_delta * Decimal("2")
        expected_bank_balance = Decimal("0") + expected_bank_change
        
        self.assertEqual(bot_balance_after.last_balance, Decimal("25"), 
                        "last_balance should be updated to new orbs value")
        self.assertEqual(user_after.bank_balance, expected_bank_balance, 
                        f"Bank balance should increase by {expected_bank_change}")
        
        print(f"    ✅ Delta calculated: {expected_delta}")
        print(f"    ✅ Bank change (delta * coefficient): {expected_bank_change}")
        print(f"    ✅ New bank balance: {user_after.bank_balance}")
        print(f"    ✅ Updated last_balance: {bot_balance_after.last_balance}")
        
        print("✅ Subsequent profile update with positive delta test completed successfully!")
    
    def test_subsequent_profile_update_negative_delta(self):
        """
        Test subsequent profile update with negative delta:
        - First profile initializes tracking (orbs = 10)
        - Second profile shows decreased orbs (orbs = 3)
        - Delta = -7, bank_change = -7 * 2 = -14
        - Bank balance decreases by 14
        - last_balance is updated to 3
        
        **Validates: Requirements 5.1, 5.3, 5.5, 14.1-14.2**
        """
        print("\n🔄 Testing subsequent profile update with negative delta...")
        
        # === PHASE 1: Initialize with first profile ===
        print("  📝 Phase 1: Initialize with first profile (orbs=10)...")
        parsed_first = self.profile_parser.parse(self.profile_message_1)
        self.balance_manager.process_profile(parsed_first)
        
        # Add some bank balance first so we can test negative delta
        user = self.repository.get_or_create_user("LucasTeam")
        self.repository.update_user_balance(user.user_id, Decimal("100"))
        
        user_initial = self.repository.get_or_create_user("LucasTeam")
        self.assertEqual(user_initial.bank_balance, Decimal("100"))
        print(f"    ✅ Initial state: last_balance=10, bank_balance={user_initial.bank_balance}")
        
        # === PHASE 2: Process second profile with decreased orbs ===
        print("  📉 Phase 2: Process second profile with decreased orbs (orbs=3)...")
        
        # Create a modified profile message with decreased orbs
        profile_message_updated = self.profile_message_1.replace("Орбы: 10", "Орбы: 3")
        parsed_updated = self.profile_parser.parse(profile_message_updated)
        
        self.assertEqual(parsed_updated.orbs, Decimal("3"), "Updated orbs should be 3")
        
        # Process the updated profile
        self.balance_manager.process_profile(parsed_updated)
        
        # === PHASE 3: Verify delta calculation and balance updates ===
        print("  🧮 Phase 3: Verify delta calculation and balance updates...")
        
        user_after = self.repository.get_or_create_user("LucasTeam")
        bot_balance_after = self.repository.get_bot_balance(user_after.user_id, "GD Cards")
        
        # Delta = 3 - 10 = -7
        expected_delta = Decimal("-7")
        # Bank change = delta * coefficient = -7 * 2 = -14
        expected_bank_change = expected_delta * Decimal("2")
        expected_bank_balance = Decimal("100") + expected_bank_change
        
        self.assertEqual(bot_balance_after.last_balance, Decimal("3"), 
                        "last_balance should be updated to new orbs value")
        self.assertEqual(user_after.bank_balance, expected_bank_balance, 
                        f"Bank balance should decrease by {abs(expected_bank_change)}")
        
        print(f"    ✅ Delta calculated: {expected_delta}")
        print(f"    ✅ Bank change (delta * coefficient): {expected_bank_change}")
        print(f"    ✅ New bank balance: {user_after.bank_balance}")
        print(f"    ✅ Updated last_balance: {bot_balance_after.last_balance}")
        
        print("✅ Subsequent profile update with negative delta test completed successfully!")
    
    def test_subsequent_profile_update_zero_delta(self):
        """
        Test subsequent profile update with zero delta:
        - First profile initializes tracking (orbs = 10)
        - Second profile shows same orbs (orbs = 10)
        - Delta = 0, no bank balance change
        - last_balance remains 10
        
        **Validates: Requirements 5.4**
        """
        print("\n🔄 Testing subsequent profile update with zero delta...")
        
        # === PHASE 1: Initialize with first profile ===
        print("  📝 Phase 1: Initialize with first profile (orbs=10)...")
        parsed_first = self.profile_parser.parse(self.profile_message_1)
        self.balance_manager.process_profile(parsed_first)
        
        user_initial = self.repository.get_or_create_user("LucasTeam")
        initial_bank_balance = user_initial.bank_balance
        print(f"    ✅ Initial state: last_balance=10, bank_balance={initial_bank_balance}")
        
        # === PHASE 2: Process second profile with same orbs ===
        print("  ➡️ Phase 2: Process second profile with same orbs (orbs=10)...")
        
        # Process the same profile again
        parsed_same = self.profile_parser.parse(self.profile_message_1)
        self.balance_manager.process_profile(parsed_same)
        
        # === PHASE 3: Verify no balance changes ===
        print("  🔍 Phase 3: Verify no balance changes...")
        
        user_after = self.repository.get_or_create_user("LucasTeam")
        bot_balance_after = self.repository.get_bot_balance(user_after.user_id, "GD Cards")
        
        self.assertEqual(bot_balance_after.last_balance, Decimal("10"), 
                        "last_balance should remain unchanged")
        self.assertEqual(user_after.bank_balance, initial_bank_balance, 
                        "Bank balance should NOT change when delta is 0")
        
        print(f"    ✅ Delta: 0")
        print(f"    ✅ Bank balance unchanged: {user_after.bank_balance}")
        print(f"    ✅ last_balance unchanged: {bot_balance_after.last_balance}")
        
        print("✅ Subsequent profile update with zero delta test completed successfully!")
    
    def test_coefficient_application(self):
        """
        Test that GD Cards coefficient (2) is correctly applied:
        - Initialize with orbs = 5
        - Update to orbs = 15 (delta = 10)
        - Bank change should be 10 * 2 = 20
        
        **Validates: Requirements 14.1-14.2**
        """
        print("\n🔄 Testing GD Cards coefficient application (coefficient=2)...")
        
        # Create a simple profile message
        simple_profile = """ПРОФИЛЬ TestPlayer
───────────────
Орбы: 5 (#100)
───────────────"""
        
        # Initialize
        parsed_init = self.profile_parser.parse(simple_profile)
        self.balance_manager.process_profile(parsed_init)
        
        # Update with increased orbs
        updated_profile = simple_profile.replace("Орбы: 5", "Орбы: 15")
        parsed_updated = self.profile_parser.parse(updated_profile)
        self.balance_manager.process_profile(parsed_updated)
        
        # Verify coefficient was applied
        user = self.repository.get_or_create_user("TestPlayer")
        
        # Delta = 15 - 5 = 10
        # Bank change = 10 * 2 = 20
        expected_bank_balance = Decimal("20")
        
        self.assertEqual(user.bank_balance, expected_bank_balance, 
                        "Coefficient 2 should be applied to delta")
        
        print(f"    ✅ Delta: 10")
        print(f"    ✅ Coefficient: 2")
        print(f"    ✅ Bank change: 20")
        print(f"    ✅ Final bank balance: {user.bank_balance}")
        
        print("✅ Coefficient application test completed successfully!")
    
    def test_multiple_players_isolation(self):
        """
        Test that multiple players' balances are isolated:
        - Process profiles for two different players
        - Verify each has independent bot_balance and bank_balance
        
        **Validates: Requirements 10.4**
        """
        print("\n🔄 Testing multiple players isolation...")
        
        # Process first player
        parsed_player1 = self.profile_parser.parse(self.profile_message_1)
        self.balance_manager.process_profile(parsed_player1)
        
        # Process second player
        parsed_player2 = self.profile_parser.parse(self.profile_message_2)
        self.balance_manager.process_profile(parsed_player2)
        
        # Verify both players exist independently
        user1 = self.repository.get_or_create_user("LucasTeam")
        user2 = self.repository.get_or_create_user("CrazyTimeI")
        
        bot_balance1 = self.repository.get_bot_balance(user1.user_id, "GD Cards")
        bot_balance2 = self.repository.get_bot_balance(user2.user_id, "GD Cards")
        
        self.assertNotEqual(user1.user_id, user2.user_id, "Players should have different user_ids")
        self.assertEqual(bot_balance1.last_balance, Decimal("10"), "Player 1 should have orbs=10")
        self.assertEqual(bot_balance2.last_balance, Decimal("5"), "Player 2 should have orbs=5")
        
        print(f"    ✅ Player 1 (LucasTeam): orbs=10, bank_balance={user1.bank_balance}")
        print(f"    ✅ Player 2 (CrazyTimeI): orbs=5, bank_balance={user2.bank_balance}")
        print("    ✅ Players are properly isolated")
        
        print("✅ Multiple players isolation test completed successfully!")


def run_e2e_tests():
    """Run all end-to-end tests."""
    print("🚀 Starting GD Cards Profile End-to-End Integration Tests...")
    print("=" * 80)
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(TestGDCardsProfileE2E('test_first_time_profile_initialization'))
    suite.addTest(TestGDCardsProfileE2E('test_subsequent_profile_update_positive_delta'))
    suite.addTest(TestGDCardsProfileE2E('test_subsequent_profile_update_negative_delta'))
    suite.addTest(TestGDCardsProfileE2E('test_subsequent_profile_update_zero_delta'))
    suite.addTest(TestGDCardsProfileE2E('test_coefficient_application'))
    suite.addTest(TestGDCardsProfileE2E('test_multiple_players_isolation'))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("=" * 80)
    print(f"📊 Test Results: {result.testsRun - len(result.failures) - len(result.errors)}/{result.testsRun} tests passed")
    
    if result.failures:
        print(f"❌ Failures: {len(result.failures)}")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print(f"💥 Errors: {len(result.errors)}")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    
    if success:
        print("🎉 All GD Cards profile E2E tests passed! Complete flow is working correctly.")
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
    
    return success


if __name__ == "__main__":
    success = run_e2e_tests()
    sys.exit(0 if success else 1)
