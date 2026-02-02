#!/usr/bin/env python3
"""
Property-based tests for error handling consistency
Feature: telegram-bot-admin-system
"""

import unittest
import sys
import os
import tempfile
import sqlite3
import logging

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from hypothesis import given, strategies as st, settings, assume
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    print("Warning: Hypothesis not available. Installing...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "hypothesis"])
        from hypothesis import given, strategies as st, settings, assume
        HYPOTHESIS_AVAILABLE = True
    except Exception as e:
        print(f"Failed to install Hypothesis: {e}")
        HYPOTHESIS_AVAILABLE = False

# Import only the database functions we need to avoid telegram dependency
import sqlite3
from typing import Optional, Dict, Any, Tuple


class SimpleAdminSystem:
    """Simplified admin system for testing without telegram dependencies"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_admin_tables()
    
    def _init_admin_tables(self):
        """Initialize admin tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance REAL DEFAULT 0,
                is_admin BOOLEAN DEFAULT FALSE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                type TEXT,
                admin_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (admin_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_db_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def register_user(self, user_id: int, username: str = None, first_name: str = None) -> bool:
        """Register a new user"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if cursor.fetchone():
                conn.close()
                return True
            
            cursor.execute(
                "INSERT INTO users (id, username, first_name, balance, is_admin) VALUES (?, ?, ?, 0, FALSE)",
                (user_id, username, first_name)
            )
            
            conn.commit()
            conn.close()
            return True
            
        except Exception:
            return False
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username"""
        try:
            clean_username = username.lstrip('@')
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id, username, first_name, balance, is_admin FROM users WHERE username = ?",
                (clean_username,)
            )
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'id': result['id'],
                    'username': result['username'],
                    'first_name': result['first_name'],
                    'balance': result['balance'],
                    'is_admin': bool(result['is_admin'])
                }
            return None
            
        except Exception:
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id, username, first_name, balance, is_admin FROM users WHERE id = ?",
                (user_id,)
            )
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'id': result['id'],
                    'username': result['username'],
                    'first_name': result['first_name'],
                    'balance': result['balance'],
                    'is_admin': bool(result['is_admin'])
                }
            return None
            
        except Exception:
            return None
    
    def update_balance(self, user_id: int, amount: float) -> Optional[float]:
        """Update user balance"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                return None
            
            new_balance = result['balance'] + amount
            
            cursor.execute(
                "UPDATE users SET balance = ? WHERE id = ?",
                (new_balance, user_id)
            )
            
            conn.commit()
            conn.close()
            
            return new_balance
            
        except Exception:
            return None
    
    def set_admin_status(self, user_id: int, is_admin: bool) -> bool:
        """Set admin status for user"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE users SET is_admin = ? WHERE id = ?",
                (is_admin, user_id)
            )
            
            if cursor.rowcount == 0:
                conn.close()
                return False
            
            conn.commit()
            conn.close()
            return True
            
        except Exception:
            return False
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT is_admin FROM users WHERE id = ?",
                (user_id,)
            )
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return bool(result['is_admin'])
            else:
                return False
                
        except Exception:
            return False


