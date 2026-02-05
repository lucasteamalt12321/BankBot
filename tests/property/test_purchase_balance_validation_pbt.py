#!/usr/bin/env python3
"""
Property-based tests for purchase balance validation
Feature: telegram-bot-admin-system, Property 6: Purchase balance validation
"""

import unittest
import sys
import os
import tempfile
import sqlite3

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from hypothesis import given, strategies as st, settings
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    print("Warning: Hypothesis not available. Installing...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "hypothesis"])
        from hypothesis import given, strategies as st, settings
        HYPOTHESIS_AVAILABLE = True
    except Exception as e:
        print(f"Failed to install Hypothesis: {e}")
        HYPOTHESIS_AVAILABLE = False

from typing import Optional, Dict


class SimplePurchaseSystem:
    """Simplified purchase system for testing without telegram dependencies"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_tables()
    
    def _init_tables(self):
        """Initialize database tables"""
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
    
    def register_user(self, user_id: int, username: str = None, first_name: str = None, balance: float = 0) -> bool:
        """Register a new user with specified balance"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if cursor.fetchone():
                # Update existing user's balance
                cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (balance, user_id))
            else:
                # Create new user
                cursor.execute(
                    "INSERT INTO users (id, username, first_name, balance, is_admin) VALUES (?, ?, ?, ?, FALSE)",
                    (user_id, username, first_name, balance)
                )
            
            conn.commit()
            conn.close()
            return True
            
        except Exception:
            return False
    
    def get_user_balance(self, user_id: int) -> Optional[float]:
        """Get user balance"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
            result = cursor.fetchone()
            conn.close()
            
            return result['balance'] if result else None
            
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
            
            cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
            
            conn.commit()
            conn.close()
            
            return new_balance
            
        except Exception:
            return None
    
    def add_transaction(self, user_id: int, amount: float, transaction_type: str) -> Optional[int]:
        """Add transaction record"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO transactions (user_id, amount, type) VALUES (?, ?, ?)",
                (user_id, amount, transaction_type)
            )
            
            transaction_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return transaction_id
            
        except Exception:
            return None
    
    def attempt_purchase(self, user_id: int, item_price: float) -> Dict:
        """
        Attempt to purchase an item
        Returns dict with success status and details
        """
        try:
            # Get current balance
            current_balance = self.get_user_balance(user_id)
            if current_balance is None:
                return {"success": False, "error": "User not found"}
            
            # Check if balance is sufficient
            has_sufficient_balance = current_balance >= item_price
            
            if not has_sufficient_balance:
                return {
                    "success": False,
                    "error": "Insufficient balance",
                    "current_balance": current_balance,
                    "required": item_price,
                    "balance_check": False
                }
            
            # Process purchase
            new_balance = self.update_balance(user_id, -item_price)
            if new_balance is None:
                return {"success": False, "error": "Failed to update balance"}
            
            # Create transaction
            transaction_id = self.add_transaction(user_id, -item_price, 'buy')
            
            return {
                "success": True,
                "new_balance": new_balance,
                "transaction_id": transaction_id,
                "balance_check": True
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}


