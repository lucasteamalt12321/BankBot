#!/usr/bin/env python3
"""
Tests for the user management system
"""

import unittest
import sys
import os

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import create_tables, get_db, User
from utils.user_manager import UserManager


class TestUserManager(unittest.TestCase):
    """Tests for the user manager functionality"""
    
    def setUp(self):
        """Setup test database"""
        create_tables()
        db_gen = get_db()
        self.db = next(db_gen)
        self.user_manager = UserManager(self.db)
        
    def tearDown(self):
        """Clean up after tests"""
        # Clear test data
        from database.database import UserAlias
        self.db.query(UserAlias).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.db.close()
    
    def test_user_identification_new_user(self):
        """Test identifying a new user (should create automatically)"""
        user = self.user_manager.identify_user("NewTestUser", telegram_id=999999999)
        
        self.assertIsNotNone(user)
        self.assertEqual(user.first_name, "NewTestUser")
        self.assertEqual(user.telegram_id, 999999999)
        self.assertEqual(user.balance, 0)
    
    def test_user_identification_existing_user(self):
        """Test identifying an existing user"""
        # First, create a user
        first_user = self.user_manager.identify_user("ExistingUser", telegram_id=888888888)
        self.assertIsNotNone(first_user)
        
        # Then try to get the same user again
        second_user = self.user_manager.identify_user("ExistingUser", telegram_id=888888888)
        self.assertEqual(first_user.id, second_user.id)
        self.assertEqual(first_user.telegram_id, second_user.telegram_id)
    
    def test_username_normalization(self):
        """Test username normalization functionality"""
        test_cases = [
            ("@username", "username"),
            ("@Username", "username"),
            ("  @username  ", "username"),
            ("USERNAME", "username"),
            ("user@name", "username"),  # Should remove special chars
        ]
        
        for input_username, expected in test_cases:
            result = self.user_manager.normalize_username(input_username)
            self.assertEqual(result, expected, f"Failed for input: {input_username}")
    
    def test_name_normalization(self):
        """Test name normalization functionality"""
        test_cases = [
            ("Test User", "test user"),
            ("  TEST USER  ", "test user"),
            ("Test@User", "testuser"),  # Should remove special chars
            ("Test-User", "testuser"),  # Should remove special chars
        ]
        
        for input_name, expected in test_cases:
            result = self.user_manager.normalize_name(input_name)
            self.assertEqual(result, expected, f"Failed for input: {input_name}")
    
    def test_user_alias_addition(self):
        """Test adding aliases to users"""
        user = self.user_manager.identify_user("AliasTestUser", telegram_id=777777777)
        self.assertIsNotNone(user)
        
        # Add an alias
        self.user_manager.add_alias(user, 'game_nickname', 'AliasName', 'test_source')
        
        # Verify alias was added
        from database.database import UserAlias
        alias = self.db.query(UserAlias).filter(
            UserAlias.user_id == user.id,
            UserAlias.alias_value == 'AliasName'
        ).first()
        
        self.assertIsNotNone(alias)
        self.assertEqual(alias.alias_type, 'game_nickname')
        self.assertEqual(alias.game_source, 'test_source')


if __name__ == '__main__':
    unittest.main()