#!/usr/bin/env python3
"""
Property-based tests for sticker access lifecycle
Feature: telegram-bot-advanced-features, Property 3: Sticker Access Lifecycle
"""

import unittest
import sys
import os
import tempfile
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

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
from database.database import Base, User, ShopItem, ShopCategory
from core.managers.sticker_manager import StickerManager
from core.managers.shop_manager import ShopManager


class TestStickerAccessLifecyclePBT(unittest.TestCase):
    """Property-based tests for sticker access lifecycle"""
    
    def setUp(self):
        """Setup test database and managers"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Create database engine and session
        self.engine = create_engine(f"sqlite:///{self.temp_db.name}")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Initialize managers
        self.sticker_manager = StickerManager(self.session)
        self.shop_manager = ShopManager(self.session)
        
        # Create test shop category
        category = ShopCategory(
            name="Test Category",
            description="Test category for sticker tests",
            is_active=True
        )
        self.session.add(category)
        self.session.commit()
        self.session.refresh(category)
        
        # Create sticker shop item
        sticker_item = ShopItem(
            category_id=category.id,
            name="Stickers",
            description="Unlimited sticker access for 24 hours",
            price=100,
            item_type="sticker",
            is_active=True
        )
        self.session.add(sticker_item)
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
    
    def _create_test_user(self, user_id: int, balance: int = 1000) -> User:
        """Create a test user with specified balance"""
        # Check if user already exists and delete it
        existing_user = self.session.query(User).filter(User.telegram_id == user_id).first()
        if existing_user:
            self.session.delete(existing_user)
            self.session.commit()
        
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
        st.integers(min_value=1, max_value=2147483647),  # user_id
        st.integers(min_value=1, max_value=168)          # duration_hours (1 hour to 1 week)
    )
    @settings(max_examples=20, deadline=None)
    def test_sticker_access_lifecycle_property(self, user_id, duration_hours):
        """
        **Property 3: Sticker Access Lifecycle**
        **Validates: Requirements 2.1, 2.2, 2.4**
        
        For any user purchasing stickers, the system should set unlimited access to True 
        with expiration exactly 24 hours from purchase time, and automatically revoke 
        access when expired
        """
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # Create test user with sufficient balance
        user = self._create_test_user(user_id, balance=1000)
        
        # Record the time before granting access
        before_grant = datetime.utcnow()
        
        # Grant unlimited sticker access
        asyncio.run(self.sticker_manager.grant_unlimited_access(user_id, duration_hours))
        
        # Record the time after granting access
        after_grant = datetime.utcnow()
        
        # Refresh user from database
        self.session.refresh(user)
        
        # **Property Part 1: Access should be granted (Requirement 2.1)**
        self.assertTrue(
            user.sticker_unlimited,
            f"User {user_id} should have unlimited sticker access after granting"
        )
        
        # **Property Part 2: Expiration should be set correctly (Requirement 2.2)**
        self.assertIsNotNone(
            user.sticker_unlimited_until,
            f"User {user_id} should have expiration time set"
        )
        
        # Calculate expected expiration range
        expected_min_expiration = before_grant + timedelta(hours=duration_hours)
        expected_max_expiration = after_grant + timedelta(hours=duration_hours)
        
        # Verify expiration is within expected range
        self.assertGreaterEqual(
            user.sticker_unlimited_until, expected_min_expiration,
            f"Expiration time should be at least {duration_hours} hours from grant time"
        )
        self.assertLessEqual(
            user.sticker_unlimited_until, expected_max_expiration,
            f"Expiration time should be at most {duration_hours} hours from grant time"
        )
        
        # **Property Part 3: Access should be valid before expiration**
        has_access_before_expiry = asyncio.run(self.sticker_manager.check_access(user_id))
        self.assertTrue(
            has_access_before_expiry,
            f"User {user_id} should have access before expiration"
        )
        
        # **Property Part 4: Access should be automatically revoked when expired (Requirement 2.4)**
        # Simulate expiration by setting the expiration time to the past
        user.sticker_unlimited_until = datetime.utcnow() - timedelta(minutes=1)
        self.session.commit()
        
        # Check access - this should automatically revoke expired access
        has_access_after_expiry = asyncio.run(self.sticker_manager.check_access(user_id))
        self.assertFalse(
            has_access_after_expiry,
            f"User {user_id} should not have access after expiration"
        )
        
        # Verify the unlimited flag was automatically set to False
        self.session.refresh(user)
        self.assertFalse(
            user.sticker_unlimited,
            f"User {user_id} unlimited flag should be False after expiration"
        )
        self.assertIsNone(
            user.sticker_unlimited_until,
            f"User {user_id} expiration time should be cleared after expiration"
        )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647)   # user_id
    )
    @settings(max_examples=20, deadline=None)
    def test_sticker_purchase_lifecycle_property(self, user_id):
        """
        **Property 3: Sticker Access Lifecycle**
        **Validates: Requirements 2.1, 2.2, 2.4**
        
        For any user purchasing stickers through the shop system, the complete lifecycle 
        should work: purchase -> access granted -> 24 hours expiration -> automatic revocation
        """
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # Create test user with sufficient balance
        user = self._create_test_user(user_id, balance=1000)
        
        # Record time before purchase
        before_purchase = datetime.utcnow()
        
        # Purchase sticker item (item number 1)
        purchase_result = asyncio.run(self.shop_manager.process_purchase(user_id, 1))
        
        # Record time after purchase
        after_purchase = datetime.utcnow()
        
        # Verify purchase was successful
        self.assertTrue(
            purchase_result.success,
            f"Sticker purchase should succeed for user {user_id} with sufficient balance"
        )
        
        # Refresh user from database
        self.session.refresh(user)
        
        # **Property Part 1: Sticker purchase should grant unlimited access (Requirement 2.1)**
        self.assertTrue(
            user.sticker_unlimited,
            f"User {user_id} should have unlimited sticker access after purchase"
        )
        
        # **Property Part 2: Expiration should be exactly 24 hours from purchase (Requirement 2.2)**
        self.assertIsNotNone(
            user.sticker_unlimited_until,
            f"User {user_id} should have expiration time set after sticker purchase"
        )
        
        # Calculate expected 24-hour expiration range
        expected_min_expiration = before_purchase + timedelta(hours=24)
        expected_max_expiration = after_purchase + timedelta(hours=24)
        
        # Verify expiration is exactly 24 hours from purchase time
        self.assertGreaterEqual(
            user.sticker_unlimited_until, expected_min_expiration,
            f"Sticker access should expire at least 24 hours from purchase time"
        )
        self.assertLessEqual(
            user.sticker_unlimited_until, expected_max_expiration,
            f"Sticker access should expire at most 24 hours from purchase time"
        )
        
        # **Property Part 3: Access should be valid immediately after purchase**
        has_access_after_purchase = asyncio.run(self.sticker_manager.check_access(user_id))
        self.assertTrue(
            has_access_after_purchase,
            f"User {user_id} should have access immediately after sticker purchase"
        )
        
        # **Property Part 4: Access should be automatically revoked when expired (Requirement 2.4)**
        # Simulate expiration by setting the expiration time to the past
        original_expiration = user.sticker_unlimited_until
        user.sticker_unlimited_until = datetime.utcnow() - timedelta(minutes=1)
        self.session.commit()
        
        # Check access - this should automatically revoke expired access
        has_access_after_expiry = asyncio.run(self.sticker_manager.check_access(user_id))
        self.assertFalse(
            has_access_after_expiry,
            f"User {user_id} should not have access after sticker access expires"
        )
        
        # Verify automatic revocation occurred
        self.session.refresh(user)
        self.assertFalse(
            user.sticker_unlimited,
            f"User {user_id} unlimited flag should be automatically set to False after expiration"
        )
        self.assertIsNone(
            user.sticker_unlimited_until,
            f"User {user_id} expiration time should be cleared after automatic revocation"
        )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647),  # user_id
        st.integers(min_value=1, max_value=1440)         # minutes_until_expiry (1 minute to 24 hours)
    )
    @settings(max_examples=20, deadline=None)
    def test_automatic_expiration_timing_property(self, user_id, minutes_until_expiry):
        """
        **Property 3: Sticker Access Lifecycle**
        **Validates: Requirements 2.4**
        
        For any user with sticker access, the system should automatically revoke access 
        exactly when the expiration time is reached, not before or after
        """
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # Create test user
        user = self._create_test_user(user_id, balance=1000)
        
        # Set up access with specific expiration time
        expiration_time = datetime.utcnow() + timedelta(minutes=minutes_until_expiry)
        user.sticker_unlimited = True
        user.sticker_unlimited_until = expiration_time
        self.session.commit()
        
        # **Property Part 1: Access should be valid before expiration**
        # Set time to 1 minute before expiration
        user.sticker_unlimited_until = datetime.utcnow() + timedelta(minutes=1)
        self.session.commit()
        
        has_access_before = asyncio.run(self.sticker_manager.check_access(user_id))
        self.assertTrue(
            has_access_before,
            f"User {user_id} should have access before expiration time"
        )
        
        # Verify access is still active
        self.session.refresh(user)
        self.assertTrue(
            user.sticker_unlimited,
            f"User {user_id} should still have unlimited flag set before expiration"
        )
        
        # **Property Part 2: Access should be automatically revoked at expiration**
        # Set time to exactly at expiration (or 1 minute past)
        user.sticker_unlimited_until = datetime.utcnow() - timedelta(minutes=1)
        self.session.commit()
        
        has_access_at_expiry = asyncio.run(self.sticker_manager.check_access(user_id))
        self.assertFalse(
            has_access_at_expiry,
            f"User {user_id} should not have access at or after expiration time"
        )
        
        # Verify automatic revocation occurred
        self.session.refresh(user)
        self.assertFalse(
            user.sticker_unlimited,
            f"User {user_id} unlimited flag should be automatically revoked at expiration"
        )
        self.assertIsNone(
            user.sticker_unlimited_until,
            f"User {user_id} expiration time should be cleared after automatic revocation"
        )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.lists(
            st.integers(min_value=1, max_value=100000),  # user_ids
            min_size=1,
            max_size=10,
            unique=True
        )
    )
    @settings(max_examples=10, deadline=None)
    def test_multiple_users_lifecycle_property(self, user_ids):
        """
        **Property 3: Sticker Access Lifecycle**
        **Validates: Requirements 2.1, 2.2, 2.4**
        
        For any set of users purchasing stickers, each user should have independent 
        access lifecycle management
        """
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # Create test users and grant them access at different times
        users_data = []
        base_time = datetime.utcnow()
        
        for i, user_id in enumerate(user_ids):
            user = self._create_test_user(user_id, balance=1000)
            
            # Grant access with different expiration times
            expiration_offset = timedelta(hours=24, minutes=i * 10)  # Stagger expirations
            expiration_time = base_time + expiration_offset
            
            user.sticker_unlimited = True
            user.sticker_unlimited_until = expiration_time
            self.session.commit()
            
            users_data.append({
                'user_id': user_id,
                'user': user,
                'expiration_time': expiration_time
            })
        
        # **Property Part 1: All users should have access initially**
        for user_data in users_data:
            has_access = asyncio.run(self.sticker_manager.check_access(user_data['user_id']))
            self.assertTrue(
                has_access,
                f"User {user_data['user_id']} should have access after being granted"
            )
        
        # **Property Part 2: Users should lose access independently when expired**
        # Expire the first half of users
        current_time = datetime.utcnow()
        expired_count = 0
        
        for user_data in users_data[:len(users_data)//2]:
            user = user_data['user']
            user.sticker_unlimited_until = current_time - timedelta(minutes=1)
            self.session.commit()
            expired_count += 1
        
        # Check access for all users
        for i, user_data in enumerate(users_data):
            has_access = asyncio.run(self.sticker_manager.check_access(user_data['user_id']))
            
            if i < len(users_data)//2:
                # These users should have lost access
                self.assertFalse(
                    has_access,
                    f"Expired user {user_data['user_id']} should not have access"
                )
                
                # Verify automatic revocation
                self.session.refresh(user_data['user'])
                self.assertFalse(
                    user_data['user'].sticker_unlimited,
                    f"Expired user {user_data['user_id']} should have unlimited flag revoked"
                )
            else:
                # These users should still have access
                self.assertTrue(
                    has_access,
                    f"Non-expired user {user_data['user_id']} should still have access"
                )
                
                # Verify access is still active
                self.session.refresh(user_data['user'])
                self.assertTrue(
                    user_data['user'].sticker_unlimited,
                    f"Non-expired user {user_data['user_id']} should still have unlimited flag"
                )
    
    def test_sticker_access_lifecycle_without_hypothesis(self):
        """Fallback test when Hypothesis is not available"""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Test cases covering the sticker access lifecycle property
        test_cases = [
            # (user_id, duration_hours, description)
            (12345, 24, "Standard 24-hour access"),
            (12346, 1, "Short 1-hour access"),
            (12347, 48, "Extended 48-hour access"),
            (12348, 168, "Week-long access"),
        ]
        
        for user_id, duration_hours, description in test_cases:
            with self.subTest(user_id=user_id, duration_hours=duration_hours, description=description):
                # Clean up test data
                self._cleanup_test_data()
                
                # Create test user
                user = self._create_test_user(user_id, balance=1000)
                
                # Record time before granting access
                before_grant = datetime.utcnow()
                
                # Grant unlimited sticker access
                asyncio.run(self.sticker_manager.grant_unlimited_access(user_id, duration_hours))
                
                # Record time after granting access
                after_grant = datetime.utcnow()
                
                # Refresh user from database
                self.session.refresh(user)
                
                # Verify access was granted (Requirement 2.1)
                self.assertTrue(user.sticker_unlimited, f"Access should be granted for {description}")
                
                # Verify expiration was set correctly (Requirement 2.2)
                self.assertIsNotNone(user.sticker_unlimited_until, f"Expiration should be set for {description}")
                
                expected_min_expiration = before_grant + timedelta(hours=duration_hours)
                expected_max_expiration = after_grant + timedelta(hours=duration_hours)
                
                self.assertGreaterEqual(user.sticker_unlimited_until, expected_min_expiration,
                                      f"Expiration should be at least {duration_hours} hours for {description}")
                self.assertLessEqual(user.sticker_unlimited_until, expected_max_expiration,
                                    f"Expiration should be at most {duration_hours} hours for {description}")
                
                # Verify access is valid before expiration
                has_access_before = asyncio.run(self.sticker_manager.check_access(user_id))
                self.assertTrue(has_access_before, f"Access should be valid before expiration for {description}")
                
                # Simulate expiration and verify automatic revocation (Requirement 2.4)
                user.sticker_unlimited_until = datetime.utcnow() - timedelta(minutes=1)
                self.session.commit()
                
                has_access_after = asyncio.run(self.sticker_manager.check_access(user_id))
                self.assertFalse(has_access_after, f"Access should be revoked after expiration for {description}")
                
                # Verify automatic cleanup
                self.session.refresh(user)
                self.assertFalse(user.sticker_unlimited, f"Unlimited flag should be cleared for {description}")
                self.assertIsNone(user.sticker_unlimited_until, f"Expiration time should be cleared for {description}")


if __name__ == '__main__':
    unittest.main()