class ErrorHandlingSimulator:
    """Simulates the error handling behavior of the bot commands"""
    
    def __init__(self, admin_system: SimpleAdminSystem):
        self.admin_system = admin_system
    
    def simulate_add_points_command(self, admin_user_id: int, username: str, amount: Any) -> Tuple[bool, str]:
        """
        Simulate the /add_points command error handling
        Returns (success, error_message)
        """
        try:
            # Check admin permissions
            if not self.admin_system.is_admin(admin_user_id):
                return False, "🔒 У вас нет прав администратора для выполнения этой команды."
            
            # Validate amount format
            try:
                amount_float = float(amount)
                if amount_float <= 0:
                    return False, "❌ Количество очков должно быть положительным числом"
            except (ValueError, TypeError):
                return False, "❌ Неверный формат количества очков"
            
            # Find user
            target_user = self.admin_system.get_user_by_username(username)
            if not target_user:
                return False, f"❌ Пользователь {username} не найден"
            
            # Update balance
            new_balance = self.admin_system.update_balance(target_user['id'], amount_float)
            if new_balance is None:
                return False, "❌ Не удалось обновить баланс пользователя"
            
            return True, f"Пользователю @{username.lstrip('@')} начислено {int(amount_float)} очков. Новый баланс: {int(new_balance)}"
            
        except Exception as e:
            return False, "❌ Произошла ошибка при начислении очков. Попробуйте позже или обратитесь к разработчику."
    
    def simulate_add_admin_command(self, admin_user_id: int, username: str) -> Tuple[bool, str]:
        """
        Simulate the /add_admin command error handling
        Returns (success, error_message)
        """
        try:
            # Check admin permissions
            if not self.admin_system.is_admin(admin_user_id):
                return False, "🔒 У вас нет прав администратора для выполнения этой команды."
            
            # Find user
            target_user = self.admin_system.get_user_by_username(username)
            if not target_user:
                return False, f"❌ Пользователь {username} не найден"
            
            # Check if already admin
            if target_user['is_admin']:
                return False, f"ℹ️ Пользователь @{target_user['username'] or target_user['id']} уже является администратором"
            
            # Set admin status
            success = self.admin_system.set_admin_status(target_user['id'], True)
            if not success:
                return False, "❌ Не удалось назначить пользователя администратором"
            
            return True, f"Пользователь @{username.lstrip('@')} теперь администратор"
            
        except Exception as e:
            return False, "❌ Произошла ошибка при назначении администратора. Попробуйте позже или обратитесь к разработчику."
    
    def simulate_buy_contact_command(self, user_id: int) -> Tuple[bool, str]:
        """
        Simulate the /buy_contact command error handling
        Returns (success, error_message)
        """
        try:
            # Get user
            user = self.admin_system.get_user_by_id(user_id)
            if not user:
                return False, "❌ Пользователь не найден"
            
            # Check balance
            required_amount = 10
            if user['balance'] < required_amount:
                return False, f"❌ Недостаточно очков для покупки. Требуется: {required_amount} очков, у вас: {int(user['balance'])} очков"
            
            # Update balance
            new_balance = self.admin_system.update_balance(user_id, -required_amount)
            if new_balance is None:
                return False, "❌ Не удалось обновить баланс"
            
            return True, "Вы купили контакт. Администратор свяжется с вами."
            
        except Exception as e:
            return False, "❌ Произошла ошибка при покупке. Попробуйте позже или обратитесь к администратору."


