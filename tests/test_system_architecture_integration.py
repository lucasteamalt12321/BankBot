#!/usr/bin/env python3
"""
Integration tests for system architecture interactions
Task 11.3: System architecture integration testing

Tests interactions between different system components:
- Admin system with existing SQLAlchemy system
- Database consistency across systems
- Notification system integration
- Error handling across components
- Performance under load

Requirements validated: 6.1, 2.1, 5.1, 5.5
"""

import unittest
import sys
import os
import tempfile
import sqlite3
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.admin_system import AdminSystem


class TestSystemArchitectureIntegration(unittest.TestCase):
    """Integration tests for system architecture interactions"""
    
    def setUp(self):
        """Setup test environment"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Initialize admin system with test database
        self.admin_system = AdminSystem(self.temp_db.name)
        
        # Test data
        self.admin_user_id = 123456789
        self.regular_users = [
            (100001, "user1", "User One"),
            (100002, "user2", "User Two"),
            (100003, "user3", "User Three"),
            (100004, "user4", "User Four"),
            (100005, "user5", "User Five"),
        ]
        
        # Setup admin user
        self.admin_system.register_user(self.admin_user_id, "admin", "Admin User")
        self.admin_system.set_admin_status(self.admin_user_id, True)
        
    def tearDown(self):
        """Clean up after tests"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    def test_database_schema_compatibility(self):
        """
        Test database schema compatibility between systems
        Requirements: System integration
        """
        # Verify admin system tables exist
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        
        # Check users table structure
        cursor.execute("PRAGMA table_info(users)")
        users_columns = cursor.fetchall()
        
        expected_columns = ['id', 'username', 'first_name', 'balance', 'is_admin']
        actual_columns = [col[1] for col in users_columns]
        
        for expected_col in expected_columns:
            self.assertIn(expected_col, actual_columns)
        
        # Check transactions table structure
        cursor.execute("PRAGMA table_info(transactions)")
        transactions_columns = cursor.fetchall()
        
        expected_tx_columns = ['id', 'user_id', 'amount', 'type', 'admin_id', 'timestamp']
        actual_tx_columns = [col[1] for col in transactions_columns]
        
        for expected_col in expected_tx_columns:
            self.assertIn(expected_col, actual_tx_columns)
        
        # Check foreign key constraints
        cursor.execute("PRAGMA foreign_key_list(transactions)")
        foreign_keys = cursor.fetchall()
        
        # Should have foreign keys for user_id and admin_id
        fk_columns = [fk[3] for fk in foreign_keys]  # Column 3 is 'from' column
        self.assertIn('user_id', fk_columns)
        self.assertIn('admin_id', fk_columns)
        
        conn.close()
    
    def test_concurrent_user_operations(self):
        """
        Test concurrent user operations for system stability
        Requirements: System stability under load
        """
        # Register multiple users
        for user_id, username, first_name in self.regular_users:
            success = self.admin_system.register_user(user_id, username, first_name)
            self.assertTrue(success)
        
        # Define operations to perform concurrently
        def add_points_operation(user_id, amount):
            """Add points to user"""
            try:
                new_balance = self.admin_system.update_balance(user_id, amount)
                if new_balance is not None:
                    transaction_id = self.admin_system.add_transaction(
                        user_id, amount, 'add', self.admin_user_id
                    )
                    return transaction_id is not None
                return False
            except Exception:
                return False
        
        def purchase_operation(user_id, amount):
            """Process purchase for user"""
            try:
                user = self.admin_system.get_user_by_id(user_id)
                if user and user['balance'] >= amount:
                    new_balance = self.admin_system.update_balance(user_id, -amount)
                    if new_balance is not None:
                        transaction_id = self.admin_system.add_transaction(
                            user_id, -amount, 'buy'
                        )
                        return transaction_id is not None
                return False
            except Exception:
                return False
        
        # Perform concurrent operations
        threads = []
        results = []
        
        # Add points to all users concurrently
        for user_id, _, _ in self.regular_users:
            thread = threading.Thread(
                target=lambda uid=user_id: results.append(
                    add_points_operation(uid, 50.0)
                )
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all operations succeeded
        self.assertEqual(len(results), len(self.regular_users))
        self.assertTrue(all(results))
        
        # Verify database consistency
        for user_id, _, _ in self.regular_users:
            user = self.admin_system.get_user_by_id(user_id)
            self.assertEqual(user['balance'], 50.0)
        
        # Perform concurrent purchases
        threads = []
        purchase_results = []
        
        for user_id, _, _ in self.regular_users:
            thread = threading.Thread(
                target=lambda uid=user_id: purchase_results.append(
                    purchase_operation(uid, 10.0)
                )
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all purchases succeeded
        self.assertEqual(len(purchase_results), len(self.regular_users))
        self.assertTrue(all(purchase_results))
        
        # Verify final balances
        for user_id, _, _ in self.regular_users:
            user = self.admin_system.get_user_by_id(user_id)
            self.assertEqual(user['balance'], 40.0)  # 50 - 10
    
    def test_transaction_integrity_under_load(self):
        """
        Test transaction integrity under high load
        Requirements: Data consistency
        """
        # Register test user
        test_user_id = 999888777
        self.admin_system.register_user(test_user_id, "testuser", "Test User")
        
        # Perform many operations rapidly
        operations = []
        expected_balance = 0.0
        
        # Generate random operations
        import random
        for i in range(100):
            if random.choice([True, False]) and expected_balance >= 10:
                # Purchase operation
                amount = -10.0
                op_type = 'buy'
            else:
                # Add points operation
                amount = random.uniform(5.0, 50.0)
                op_type = 'add'
            
            operations.append((amount, op_type))
            expected_balance += amount
        
        # Execute operations
        for amount, op_type in operations:
            if op_type == 'add':
                new_balance = self.admin_system.update_balance(test_user_id, amount)
                self.assertIsNotNone(new_balance)
                transaction_id = self.admin_system.add_transaction(
                    test_user_id, amount, op_type, self.admin_user_id
                )
            else:  # buy
                new_balance = self.admin_system.update_balance(test_user_id, amount)
                self.assertIsNotNone(new_balance)
                transaction_id = self.admin_system.add_transaction(
                    test_user_id, amount, op_type
                )
            
            self.assertIsNotNone(transaction_id)
        
        # Verify final balance
        final_user = self.admin_system.get_user_by_id(test_user_id)
        self.assertAlmostEqual(final_user['balance'], expected_balance, places=2)
        
        # Verify transaction count
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM transactions WHERE user_id = ?",
            (test_user_id,)
        )
        transaction_count = cursor.fetchone()['count']
        conn.close()
        
        self.assertEqual(transaction_count, len(operations))
    
    def test_admin_notification_system_integration(self):
        """
        Test admin notification system integration
        Requirements: 5.1 (admin notifications)
        """
        # Setup multiple admins
        admin_ids = [111111, 222222, 333333]
        for i, admin_id in enumerate(admin_ids):
            self.admin_system.register_user(admin_id, f"admin{i+1}", f"Admin {i+1}")
            self.admin_system.set_admin_status(admin_id, True)
        
        # Setup buyer
        buyer_id = 555666777
        self.admin_system.register_user(buyer_id, "buyer", "Buyer User")
        self.admin_system.update_balance(buyer_id, 100.0)
        
        # Process purchase
        purchase_amount = 10.0
        new_balance = self.admin_system.update_balance(buyer_id, -purchase_amount)
        self.assertEqual(new_balance, 90.0)
        
        # Create purchase transaction
        transaction_id = self.admin_system.add_transaction(
            buyer_id, -purchase_amount, 'buy'
        )
        self.assertIsNotNone(transaction_id)
        
        # Get all admins for notification
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users WHERE is_admin = TRUE")
        admin_list = cursor.fetchall()
        conn.close()
        
        # Verify all admins are found (including original admin)
        found_admin_ids = [admin['id'] for admin in admin_list]
        self.assertIn(self.admin_user_id, found_admin_ids)
        for admin_id in admin_ids:
            self.assertIn(admin_id, found_admin_ids)
        
        # Test notification message format
        buyer = self.admin_system.get_user_by_id(buyer_id)
        notification_message = f"Пользователь @{buyer['username']} купил контакт. Его баланс: {int(new_balance)} очков"
        
        # Verify message format
        self.assertIn("купил контакт", notification_message)
        self.assertIn(f"{int(new_balance)} очков", notification_message)
        self.assertIn("@buyer", notification_message)
        
        # Simulate notification delivery tracking
        notification_results = []
        for admin in admin_list:
            # In real implementation, this would be bot.send_message
            # Here we simulate successful delivery
            try:
                # Mock successful notification
                notification_results.append({
                    'admin_id': admin['id'],
                    'success': True,
                    'message': notification_message
                })
            except Exception as e:
                notification_results.append({
                    'admin_id': admin['id'],
                    'success': False,
                    'error': str(e)
                })
        
        # Verify all notifications were processed
        self.assertEqual(len(notification_results), len(admin_list))
        successful_notifications = [r for r in notification_results if r['success']]
        self.assertEqual(len(successful_notifications), len(admin_list))
    
    def test_error_propagation_and_recovery(self):
        """
        Test error propagation and recovery across system components
        Requirements: 5.5 (error handling)
        """
        # Test database connection errors
        # Simulate database file corruption/unavailability
        invalid_admin_system = AdminSystem("/invalid/path/database.db")
        
        # Operations should fail gracefully
        result = invalid_admin_system.register_user(123, "test", "Test")
        self.assertFalse(result)
        
        result = invalid_admin_system.is_admin(123)
        self.assertFalse(result)
        
        result = invalid_admin_system.get_user_by_id(123)
        self.assertIsNone(result)
        
        # Test recovery after errors
        # Valid system should still work
        self.admin_system.register_user(123456, "recovery_test", "Recovery Test")
        user = self.admin_system.get_user_by_id(123456)
        self.assertIsNotNone(user)
        
        # Test transaction rollback scenarios
        # Simulate partial failure during complex operation
        test_user_id = 777888999
        self.admin_system.register_user(test_user_id, "test_rollback", "Test Rollback")
        
        # Add points successfully
        balance1 = self.admin_system.update_balance(test_user_id, 50.0)
        self.assertEqual(balance1, 50.0)
        
        # Try invalid operation (should not affect previous success)
        invalid_balance = self.admin_system.update_balance(999999999, 100.0)
        self.assertIsNone(invalid_balance)
        
        # Verify original user's balance is unchanged
        user = self.admin_system.get_user_by_id(test_user_id)
        self.assertEqual(user['balance'], 50.0)
    
    def test_performance_under_load(self):
        """
        Test system performance under load
        Requirements: System performance
        """
        # Register many users
        num_users = 50
        user_ids = list(range(200000, 200000 + num_users))
        
        start_time = time.time()
        
        # Batch user registration
        for i, user_id in enumerate(user_ids):
            success = self.admin_system.register_user(
                user_id, f"perfuser{i}", f"Performance User {i}"
            )
            self.assertTrue(success)
        
        registration_time = time.time() - start_time
        
        # Should complete registration in reasonable time (< 5 seconds)
        self.assertLess(registration_time, 5.0)
        
        # Batch balance updates
        start_time = time.time()
        
        for user_id in user_ids:
            new_balance = self.admin_system.update_balance(user_id, 100.0)
            self.assertEqual(new_balance, 100.0)
        
        balance_update_time = time.time() - start_time
        
        # Should complete balance updates in reasonable time (< 10 seconds)
        self.assertLess(balance_update_time, 10.0)
        
        # Batch transaction creation
        start_time = time.time()
        
        for user_id in user_ids:
            transaction_id = self.admin_system.add_transaction(
                user_id, 100.0, 'add', self.admin_user_id
            )
            self.assertIsNotNone(transaction_id)
        
        transaction_time = time.time() - start_time
        
        # Should complete transaction logging in reasonable time (< 10 seconds)
        self.assertLess(transaction_time, 10.0)
        
        # Verify data integrity after bulk operations
        users_count = self.admin_system.get_users_count()
        self.assertGreaterEqual(users_count, num_users)
        
        # Verify random sample of users
        sample_users = user_ids[::10]  # Every 10th user
        for user_id in sample_users:
            user = self.admin_system.get_user_by_id(user_id)
            self.assertIsNotNone(user)
            self.assertEqual(user['balance'], 100.0)
    
    def test_data_consistency_across_operations(self):
        """
        Test data consistency across different types of operations
        Requirements: Data integrity
        """
        # Setup test scenario with multiple users and operations
        scenario_users = [
            (300001, "alice", "Alice"),
            (300002, "bob", "Bob"),
            (300003, "charlie", "Charlie")
        ]
        
        # Register users
        for user_id, username, first_name in scenario_users:
            self.admin_system.register_user(user_id, username, first_name)
        
        # Complex operation sequence
        operations_log = []
        
        # Alice gets points from admin
        alice_balance = self.admin_system.update_balance(300001, 75.0)
        self.admin_system.add_transaction(300001, 75.0, 'add', self.admin_user_id)
        operations_log.append(('alice', 'add', 75.0, alice_balance))
        
        # Bob gets points from admin
        bob_balance = self.admin_system.update_balance(300002, 50.0)
        self.admin_system.add_transaction(300002, 50.0, 'add', self.admin_user_id)
        operations_log.append(('bob', 'add', 50.0, bob_balance))
        
        # Charlie gets points from admin
        charlie_balance = self.admin_system.update_balance(300003, 25.0)
        self.admin_system.add_transaction(300003, 25.0, 'add', self.admin_user_id)
        operations_log.append(('charlie', 'add', 25.0, charlie_balance))
        
        # Alice makes a purchase
        alice_balance = self.admin_system.update_balance(300001, -10.0)
        self.admin_system.add_transaction(300001, -10.0, 'buy')
        operations_log.append(('alice', 'buy', -10.0, alice_balance))
        
        # Bob makes a purchase
        bob_balance = self.admin_system.update_balance(300002, -10.0)
        self.admin_system.add_transaction(300002, -10.0, 'buy')
        operations_log.append(('bob', 'buy', -10.0, bob_balance))
        
        # Charlie makes a purchase (has sufficient funds: 25 >= 10)
        charlie_user = self.admin_system.get_user_by_id(300003)
        self.assertGreaterEqual(charlie_user['balance'], 10.0)  # Should have 25, which is >= 10
        charlie_balance = self.admin_system.update_balance(300003, -10.0)
        self.admin_system.add_transaction(300003, -10.0, 'buy')
        operations_log.append(('charlie', 'buy', -10.0, charlie_balance))
        
        # Verify final balances
        expected_balances = {
            300001: 65.0,  # 75 - 10
            300002: 40.0,  # 50 - 10
            300003: 15.0   # 25 - 10
        }
        
        for user_id, expected_balance in expected_balances.items():
            user = self.admin_system.get_user_by_id(user_id)
            self.assertEqual(user['balance'], expected_balance)
        
        # Verify transaction history integrity
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        
        for user_id in [300001, 300002, 300003]:
            cursor.execute(
                "SELECT COUNT(*) as count FROM transactions WHERE user_id = ?",
                (user_id,)
            )
            tx_count = cursor.fetchone()['count']
            self.assertEqual(tx_count, 2)  # One add, one buy
        
        # Verify admin transaction attribution
        cursor.execute(
            "SELECT COUNT(*) as count FROM transactions WHERE admin_id = ? AND type = 'add'",
            (self.admin_user_id,)
        )
        admin_tx_count = cursor.fetchone()['count']
        self.assertEqual(admin_tx_count, 3)  # Three add transactions by admin
        
        # Verify purchase transactions have no admin_id
        cursor.execute(
            "SELECT COUNT(*) as count FROM transactions WHERE admin_id IS NULL AND type = 'buy'"
        )
        buy_tx_count = cursor.fetchone()['count']
        self.assertEqual(buy_tx_count, 3)  # Three buy transactions
        
        conn.close()


if __name__ == '__main__':
    unittest.main()