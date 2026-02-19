#!/usr/bin/env python3
"""
Unit tests for shop system edge cases and boundary conditions
Tests Requirements 5.1 - Shop purchase edge cases and boundary conditions

This test file validates edge cases for:
- Purchase operations with exact balance amounts
- Edge cases for insufficient balance scenarios
- Boundary conditions for shop item prices
- Transaction edge cases in purchase flow
"""

import unittest
import sys
import os
import sqlite3
import tempfile

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.admin.admin_system import AdminSystem


class TestShopEdgeCasesUnit(unittest.TestCase):
    """Unit tests for shop system edge cases and boundary conditions"""
    
    def setUp(self):
        """Set up test database and admin system"""
        # Create temporary database for testing
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.admin_system = AdminSystem(self.db_path)
        
        # Create test users
        self.setup_test_users()
    
    def tearDown(self):
        """Clean up test database"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def setup_test_users(self):
        """Set up test users for shop edge case testing"""
        # Users with various balance scenarios
        self.admin_system.register_user(100001, "zero_balance", "Zero Balance User")  # 0 balance
        self.admin_system.register_user(100002, "exact_balance", "Exact Balance User")  # Will set to 10
        self.admin_system.register_user(100003, "insufficient", "Insufficient User")  # Will set to 9.99
        self.admin_system.register_user(100004, "high_balance", "High Balance User")  # Will set to 1000
        self.admin_system.register_user(100005, "negative_balance", "Negative User")  # Will set to -10
        self.admin_system.register_user(100006, "admin_user", "Admin User")
        
        # Set balances
        self.admin_system.update_balance(100002, 10.0)  # Exact balance for purchase
        self.admin_system.update_balance(100003, 9.99)  # Just under required amount
        self.admin_system.update_balance(100004, 1000.0)  # High balance
        self.admin_system.update_balance(100005, -10.0)  # Negative balance
        
        # Set admin status
        self.admin_system.set_admin_status(100006, True)
    
    # ========== EXACT BALANCE EDGE CASES ==========
    
    def test_purchase_with_exact_balance(self):
        """Test purchase with exactly the required balance
        
        Validates: Requirements 5.1 - Exact balance purchase edge case
        """
        user_id = 100002  # Has exactly 10.0 balance
        item_price = 10.0
        
        # Verify initial balance
        user = self.admin_system.get_user_by_id(user_id)
        self.assertEqual(user['balance'], item_price, "User should have exact balance")
        
        # Simulate purchase by deducting exact amount
        new_balance = self.admin_system.update_balance(user_id, -item_price)
        self.assertEqual(new_balance, 0.0, "Balance should be zero after exact purchase")
        
        # Create purchase transaction
        transaction_id = self.admin_system.add_transaction(user_id, -item_price, 'buy')
        self.assertIsNotNone(transaction_id, "Should create purchase transaction")
        
        # Verify final state
        final_user = self.admin_system.get_user_by_id(user_id)
        self.assertEqual(final_user['balance'], 0.0, "Final balance should be zero")
    
    def test_purchase_with_fractional_balance_difference(self):
        """Test purchase with fractional balance differences
        
        Validates: Requirements 5.1 - Fractional balance edge cases
        """
        user_id = 100003  # Has 9.99 balance
        item_price = 10.0
        
        # Verify insufficient balance
        user = self.admin_system.get_user_by_id(user_id)
        self.assertLess(user['balance'], item_price, "User should have insufficient balance")
        self.assertEqual(user['balance'], 9.99, "User should have 9.99 balance")
        
        # Attempt to purchase should fail in real implementation
        # Here we test the balance check logic
        can_purchase = user['balance'] >= item_price
        self.assertFalse(can_purchase, "Should not be able to purchase with insufficient balance")
        
        # Test the exact difference
        difference = item_price - user['balance']
        self.assertAlmostEqual(difference, 0.01, places=2, 
                              msg="Difference should be exactly 0.01")
    
    def test_purchase_with_zero_balance(self):
        """Test purchase attempt with zero balance
        
        Validates: Requirements 5.1 - Zero balance purchase edge case
        """
        user_id = 100001  # Has 0 balance
        item_price = 10.0
        
        # Verify zero balance
        user = self.admin_system.get_user_by_id(user_id)
        self.assertEqual(user['balance'], 0.0, "User should have zero balance")
        
        # Check purchase eligibility
        can_purchase = user['balance'] >= item_price
        self.assertFalse(can_purchase, "Should not be able to purchase with zero balance")
        
        # Test that balance remains unchanged if purchase is blocked
        # (In real implementation, purchase would be rejected)
        current_balance = user['balance']
        self.assertEqual(current_balance, 0.0, "Balance should remain zero")
    
    def test_purchase_with_negative_balance(self):
        """Test purchase attempt with negative balance
        
        Validates: Requirements 5.1 - Negative balance purchase edge case
        """
        user_id = 100005  # Has -10 balance
        item_price = 10.0
        
        # Verify negative balance
        user = self.admin_system.get_user_by_id(user_id)
        self.assertEqual(user['balance'], -10.0, "User should have negative balance")
        
        # Check purchase eligibility
        can_purchase = user['balance'] >= item_price
        self.assertFalse(can_purchase, "Should not be able to purchase with negative balance")
        
        # Test the deficit amount
        deficit = item_price - user['balance']
        self.assertEqual(deficit, 20.0, "Deficit should be 20.0 (10 + 10)")
    
    # ========== HIGH BALANCE EDGE CASES ==========
    
    def test_purchase_with_high_balance(self):
        """Test purchase with very high balance
        
        Validates: Requirements 5.1 - High balance purchase edge case
        """
        user_id = 100004  # Has 1000 balance
        item_price = 10.0
        
        # Verify high balance
        user = self.admin_system.get_user_by_id(user_id)
        self.assertEqual(user['balance'], 1000.0, "User should have high balance")
        
        # Check purchase eligibility
        can_purchase = user['balance'] >= item_price
        self.assertTrue(can_purchase, "Should be able to purchase with high balance")
        
        # Simulate purchase
        new_balance = self.admin_system.update_balance(user_id, -item_price)
        expected_balance = 1000.0 - item_price
        self.assertEqual(new_balance, expected_balance, "Balance should be reduced correctly")
        
        # Create purchase transaction
        transaction_id = self.admin_system.add_transaction(user_id, -item_price, 'buy')
        self.assertIsNotNone(transaction_id, "Should create purchase transaction")
    
    def test_multiple_purchases_edge_cases(self):
        """Test multiple consecutive purchases edge cases
        
        Validates: Requirements 5.1 - Multiple purchase edge cases
        """
        user_id = 100004  # Has 1000 balance
        item_price = 10.0
        
        # Calculate maximum possible purchases
        initial_balance = self.admin_system.get_user_by_id(user_id)['balance']
        max_purchases = int(initial_balance // item_price)
        self.assertEqual(max_purchases, 100, "Should be able to make 100 purchases")
        
        # Simulate multiple purchases
        current_balance = initial_balance
        for i in range(5):  # Test first 5 purchases
            # Check if purchase is possible
            can_purchase = current_balance >= item_price
            self.assertTrue(can_purchase, f"Should be able to make purchase {i+1}")
            
            # Make purchase
            new_balance = self.admin_system.update_balance(user_id, -item_price)
            current_balance = new_balance
            
            # Create transaction
            transaction_id = self.admin_system.add_transaction(user_id, -item_price, 'buy')
            self.assertIsNotNone(transaction_id, f"Should create transaction for purchase {i+1}")
        
        # Verify final balance
        expected_final_balance = initial_balance - (5 * item_price)
        final_user = self.admin_system.get_user_by_id(user_id)
        self.assertEqual(final_user['balance'], expected_final_balance, 
                        "Final balance should be correct after multiple purchases")
    
    # ========== ITEM PRICE EDGE CASES ==========
    
    def test_purchase_with_fractional_item_price(self):
        """Test purchase with fractional item prices
        
        Validates: Requirements 5.1 - Fractional price edge cases
        """
        # Set up user with fractional balance
        user_id = 100002
        self.admin_system.update_balance(user_id, -10.0)  # Reset to 0
        self.admin_system.update_balance(user_id, 15.50)  # Set to 15.50
        
        # Test purchase with fractional price
        fractional_price = 10.99
        
        user = self.admin_system.get_user_by_id(user_id)
        can_purchase = user['balance'] >= fractional_price
        self.assertTrue(can_purchase, "Should be able to purchase with fractional price")
        
        # Make purchase
        new_balance = self.admin_system.update_balance(user_id, -fractional_price)
        expected_balance = 15.50 - 10.99
        self.assertAlmostEqual(new_balance, expected_balance, places=2,
                              msg="Balance should be correct after fractional purchase")
    
    def test_purchase_with_very_small_price(self):
        """Test purchase with very small item price
        
        Validates: Requirements 5.1 - Small price edge cases
        """
        user_id = 100002
        small_price = 0.01
        
        # Reset and set small balance
        user = self.admin_system.get_user_by_id(user_id)
        current_balance = user['balance']
        self.admin_system.update_balance(user_id, -current_balance)  # Reset to 0
        self.admin_system.update_balance(user_id, 1.0)  # Set to 1.0
        
        # Test purchase with very small price
        user = self.admin_system.get_user_by_id(user_id)
        can_purchase = user['balance'] >= small_price
        self.assertTrue(can_purchase, "Should be able to purchase with small price")
        
        # Make purchase
        new_balance = self.admin_system.update_balance(user_id, -small_price)
        expected_balance = 1.0 - small_price
        self.assertAlmostEqual(new_balance, expected_balance, places=2,
                              msg="Balance should be correct after small purchase")
    
    def test_purchase_with_zero_price(self):
        """Test purchase with zero price (free item)
        
        Validates: Requirements 5.1 - Zero price edge case
        """
        user_id = 100001  # Zero balance user
        zero_price = 0.0
        
        user = self.admin_system.get_user_by_id(user_id)
        can_purchase = user['balance'] >= zero_price
        self.assertTrue(can_purchase, "Should be able to purchase free item with zero balance")
        
        # Make "purchase" (no balance change)
        initial_balance = user['balance']
        new_balance = self.admin_system.update_balance(user_id, -zero_price)
        self.assertEqual(new_balance, initial_balance, "Balance should not change for free item")
        
        # Create transaction for free item
        transaction_id = self.admin_system.add_transaction(user_id, -zero_price, 'buy')
        self.assertIsNotNone(transaction_id, "Should create transaction for free item")
    
    # ========== TRANSACTION EDGE CASES ==========
    
    def test_purchase_transaction_consistency(self):
        """Test purchase transaction consistency edge cases
        
        Validates: Requirements 5.1 - Transaction consistency
        """
        user_id = 100004  # High balance user
        item_price = 10.0
        
        initial_balance = self.admin_system.get_user_by_id(user_id)['balance']
        
        # Make purchase with balance update and transaction
        new_balance = self.admin_system.update_balance(user_id, -item_price)
        transaction_id = self.admin_system.add_transaction(user_id, -item_price, 'buy')
        
        # Verify consistency
        self.assertIsNotNone(transaction_id, "Transaction should be created")
        self.assertEqual(new_balance, initial_balance - item_price, 
                        "Balance should be updated correctly")
        
        # Verify transaction was recorded
        final_user = self.admin_system.get_user_by_id(user_id)
        self.assertEqual(final_user['balance'], new_balance, 
                        "Final balance should match transaction result")
    
    def test_failed_purchase_rollback_simulation(self):
        """Test failed purchase rollback simulation
        
        Validates: Requirements 5.1 - Failed purchase handling
        """
        user_id = 100003  # Insufficient balance user (9.99)
        item_price = 10.0
        
        initial_balance = self.admin_system.get_user_by_id(user_id)['balance']
        
        # Simulate failed purchase (balance check fails)
        can_purchase = initial_balance >= item_price
        self.assertFalse(can_purchase, "Purchase should fail due to insufficient balance")
        
        # Verify balance remains unchanged
        current_user = self.admin_system.get_user_by_id(user_id)
        self.assertEqual(current_user['balance'], initial_balance, 
                        "Balance should remain unchanged after failed purchase")
        
        # No transaction should be created for failed purchase
        # (In real implementation, transaction would only be created on success)
    
    def test_concurrent_purchase_edge_cases(self):
        """Test concurrent purchase edge cases
        
        Validates: Requirements 5.1 - Concurrent purchase handling
        """
        user_id = 100004  # High balance user
        item_price = 10.0
        
        initial_balance = self.admin_system.get_user_by_id(user_id)['balance']
        
        # Simulate rapid consecutive purchases
        purchase_count = 3
        transaction_ids = []
        
        for i in range(purchase_count):
            # Check balance before each purchase
            current_user = self.admin_system.get_user_by_id(user_id)
            can_purchase = current_user['balance'] >= item_price
            self.assertTrue(can_purchase, f"Should be able to make purchase {i+1}")
            
            # Make purchase
            new_balance = self.admin_system.update_balance(user_id, -item_price)
            transaction_id = self.admin_system.add_transaction(user_id, -item_price, 'buy')
            
            transaction_ids.append(transaction_id)
            self.assertIsNotNone(transaction_id, f"Should create transaction {i+1}")
        
        # Verify all transactions were created
        self.assertEqual(len(transaction_ids), purchase_count, 
                        "All transactions should be created")
        
        # Verify final balance
        expected_final_balance = initial_balance - (purchase_count * item_price)
        final_user = self.admin_system.get_user_by_id(user_id)
        self.assertEqual(final_user['balance'], expected_final_balance, 
                        "Final balance should be correct")
    
    # ========== BOUNDARY CONDITIONS ==========
    
    def test_balance_boundary_conditions_for_purchase(self):
        """Test balance boundary conditions for purchases
        
        Validates: Requirements 5.1 - Balance boundary conditions
        """
        test_cases = [
            # (initial_balance, item_price, should_succeed)
            (10.0, 10.0, True),    # Exact balance
            (10.01, 10.0, True),   # Just over
            (9.99, 10.0, False),   # Just under
            (0.0, 10.0, False),    # Zero balance
            (-1.0, 10.0, False),   # Negative balance
            (1000.0, 10.0, True), # High balance
        ]
        
        for i, (initial_balance, item_price, should_succeed) in enumerate(test_cases):
            with self.subTest(case=i, balance=initial_balance, price=item_price):
                # Create test user for this case
                test_user_id = 200000 + i
                self.admin_system.register_user(test_user_id, f"test_user_{i}", f"Test User {i}")
                self.admin_system.update_balance(test_user_id, initial_balance)
                
                # Test purchase eligibility
                user = self.admin_system.get_user_by_id(test_user_id)
                can_purchase = user['balance'] >= item_price
                
                self.assertEqual(can_purchase, should_succeed, 
                               f"Purchase eligibility should be {should_succeed} for balance {initial_balance} and price {item_price}")
    
    def test_floating_point_precision_in_purchases(self):
        """Test floating point precision in purchase calculations
        
        Validates: Requirements 5.1 - Floating point precision in purchases
        """
        user_id = 100002
        
        # Reset balance
        current_user = self.admin_system.get_user_by_id(user_id)
        self.admin_system.update_balance(user_id, -current_user['balance'])
        
        # Set precise balance
        precise_balance = 10.123456789
        self.admin_system.update_balance(user_id, precise_balance)
        
        # Test purchase with precise price
        precise_price = 5.123456789
        
        user = self.admin_system.get_user_by_id(user_id)
        can_purchase = user['balance'] >= precise_price
        self.assertTrue(can_purchase, "Should handle precise floating point comparisons")
        
        # Make purchase
        new_balance = self.admin_system.update_balance(user_id, -precise_price)
        expected_balance = precise_balance - precise_price
        
        self.assertAlmostEqual(new_balance, expected_balance, places=6,
                              msg="Should handle precise floating point arithmetic")
    
    def test_purchase_with_admin_notification_edge_cases(self):
        """Test purchase with admin notification edge cases
        
        Validates: Requirements 5.1 - Admin notification edge cases
        """
        user_id = 100002  # Regular user
        admin_id = 100006  # Admin user
        item_price = 10.0
        
        # Reset user balance
        current_user = self.admin_system.get_user_by_id(user_id)
        self.admin_system.update_balance(user_id, -current_user['balance'])
        self.admin_system.update_balance(user_id, item_price)
        
        # Make purchase
        new_balance = self.admin_system.update_balance(user_id, -item_price)
        
        # Create purchase transaction (simulating admin notification)
        transaction_id = self.admin_system.add_transaction(user_id, -item_price, 'buy')
        self.assertIsNotNone(transaction_id, "Should create purchase transaction")
        
        # Verify admin exists for notification
        admin_user = self.admin_system.get_user_by_id(admin_id)
        self.assertIsNotNone(admin_user, "Admin user should exist")
        self.assertTrue(admin_user['is_admin'], "User should be admin")
        
        # Verify purchase user state for notification
        purchase_user = self.admin_system.get_user_by_id(user_id)
        self.assertEqual(purchase_user['balance'], 0.0, "User balance should be zero after purchase")
        self.assertIsNotNone(purchase_user['username'], "User should have username for notification")


if __name__ == '__main__':
    unittest.main()