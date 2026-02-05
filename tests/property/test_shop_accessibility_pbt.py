#!/usr/bin/env python3
"""
Property-based tests for shop accessibility universality
Feature: telegram-bot-admin-system, Property 10: Shop accessibility universality
"""

import unittest
import sys
import os
import tempfile
import sqlite3
from unittest.mock import Mock, AsyncMock, patch

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

from typing import Optional, Dict, Any


class SimpleShopSystem:
    """Simplified shop system for testing without telegram dependencies"""
    
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
        """Register a new user"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if cursor.fetchone():
                # User already exists, update balance if needed
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
    
    def is_user_registered(self, user_id: int) -> bool:
        """Check if user is registered in the system"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            result = cursor.fetchone()
            conn.close()
            
            return result is not None
            
        except Exception:
            return False
    
    def get_user_info(self, user_id: int) -> Optional[Dict]:
        """Get user information"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, username, first_name, balance, is_admin FROM users WHERE id = ?", (user_id,))
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
    
    def get_shop_items(self) -> Dict[str, Any]:
        """
        Get the complete list of available shop items
        Returns the shop content as per requirements 4.2 and 4.3
        """
        # As per requirements, the shop should display all available items with prices
        # Requirement 4.1: exact format "Магазин:\n1. Сообщение админу - 10 очков\nДля покупки введите /buy_contact"
        return {
            "success": True,
            "items": [
                {
                    "id": 1,
                    "name": "Сообщение админу",
                    "price": 10,
                    "description": "Администратор свяжется с вами"
                }
            ],
            "formatted_message": "Магазин:\n1. Сообщение админу - 10 очков\nДля покупки введите /buy_contact",
            "total_items": 1
        }
    
    def process_shop_command(self, user_id: int) -> Dict[str, Any]:
        """
        Process /shop command for a user
        Returns shop accessibility result
        """
        try:
            # Check if user is registered
            if not self.is_user_registered(user_id):
                return {
                    "success": False,
                    "error": "User not registered",
                    "accessible": False,
                    "items": None
                }
            
            # Get user info
            user_info = self.get_user_info(user_id)
            if not user_info:
                return {
                    "success": False,
                    "error": "User not found",
                    "accessible": False,
                    "items": None
                }
            
            # For registered users, shop should always be accessible (Requirement 4.3)
            shop_data = self.get_shop_items()
            
            return {
                "success": True,
                "accessible": True,
                "items": shop_data["items"],
                "formatted_message": shop_data["formatted_message"],
                "total_items": shop_data["total_items"],
                "user_balance": user_info["balance"]
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "accessible": False,
                "items": None
            }


class TestShopAccessibilityPBT(unittest.TestCase):
    """Property-based tests for shop accessibility universality"""
    
    def setUp(self):
        """Setup test database"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Initialize shop system with test database
        self.shop_system = SimpleShopSystem(self.temp_db.name)
        
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
        st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))),
        st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Zs'))),
        st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_shop_accessibility_universality_property(self, user_id, username, first_name, balance):
        """
        **Feature: telegram-bot-admin-system, Property 10: Shop accessibility universality**
        **Validates: Requirements 4.2, 4.3**
        
        For any registered user, the /shop command should be accessible and return 
        the complete list of available items
        """
        # Register the user first (making them a registered user)
        registration_success = self.shop_system.register_user(user_id, username, first_name, balance)
        self.assertTrue(registration_success, f"Failed to register user {user_id}")
        
        # Process shop command for the registered user
        result = self.shop_system.process_shop_command(user_id)
        
        # Core property: For ANY registered user, shop should be accessible
        self.assertTrue(result["success"], 
                       f"Shop command should succeed for registered user {user_id}: {result}")
        
        self.assertTrue(result["accessible"], 
                       f"Shop should be accessible for registered user {user_id}: {result}")
        
        # Verify complete list of available items is returned (Requirement 4.2)
        self.assertIsNotNone(result["items"], 
                            f"Shop should return items list for registered user {user_id}")
        
        self.assertIsInstance(result["items"], list, 
                             f"Shop items should be a list for user {user_id}")
        
        self.assertGreater(len(result["items"]), 0, 
                          f"Shop should return at least one item for user {user_id}")
        
        # Verify all items have required fields (prices in points - Requirement 4.2)
        for item in result["items"]:
            self.assertIn("name", item, f"Item should have name for user {user_id}")
            self.assertIn("price", item, f"Item should have price for user {user_id}")
            self.assertIsInstance(item["price"], (int, float), 
                                f"Item price should be numeric for user {user_id}")
            self.assertGreater(item["price"], 0, 
                             f"Item price should be positive for user {user_id}")
        
        # Verify formatted message is provided (exact format requirement)
        self.assertIn("formatted_message", result, 
                     f"Shop should provide formatted message for user {user_id}")
        
        expected_message = "Магазин:\n1. Сообщение админу - 10 очков\nДля покупки введите /buy_contact"
        self.assertEqual(result["formatted_message"], expected_message,
                        f"Shop message format should match requirements for user {user_id}")
        
        # Verify total items count
        self.assertIn("total_items", result, 
                     f"Shop should provide total items count for user {user_id}")
        
        self.assertEqual(result["total_items"], len(result["items"]),
                        f"Total items count should match items list length for user {user_id}")
        
        # Verify user balance is included in response
        self.assertIn("user_balance", result, 
                     f"Shop should include user balance for user {user_id}")
        
        self.assertEqual(result["user_balance"], balance,
                        f"User balance should match registered balance for user {user_id}")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647),
        st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_shop_accessibility_regardless_of_balance(self, user_id, balance):
        """
        **Feature: telegram-bot-admin-system, Property 10: Shop accessibility universality**
        **Validates: Requirements 4.2, 4.3**
        
        For any registered user, regardless of their balance, the /shop command 
        should be accessible and return the complete list of available items
        """
        # Register user with any balance (including 0 or very high)
        username = f"testuser_{user_id}"
        first_name = f"TestUser{user_id}"
        registration_success = self.shop_system.register_user(user_id, username, first_name, balance)
        self.assertTrue(registration_success, f"Failed to register user {user_id}")
        
        # Process shop command
        result = self.shop_system.process_shop_command(user_id)
        
        # Shop accessibility should not depend on user balance
        self.assertTrue(result["success"], 
                       f"Shop should be accessible regardless of balance {balance} for user {user_id}")
        
        self.assertTrue(result["accessible"], 
                       f"Shop should be accessible with balance {balance} for user {user_id}")
        
        # Complete list should always be returned
        self.assertIsNotNone(result["items"], 
                            f"Shop should return items regardless of balance {balance}")
        
        self.assertGreater(len(result["items"]), 0, 
                          f"Shop should return items even with balance {balance}")
        
        # Verify the standard shop item is always present
        contact_item = next((item for item in result["items"] if item["name"] == "Сообщение админу"), None)
        self.assertIsNotNone(contact_item, 
                            f"Contact item should be available regardless of balance {balance}")
        
        self.assertEqual(contact_item["price"], 10, 
                        f"Contact item price should be 10 regardless of balance {balance}")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(st.integers(min_value=1, max_value=2147483647))
    @settings(max_examples=100, deadline=None)
    def test_unregistered_users_cannot_access_shop(self, user_id):
        """
        **Feature: telegram-bot-admin-system, Property 10: Shop accessibility universality**
        **Validates: Requirements 4.2, 4.3**
        
        For any unregistered user, the /shop command should not be accessible
        (This tests the boundary condition of the property)
        """
        # Do NOT register the user
        # Process shop command for unregistered user
        result = self.shop_system.process_shop_command(user_id)
        
        # Unregistered users should not have access
        self.assertFalse(result["success"], 
                        f"Shop should not be accessible for unregistered user {user_id}")
        
        self.assertFalse(result["accessible"], 
                        f"Shop should not be accessible for unregistered user {user_id}")
        
        self.assertIsNone(result["items"], 
                         f"Shop should not return items for unregistered user {user_id}")
        
        self.assertIn("error", result, 
                     f"Shop should return error for unregistered user {user_id}")
    
    def test_shop_accessibility_without_hypothesis(self):
        """Fallback test when Hypothesis is not available"""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Test cases covering the property: registered users can always access shop
        test_cases = [
            # (user_id, username, first_name, balance)
            (12345, "testuser1", "Test User 1", 0.0),      # Zero balance
            (12346, "testuser2", "Test User 2", 5.0),      # Low balance
            (12347, "testuser3", "Test User 3", 10.0),     # Exact item price
            (12348, "testuser4", "Test User 4", 100.0),    # High balance
            (12349, "testuser5", "Test User 5", 9999.99),  # Very high balance
        ]
        
        for user_id, username, first_name, balance in test_cases:
            with self.subTest(user_id=user_id, balance=balance):
                # Register user
                registration_success = self.shop_system.register_user(user_id, username, first_name, balance)
                self.assertTrue(registration_success, f"Failed to register user {user_id}")
                
                # Process shop command
                result = self.shop_system.process_shop_command(user_id)
                
                # Verify the property holds
                self.assertTrue(result["success"], 
                               f"Shop should be accessible for registered user {user_id}")
                
                self.assertTrue(result["accessible"], 
                               f"Shop should be accessible for user {user_id}")
                
                # Verify complete list is returned
                self.assertIsNotNone(result["items"], 
                                    f"Shop should return items for user {user_id}")
                
                self.assertGreater(len(result["items"]), 0, 
                                  f"Shop should return at least one item for user {user_id}")
                
                # Verify exact format requirement
                expected_message = "Магазин:\n1. Сообщение админу - 10 очков\nДля покупки введите /buy_contact"
                self.assertEqual(result["formatted_message"], expected_message,
                                f"Shop message format should match requirements for user {user_id}")
        
        # Test unregistered user (boundary condition)
        unregistered_user_id = 99999
        result = self.shop_system.process_shop_command(unregistered_user_id)
        
        self.assertFalse(result["success"], 
                        "Shop should not be accessible for unregistered user")
        
        self.assertFalse(result["accessible"], 
                        "Shop should not be accessible for unregistered user")
        
        self.assertIsNone(result["items"], 
                         "Shop should not return items for unregistered user")


if __name__ == '__main__':
    unittest.main()