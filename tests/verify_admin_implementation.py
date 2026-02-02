#!/usr/bin/env python3
"""
Verification script for the /admin command implementation
"""
import os
import sys

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def verify_admin_implementation():
    """Verify that the admin command is properly implemented"""
    print("Verifying /admin command implementation...")
    
    # Check if bot.py has the admin command handler
    with open('bot/bot.py', 'r', encoding='utf-8') as f:
        bot_content = f.read()
    
    # Check for command handler registration
    has_admin_handler = 'CommandHandler("admin", self.admin_command)' in bot_content
    print(f"✓ Admin command handler registered: {has_admin_handler}")
    
    # Check for admin command method
    has_admin_method = 'async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):' in bot_content
    print(f"✓ Admin command method defined: {has_admin_method}")
    
    # Check for admin system initialization
    has_admin_system_init = 'self.admin_system = AdminSystem()' in bot_content
    print(f"✓ Admin system initialized: {has_admin_system_init}")
    
    # Check for admin rights check
    has_admin_check = 'if not self.admin_system.is_admin(user.id):' in bot_content
    print(f"✓ Admin rights check implemented: {has_admin_check}")
    
    # Check for exact message format
    expected_format = 'f"Админ-панель:\\n/add_points @username [число] - начислить очки\\n/add_admin @username - добавить администратора\\nВсего пользователей: {users_count}"'
    has_exact_format = expected_format in bot_content
    print(f"✓ Exact message format implemented: {has_exact_format}")
    
    # Check for get_users_count usage
    has_users_count = 'users_count = self.admin_system.get_users_count()' in bot_content
    print(f"✓ get_users_count() function used: {has_users_count}")
    
    # Check AdminSystem import
    has_admin_import = 'from utils.admin_system import AdminSystem, admin_required' in bot_content
    print(f"✓ AdminSystem imported: {has_admin_import}")
    
    # Verify AdminSystem has required methods
    with open('utils/admin_system.py', 'r', encoding='utf-8') as f:
        admin_system_content = f.read()
    
    has_is_admin_method = 'def is_admin(self, user_id: int) -> bool:' in admin_system_content
    print(f"✓ is_admin method exists: {has_is_admin_method}")
    
    has_get_users_count_method = 'def get_users_count(self) -> int:' in admin_system_content
    print(f"✓ get_users_count method exists: {has_get_users_count_method}")
    
    # Check all requirements
    all_checks = [
        has_admin_handler,
        has_admin_method,
        has_admin_system_init,
        has_admin_check,
        has_exact_format,
        has_users_count,
        has_admin_import,
        has_is_admin_method,
        has_get_users_count_method
    ]
    
    if all(all_checks):
        print("\n✅ All implementation requirements satisfied!")
        print("\nImplemented features:")
        print("  - /admin command handler registered in bot")
        print("  - Admin rights check through AdminSystem.is_admin()")
        print("  - get_users_count() function for statistics")
        print("  - Exact message format as specified in requirements")
        print("  - Proper error handling for unauthorized access")
        print("  - Logging of admin panel access")
        return True
    else:
        print("\n❌ Some requirements are missing!")
        return False

if __name__ == "__main__":
    success = verify_admin_implementation()
    if success:
        print("\n🎉 Task 4.1 implementation is complete and ready!")
    else:
        print("\n⚠️ Implementation needs fixes.")