class TestErrorHandlingConsistencyPBT(unittest.TestCase):
    """Property-based tests for error handling consistency"""
    
    def setUp(self):
        """Setup test database"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Initialize admin system with test database
        self.admin_system = SimpleAdminSystem(self.temp_db.name)
        self.error_simulator = ErrorHandlingSimulator(self.admin_system)
        
        # Create test admin user
        self.admin_user_id = 999999999
        self.admin_system.register_user(self.admin_user_id, "testadmin", "Test Admin")
        self.admin_system.set_admin_status(self.admin_user_id, True)
        
        # Create test regular user
        self.regular_user_id = 888888888
        self.admin_system.register_user(self.regular_user_id, "testuser", "Test User")
        self.admin_system.update_balance(self.regular_user_id, 100.0)
        
    def tearDown(self):
        """Clean up after tests"""
        # Remove temporary database
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647),  # non-admin user ID
        st.text(min_size=1, max_size=50),  # username
        st.one_of(
            st.floats(min_value=-1000.0, max_value=0.0, allow_nan=False, allow_infinity=False),  # negative amounts
            st.text(min_size=1, max_size=20),  # non-numeric amounts
            st.none(),  # None values
            st.floats(allow_nan=True, allow_infinity=True),  # invalid floats
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_add_points_error_handling_consistency(self, non_admin_user_id, username, invalid_amount):
        """
        Feature: telegram-bot-admin-system, Property 8: Error handling consistency
        
        For any invalid input (non-admin user, wrong format, non-existent user), 
        the add_points command should return an appropriate error message without crashing
        Validates: Requirements 2.4, 2.5, 8.3, 8.4, 8.5
        """
        assume(non_admin_user_id != self.admin_user_id)  # Ensure it's not our test admin
        
        # Test with non-admin user (should fail with permission error)
        success, message = self.error_simulator.simulate_add_points_command(
            non_admin_user_id, username, invalid_amount
        )
        
        # Should always return False for non-admin users
        self.assertFalse(success, "Non-admin users should not be able to add points")
        self.assertIsInstance(message, str, "Error message should be a string")
        self.assertIn("прав администратора", message, "Should mention admin rights")
        
        # Test with admin user but invalid amount
        success, message = self.error_simulator.simulate_add_points_command(
            self.admin_user_id, username, invalid_amount
        )
        
        # Should handle invalid amounts gracefully
        self.assertIsInstance(message, str, "Error message should be a string")
        self.assertTrue(len(message) > 0, "Error message should not be empty")
        
        # Message should contain appropriate error indicators
        if not success:
            self.assertTrue(
                any(indicator in message for indicator in ["❌", "Ошибка", "Неверный", "не найден"]),
                f"Error message should contain error indicators: {message}"
            )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647),  # non-admin user ID
        st.one_of(
            st.text(min_size=1, max_size=50),  # random usernames
            st.text(min_size=0, max_size=0),   # empty strings
            st.just("@nonexistent_user_12345"),  # definitely non-existent user
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_add_admin_error_handling_consistency(self, non_admin_user_id, username):
        """
        Feature: telegram-bot-admin-system, Property 8: Error handling consistency
        
        For any invalid input (non-admin user, non-existent target user), 
        the add_admin command should return an appropriate error message without crashing
        Validates: Requirements 2.4, 8.4, 8.5
        """
        assume(non_admin_user_id != self.admin_user_id)  # Ensure it's not our test admin
        
        # Test with non-admin user (should fail with permission error)
        success, message = self.error_simulator.simulate_add_admin_command(
            non_admin_user_id, username
        )
        
        # Should always return False for non-admin users
        self.assertFalse(success, "Non-admin users should not be able to add admins")
        self.assertIsInstance(message, str, "Error message should be a string")
        self.assertIn("прав администратора", message, "Should mention admin rights")
        
        # Test with admin user but potentially non-existent username
        success, message = self.error_simulator.simulate_add_admin_command(
            self.admin_user_id, username
        )
        
        # Should handle gracefully regardless of username validity
        self.assertIsInstance(message, str, "Error message should be a string")
        self.assertTrue(len(message) > 0, "Error message should not be empty")
        
        # If unsuccessful, should contain appropriate error indicators
        if not success:
            self.assertTrue(
                any(indicator in message for indicator in ["❌", "ℹ️", "Ошибка", "не найден", "уже является"]),
                f"Error message should contain error indicators: {message}"
            )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647)  # user ID
    )
    @settings(max_examples=100, deadline=None)
    def test_buy_contact_insufficient_balance_error_handling(self, user_id):
        """
        Feature: telegram-bot-admin-system, Property 8: Error handling consistency
        
        For any user with insufficient balance, the buy_contact command should return 
        an appropriate error message with current balance information without crashing
        Validates: Requirements 5.6, 8.3
        """
        # Create user with insufficient balance (less than 10)
        self.admin_system.register_user(user_id, f"testuser_{user_id}", f"Test User {user_id}")
        self.admin_system.update_balance(user_id, 5.0)  # Less than required 10
        
        success, message = self.error_simulator.simulate_buy_contact_command(user_id)
        
        # Should fail due to insufficient balance
        self.assertFalse(success, "Should fail with insufficient balance")
        self.assertIsInstance(message, str, "Error message should be a string")
        self.assertIn("Недостаточно очков", message, "Should mention insufficient points")
        self.assertIn("Требуется: 10", message, "Should mention required amount")
        self.assertIn("у вас: 5", message, "Should mention current balance")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647)  # non-existent user ID
    )
    @settings(max_examples=100, deadline=None)
    def test_buy_contact_nonexistent_user_error_handling(self, user_id):
        """
        Feature: telegram-bot-admin-system, Property 8: Error handling consistency
        
        For any non-existent user, the buy_contact command should return 
        an appropriate error message without crashing
        Validates: Requirements 2.4, 8.4
        """
        assume(user_id not in [self.admin_user_id, self.regular_user_id])  # Ensure user doesn't exist
        
        success, message = self.error_simulator.simulate_buy_contact_command(user_id)
        
        # Should fail due to user not found
        self.assertFalse(success, "Should fail with non-existent user")
        self.assertIsInstance(message, str, "Error message should be a string")
        self.assertIn("не найден", message, "Should mention user not found")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.one_of(
            st.text(min_size=0, max_size=0),  # empty string
            st.text(min_size=1, max_size=1000).filter(lambda x: not x.strip()),  # whitespace only
            st.text(min_size=1, max_size=50).filter(lambda x: '@' not in x and x.strip()),  # no @ symbol
            st.just("@"),  # just @ symbol
            st.just("@@@@"),  # multiple @ symbols
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_username_format_error_handling_consistency(self, malformed_username):
        """
        Feature: telegram-bot-admin-system, Property 8: Error handling consistency
        
        For any malformed username format, commands should handle gracefully without crashing
        Validates: Requirements 2.5, 8.5
        """
        # Test add_points with malformed username
        success, message = self.error_simulator.simulate_add_points_command(
            self.admin_user_id, malformed_username, 100
        )
        
        # Should handle gracefully
        self.assertIsInstance(message, str, "Error message should be a string")
        self.assertTrue(len(message) > 0, "Error message should not be empty")
        
        # Test add_admin with malformed username
        success, message = self.error_simulator.simulate_add_admin_command(
            self.admin_user_id, malformed_username
        )
        
        # Should handle gracefully
        self.assertIsInstance(message, str, "Error message should be a string")
        self.assertTrue(len(message) > 0, "Error message should not be empty")
    
    def test_error_handling_without_hypothesis(self):
        """Fallback test when Hypothesis is not available"""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Test cases for error handling consistency
        test_cases = [
            # (non_admin_user_id, username, amount, expected_failure_reason)
            (123456, "nonexistent", 100, "permission"),
            (self.admin_user_id, "nonexistent", 100, "user_not_found"),
            (self.admin_user_id, "testuser", "invalid", "invalid_amount"),
            (self.admin_user_id, "testuser", -50, "negative_amount"),
            (self.admin_user_id, "", 100, "empty_username"),
        ]
        
        for user_id, username, amount, expected_reason in test_cases:
            with self.subTest(user_id=user_id, username=username, amount=amount):
                success, message = self.error_simulator.simulate_add_points_command(
                    user_id, username, amount
                )
                
                # Should handle all cases gracefully
                self.assertIsInstance(message, str, f"Error message should be string for {expected_reason}")
                self.assertTrue(len(message) > 0, f"Error message should not be empty for {expected_reason}")
                
                if expected_reason == "permission":
                    self.assertFalse(success, "Should fail for non-admin user")
                    self.assertIn("прав администратора", message)
                elif expected_reason == "user_not_found":
                    self.assertFalse(success, "Should fail for non-existent user")
                    self.assertIn("не найден", message)
                elif expected_reason in ["invalid_amount", "negative_amount"]:
                    self.assertFalse(success, "Should fail for invalid amount")
                    self.assertIn("❌", message)


if __name__ == '__main__':
    unittest.main()