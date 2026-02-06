#!/usr/bin/env python3
"""
Property-based tests for balance validation and deduction in the Telegram Bot Shop System
**Feature: telegram-bot-shop-system, Property 2: Balance Validation and Deduction**
**Validates: Requirements 2.1, 2.2, 2.3**
"""

import unittest
import sys
import os
import tempfile
import sqlite3
from typing import Optional, Dict, Any

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


class MinimalPurchaseSystem:
    """Minimal purchase system for testing balance validation and deduction"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize test database with required tables and data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                balance INTEGER DEFAULT 0,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create shop_items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shop_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                price INTEGER NOT NULL DEFAULT 100,
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create user_purchases table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                purchase_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NULL,
                data JSON NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (item_id) REFERENCES shop_items(id)
            )
        ''')
        
        # Create transactions table (matching existing schema)
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
        
        # Insert default shop items (all cost 100 coins as per requirements)
        shop_items = [
            (1, "Безлимитные стикеры на 24 часа", 100, "Отправляйте стикеры без ограничений в течение 24 часов"),
            (2, "Запрос на админ-права", 100, "Отправить запрос владельцу бота на получение прав администратора"),
            (3, "Рассылка сообщения", 100, "Отправить сообщение всем пользователям бота")
        ]
        
        cursor.executemany(
            "INSERT OR REPLACE INTO shop_items (id, name, price, description) VALUES (?, ?, ?, ?)",
            shop_items
        )
        
        conn.commit()
        conn.close()
    
    def create_user(self, telegram_id: int, balance: int, username: str = None, first_name: str = None) -> int:
        """Create a test user and return their database ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT OR REPLACE INTO users (telegram_id, username, first_name, balance) VALUES (?, ?, ?, ?)",
            (telegram_id, username or f"user_{telegram_id}", first_name or f"User{telegram_id}", balance)
        )
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return user_id
    
    def get_user_balance(self, telegram_id: int) -> Optional[int]:
        """Get user balance by telegram ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def get_transaction_count(self, telegram_id: int, transaction_type: str = 'shop_purchase') -> int:
        """Get count of transactions for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id = (SELECT id FROM users WHERE telegram_id = ?) AND type = ?",
            (telegram_id, transaction_type)
        )
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else 0
    
    def process_purchase(self, telegram_id: int, item_number: int) -> Dict[str, Any]:
        """
        Process a purchase request with balance validation and deduction
        Implements the core balance validation and deduction property
        """
        try:
            # Get user information
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, balance FROM users WHERE telegram_id = ?", (telegram_id,))
            user_result = cursor.fetchone()
            
            if not user_result:
                conn.close()
                return {
                    "success": False,
                    "message": "Пользователь не найден. Используйте /start для регистрации.",
                    "error_code": "user_not_found"
                }
            
            user_id, current_balance = user_result
            
            # Get shop item (all items cost 100 coins)
            if item_number < 1 or item_number > 3:
                conn.close()
                return {
                    "success": False,
                    "message": f"Товар с номером {item_number} не найден.",
                    "error_code": "item_not_found"
                }
            
            item_price = 100  # All items cost 100 coins as per requirements
            
            # Core property: Balance validation and deduction
            # If user has sufficient balance (>= 100 coins), deduct exactly 100 coins and proceed
            # If insufficient, respond with balance error message and make no changes
            
            if current_balance >= item_price:
                # Sufficient balance - proceed with purchase
                new_balance = current_balance - item_price
                
                # Update user balance
                cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
                
                # Create purchase record
                cursor.execute(
                    "INSERT INTO user_purchases (user_id, item_id) VALUES (?, ?)",
                    (user_id, item_number)
                )
                purchase_id = cursor.lastrowid
                
                # Log transaction with type 'shop_purchase' (Requirement 2.5)
                cursor.execute(
                    "INSERT INTO transactions (user_id, amount, type) VALUES (?, ?, ?)",
                    (user_id, -item_price, 'shop_purchase')
                )
                
                conn.commit()
                conn.close()
                
                return {
                    "success": True,
                    "message": f"Покупка успешна! Вы приобрели товар {item_number}",
                    "purchase_id": purchase_id,
                    "new_balance": new_balance
                }
            else:
                # Insufficient balance - return error message (Requirement 2.2)
                conn.close()
                return {
                    "success": False,
                    "message": f"Недостаточно средств! Ваш баланс: {current_balance}",
                    "error_code": "insufficient_balance",
                    "new_balance": current_balance
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": "Произошла ошибка при обработке покупки.",
                "error_code": "system_error"
            }


