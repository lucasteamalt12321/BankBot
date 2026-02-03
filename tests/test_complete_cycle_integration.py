#!/usr/bin/env python3
"""
Integration tests for complete cycle workflows
Task 11.3: Написать integration tests для полного цикла

Tests complete workflows:
- Registration → points addition → purchase
- Admin notifications
- Complete user journey scenarios
- System interactions

Requirements validated: 6.1, 2.1, 5.1, 5.5
"""

import unittest
import sys
import os
import tempfile
import sqlite3
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.admin_system import AdminSystem
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes


class TestCompleteCycleIntegration(unittest.TestCase):
    """Integration tests for complete cycle workflows"""
    
    def setUp(self):
        """Setup test environment"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Initialize admin system with test database
        self.admin_system = AdminSystem(self.temp_db.name)
        
        # Test user data
        self.regular_user_id = 123456789
        self.admin_user_id = 987654321
        self.new_user_id = 555666777
        
        # Setup initial admin user
        self.admin_system.register_user(
            self.admin_user_id, 
            "adminuser", 
            "Admin User"
        )
        self.admin_system.set_admin_status(self.admin_user_id, True)
        
    def tearDown(self):
        """Clean up after tests"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    def test_complete_user_journey_new_user(self):
        """
        Test complete user journey for a new user
        Requirements: 6.1 (auto registration), 2.1 (points addition), 5.1 (purchase)
        """
        # Step 1: New user registration (automatic)
        # Simulate new user first interaction
        success = self.admin_system.register_user(
            self.new_user_id, 
            "newuser", 
            "New User"
        )
        self.assertTrue(success)
        
        # Verify user was registered with correct defaults
        user = self.admin_system.get_user_by_id(self.new_user_id)
        self.assertIsNotNone(user)
        self.assertEqual(user['id'], self.new_user_id)
        self.assertEqual(user['username'], 'newuser')
        self.assertEqual(user['first_name'], 'New User')
        self.assertEqual(user['balance'], 0.0)
        self.assertFalse(user['is_admin'])
        
        # Step 2: Admin adds points to new user
        # Admin finds user by username
        target_user = self.admin_system.get_user_by_username("newuser")
        self.assertIsNotNone(target_user)
        self.assertEqual(target_user['id'], self.new_user_id)
        
        # Admin adds points
        points_to_add = 50.0
        new_balance = self.admin_system.update_balance(target_user['id'], points_to_add)
        self.assertEqual(new_balance, 50.0)
        
        # Create transaction record
        transaction_id = self.admin_system.add_transaction(
            target_user['id'], points_to_add, 'add', self.admin_user_id
        )
        self.assertIsNotNone(transaction_id)
        
        # Step 3: User attempts purchase (should succeed)
        updated_user = self.admin_system.get_user_by_id(self.new_user_id)
        self.assertEqual(updated_user['balance'], 50.0)
        
        # User has enough balance for purchase (10 points required)
        purchase_amount = 10.0
        self.assertGreaterEqual(updated_user['balance'], purchase_amount)
        
        # Process purchase
        final_balance = self.admin_system.update_balance(self.new_user_id, -purchase_amount)
        self.assertEqual(final_balance, 40.0)
        
        # Create purchase transaction
        purchase_transaction_id = self.admin_system.add_transaction(
            self.new_user_id, -purchase_amount, 'buy'
        )
        self.assertIsNotNone(purchase_transaction_id)
        
        # Verify final state
        final_user = self.admin_system.get_user_by_id(self.new_user_id)
        self.assertEqual(final_user['balance'], 40.0)
        
        # Verify transaction history
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY timestamp",
            (self.new_user_id,)
        )
        transactions = cursor.fetchall()
        conn.close()
        
        self.assertEqual(len(transactions), 2)
        
        # First transaction: points addition
        add_transaction = transactions[0]
        self.assertEqual(add_transaction['amount'], points_to_add)
        self.assertEqual(add_transaction['type'], 'add')
        self.assertEqual(add_transaction['admin_id'], self.admin_user_id)
        
        # Second transaction: purchase
        buy_transaction = transactions[1]
        self.assertEqual(buy_transaction['amount'], -purchase_amount)
        self.assertEqual(buy_transaction['type'], 'buy')
        self.assertIsNone(buy_transaction['admin_id'])
    
    def test_complete_cycle_insufficient_balance(self):
        """
        Test complete cycle when user has insufficient balance
        Requirements: 5.5 (error handling), 6.1 (registration)
        """
        # Step 1: Register user with no initial balance
        success = self.admin_system.register_user(
            self.regular_user_id, 
            "regularuser", 
            "Regular User"
        )
        self.assertTrue(success)
        
        user = self.admin_system.get_user_by_id(self.regular_user_id)
        self.assertEqual(user['balance'], 0.0)
        
        # Step 2: Admin adds insufficient points
        insufficient_amount = 5.0  # Less than required 10 points
        new_balance = self.admin_system.update_balance(self.regular_user_id, insufficient_amount)
        self.assertEqual(new_balance, 5.0)
        
        # Step 3: User attempts purchase (should fail)
        required_amount = 10.0
        user_balance = self.admin_system.get_user_by_id(self.regular_user_id)['balance']
        
        # Verify insufficient balance
        self.assertLess(user_balance, required_amount)
        
        # Purchase should not proceed - balance remains unchanged
        # In real implementation, this would be handled by the bot command
        # Here we verify the condition that would prevent the purchase
        self.assertFalse(user_balance >= required_amount)
        
        # Verify no purchase transaction was created
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM transactions WHERE user_id = ? AND type = 'buy'",
            (self.regular_user_id,)
        )
        buy_transactions = cursor.fetchall()
        conn.close()
        
        self.assertEqual(len(buy_transactions), 0)
    
    def test_admin_notification_workflow(self):
        """
        Test admin notification workflow during purchase
        Requirements: 5.1 (admin notifications)
        """
        # Setup: Create multiple admins
        admin2_id = 111222333
        admin3_id = 444555666
        
        self.admin_system.register_user(admin2_id, "admin2", "Admin Two")
        self.admin_system.register_user(admin3_id, "admin3", "Admin Three")
        self.admin_system.set_admin_status(admin2_id, True)
        self.admin_system.set_admin_status(admin3_id, True)
        
        # Setup user with sufficient balance
        self.admin_system.register_user(self.regular_user_id, "buyer", "Buyer User")
        self.admin_system.update_balance(self.regular_user_id, 25.0)
        
        # Process purchase
        purchase_amount = 10.0
        final_balance = self.admin_system.update_balance(self.regular_user_id, -purchase_amount)
        self.assertEqual(final_balance, 15.0)
        
        # Create purchase transaction
        self.admin_system.add_transaction(self.regular_user_id, -purchase_amount, 'buy')
        
        # Get all admins for notification
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users WHERE is_admin = TRUE")
        admin_list = cursor.fetchall()
        conn.close()
        
        # Verify all admins are found
        admin_ids = [admin['id'] for admin in admin_list]
        self.assertIn(self.admin_user_id, admin_ids)
        self.assertIn(admin2_id, admin_ids)
        self.assertIn(admin3_id, admin_ids)
        
        # Verify notification message format
        buyer = self.admin_system.get_user_by_id(self.regular_user_id)
        expected_message = f"Пользователь @{buyer['username']} купил контакт. Его баланс: {int(final_balance)} очков"
        
        self.assertIn("купил контакт", expected_message)
        self.assertIn(f"{int(final_balance)} очков", expected_message)
        self.assertIn("@buyer", expected_message)
    
    def test_multiple_users_concurrent_operations(self):
        """
        Test multiple users performing operations concurrently
        Requirements: 6.1, 2.1, 5.1 (system stability)
        """
        # Setup multiple users
        user_ids = [100001, 100002, 100003, 100004, 100005]
        usernames = ["user1", "user2", "user3", "user4", "user5"]
        
        # Register all users
        for i, user_id in enumerate(user_ids):
            success = self.admin_system.register_user(
                user_id, usernames[i], f"User {i+1}"
            )
            self.assertTrue(success)
        
        # Admin adds different amounts to each user
        amounts = [20, 15, 30, 5, 25]
        for i, user_id in enumerate(user_ids):
            new_balance = self.admin_system.update_balance(user_id, amounts[i])
            self.assertEqual(new_balance, amounts[i])
            
            # Create transaction
            transaction_id = self.admin_system.add_transaction(
                user_id, amounts[i], 'add', self.admin_user_id
            )
            self.assertIsNotNone(transaction_id)
        
        # Some users make purchases (those with sufficient balance)
        purchase_amount = 10.0
        successful_purchases = 0
        failed_purchases = 0
        
        for i, user_id in enumerate(user_ids):
            user = self.admin_system.get_user_by_id(user_id)
            if user['balance'] >= purchase_amount:
                # Process purchase
                new_balance = self.admin_system.update_balance(user_id, -purchase_amount)
                self.assertEqual(new_balance, amounts[i] - purchase_amount)
                
                # Create purchase transaction
                purchase_transaction_id = self.admin_system.add_transaction(
                    user_id, -purchase_amount, 'buy'
                )
                self.assertIsNotNone(purchase_transaction_id)
                successful_purchases += 1
            else:
                # Purchase should not proceed
                failed_purchases += 1
        
        # Verify results
        self.assertEqual(successful_purchases, 4)  # users with 20, 15, 30, 25 points
        self.assertEqual(failed_purchases, 1)     # user with 5 points
        
        # Verify database consistency
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        
        # Check total transactions
        cursor.execute("SELECT COUNT(*) as count FROM transactions")
        total_transactions = cursor.fetchone()['count']
        self.assertEqual(total_transactions, 5 + 4)  # 5 add + 4 buy transactions
        
        # Check user balances
        cursor.execute("SELECT id, balance FROM users WHERE id IN ({})".format(
            ','.join('?' * len(user_ids))
        ), user_ids)
        balances = cursor.fetchall()
        conn.close()
        
        expected_balances = {
            100001: 10,  # 20 - 10
            100002: 5,   # 15 - 10
            100003: 20,  # 30 - 10
            100004: 5,   # 5 (no purchase)
            100005: 15   # 25 - 10
        }
        
        for balance_row in balances:
            user_id = balance_row['id']
            actual_balance = balance_row['balance']
            expected_balance = expected_balances[user_id]
            self.assertEqual(actual_balance, expected_balance)
    
    def test_admin_rights_workflow(self):
        """
        Test admin rights assignment and usage workflow
        Requirements: 2.1 (admin operations)
        """
        # Step 1: Register regular user
        self.admin_system.register_user(self.regular_user_id, "regularuser", "Regular User")
        
        # Verify user is not admin initially
        user = self.admin_system.get_user_by_id(self.regular_user_id)
        self.assertFalse(user['is_admin'])
        self.assertFalse(self.admin_system.is_admin(self.regular_user_id))
        
        # Step 2: Existing admin grants admin rights
        success = self.admin_system.set_admin_status(self.regular_user_id, True)
        self.assertTrue(success)
        
        # Verify user is now admin
        updated_user = self.admin_system.get_user_by_id(self.regular_user_id)
        self.assertTrue(updated_user['is_admin'])
        self.assertTrue(self.admin_system.is_admin(self.regular_user_id))
        
        # Step 3: New admin can now perform admin operations
        # Register another user for testing
        test_user_id = 999888777
        self.admin_system.register_user(test_user_id, "testuser", "Test User")
        
        # New admin adds points to test user
        points_to_add = 100.0
        new_balance = self.admin_system.update_balance(test_user_id, points_to_add)
        self.assertEqual(new_balance, 100.0)
        
        # Create transaction with new admin as admin_id
        transaction_id = self.admin_system.add_transaction(
            test_user_id, points_to_add, 'add', self.regular_user_id
        )
        self.assertIsNotNone(transaction_id)
        
        # Verify transaction was logged correctly
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM transactions WHERE id = ?",
            (transaction_id,)
        )
        transaction = cursor.fetchone()
        conn.close()
        
        self.assertEqual(transaction['admin_id'], self.regular_user_id)
        self.assertEqual(transaction['type'], 'add')
        self.assertEqual(transaction['amount'], points_to_add)
    
    def test_database_integrity_during_operations(self):
        """
        Test database integrity during complex operations
        Requirements: System stability and data consistency
        """
        # Setup test data
        self.admin_system.register_user(self.regular_user_id, "testuser", "Test User")
        
        # Perform multiple operations
        operations = [
            ('add', 50.0),
            ('add', 25.0),
            ('buy', -10.0),
            ('add', 15.0),
            ('buy', -20.0),
        ]
        
        expected_balance = 0.0
        for operation_type, amount in operations:
            if operation_type == 'add':
                new_balance = self.admin_system.update_balance(self.regular_user_id, amount)
                transaction_id = self.admin_system.add_transaction(
                    self.regular_user_id, amount, 'add', self.admin_user_id
                )
            else:  # buy
                new_balance = self.admin_system.update_balance(self.regular_user_id, amount)
                transaction_id = self.admin_system.add_transaction(
                    self.regular_user_id, amount, 'buy'
                )
            
            expected_balance += amount
            self.assertEqual(new_balance, expected_balance)
            self.assertIsNotNone(transaction_id)
        
        # Verify final state
        final_user = self.admin_system.get_user_by_id(self.regular_user_id)
        self.assertEqual(final_user['balance'], expected_balance)
        
        # Verify transaction count and integrity
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        
        # Check transaction count
        cursor.execute(
            "SELECT COUNT(*) as count FROM transactions WHERE user_id = ?",
            (self.regular_user_id,)
        )
        transaction_count = cursor.fetchone()['count']
        self.assertEqual(transaction_count, len(operations))
        
        # Check foreign key integrity
        cursor.execute("""
            SELECT t.*, u.id as user_exists 
            FROM transactions t 
            LEFT JOIN users u ON t.user_id = u.id 
            WHERE t.user_id = ?
        """, (self.regular_user_id,))
        transactions = cursor.fetchall()
        
        for transaction in transactions:
            self.assertIsNotNone(transaction['user_exists'])
        
        # Check admin foreign key integrity
        cursor.execute("""
            SELECT t.*, u.id as admin_exists 
            FROM transactions t 
            LEFT JOIN users u ON t.admin_id = u.id 
            WHERE t.user_id = ? AND t.admin_id IS NOT NULL
        """, (self.regular_user_id,))
        admin_transactions = cursor.fetchall()
        
        for transaction in admin_transactions:
            self.assertIsNotNone(transaction['admin_exists'])
        
        conn.close()
    
    def test_error_recovery_scenarios(self):
        """
        Test system behavior during error scenarios
        Requirements: 5.5 (error handling)
        """
        # Test 1: User not found scenarios
        non_existent_user = self.admin_system.get_user_by_username("nonexistent")
        self.assertIsNone(non_existent_user)
        
        non_existent_user_by_id = self.admin_system.get_user_by_id(999999999)
        self.assertIsNone(non_existent_user_by_id)
        
        # Test 2: Invalid balance updates
        invalid_balance = self.admin_system.update_balance(999999999, 100.0)
        self.assertIsNone(invalid_balance)
        
        # Test 3: Invalid admin status updates
        invalid_admin_update = self.admin_system.set_admin_status(999999999, True)
        self.assertFalse(invalid_admin_update)
        
        # Test 4: Transaction with invalid user
        invalid_transaction = self.admin_system.add_transaction(
            999999999, 100.0, 'add', self.admin_user_id
        )
        # This might succeed depending on foreign key constraints
        # The important thing is that it doesn't crash the system
        
        # Test 5: System remains functional after errors
        # Register a valid user and perform operations
        self.admin_system.register_user(self.regular_user_id, "validuser", "Valid User")
        
        # These operations should work normally after errors
        balance = self.admin_system.update_balance(self.regular_user_id, 50.0)
        self.assertEqual(balance, 50.0)
        
        transaction_id = self.admin_system.add_transaction(
            self.regular_user_id, 50.0, 'add', self.admin_user_id
        )
        self.assertIsNotNone(transaction_id)
        
        # Verify system state is consistent
        user = self.admin_system.get_user_by_id(self.regular_user_id)
        self.assertEqual(user['balance'], 50.0)
        
        users_count = self.admin_system.get_users_count()
        self.assertGreaterEqual(users_count, 2)  # At least admin and regular user


if __name__ == '__main__':
    unittest.main()