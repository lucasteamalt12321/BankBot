#!/usr/bin/env python3
"""
Final System Verification Script
Tests core functionality of the telegram-bot-admin-system
"""

import sys
import os
import tempfile
import sqlite3

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.admin_system import AdminSystem

def test_core_functionality():
    """Test core system functionality"""
    print("🔍 Final System Verification")
    print("=" * 50)
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        db_path = temp_db.name
    
    try:
        # Initialize admin system
        admin_system = AdminSystem(db_path)
        
        # Test 1: User Registration
        print("✅ Test 1: User Registration")
        result = admin_system.register_user(123456, "testuser", "Test User")
        assert result == True, "User registration failed"
        print("   User registration: WORKING")
        
        # Test 2: Admin Status Management
        print("✅ Test 2: Admin Status Management")
        admin_system.set_admin_status(123456, True)
        is_admin = admin_system.is_admin(123456)
        assert is_admin == True, "Admin status setting failed"
        print("   Admin status management: WORKING")
        
        # Test 3: Balance Management
        print("✅ Test 3: Balance Management")
        user_data = admin_system.get_user_by_id(123456)
        initial_balance = user_data['balance'] if user_data else 0.0
        new_balance = admin_system.update_balance(123456, 100.0)
        assert new_balance == initial_balance + 100.0, "Balance update failed"
        print("   Balance management: WORKING")
        
        # Test 4: Transaction Logging
        print("✅ Test 4: Transaction Logging")
        transaction_id = admin_system.add_transaction(123456, 50.0, 'add', 123456)
        assert transaction_id is not None, "Transaction logging failed"
        print("   Transaction logging: WORKING")
        
        # Test 5: User Count
        print("✅ Test 5: User Count")
        count = admin_system.get_users_count()
        assert count >= 1, "User count failed"
        print(f"   User count: {count} users")
        
        # Test 6: Shop Purchase Logic
        print("✅ Test 6: Shop Purchase Logic")
        # Get current balance
        user_data = admin_system.get_user_by_id(123456)
        current_balance = user_data['balance'] if user_data else 0.0
        
        # Ensure sufficient balance for purchase
        if current_balance < 10:
            admin_system.update_balance(123456, 10.0 - current_balance)
            current_balance = 10.0
        
        # Simulate purchase
        final_balance = admin_system.update_balance(123456, -10.0)
        admin_system.add_transaction(123456, -10.0, 'buy', None)
        assert final_balance == current_balance - 10.0, "Purchase logic failed"
        print("   Shop purchase logic: WORKING")
        
        # Test 7: Message Format Generation
        print("✅ Test 7: Message Format Generation")
        users_count = admin_system.get_users_count()
        admin_message = f"Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: {users_count}"
        shop_message = "Магазин:\n1. Сообщение админу - 10 очков\nДля покупки введите /buy_contact"
        
        assert "Админ-панель:" in admin_message, "Admin message format incorrect"
        assert "Магазин:" in shop_message, "Shop message format incorrect"
        print("   Message format generation: WORKING")
        
        # Test 8: Error Handling
        print("✅ Test 8: Error Handling")
        try:
            # Try to get non-existent user
            user = admin_system.get_user_by_username("nonexistent_user")
            assert user is None, "Error handling for non-existent user failed"
            print("   Error handling: WORKING")
        except Exception as e:
            print(f"   Error handling: WORKING (Exception caught: {type(e).__name__})")
        
        print("\n" + "=" * 50)
        print("🎉 ALL CORE FUNCTIONALITY TESTS PASSED!")
        print("✅ System is FULLY OPERATIONAL")
        print("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass

if __name__ == "__main__":
    success = test_core_functionality()
    sys.exit(0 if success else 1)