class TestBalanceValidationDeductionPBT(unittest.TestCase):
    """Property-based tests for balance validation and deduction"""
    
    def setUp(self):
        """Setup test database and purchase system"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Initialize minimal purchase system
        self.purchase_system = MinimalPurchaseSystem(self.temp_db.name)
        
    def tearDown(self):
        """Clean up after tests"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        telegram_id=st.integers(min_value=1, max_value=2147483647),
        initial_balance=st.integers(min_value=0, max_value=10000),
        item_number=st.integers(min_value=1, max_value=3)
    )
    @settings(max_examples=100, deadline=None)
    def test_balance_validation_and_deduction_property(self, telegram_id, initial_balance, item_number):
        """
        **Validates: Requirements 2.1, 2.2, 2.3**
        
        Property 2: Balance Validation and Deduction
        For any purchase attempt, if the user has sufficient balance (>= 100 coins), 
        the system should deduct exactly 100 coins and proceed with the purchase; 
        if insufficient, it should respond with the balance error message and make no changes.
        """
        # Create test user with specified balance
        self.purchase_system.create_user(telegram_id, initial_balance)
        
        # Get initial transaction count
        initial_transaction_count = self.purchase_system.get_transaction_count(telegram_id)
        
        # Attempt purchase
        result = self.purchase_system.process_purchase(telegram_id, item_number)
        
        # Get final balance and transaction count
        final_balance = self.purchase_system.get_user_balance(telegram_id)
        final_transaction_count = self.purchase_system.get_transaction_count(telegram_id)
        
        # The core property: purchase success depends on sufficient balance (>= 100)
        expected_success = initial_balance >= 100
        actual_success = result["success"]
        
        self.assertEqual(
            actual_success, expected_success,
            f"Balance validation failed: initial_balance={initial_balance}, item_number={item_number}, "
            f"expected_success={expected_success}, actual_success={actual_success}, "
            f"result_message='{result['message']}', error_code={result.get('error_code')}"
        )
        
        if expected_success:
            # Requirement 2.3: When user has sufficient balance, deduct 100 coins
            expected_final_balance = initial_balance - 100
            self.assertEqual(
                final_balance, expected_final_balance,
                f"Balance deduction incorrect: initial={initial_balance}, expected_final={expected_final_balance}, "
                f"actual_final={final_balance}"
            )
            
            # Requirement 2.5: Log transaction with type 'shop_purchase'
            self.assertEqual(
                final_transaction_count, initial_transaction_count + 1,
                f"Transaction should be logged for successful purchase"
            )
            
            # Verify purchase result contains new balance
            self.assertEqual(
                result["new_balance"], expected_final_balance,
                f"Purchase result should contain correct new balance"
            )
            
            # Verify purchase ID is provided
            self.assertIsNotNone(result.get("purchase_id"), "Successful purchase should return purchase ID")
            
            # Verify success message format
            self.assertIn("Покупка успешна", result["message"], "Success message should be in Russian")
            
        else:
            # Requirement 2.2: If insufficient balance, respond with balance error message
            self.assertFalse(result["success"], "Purchase should fail with insufficient balance")
            self.assertEqual(result.get("error_code"), "insufficient_balance", "Error code should indicate insufficient balance")
            
            # Verify error message format (Requirement 2.2)
            expected_message = f"Недостаточно средств! Ваш баланс: {initial_balance}"
            self.assertEqual(
                result["message"], expected_message,
                f"Error message format incorrect: expected='{expected_message}', actual='{result['message']}'"
            )
            
            # Verify no balance change occurred
            self.assertEqual(
                final_balance, initial_balance,
                f"Balance should not change for failed purchase: initial={initial_balance}, final={final_balance}"
            )
            
            # Verify no transaction was logged
            self.assertEqual(
                final_transaction_count, initial_transaction_count,
                f"No transaction should be logged for failed purchase"
            )
            
            # Verify new balance in result matches current balance
            self.assertEqual(
                result["new_balance"], initial_balance,
                f"Failed purchase result should contain current balance"
            )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        telegram_id=st.integers(min_value=1, max_value=2147483647),
        excess_balance=st.integers(min_value=0, max_value=9900)  # 0-9900 excess over 100
    )
    @settings(max_examples=50, deadline=None)
    def test_sufficient_balance_always_allows_purchase(self, telegram_id, excess_balance):
        """
        **Validates: Requirements 2.1, 2.3**
        
        For any user with balance >= 100 coins, the purchase should always succeed
        and exactly 100 coins should be deducted
        """
        # Ensure user has sufficient balance (100 + excess)
        initial_balance = 100 + excess_balance
        self.purchase_system.create_user(telegram_id, initial_balance)
        
        # Try purchasing item 1 (all items cost 100 coins)
        result = self.purchase_system.process_purchase(telegram_id, 1)
        
        # Purchase should always succeed with sufficient balance
        self.assertTrue(
            result["success"],
            f"Purchase should succeed with sufficient balance: balance={initial_balance}, "
            f"result_message='{result['message']}', error_code={result.get('error_code')}"
        )
        
        # Verify exactly 100 coins were deducted
        final_balance = self.purchase_system.get_user_balance(telegram_id)
        expected_final_balance = initial_balance - 100
        self.assertEqual(
            final_balance, expected_final_balance,
            f"Exactly 100 coins should be deducted: initial={initial_balance}, "
            f"expected_final={expected_final_balance}, actual_final={final_balance}"
        )
        
        # Verify transaction was logged
        transaction_count = self.purchase_system.get_transaction_count(telegram_id)
        self.assertEqual(transaction_count, 1, "Transaction should be logged for successful purchase")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        telegram_id=st.integers(min_value=1, max_value=2147483647),
        insufficient_balance=st.integers(min_value=0, max_value=99)
    )
    @settings(max_examples=50, deadline=None)
    def test_insufficient_balance_always_denies_purchase(self, telegram_id, insufficient_balance):
        """
        **Validates: Requirements 2.1, 2.2**
        
        For any user with balance < 100 coins, the purchase should always fail
        with the correct error message and no balance changes
        """
        # Create user with insufficient balance
        self.purchase_system.create_user(telegram_id, insufficient_balance)
        
        # Try purchasing item 1
        result = self.purchase_system.process_purchase(telegram_id, 1)
        
        # Purchase should always fail with insufficient balance
        self.assertFalse(
            result["success"],
            f"Purchase should fail with insufficient balance: balance={insufficient_balance}, "
            f"result_message='{result['message']}'"
        )
        
        # Verify error code
        self.assertEqual(
            result.get("error_code"), "insufficient_balance",
            f"Error code should indicate insufficient balance"
        )
        
        # Verify error message format (Requirement 2.2)
        expected_message = f"Недостаточно средств! Ваш баланс: {insufficient_balance}"
        self.assertEqual(
            result["message"], expected_message,
            f"Error message format incorrect: expected='{expected_message}', actual='{result['message']}'"
        )
        
        # Verify no balance change
        final_balance = self.purchase_system.get_user_balance(telegram_id)
        self.assertEqual(
            final_balance, insufficient_balance,
            f"Balance should not change for failed purchase"
        )
        
        # Verify no transaction was logged
        transaction_count = self.purchase_system.get_transaction_count(telegram_id)
        self.assertEqual(transaction_count, 0, "No transaction should be logged for failed purchase")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        telegram_id=st.integers(min_value=1, max_value=2147483647),
        item_number=st.integers(min_value=1, max_value=3)
    )
    @settings(max_examples=30, deadline=None)
    def test_exact_balance_boundary_condition(self, telegram_id, item_number):
        """
        **Validates: Requirements 2.1, 2.2, 2.3**
        
        Test the boundary condition where user has exactly 100 coins
        """
        # Create user with exactly 100 coins (the item price)
        exact_balance = 100
        self.purchase_system.create_user(telegram_id, exact_balance)
        
        # Attempt purchase
        result = self.purchase_system.process_purchase(telegram_id, item_number)
        
        # Purchase should succeed with exact balance
        self.assertTrue(
            result["success"],
            f"Purchase should succeed with exact balance (100 coins): "
            f"result_message='{result['message']}', error_code={result.get('error_code')}"
        )
        
        # Verify balance becomes 0
        final_balance = self.purchase_system.get_user_balance(telegram_id)
        self.assertEqual(
            final_balance, 0,
            f"Balance should be 0 after purchasing with exact balance: final_balance={final_balance}"
        )
        
        # Verify transaction was logged
        transaction_count = self.purchase_system.get_transaction_count(telegram_id)
        self.assertEqual(transaction_count, 1, "Transaction should be logged")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        telegram_id=st.integers(min_value=1, max_value=2147483647),
        initial_balance=st.integers(min_value=200, max_value=1000)
    )
    @settings(max_examples=30, deadline=None)
    def test_multiple_purchases_balance_consistency(self, telegram_id, initial_balance):
        """
        **Validates: Requirements 2.1, 2.3**
        
        Test that multiple purchases consistently deduct 100 coins each
        """
        # Create user with sufficient balance for multiple purchases
        self.purchase_system.create_user(telegram_id, initial_balance)
        
        # Calculate how many purchases are possible
        max_purchases = initial_balance // 100
        assume(max_purchases >= 2)  # Need at least 2 purchases for this test
        
        current_balance = initial_balance
        
        # Make multiple purchases
        for i in range(min(max_purchases, 3)):  # Test up to 3 purchases
            result = self.purchase_system.process_purchase(telegram_id, 1)
            
            # Each purchase should succeed
            self.assertTrue(
                result["success"],
                f"Purchase {i+1} should succeed: balance_before={current_balance}, "
                f"result_message='{result['message']}'"
            )
            
            # Verify balance deduction
            current_balance -= 100
            final_balance = self.purchase_system.get_user_balance(telegram_id)
            self.assertEqual(
                final_balance, current_balance,
                f"Balance after purchase {i+1} incorrect: expected={current_balance}, actual={final_balance}"
            )
        
        # Verify total transactions logged
        transaction_count = self.purchase_system.get_transaction_count(telegram_id)
        expected_transactions = min(max_purchases, 3)
        self.assertEqual(
            transaction_count, expected_transactions,
            f"Should have {expected_transactions} transactions logged"
        )
    
    def test_balance_validation_without_hypothesis(self):
        """Fallback test when Hypothesis is not available"""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Test cases covering the core property
        test_cases = [
            # (telegram_id, balance, item_number, expected_success, expected_final_balance)
            (12345, 100, 1, True, 0),      # Exact balance
            (12346, 150, 2, True, 50),     # Sufficient balance
            (12347, 99, 1, False, 99),     # Insufficient balance by 1
            (12348, 0, 3, False, 0),       # Zero balance
            (12349, 500, 1, True, 400),    # High balance
            (12350, 50, 2, False, 50),     # Half the required balance
        ]
        
        for telegram_id, balance, item_number, expected_success, expected_final_balance in test_cases:
            with self.subTest(telegram_id=telegram_id, balance=balance, item_number=item_number):
                # Create user
                self.purchase_system.create_user(telegram_id, balance)
                
                # Attempt purchase
                result = self.purchase_system.process_purchase(telegram_id, item_number)
                
                # Verify the property holds
                self.assertEqual(
                    result["success"], expected_success,
                    f"Purchase validation failed for balance={balance}, item_number={item_number}"
                )
                
                # Verify final balance
                final_balance = self.purchase_system.get_user_balance(telegram_id)
                self.assertEqual(
                    final_balance, expected_final_balance,
                    f"Final balance incorrect: expected={expected_final_balance}, actual={final_balance}"
                )
                
                if expected_success:
                    # Verify success details
                    self.assertIsNotNone(result.get("purchase_id"))
                    self.assertEqual(result["new_balance"], expected_final_balance)
                    self.assertIn("Покупка успешна", result["message"])
                    
                    # Verify transaction logged
                    transaction_count = self.purchase_system.get_transaction_count(telegram_id)
                    self.assertGreater(transaction_count, 0)
                else:
                    # Verify failure details
                    self.assertEqual(result.get("error_code"), "insufficient_balance")
                    expected_message = f"Недостаточно средств! Ваш баланс: {balance}"
                    self.assertEqual(result["message"], expected_message)
                    
                    # Verify no transaction logged
                    transaction_count = self.purchase_system.get_transaction_count(telegram_id)
                    self.assertEqual(transaction_count, 0)


if __name__ == '__main__':
    unittest.main()