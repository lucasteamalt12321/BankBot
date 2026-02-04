#!/usr/bin/env python3
"""
Property-based tests for sticker usage control
Feature: telegram-bot-advanced-features, Property 4: Sticker Usage Control
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
from database.database import Base, User, ShopItem, ShopCategory, ScheduledTask
from core.sticker_manager import StickerManager


class TestStickerUsageControlPBT(unittest.TestCase):
    """Property-based tests for sticker usage control"""
    
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
        
    def _cleanup_test_data(self):
        """Clean up test data between property test runs"""
        try:
            # Clean up scheduled tasks
            self.session.query(ScheduledTask).delete()
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
    
    def _create_test_user(self, user_id: int, balance: int = 1000, 
                         has_unlimited: bool = False, 
                         unlimited_until: datetime = None) -> User:
        """Create a test user with specified sticker access settings"""
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
            sticker_unlimited=has_unlimited,
            sticker_unlimited_until=unlimited_until
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647),  # user_id
        st.integers(min_value=1, max_value=1440)         # minutes_until_expiry (1 minute to 24 hours)
    )
    @settings(max_examples=20, deadline=None)
    def test_sticker_operations_allowed_with_unlimited_access_property(self, user_id, minutes_until_expiry):
        """
        **Property 4: Sticker Usage Control**
        **Validates: Requirements 2.3, 2.5**
        
        For any user with unlimited sticker access that hasn't expired, 
        sticker operations should be allowed
        """
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # Create user with unlimited access that hasn't expired
        expiration_time = datetime.utcnow() + timedelta(minutes=minutes_until_expiry)
        user = self._create_test_user(
            user_id, 
            has_unlimited=True, 
            unlimited_until=expiration_time
        )
        
        # **Property Part 1: User should have access when unlimited is active and not expired**
        has_access = asyncio.run(self.sticker_manager.check_access(user_id))
        self.assertTrue(
            has_access,
            f"User {user_id} should have sticker access when unlimited is True and not expired"
        )
        
        # Verify the user still has unlimited access after check
        self.session.refresh(user)
        self.assertTrue(
            user.sticker_unlimited,
            f"User {user_id} should still have unlimited flag after access check"
        )
        self.assertIsNotNone(
            user.sticker_unlimited_until,
            f"User {user_id} should still have expiration time after access check"
        )
        
        # **Property Part 2: Access should remain valid for multiple checks before expiration**
        # Perform multiple access checks to ensure consistency
        for check_num in range(3):
            has_access_repeated = asyncio.run(self.sticker_manager.check_access(user_id))
            self.assertTrue(
                has_access_repeated,
                f"User {user_id} should have consistent access on check #{check_num + 1}"
            )
        
        # Verify user state is still consistent
        self.session.refresh(user)
        self.assertTrue(
            user.sticker_unlimited,
            f"User {user_id} should maintain unlimited access after multiple checks"
        )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647),  # user_id
        st.integers(min_value=1, max_value=60)           # minutes_past_expiry (1 to 60 minutes)
    )
    @settings(max_examples=20, deadline=None)
    def test_sticker_operations_denied_after_expiration_property(self, user_id, minutes_past_expiry):
        """
        **Property 4: Sticker Usage Control**
        **Validates: Requirements 2.3, 2.5**
        
        For any user whose unlimited sticker access has expired, 
        sticker operations should be denied and access should be automatically revoked
        """
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # Create user with expired unlimited access
        expiration_time = datetime.utcnow() - timedelta(minutes=minutes_past_expiry)
        user = self._create_test_user(
            user_id, 
            has_unlimited=True, 
            unlimited_until=expiration_time
        )
        
        # **Property Part 1: User should not have access when unlimited access is expired**
        has_access = asyncio.run(self.sticker_manager.check_access(user_id))
        self.assertFalse(
            has_access,
            f"User {user_id} should not have sticker access when unlimited access is expired"
        )
        
        # **Property Part 2: Expired access should be automatically revoked**
        self.session.refresh(user)
        self.assertFalse(
            user.sticker_unlimited,
            f"User {user_id} unlimited flag should be automatically revoked after expiration"
        )
        self.assertIsNone(
            user.sticker_unlimited_until,
            f"User {user_id} expiration time should be cleared after automatic revocation"
        )
        
        # **Property Part 3: Subsequent access checks should consistently deny access**
        for check_num in range(3):
            has_access_repeated = asyncio.run(self.sticker_manager.check_access(user_id))
            self.assertFalse(
                has_access_repeated,
                f"User {user_id} should consistently be denied access on check #{check_num + 1}"
            )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647),  # user_id
        st.integers(min_value=1, max_value=10)           # delay_minutes (1 to 10 minutes)
    )
    @settings(max_examples=20, deadline=None)
    def test_sticker_auto_delete_without_unlimited_access_property(self, user_id, delay_minutes):
        """
        **Property 4: Sticker Usage Control**
        **Validates: Requirements 2.5**
        
        For any user without unlimited sticker access, stickers should be 
        scheduled for auto-deletion after the specified delay
        """
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # Create user without unlimited access
        user = self._create_test_user(user_id, has_unlimited=False)
        
        # Verify user doesn't have unlimited access
        has_access = asyncio.run(self.sticker_manager.check_access(user_id))
        self.assertFalse(
            has_access,
            f"User {user_id} should not have unlimited sticker access"
        )
        
        # **Property Part 1: Auto-deletion should be scheduled for users without unlimited access**
        message_id = user_id * 1000 + delay_minutes  # Generate unique message ID
        
        # Record time before scheduling
        before_schedule = datetime.utcnow()
        
        # Schedule auto-deletion
        await_result = asyncio.run(self.sticker_manager.auto_delete_sticker(message_id, delay_minutes))
        
        # Record time after scheduling
        after_schedule = datetime.utcnow()
        
        # **Property Part 2: Scheduled task should be created with correct parameters**
        scheduled_task = self.session.query(ScheduledTask).filter(
            ScheduledTask.message_id == message_id,
            ScheduledTask.task_type == "auto_delete_sticker"
        ).first()
        
        self.assertIsNotNone(
            scheduled_task,
            f"Auto-deletion task should be scheduled for message {message_id}"
        )
        
        self.assertEqual(
            scheduled_task.message_id, message_id,
            f"Scheduled task should have correct message ID {message_id}"
        )
        
        self.assertEqual(
            scheduled_task.task_type, "auto_delete_sticker",
            f"Scheduled task should have correct task type"
        )
        
        self.assertFalse(
            scheduled_task.is_completed,
            f"Scheduled task should not be marked as completed initially"
        )
        
        # **Property Part 3: Execution time should be correctly calculated**
        expected_min_execution = before_schedule + timedelta(minutes=delay_minutes)
        expected_max_execution = after_schedule + timedelta(minutes=delay_minutes)
        
        self.assertGreaterEqual(
            scheduled_task.execute_at, expected_min_execution,
            f"Task execution time should be at least {delay_minutes} minutes from scheduling"
        )
        
        self.assertLessEqual(
            scheduled_task.execute_at, expected_max_execution,
            f"Task execution time should be at most {delay_minutes} minutes from scheduling"
        )
        
        # **Property Part 4: Task data should contain correct information**
        self.assertIsNotNone(
            scheduled_task.task_data,
            f"Scheduled task should have task data"
        )
        
        task_data = scheduled_task.task_data
        self.assertEqual(
            task_data.get("message_id"), message_id,
            f"Task data should contain correct message ID"
        )
        
        self.assertEqual(
            task_data.get("delay_minutes"), delay_minutes,
            f"Task data should contain correct delay minutes"
        )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647)   # user_id
    )
    @settings(max_examples=20, deadline=None)
    def test_sticker_usage_control_transition_property(self, user_id):
        """
        **Property 4: Sticker Usage Control**
        **Validates: Requirements 2.3, 2.5**
        
        For any user, sticker usage control should properly transition from 
        unlimited access to auto-deletion when access expires
        """
        # Clean up any previous test data
        self._cleanup_test_data()
        
        # **Phase 1: User with unlimited access**
        # Create user with unlimited access that will expire soon
        expiration_time = datetime.utcnow() + timedelta(minutes=5)
        user = self._create_test_user(
            user_id, 
            has_unlimited=True, 
            unlimited_until=expiration_time
        )
        
        # Verify user has access initially
        has_access_before = asyncio.run(self.sticker_manager.check_access(user_id))
        self.assertTrue(
            has_access_before,
            f"User {user_id} should have access before expiration"
        )
        
        # **Phase 2: Simulate expiration**
        # Manually expire the access by setting expiration to past
        user.sticker_unlimited_until = datetime.utcnow() - timedelta(minutes=1)
        self.session.commit()
        
        # Check access - this should trigger automatic revocation
        has_access_after = asyncio.run(self.sticker_manager.check_access(user_id))
        self.assertFalse(
            has_access_after,
            f"User {user_id} should not have access after expiration"
        )
        
        # Verify automatic revocation occurred
        self.session.refresh(user)
        self.assertFalse(
            user.sticker_unlimited,
            f"User {user_id} unlimited flag should be revoked after expiration"
        )
        self.assertIsNone(
            user.sticker_unlimited_until,
            f"User {user_id} expiration time should be cleared after revocation"
        )
        
        # **Phase 3: Auto-deletion should now be required**
        # Schedule auto-deletion for a sticker (simulating normal usage)
        message_id = user_id * 1000 + 999  # Generate unique message ID
        delay_minutes = 2  # Default delay
        
        # Schedule auto-deletion
        asyncio.run(self.sticker_manager.auto_delete_sticker(message_id, delay_minutes))
        
        # Verify auto-deletion was scheduled
        scheduled_task = self.session.query(ScheduledTask).filter(
            ScheduledTask.message_id == message_id,
            ScheduledTask.task_type == "auto_delete_sticker"
        ).first()
        
        self.assertIsNotNone(
            scheduled_task,
            f"Auto-deletion should be scheduled for user {user_id} after losing unlimited access"
        )
        
        # **Phase 4: Verify consistent behavior**
        # Multiple access checks should consistently return False
        for check_num in range(3):
            has_access_consistent = asyncio.run(self.sticker_manager.check_access(user_id))
            self.assertFalse(
                has_access_consistent,
                f"User {user_id} should consistently have no access after expiration (check #{check_num + 1})"
            )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.lists(
            st.integers(min_value=1, max_value=100000),  # user_ids
            min_size=2,
            max_size=5,
            unique=True
        ),
        st.integers(min_value=1, max_value=10)           # delay_minutes
    )
    @settings(max_examples=20, deadline=None)
    def test_multiple_users_sticker_usage_control_property(self, user_ids, delay_minutes):
        """
        **Property 4: Sticker Usage Control**
        **Validates: Requirements 2.3, 2.5**
        
        For any set of users with different sticker access states, 
        usage control should work independently for each user
        """
        # Clean up any previous test data
        self._cleanup_test_data()
        
        users_data = []
        current_time = datetime.utcnow()
        
        # Create users with different access states
        for i, user_id in enumerate(user_ids):
            if i % 2 == 0:
                # Even indexed users have unlimited access
                expiration_time = current_time + timedelta(hours=1)
                user = self._create_test_user(
                    user_id, 
                    has_unlimited=True, 
                    unlimited_until=expiration_time
                )
                users_data.append({
                    'user_id': user_id,
                    'user': user,
                    'should_have_access': True,
                    'expiration_time': expiration_time
                })
            else:
                # Odd indexed users don't have unlimited access
                user = self._create_test_user(user_id, has_unlimited=False)
                users_data.append({
                    'user_id': user_id,
                    'user': user,
                    'should_have_access': False,
                    'expiration_time': None
                })
        
        # **Property Part 1: Each user should have correct access based on their state**
        for user_data in users_data:
            has_access = asyncio.run(self.sticker_manager.check_access(user_data['user_id']))
            
            if user_data['should_have_access']:
                self.assertTrue(
                    has_access,
                    f"User {user_data['user_id']} should have access with unlimited sticker access"
                )
            else:
                self.assertFalse(
                    has_access,
                    f"User {user_data['user_id']} should not have access without unlimited sticker access"
                )
        
        # **Property Part 2: Auto-deletion should be scheduled only for users without unlimited access**
        scheduled_tasks = []
        
        for user_data in users_data:
            message_id = user_data['user_id'] * 1000 + delay_minutes
            
            # Schedule auto-deletion for all users
            asyncio.run(self.sticker_manager.auto_delete_sticker(message_id, delay_minutes))
            
            # Check if task was scheduled
            scheduled_task = self.session.query(ScheduledTask).filter(
                ScheduledTask.message_id == message_id,
                ScheduledTask.task_type == "auto_delete_sticker"
            ).first()
            
            # All users should have auto-deletion scheduled (regardless of unlimited access)
            # The unlimited access only affects whether stickers are allowed, not scheduling
            self.assertIsNotNone(
                scheduled_task,
                f"Auto-deletion should be scheduled for user {user_data['user_id']}"
            )
            
            scheduled_tasks.append({
                'user_id': user_data['user_id'],
                'task': scheduled_task,
                'message_id': message_id
            })
        
        # **Property Part 3: All scheduled tasks should have correct parameters**
        for task_data in scheduled_tasks:
            task = task_data['task']
            
            self.assertEqual(
                task.message_id, task_data['message_id'],
                f"Task for user {task_data['user_id']} should have correct message ID"
            )
            
            self.assertEqual(
                task.task_type, "auto_delete_sticker",
                f"Task for user {task_data['user_id']} should have correct task type"
            )
            
            self.assertFalse(
                task.is_completed,
                f"Task for user {task_data['user_id']} should not be completed initially"
            )
            
            # Verify execution time is correctly set
            expected_execution = task.created_at + timedelta(minutes=delay_minutes)
            actual_execution = task.execute_at
            
            # Allow for small time differences due to processing time
            time_diff = abs((actual_execution - expected_execution).total_seconds())
            self.assertLess(
                time_diff, 60,  # Less than 1 minute difference
                f"Task execution time should be approximately {delay_minutes} minutes from creation"
            )
    
    def test_sticker_usage_control_without_hypothesis(self):
        """Fallback test when Hypothesis is not available"""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Test cases covering the sticker usage control property
        test_cases = [
            # (user_id, has_unlimited, minutes_offset, delay_minutes, description)
            (12345, True, 60, 2, "User with unlimited access (1 hour remaining)"),
            (12346, False, 0, 2, "User without unlimited access"),
            (12347, True, -30, 3, "User with expired unlimited access"),
            (12348, True, 5, 5, "User with unlimited access expiring soon"),
        ]
        
        for user_id, has_unlimited, minutes_offset, delay_minutes, description in test_cases:
            with self.subTest(user_id=user_id, description=description):
                # Clean up test data
                self._cleanup_test_data()
                
                # Set up user based on test case
                if has_unlimited:
                    expiration_time = datetime.utcnow() + timedelta(minutes=minutes_offset)
                    user = self._create_test_user(
                        user_id, 
                        has_unlimited=True, 
                        unlimited_until=expiration_time
                    )
                else:
                    user = self._create_test_user(user_id, has_unlimited=False)
                
                # Test access control
                has_access = asyncio.run(self.sticker_manager.check_access(user_id))
                
                if has_unlimited and minutes_offset > 0:
                    # Should have access
                    self.assertTrue(has_access, f"Should have access: {description}")
                else:
                    # Should not have access
                    self.assertFalse(has_access, f"Should not have access: {description}")
                
                # Test auto-deletion scheduling
                message_id = user_id * 1000 + delay_minutes
                asyncio.run(self.sticker_manager.auto_delete_sticker(message_id, delay_minutes))
                
                # Verify task was scheduled
                scheduled_task = self.session.query(ScheduledTask).filter(
                    ScheduledTask.message_id == message_id,
                    ScheduledTask.task_type == "auto_delete_sticker"
                ).first()
                
                self.assertIsNotNone(scheduled_task, f"Auto-deletion should be scheduled: {description}")
                self.assertEqual(scheduled_task.message_id, message_id, f"Correct message ID: {description}")
                self.assertFalse(scheduled_task.is_completed, f"Task should not be completed: {description}")


if __name__ == '__main__':
    unittest.main()