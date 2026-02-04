#!/usr/bin/env python3
"""
Property-based tests for purchase validation
Feature: telegram-bot-advanced-features, Property 1: Purchase Balance Validation
"""

import unittest
import sys
import os
import tempfile
import asyncio
from decimal import Decimal
from datetime import datetime

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

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database import Base, User, ShopItem, ShopCategory
from core.shop_manager import ShopManager


class TestPurchaseValidationPBT(unittest.TestCase):
    """Property-based tests for purchase validation"""
    
    def setUp(self):
        """Setup test database and ShopManager"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Create database engine and session
        self.engine = create_engine(f"sqlite:///{self.temp_db.name}")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Initialize ShopManager
        self.shop_manager = ShopManager(self.session)
        
        # Create test shop category
        category = ShopCategory(
            name="Test Category",
            description="Test category for property tests",
            is_active=True
        )
        self.session.add(category)
        self.session.commit()
        self.session.refresh(category)
        
        # Create test shop items with different prices
        test_items = [
            {
                "name": "Cheap Item",
                "description": "Low cost test item",
                "price": 100,
                "item_type": "custom"
            },
            {
                "name": "Medium Item", 
                "description": "Medium cost test item",
                "price": 500,
                "item_type": "sticker"
            },
            {
                "name": "Expensive Item",
                "description": "High cost test item", 
                "price": 1000,
                "item_type": "admin"
            }
        ]
        
        for item_data in test_items:
            item = ShopItem(
                category_id=category.id,
                name=item_data["name"],
                description=item_data["description"],
                price=item_data["price"],
                item_type=item_data["item_type"],
                is_active=True
            )
            self.session.add(item)
        
        self.session.commit()
        
    def _cleanup_test_data(self):
        """Clean up test data between property test runs"""
        try:
            # Clean up purchases to avoid foreign key constraints
            from database.database import UserPurchase
            self.session.query(UserPurchase).delete()
            self.session.commit()
        except Exception:
            self.session.rollback()
        
    def tearDown(self):
        """Clean up after tests"""
        self.session.close()
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    def _create_test_user(self, user_id: int, balance: int) -> User:
        """Create a test user with specified balance"""
        # Check if user already exists
        existing_user = self.session.query(User).filter(User.telegram_id == user_id).first()
        if existing_user:
            # Reset user state for clean test
            existing_user.balance = balance
            existing_user.total_purchases = 0
            existing_user.sticker_unlimited = False
            existing_user.sticker_unlimited_until = None
            self.session.commit()
            return existing_user
        
        # Create new user
        user = User(
            telegram_id=user_id,
            username=f"testuser_{user_id}",
            first_name=f"TestUser{user_id}",
            balance=balance,
            is_admin=False,
            total_purchases=0
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=0, max_value=10000),       # user_balance
        st.integers(min_value=1, max_value=3)            # item_number (1-3 for our test items)
    )
    @settings(max_examples=20, deadline=None)
    def test_purchase_balance_validation_property(self, user_balance, item_number):
        """
        **Property 1: Purchase Balance Validation**
        **Validates: Requirements 1.1, 1.2**
        
        For any user and shop item, when executing a purchase command, the system should 
        validate balance correctly: allowing purchase when balance >= price and rejecting 
        when balance < price
        """
        # Generate unique user ID for this test run to avoid conflicts
        import random
        user_id = random.randint(1000000, 2147483647)
        
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # Create test user with specified balance
        user = self._create_test_user(user_id, user_balance)
        
        # Get the shop item to determine its price
        shop_items = self.session.query(ShopItem).filter(ShopItem.is_active == True).all()
        if not shop_items or item_number > len(shop_items):
            self.skipTest(f"Item number {item_number} not available")
        
        item = shop_items[item_number - 1]  # Convert 1-based to 0-based index
        item_price = Decimal(str(item.price))
        user_balance_decimal = Decimal(str(user_balance))
        
        # Execute the purchase attempt
        result = asyncio.run(self.shop_manager.process_purchase(user_id, item_number))
        
        # The core property: purchase should succeed if and only if balance >= price
        expected_success = user_balance_decimal >= item_price
        actual_success = result.success
        
        self.assertEqual(
            actual_success, expected_success,
            f"Purchase validation failed: user_balance={user_balance}, item_price={item_price}, "
            f"item_name='{item.name}', expected_success={expected_success}, "
            f"actual_success={actual_success}, result_message='{result.message}'"
        )
        
        if expected_success:
            # If purchase should succeed, verify the balance was updated correctly
            self.assertTrue(result.success, "Purchase should have succeeded")
            self.assertIsNotNone(result.new_balance, "Successful purchase should return new balance")
            
            expected_new_balance = user_balance_decimal - item_price
            self.assertEqual(
                result.new_balance, expected_new_balance,
                f"New balance incorrect: expected {expected_new_balance}, got {result.new_balance}"
            )
            
            # Verify purchase was recorded
            self.assertIsNotNone(result.purchase_id, "Successful purchase should have purchase_id")
            
            # Verify user's balance in database was updated
            updated_user = self.session.query(User).filter(User.telegram_id == user_id).first()
            self.assertEqual(
                updated_user.balance, int(expected_new_balance),
                f"Database balance not updated correctly: expected {int(expected_new_balance)}, "
                f"got {updated_user.balance}"
            )
            
            # Verify total_purchases was incremented
            self.assertEqual(
                updated_user.total_purchases, 1,
                "Total purchases should be incremented for successful purchase"
            )
            
        else:
            # If purchase should fail, verify it failed with correct reason
            self.assertFalse(result.success, "Purchase should have failed")
            self.assertIsNotNone(result.message, "Failed purchase should return error message")
            
            # Verify balance was not changed
            unchanged_user = self.session.query(User).filter(User.telegram_id == user_id).first()
            self.assertEqual(
                unchanged_user.balance, user_balance,
                f"Balance should not change for failed purchase: expected {user_balance}, "
                f"got {unchanged_user.balance}"
            )
            
            # Verify total_purchases was not incremented
            self.assertEqual(
                unchanged_user.total_purchases, 0,
                "Total purchases should not be incremented for failed purchase"
            )
            
            # For insufficient balance, verify the error message is appropriate
            if "Недостаточно средств" in result.message:
                self.assertIn(str(item_price), result.message, 
                             "Insufficient balance message should include required amount")
                self.assertIn(str(user_balance_decimal), result.message,
                             "Insufficient balance message should include current balance")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1000, max_value=10000)     # user_balance (sufficient for all items)
    )
    @settings(max_examples=10, deadline=None)
    def test_sufficient_balance_always_allows_purchase(self, user_balance):
        """
        **Property 1: Purchase Balance Validation**
        **Validates: Requirements 1.1, 1.2**
        
        For any user with balance >= highest item price, the purchase should always succeed
        """
        # Generate unique user ID for this test run
        import random
        user_id = random.randint(1000000, 2147483647)
        
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # Create test user with sufficient balance
        user = self._create_test_user(user_id, user_balance)
        
        # Get all shop items and find the cheapest one (to ensure success)
        shop_items = self.session.query(ShopItem).filter(ShopItem.is_active == True).all()
        if not shop_items:
            self.skipTest("No shop items available")
        
        # Test with the cheapest item (item 1 - price 100)
        cheapest_item_number = 1
        cheapest_item = shop_items[0]
        
        # Ensure user has sufficient balance
        if user_balance < cheapest_item.price:
            user_balance = cheapest_item.price + 100
            user.balance = user_balance
            self.session.commit()
        
        # Execute purchase
        result = asyncio.run(self.shop_manager.process_purchase(user_id, cheapest_item_number))
        
        # Purchase should always succeed with sufficient balance
        self.assertTrue(result.success, 
                       f"Purchase should succeed with sufficient balance: "
                       f"balance={user_balance}, price={cheapest_item.price}, "
                       f"result_message='{result.message}'")
        
        # Verify balance was deducted correctly
        expected_new_balance = Decimal(str(user_balance)) - Decimal(str(cheapest_item.price))
        self.assertEqual(result.new_balance, expected_new_balance,
                        f"Balance deduction incorrect: expected {expected_new_balance}, "
                        f"got {result.new_balance}")
        
        # Verify purchase was recorded
        self.assertIsNotNone(result.purchase_id, "Purchase should be recorded with ID")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=0, max_value=99)           # user_balance (insufficient for all items)
    )
    @settings(max_examples=10, deadline=None)
    def test_insufficient_balance_always_denies_purchase(self, user_balance):
        """
        **Property 1: Purchase Balance Validation**
        **Validates: Requirements 1.1, 1.2**
        
        For any user with balance < lowest item price, the purchase should always fail
        """
        # Generate unique user ID for this test run
        import random
        user_id = random.randint(1000000, 2147483647)
        
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # Create test user with insufficient balance
        user = self._create_test_user(user_id, user_balance)
        
        # Get all shop items and find the cheapest one
        shop_items = self.session.query(ShopItem).filter(ShopItem.is_active == True).all()
        if not shop_items:
            self.skipTest("No shop items available")
        
        # Test with the cheapest item (item 1 - price 100)
        cheapest_item_number = 1
        cheapest_item = shop_items[0]
        
        # Ensure user has insufficient balance
        if user_balance >= cheapest_item.price:
            user_balance = cheapest_item.price - 1
            user.balance = user_balance
            self.session.commit()
        
        # Execute purchase
        result = asyncio.run(self.shop_manager.process_purchase(user_id, cheapest_item_number))
        
        # Purchase should always fail with insufficient balance
        self.assertFalse(result.success, 
                        f"Purchase should fail with insufficient balance: "
                        f"balance={user_balance}, price={cheapest_item.price}, "
                        f"result_message='{result.message}'")
        
        # Verify error message indicates insufficient balance
        self.assertIn("Недостаточно средств", result.message,
                     "Error message should indicate insufficient balance")
        
        # Verify balance was not changed
        unchanged_user = self.session.query(User).filter(User.telegram_id == user_id).first()
        self.assertEqual(unchanged_user.balance, user_balance,
                        "Balance should not change for failed purchase")
    
    def test_purchase_validation_without_hypothesis(self):
        """Fallback test when Hypothesis is not available"""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Test cases covering the property: balance >= price determines purchase success
        test_cases = [
            # (user_id, balance, item_number, expected_success)
            (12345, 100, 1, True),   # Exact balance for cheapest item
            (12346, 150, 1, True),   # Sufficient balance for cheapest item
            (12347, 99, 1, False),   # Insufficient balance for cheapest item
            (12348, 0, 1, False),    # Zero balance
            (12349, 1000, 3, True),  # Sufficient balance for expensive item
            (12350, 500, 3, False),  # Insufficient balance for expensive item
        ]
        
        for user_id, balance, item_number, expected_success in test_cases:
            with self.subTest(user_id=user_id, balance=balance, item_number=item_number):
                # Create test user
                user = self._create_test_user(user_id, balance)
                
                # Execute purchase
                result = asyncio.run(self.shop_manager.process_purchase(user_id, item_number))
                
                # Verify the property holds
                self.assertEqual(result.success, expected_success,
                               f"Purchase validation failed for balance={balance}, "
                               f"item_number={item_number}, result_message='{result.message}'")
                
                if expected_success:
                    # Verify successful purchase details
                    self.assertIsNotNone(result.new_balance, "Successful purchase should return new balance")
                    self.assertIsNotNone(result.purchase_id, "Successful purchase should have purchase_id")
                else:
                    # Verify failed purchase details
                    self.assertIsNotNone(result.message, "Failed purchase should return error message")


if __name__ == '__main__':
    unittest.main()