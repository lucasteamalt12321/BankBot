#!/usr/bin/env python3
"""
Property-based tests for purchase effects
Feature: telegram-bot-advanced-features, Property 2: Successful Purchase Effects
"""

import unittest
import sys
import os
import tempfile
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta

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

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database import Base, User, ShopItem, ShopCategory, UserPurchase
from core.managers.shop_manager import ShopManager


class TestPurchaseEffectsPBT(unittest.TestCase):
    """Property-based tests for successful purchase effects"""
    
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
        
        # Create test shop items with different types and prices
        test_items = [
            {
                "name": "Sticker Pack",
                "description": "Unlimited stickers for 24 hours",
                "price": 100,
                "item_type": "sticker"
            },
            {
                "name": "Admin Notification",
                "description": "Notify all administrators",
                "price": 250,
                "item_type": "admin"
            },
            {
                "name": "Mention All",
                "description": "Broadcast message to all users",
                "price": 500,
                "item_type": "mention_all"
            },
            {
                "name": "Custom Feature",
                "description": "Custom functionality",
                "price": 150,
                "item_type": "custom"
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
            total_purchases=0,
            sticker_unlimited=False,
            sticker_unlimited_until=None
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=100, max_value=10000),      # user_balance (sufficient for purchases)
        st.integers(min_value=1, max_value=4)             # item_number (1-4 for our test items)
    )
    @settings(max_examples=20, deadline=None)
    def test_successful_purchase_effects_property(self, user_balance, item_number):
        """
        **Property 2: Successful Purchase Effects**
        **Validates: Requirements 1.3, 1.4**
        
        For any successful purchase, the user's balance should decrease by exactly 
        the item price and the item's functionality should be activated for the user
        """
        # Generate unique user ID for this test run to avoid conflicts
        import random
        user_id = random.randint(1000000, 2147483647)
        
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # Get the shop item to determine its price
        shop_items = self.session.query(ShopItem).filter(ShopItem.is_active == True).all()
        if not shop_items or item_number > len(shop_items):
            self.skipTest(f"Item number {item_number} not available")
        
        item = shop_items[item_number - 1]  # Convert 1-based to 0-based index
        item_price = Decimal(str(item.price))
        user_balance_decimal = Decimal(str(user_balance))
        
        # Ensure user has sufficient balance for this test
        assume(user_balance_decimal >= item_price)
        
        # Create test user with sufficient balance
        user = self._create_test_user(user_id, user_balance)
        
        # Record initial state
        initial_balance = user_balance_decimal
        initial_purchases = user.total_purchases
        initial_sticker_unlimited = user.sticker_unlimited
        initial_sticker_until = user.sticker_unlimited_until
        
        # Execute the purchase
        result = asyncio.run(self.shop_manager.process_purchase(user_id, item_number))
        
        # The purchase should succeed since we ensured sufficient balance
        self.assertTrue(result.success, 
                       f"Purchase should succeed with sufficient balance: "
                       f"balance={user_balance}, price={item_price}, "
                       f"result_message='{result.message}'")
        
        # **Core Property 1: Balance should decrease by exactly the item price**
        expected_new_balance = initial_balance - item_price
        self.assertEqual(
            result.new_balance, expected_new_balance,
            f"Balance should decrease by exactly item price: "
            f"initial={initial_balance}, price={item_price}, "
            f"expected={expected_new_balance}, actual={result.new_balance}"
        )
        
        # Verify balance in database was updated correctly
        updated_user = self.session.query(User).filter(User.telegram_id == user_id).first()
        self.assertEqual(
            updated_user.balance, int(expected_new_balance),
            f"Database balance should match expected: "
            f"expected={int(expected_new_balance)}, actual={updated_user.balance}"
        )
        
        # **Core Property 2: Item functionality should be activated**
        # Verify purchase was recorded
        self.assertIsNotNone(result.purchase_id, "Purchase should be recorded with ID")
        
        # Verify purchase exists in database
        purchase = self.session.query(UserPurchase).filter(
            UserPurchase.id == result.purchase_id
        ).first()
        self.assertIsNotNone(purchase, "Purchase record should exist in database")
        self.assertEqual(purchase.user_id, updated_user.id, "Purchase should be linked to correct user")
        self.assertEqual(purchase.item_id, item.id, "Purchase should be linked to correct item")
        self.assertEqual(purchase.purchase_price, int(item_price), "Purchase price should match item price")
        
        # Verify total_purchases was incremented
        self.assertEqual(
            updated_user.total_purchases, initial_purchases + 1,
            "Total purchases should be incremented by 1"
        )
        
        # **Item-specific activation verification**
        if item.item_type == "sticker":
            # Sticker items should activate unlimited sticker access for 24 hours
            self.assertTrue(
                updated_user.sticker_unlimited,
                "Sticker item should activate unlimited sticker access"
            )
            self.assertIsNotNone(
                updated_user.sticker_unlimited_until,
                "Sticker item should set expiration time"
            )
            
            # Verify expiration is approximately 24 hours from now
            now = datetime.utcnow()
            expected_expiry = now + timedelta(hours=24)
            time_diff = abs((updated_user.sticker_unlimited_until - expected_expiry).total_seconds())
            self.assertLess(
                time_diff, 60,  # Allow 1 minute tolerance
                f"Sticker expiration should be ~24 hours from now: "
                f"expected={expected_expiry}, actual={updated_user.sticker_unlimited_until}"
            )
            
        elif item.item_type == "admin":
            # Admin items should trigger notification system
            # We can't easily test the actual notification sending in this unit test,
            # but we can verify the purchase was processed correctly
            self.assertIn("админ", result.message.lower(), 
                         "Admin item activation should mention admin functionality")
            
        elif item.item_type == "mention_all":
            # Mention-all items should prompt for broadcast message
            self.assertIn("рассылк", result.message.lower(),
                         "Mention-all item should mention broadcast functionality")
            
        elif item.item_type == "custom":
            # Custom items should have generic activation
            self.assertIn("активирован", result.message.lower(),
                         "Custom item should indicate activation")
        
        # Verify purchase metadata contains activation information
        if purchase.meta_data:
            self.assertIn('activation_result', purchase.meta_data,
                         "Purchase metadata should contain activation result")
            self.assertIn('activated_at', purchase.meta_data,
                         "Purchase metadata should contain activation timestamp")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1000, max_value=5000)        # user_balance (sufficient for sticker items)
    )
    @settings(max_examples=10, deadline=None)
    def test_sticker_item_activation_effects(self, user_balance):
        """
        **Property 2: Successful Purchase Effects - Sticker Specific**
        **Validates: Requirements 1.4, 2.1, 2.2**
        
        For any successful sticker item purchase, the user should get unlimited 
        sticker access for exactly 24 hours
        """
        # Generate unique user ID for this test run
        import random
        user_id = random.randint(1000000, 2147483647)
        
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # Find sticker item (item 1 in our test setup)
        sticker_item_number = 1
        shop_items = self.session.query(ShopItem).filter(ShopItem.is_active == True).all()
        sticker_item = shop_items[0]  # First item is sticker type
        
        # Ensure user has sufficient balance
        if user_balance < sticker_item.price:
            user_balance = sticker_item.price + 100
        
        # Create test user
        user = self._create_test_user(user_id, user_balance)
        
        # Record time before purchase for expiration verification
        purchase_time = datetime.utcnow()
        
        # Execute purchase
        result = asyncio.run(self.shop_manager.process_purchase(user_id, sticker_item_number))
        
        # Verify purchase succeeded
        self.assertTrue(result.success, f"Sticker purchase should succeed: {result.message}")
        
        # Verify sticker-specific effects
        updated_user = self.session.query(User).filter(User.telegram_id == user_id).first()
        
        # Should have unlimited sticker access
        self.assertTrue(
            updated_user.sticker_unlimited,
            "Sticker purchase should enable unlimited access"
        )
        
        # Should have expiration set to ~24 hours from purchase
        self.assertIsNotNone(
            updated_user.sticker_unlimited_until,
            "Sticker purchase should set expiration time"
        )
        
        # Verify expiration is approximately 24 hours from purchase time
        expected_expiry = purchase_time + timedelta(hours=24)
        actual_expiry = updated_user.sticker_unlimited_until
        time_diff = abs((actual_expiry - expected_expiry).total_seconds())
        
        self.assertLess(
            time_diff, 120,  # Allow 2 minutes tolerance for test execution time
            f"Sticker expiration should be ~24 hours from purchase: "
            f"purchase_time={purchase_time}, expected_expiry={expected_expiry}, "
            f"actual_expiry={actual_expiry}, diff_seconds={time_diff}"
        )
        
        # Verify balance was deducted correctly
        expected_balance = user_balance - sticker_item.price
        self.assertEqual(
            updated_user.balance, expected_balance,
            f"Balance should be deducted correctly: "
            f"initial={user_balance}, price={sticker_item.price}, "
            f"expected={expected_balance}, actual={updated_user.balance}"
        )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=500, max_value=3000)         # user_balance (sufficient for various items)
    )
    @settings(max_examples=10, deadline=None)
    def test_purchase_effects_consistency(self, user_balance):
        """
        **Property 2: Successful Purchase Effects - Consistency**
        **Validates: Requirements 1.3, 1.4**
        
        For any successful purchase, the effects should be consistent:
        - Balance deduction should always equal item price
        - Purchase record should always be created
        - Total purchases should always increment by 1
        - Item activation should always occur
        """
        # Generate unique user ID for this test run
        import random
        user_id = random.randint(1000000, 2147483647)
        
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # Get all shop items
        shop_items = self.session.query(ShopItem).filter(ShopItem.is_active == True).all()
        if not shop_items:
            self.skipTest("No shop items available")
        
        # Choose a random item that user can afford
        affordable_items = [item for item in shop_items if item.price <= user_balance]
        if not affordable_items:
            self.skipTest(f"No affordable items for balance {user_balance}")
        
        import random
        chosen_item = random.choice(affordable_items)
        item_number = shop_items.index(chosen_item) + 1  # Convert to 1-based index
        
        # Create test user
        user = self._create_test_user(user_id, user_balance)
        initial_purchases = user.total_purchases
        
        # Execute purchase
        result = asyncio.run(self.shop_manager.process_purchase(user_id, item_number))
        
        # Verify purchase succeeded
        self.assertTrue(result.success, f"Purchase should succeed: {result.message}")
        
        # **Consistency Check 1: Balance deduction equals item price**
        expected_new_balance = Decimal(str(user_balance)) - Decimal(str(chosen_item.price))
        self.assertEqual(
            result.new_balance, expected_new_balance,
            f"Balance deduction should equal item price: "
            f"item_price={chosen_item.price}, expected_balance={expected_new_balance}, "
            f"actual_balance={result.new_balance}"
        )
        
        # **Consistency Check 2: Purchase record created**
        self.assertIsNotNone(result.purchase_id, "Purchase record should be created")
        
        purchase = self.session.query(UserPurchase).filter(
            UserPurchase.id == result.purchase_id
        ).first()
        self.assertIsNotNone(purchase, "Purchase should exist in database")
        
        # **Consistency Check 3: Total purchases incremented by exactly 1**
        updated_user = self.session.query(User).filter(User.telegram_id == user_id).first()
        self.assertEqual(
            updated_user.total_purchases, initial_purchases + 1,
            f"Total purchases should increment by 1: "
            f"initial={initial_purchases}, actual={updated_user.total_purchases}"
        )
        
        # **Consistency Check 4: Item activation occurred**
        # Verify purchase metadata contains activation information
        self.assertIsNotNone(purchase.meta_data, "Purchase should have metadata")
        if purchase.meta_data:
            self.assertIn('activation_result', purchase.meta_data,
                         "Purchase metadata should contain activation result")
            
            activation_result = purchase.meta_data['activation_result']
            self.assertIn('activated', activation_result,
                         "Activation result should indicate if activation occurred")
    
    def test_purchase_effects_without_hypothesis(self):
        """Fallback test when Hypothesis is not available"""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Test cases covering the property: successful purchases have correct effects
        test_cases = [
            # (user_id, balance, item_number, expected_item_type)
            (12345, 200, 1, "sticker"),     # Sticker item
            (12346, 300, 2, "admin"),       # Admin item  
            (12347, 600, 3, "mention_all"), # Mention-all item
            (12348, 200, 4, "custom"),      # Custom item
        ]
        
        for user_id, balance, item_number, expected_item_type in test_cases:
            with self.subTest(user_id=user_id, balance=balance, item_number=item_number):
                # Clean up test data
                self._cleanup_test_data()
                
                # Get item details
                shop_items = self.session.query(ShopItem).filter(ShopItem.is_active == True).all()
                if item_number > len(shop_items):
                    continue
                
                item = shop_items[item_number - 1]
                
                # Ensure sufficient balance
                if balance < item.price:
                    balance = item.price + 100
                
                # Create test user
                user = self._create_test_user(user_id, balance)
                initial_balance = balance
                initial_purchases = user.total_purchases
                
                # Execute purchase
                result = asyncio.run(self.shop_manager.process_purchase(user_id, item_number))
                
                # Verify purchase succeeded
                self.assertTrue(result.success, f"Purchase should succeed: {result.message}")
                
                # Verify balance deduction
                expected_new_balance = Decimal(str(initial_balance)) - Decimal(str(item.price))
                self.assertEqual(result.new_balance, expected_new_balance,
                               f"Balance should be deducted correctly")
                
                # Verify purchase record
                self.assertIsNotNone(result.purchase_id, "Purchase should be recorded")
                
                # Verify database state
                updated_user = self.session.query(User).filter(User.telegram_id == user_id).first()
                self.assertEqual(updated_user.balance, int(expected_new_balance),
                               "Database balance should match")
                self.assertEqual(updated_user.total_purchases, initial_purchases + 1,
                               "Total purchases should increment")
                
                # Verify item-specific activation
                if expected_item_type == "sticker":
                    self.assertTrue(updated_user.sticker_unlimited,
                                   "Sticker item should activate unlimited access")
                    self.assertIsNotNone(updated_user.sticker_unlimited_until,
                                        "Sticker item should set expiration")


if __name__ == '__main__':
    unittest.main()