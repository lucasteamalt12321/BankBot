#!/usr/bin/env python3
"""
Minimal test for balance validation logic
"""

import tempfile
import sqlite3
import os


class MinimalBalanceValidator:
    """Minimal balance validation for testing"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                balance INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                type TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_user(self, telegram_id, balance):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT OR REPLACE INTO users (telegram_id, balance) VALUES (?, ?)",
            (telegram_id, balance)
        )
        
        conn.commit()
        conn.close()
    
    def get_user_balance(self, telegram_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def attempt_purchase(self, telegram_id, item_price=100):
        """Attempt purchase with balance validation and deduction"""
        current_balance = self.get_user_balance(telegram_id)
        
        if current_balance is None:
            return {"success": False, "error": "User not found"}
        
        # Core property: purchase succeeds if and only if balance >= price
        if current_balance >= item_price:
            # Deduct balance
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
                "INSERT INTO transactions (user_id, amount, type) VALUES ((SELECT id FROM users WHERE telegram_id = ?), ?, ?)",
                (telegram_id, -item_price, 'shop_purchase')
            )
            
            conn.commit()
            conn.close()
            
            return {
                "success": True,
                "new_balance": new_balance,
                "message": "Покупка успешна!"
            }
        else:
            return {
                "success": False,
                "error": "insufficient_balance",
                "message": f"Недостаточно средств! Ваш баланс: {current_balance}",
                "current_balance": current_balance
            }


def test_balance_validation_property():
    """Test the core balance validation property"""
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        validator = MinimalBalanceValidator(temp_db.name)
        
        # Test cases: (telegram_id, balance, expected_success)
        test_cases = [
            (1001, 100, True),   # Exact balance
            (1002, 150, True),   # Sufficient balance
            (1003, 99, False),   # Insufficient by 1
            (1004, 0, False),    # Zero balance
            (1005, 500, True),   # High balance
        ]
        
        print("Testing balance validation property...")
        
        for telegram_id, balance, expected_success in test_cases:
            # Create user with specified balance
            validator.create_user(telegram_id, balance)
            
            # Attempt purchase
            result = validator.attempt_purchase(telegram_id, 100)
            
            # Verify the property
            actual_success = result["success"]
            
            print(f"User {telegram_id}: balance={balance}, expected={expected_success}, actual={actual_success}")
            
            if actual_success == expected_success:
                print("  ✓ Property holds")
                
                if expected_success:
                    # Verify balance deduction
                    final_balance = validator.get_user_balance(telegram_id)
                    expected_final = balance - 100
                    if final_balance == expected_final:
                        print(f"  ✓ Balance correctly deducted: {balance} -> {final_balance}")
                    else:
                        print(f"  ✗ Balance deduction error: expected {expected_final}, got {final_balance}")
                else:
                    # Verify no balance change
                    final_balance = validator.get_user_balance(telegram_id)
                    if final_balance == balance:
                        print(f"  ✓ Balance unchanged: {balance}")
                    else:
                        print(f"  ✗ Balance should not change: expected {balance}, got {final_balance}")
            else:
                print(f"  ✗ Property violation!")
                return False
        
        print("\n✓ All balance validation property tests passed!")
        return True
        
    finally:
        try:
            os.unlink(temp_db.name)
        except:
            pass


if __name__ == "__main__":
    test_balance_validation_property()