class TestPurchaseBalanceValidationPBT(unittest.TestCase):
    """Property-based tests for purchase balance validation"""
    
    def setUp(self):
        """Setup test database"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Initialize purchase system with test database
        self.purchase_system = SimplePurchaseSystem(self.temp_db.name)
        
    def tearDown(self):
        """Clean up after tests"""
        # Remove temporary database
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647),
        st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_purchase_balance_validation_property(self, user_id, user_balance, item_price):
        """
        **Feature: telegram-bot-admin-system, Property 6: Purchase balance validation**
        **Validates: Requirements 5.1, 5.2**
        
        For any purchase attempt, the system should allow the purchase if and only if 
        the user's balance is greater than or equal to the item price
        """
        # Register user with specified balance
        username = f"testuser_{user_id}"
        first_name = f"TestUser{user_id}"
        self.purchase_system.register_user(user_id, username, first_name, user_balance)
        
        # Attempt purchase
        result = self.purchase_system.attempt_purchase(user_id, item_price)
        
        # The core property: purchase should succeed if and only if balance >= price
        expected_success = user_balance >= item_price
        actual_success = result["success"]
        
        self.assertEqual(
            actual_success, expected_success,
            f"Purchase validation failed: user_balance={user_balance}, item_price={item_price}, "
            f"expected_success={expected_success}, actual_success={actual_success}, "
            f"result={result}"
        )
        
        if expected_success:
            # If purchase should succeed, verify the balance was updated correctly
            self.assertTrue(result["success"], "Purchase should have succeeded")
            self.assertIn("new_balance", result, "Successful purchase should return new balance")
            expected_new_balance = user_balance - item_price
            self.assertAlmostEqual(
                result["new_balance"], expected_new_balance, places=2,
                msg=f"New balance incorrect: expected {expected_new_balance}, got {result['new_balance']}"
            )
            
            # Verify transaction was created
            self.assertIn("transaction_id", result, "Successful purchase should create transaction")
            self.assertIsNotNone(result["transaction_id"], "Transaction ID should not be None")
            
            # Verify balance check was positive
            self.assertTrue(result.get("balance_check", False), "Balance check should be True for successful purchase")
            
        else:
            # If purchase should fail, verify it failed with correct reason
            self.assertFalse(result["success"], "Purchase should have failed")
            self.assertIn("error", result, "Failed purchase should return error message")
            
            # For insufficient balance, verify the balance check was negative
            if "Insufficient balance" in result.get("error", ""):
                self.assertFalse(result.get("balance_check", True), "Balance check should be False for insufficient balance")
                self.assertIn("current_balance", result, "Insufficient balance error should include current balance")
                self.assertIn("required", result, "Insufficient balance error should include required amount")
                self.assertEqual(result["current_balance"], user_balance, "Current balance should match user balance")
                self.assertEqual(result["required"], item_price, "Required amount should match item price")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647),
        st.floats(min_value=10.0, max_value=10000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_sufficient_balance_always_allows_purchase(self, user_id, user_balance):
        """
        **Feature: telegram-bot-admin-system, Property 6: Purchase balance validation**
        **Validates: Requirements 5.1, 5.2**
        
        For any user with balance >= 10 (contact price), the purchase should always succeed
        """
        # Use the standard contact price of 10 points
        contact_price = 10.0
        
        # Ensure user has sufficient balance (balance >= contact_price)
        if user_balance < contact_price:
            user_balance = contact_price + abs(user_balance - contact_price)
        
        # Register user with sufficient balance
        username = f"testuser_{user_id}"
        first_name = f"TestUser{user_id}"
        self.purchase_system.register_user(user_id, username, first_name, user_balance)
        
        # Attempt purchase
        result = self.purchase_system.attempt_purchase(user_id, contact_price)
        
        # Purchase should always succeed with sufficient balance
        self.assertTrue(result["success"], 
                       f"Purchase should succeed with sufficient balance: "
                       f"balance={user_balance}, price={contact_price}, result={result}")
        
        # Verify balance was deducted correctly
        expected_new_balance = user_balance - contact_price
        self.assertAlmostEqual(result["new_balance"], expected_new_balance, places=2,
                              msg=f"Balance deduction incorrect: expected {expected_new_balance}, "
                                  f"got {result['new_balance']}")
        
        # Verify transaction was created
        self.assertIsNotNone(result["transaction_id"], "Transaction should be created for successful purchase")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647),
        st.floats(min_value=0.0, max_value=9.99, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_insufficient_balance_always_denies_purchase(self, user_id, user_balance):
        """
        **Feature: telegram-bot-admin-system, Property 6: Purchase balance validation**
        **Validates: Requirements 5.1, 5.2**
        
        For any user with balance < 10 (contact price), the purchase should always fail
        """
        # Use the standard contact price of 10 points
        contact_price = 10.0
        
        # Ensure user has insufficient balance (balance < contact_price)
        if user_balance >= contact_price:
            user_balance = contact_price - 0.01
        
        # Register user with insufficient balance
        username = f"testuser_{user_id}"
        first_name = f"TestUser{user_id}"
        self.purchase_system.register_user(user_id, username, first_name, user_balance)
        
        # Attempt purchase
        result = self.purchase_system.attempt_purchase(user_id, contact_price)
        
        # Purchase should always fail with insufficient balance
        self.assertFalse(result["success"], 
                        f"Purchase should fail with insufficient balance: "
                        f"balance={user_balance}, price={contact_price}, result={result}")
        
        # Verify error details
        self.assertIn("error", result, "Failed purchase should include error message")
        self.assertIn("Insufficient balance", result["error"], "Error should indicate insufficient balance")
        
        # Verify balance information is provided
        if "current_balance" in result:
            self.assertEqual(result["current_balance"], user_balance, "Current balance should be reported correctly")
        if "required" in result:
            self.assertEqual(result["required"], contact_price, "Required amount should be reported correctly")
    
    def test_purchase_balance_validation_without_hypothesis(self):
        """Fallback test when Hypothesis is not available"""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Test cases covering the property: balance >= price determines purchase success
        test_cases = [
            # (user_id, balance, price, expected_success)
            (12345, 10.0, 10.0, True),   # Exact balance
            (12346, 15.0, 10.0, True),   # Sufficient balance
            (12347, 9.99, 10.0, False),  # Insufficient balance
            (12348, 0.0, 10.0, False),   # Zero balance
            (12349, 100.0, 10.0, True),  # High balance
            (12350, 5.0, 10.0, False),   # Half the required balance
        ]
        
        for user_id, balance, price, expected_success in test_cases:
            with self.subTest(user_id=user_id, balance=balance, price=price):
                # Register user
                username = f"testuser_{user_id}"
                first_name = f"TestUser{user_id}"
                self.purchase_system.register_user(user_id, username, first_name, balance)
                
                # Attempt purchase
                result = self.purchase_system.attempt_purchase(user_id, price)
                
                # Verify the property holds
                self.assertEqual(result["success"], expected_success,
                               f"Purchase validation failed for balance={balance}, price={price}")
                
                if expected_success:
                    # Verify successful purchase details
                    self.assertAlmostEqual(result["new_balance"], balance - price, places=2)
                    self.assertIsNotNone(result["transaction_id"])
                else:
                    # Verify failed purchase details
                    self.assertIn("error", result)


if __name__ == '__main__':
    unittest.main()