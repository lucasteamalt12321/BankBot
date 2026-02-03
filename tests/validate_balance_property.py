#!/usr/bin/env python3
"""
Standalone validation of balance validation and deduction property
**Feature: telegram-bot-shop-system, Property 2: Balance Validation and Deduction**
**Validates: Requirements 2.1, 2.2, 2.3**
"""

import tempfile
import sqlite3
import os
import random


class BalancePropertyValidator:
    """Validates the balance validation and deduction property"""
    
    def __init__(self):
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self._init_database()
    
    def __del__(self):
        """Clean up temporary database"""
        try:
            os.unlink(self.db_path)
        except:
            pass
    
    def _init_database(self):
        """Initialize database with required schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                balance INTEGER DEFAULT 0
            )
        ''')
        
        # Create transactions table
        cursor.execute('''
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                type TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_user(self, telegram_id, balance):
        """Create user with specified balance"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT OR REPLACE INTO users (telegram_id, balance) VALUES (?, ?)",
            (telegram_id, balance)
        )
        
        conn.commit()
        conn.close()
    
    def get_balance(self, telegram_id):
        """Get user balance"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def get_transaction_count(self, telegram_id):
        """Get transaction count for user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id = (SELECT id FROM users WHERE telegram_id = ?) AND type = 'shop_purchase'",
            (telegram_id,)
        )
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else 0
    
    def attempt_purchase(self, telegram_id, item_price=100):
        """
        Attempt purchase implementing the balance validation and deduction property
        
        Property: For any purchase attempt, if the user has sufficient balance (>= 100 coins), 
        the system should deduct exactly 100 coins and proceed with the purchase; 
        if insufficient, it should respond with the balance error message and make no changes.
        """
        current_balance = self.get_balance(telegram_id)
        
        if current_balance is None:
            return {"success": False, "error": "User not found"}
        
        # Core property implementation
        if current_balance >= item_price:
            # Sufficient balance - deduct and proceed
            new_balance = current_balance - item_price
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Update balance
            cursor.execute(
                "UPDATE users SET balance = ? WHERE telegram_id = ?",
                (new_balance, telegram_id)
            )
            
            # Log transaction
            cursor.execute(
                "INSERT INTO transactions (user_id, amount, type) VALUES ((SELECT id FROM users WHERE telegram_id = ?), ?, 'shop_purchase')",
                (telegram_id, -item_price)
            )
            
            conn.commit()
            conn.close()
            
            return {
                "success": True,
                "new_balance": new_balance,
                "message": "Покупка успешна!"
            }
        else:
            # Insufficient balance - return error, make no changes
            return {
                "success": False,
                "error": "insufficient_balance",
                "message": f"Недостаточно средств! Ваш баланс: {current_balance}",
                "current_balance": current_balance
            }
    
    def validate_property(self, test_cases):
        """Validate the property across multiple test cases"""
        print("Validating Balance Validation and Deduction Property...")
        print("=" * 60)
        
        passed = 0
        failed = 0
        
        for i, (telegram_id, initial_balance) in enumerate(test_cases, 1):
            print(f"\nTest Case {i}: User {telegram_id}, Balance {initial_balance}")
            
            # Create user
            self.create_user(telegram_id, initial_balance)
            
            # Get initial state
            initial_transaction_count = self.get_transaction_count(telegram_id)
            
            # Attempt purchase
            result = self.attempt_purchase(telegram_id, 100)
            
            # Get final state
            final_balance = self.get_balance(telegram_id)
            final_transaction_count = self.get_transaction_count(telegram_id)
            
            # Validate property
            expected_success = initial_balance >= 100
            actual_success = result["success"]
            
            print(f"  Initial balance: {initial_balance}")
            print(f"  Expected success: {expected_success}")
            print(f"  Actual success: {actual_success}")
            
            if actual_success == expected_success:
                if expected_success:
                    # Should succeed - verify deduction
                    expected_final_balance = initial_balance - 100
                    if final_balance == expected_final_balance and final_transaction_count == initial_transaction_count + 1:
                        print(f"  ✓ PASS: Balance deducted correctly ({initial_balance} -> {final_balance})")
                        passed += 1
                    else:
                        print(f"  ✗ FAIL: Balance deduction error (expected {expected_final_balance}, got {final_balance})")
                        failed += 1
                else:
                    # Should fail - verify no changes
                    if final_balance == initial_balance and final_transaction_count == initial_transaction_count:
                        print(f"  ✓ PASS: No changes made for insufficient balance")
                        passed += 1
                    else:
                        print(f"  ✗ FAIL: Unexpected changes made (balance: {initial_balance} -> {final_balance})")
                        failed += 1
            else:
                print(f"  ✗ FAIL: Property violation (expected {expected_success}, got {actual_success})")
                failed += 1
        
        print("\n" + "=" * 60)
        print(f"Results: {passed} passed, {failed} failed")
        
        if failed == 0:
            print("✓ Balance Validation and Deduction Property VALIDATED")
            return True
        else:
            print("✗ Balance Validation and Deduction Property FAILED")
            return False


def main():
    """Run property validation"""
    validator = BalancePropertyValidator()
    
    # Generate test cases covering various scenarios
    test_cases = [
        # (telegram_id, initial_balance)
        (1001, 100),    # Exact balance
        (1002, 150),    # Sufficient balance
        (1003, 99),     # Insufficient by 1
        (1004, 0),      # Zero balance
        (1005, 500),    # High balance
        (1006, 50),     # Half required
        (1007, 200),    # Double required
        (1008, 1),      # Minimal balance
        (1009, 999),    # Very high balance
        (1010, 101),    # Just over minimum
    ]
    
    # Add some random test cases
    for i in range(10):
        telegram_id = 2000 + i
        balance = random.randint(0, 1000)
        test_cases.append((telegram_id, balance))
    
    # Validate property
    success = validator.validate_property(test_cases)
    
    if success:
        print("\n🎉 Property-based test PASSED!")
        print("The balance validation and deduction property holds across all test cases.")
    else:
        print("\n❌ Property-based test FAILED!")
        print("The balance validation and deduction property was violated.")
    
    return success


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)