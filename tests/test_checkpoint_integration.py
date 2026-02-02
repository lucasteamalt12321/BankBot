#!/usr/bin/env python3
"""
Integration test for Task 8 - Checkpoint verification
Tests all main functionality of the Telegram bot admin system
"""

import os
import sys
import sqlite3
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.admin_system import AdminSystem


def test_admin_system_integration():
    """Test the complete admin system functionality"""
    print("🔧 Testing Admin System Integration...")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = tmp_db.name
    
    try:
        # Initialize admin system
        admin_system = AdminSystem(db_path)
        
        # Test 1: User registration
        print("  ✓ Testing user registration...")
        user_id = 123456789
        username = "testuser"
        first_name = "Test User"
        
        success = admin_system.register_user(user_id, username, first_name)
        assert success, "User registration failed"
        
        # Test 2: Admin rights check (should be False initially)
        print("  ✓ Testing admin rights check...")
        is_admin = admin_system.is_admin(user_id)
        assert not is_admin, "User should not be admin initially"
        
        # Test 3: Set admin status
        print("  ✓ Testing admin status setting...")
        success = admin_system.set_admin_status(user_id, True)
        assert success, "Setting admin status failed"
        
        # Test 4: Verify admin status
        is_admin = admin_system.is_admin(user_id)
        assert is_admin, "User should be admin after setting status"
        
        # Test 5: User lookup by username
        print("  ✓ Testing user lookup...")
        user = admin_system.get_user_by_username(username)
        assert user is not None, "User lookup failed"
        assert user['id'] == user_id, "User ID mismatch"
        assert user['username'] == username, "Username mismatch"
        assert user['is_admin'] == True, "Admin status mismatch"
        
        # Test 6: Balance operations
        print("  ✓ Testing balance operations...")
        initial_balance = user['balance']
        amount = 100.0
        
        new_balance = admin_system.update_balance(user_id, amount)
        assert new_balance == initial_balance + amount, "Balance update failed"
        
        # Test 7: Transaction logging
        print("  ✓ Testing transaction logging...")
        admin_id = 987654321
        transaction_id = admin_system.add_transaction(user_id, amount, 'add', admin_id)
        assert transaction_id is not None, "Transaction logging failed"
        
        # Test 8: Users count
        print("  ✓ Testing users count...")
        count = admin_system.get_users_count()
        assert count >= 1, "Users count should be at least 1"
        
        # Test 9: Shop functionality simulation
        print("  ✓ Testing shop functionality...")
        # Simulate buy_contact operation
        purchase_amount = 10.0
        current_balance = admin_system.get_user_by_username(username)['balance']
        
        if current_balance >= purchase_amount:
            new_balance = admin_system.update_balance(user_id, -purchase_amount)
            transaction_id = admin_system.add_transaction(user_id, -purchase_amount, 'buy')
            assert new_balance == current_balance - purchase_amount, "Purchase balance update failed"
            assert transaction_id is not None, "Purchase transaction logging failed"
            print(f"    ✓ Purchase successful: {purchase_amount} points deducted")
        else:
            print(f"    ⚠ Insufficient balance for purchase: {current_balance} < {purchase_amount}")
        
        print("✅ All admin system integration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False
    finally:
        # Clean up temporary database
        try:
            os.unlink(db_path)
        except:
            pass


def test_database_schema():
    """Test database schema integrity"""
    print("🗄️ Testing Database Schema...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = tmp_db.name
    
    try:
        admin_system = AdminSystem(db_path)
        
        # Check tables exist
        conn = admin_system.get_db_connection()
        cursor = conn.cursor()
        
        # Check users table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        assert cursor.fetchone() is not None, "Users table not found"
        
        # Check transactions table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
        assert cursor.fetchone() is not None, "Transactions table not found"
        
        # Check users table schema
        cursor.execute("PRAGMA table_info(users)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        expected_columns = {
            'id': 'INTEGER',
            'username': 'TEXT',
            'first_name': 'TEXT',
            'balance': 'REAL',
            'is_admin': 'BOOLEAN'
        }
        
        for col_name, col_type in expected_columns.items():
            assert col_name in columns, f"Column {col_name} not found in users table"
            print(f"    ✓ Users table column: {col_name} ({columns[col_name]})")
        
        # Check transactions table schema
        cursor.execute("PRAGMA table_info(transactions)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        expected_columns = {
            'id': 'INTEGER',
            'user_id': 'INTEGER',
            'amount': 'REAL',
            'type': 'TEXT',
            'admin_id': 'INTEGER',
            'timestamp': 'DATETIME'
        }
        
        for col_name, col_type in expected_columns.items():
            assert col_name in columns, f"Column {col_name} not found in transactions table"
            print(f"    ✓ Transactions table column: {col_name} ({columns[col_name]})")
        
        conn.close()
        print("✅ Database schema tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Database schema test failed: {e}")
        return False
    finally:
        try:
            os.unlink(db_path)
        except:
            pass


def test_error_handling():
    """Test error handling scenarios"""
    print("⚠️ Testing Error Handling...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = tmp_db.name
    
    try:
        admin_system = AdminSystem(db_path)
        
        # Test 1: Non-existent user lookup
        print("  ✓ Testing non-existent user lookup...")
        user = admin_system.get_user_by_username("nonexistent")
        assert user is None, "Non-existent user should return None"
        
        # Test 2: Admin check for non-existent user
        print("  ✓ Testing admin check for non-existent user...")
        is_admin = admin_system.is_admin(999999999)
        assert not is_admin, "Non-existent user should not be admin"
        
        # Test 3: Balance update for non-existent user
        print("  ✓ Testing balance update for non-existent user...")
        new_balance = admin_system.update_balance(999999999, 100.0)
        assert new_balance is None, "Balance update for non-existent user should return None"
        
        # Test 4: Admin status setting for non-existent user
        print("  ✓ Testing admin status setting for non-existent user...")
        success = admin_system.set_admin_status(999999999, True)
        assert not success, "Admin status setting for non-existent user should fail"
        
        print("✅ Error handling tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False
    finally:
        try:
            os.unlink(db_path)
        except:
            pass


def main():
    """Run all integration tests"""
    print("🚀 Starting Checkpoint Integration Tests...")
    print("=" * 60)
    
    tests = [
        test_database_schema,
        test_admin_system_integration,
        test_error_handling,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            print()
    
    print("=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All integration tests passed! Main functionality is working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)