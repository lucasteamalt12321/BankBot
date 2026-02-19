"""
Property-based tests for transaction atomicity.

Tests Property 20 from the message-parsing-system design:
- Property 20: Transaction Atomicity
"""

import pytest
import tempfile
import os
from decimal import Decimal
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch
import sqlite3

from src.repository import SQLiteRepository
from src.balance_manager import BalanceManager
from src.coefficient_provider import CoefficientProvider
from src.parsers import ParsedAccrual, ParsedProfile
from src.audit_logger import AuditLogger


def create_temp_repository():
    """Create a temporary repository for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    repo = SQLiteRepository(path)
    return repo, path


def cleanup_repository(repo, path):
    """Clean up repository and database file."""
    try:
        repo.conn.close()
    except:
        pass
    try:
        if os.path.exists(path):
            os.remove(path)
    except:
        pass


def create_balance_manager(repository):
    """Create a balance manager with test dependencies."""
    coefficients = {
        "GD Cards": 2,
        "Shmalala": 1,
        "Shmalala Karma": 10,
        "True Mafia": 15,
        "Bunker RP": 20
    }
    coefficient_provider = CoefficientProvider(coefficients)
    
    # Create a mock logger
    logger = Mock(spec=AuditLogger)
    
    return BalanceManager(repository, coefficient_provider, logger)


@st.composite
def user_and_accrual_strategy(draw):
    """Generate a user name and accrual data for testing."""
    user_name = draw(st.text(
        min_size=1,
        max_size=30,
        alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            min_codepoint=32,
            max_codepoint=1000
        )
    ))
    # Filter out names that are just whitespace
    from hypothesis import assume
    assume(user_name.strip() != "")
    
    points = draw(st.decimals(
        min_value=Decimal("1"),
        max_value=Decimal("1000"),
        allow_nan=False,
        allow_infinity=False,
        places=2
    ))
    
    return user_name, points


class TestTransactionAtomicity:
    """
    Property 20: Transaction Atomicity
    
    For any balance update operation, if any part of the update fails
    (e.g., database error), then all changes should be rolled back and
    no partial updates should be visible in the database.
    
    **Validates: Requirements 9.1, 9.2, 9.3, 12.3**
    """
    
    @given(user_data=user_and_accrual_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_accrual_rollback_on_bank_balance_update_failure(self, user_data):
        """
        Test that if bank balance update fails during accrual processing,
        all changes (including bot balance creation) are rolled back.
        
        Scenario: Process an accrual message, but simulate a failure when
        updating the bank balance. The bot balance should not be created.
        """
        user_name, points = user_data
        
        # Create repository
        repository, db_path = create_temp_repository()
        
        try:
            # Create balance manager
            balance_manager = create_balance_manager(repository)
            
            # Create parsed accrual
            parsed = ParsedAccrual(
                player_name=user_name,
                points=points,
                game="GD Cards"
            )
            
            # Get initial state
            user = repository.get_or_create_user(user_name)
            initial_bank_balance = user.bank_balance
            initial_bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
            
            # Begin transaction
            repository.begin_transaction()
            
            try:
                # Process accrual partially - create bot balance
                bot_balance_exists_before = repository.get_bot_balance(user.user_id, "GD Cards")
                if bot_balance_exists_before is None:
                    repository.create_bot_balance(
                        user_id=user.user_id,
                        game="GD Cards",
                        last_balance=Decimal(0),
                        current_bot_balance=points
                    )
                
                # Simulate failure by raising an exception
                raise sqlite3.OperationalError("Simulated database error")
                
            except sqlite3.OperationalError:
                # Rollback on error
                repository.rollback_transaction()
            
            # Verify rollback: Check that no changes persisted
            user_after = repository.get_or_create_user(user_name)
            bot_balance_after = repository.get_bot_balance(user.user_id, "GD Cards")
            
            # Bank balance should be unchanged
            assert user_after.bank_balance == initial_bank_balance, \
                f"Bank balance should be rolled back to {initial_bank_balance}, got {user_after.bank_balance}"
            
            # Bot balance should be unchanged (None if it didn't exist before)
            if initial_bot_balance is None:
                assert bot_balance_after is None, \
                    "Bot balance should not exist after rollback"
            else:
                assert bot_balance_after.current_bot_balance == initial_bot_balance.current_bot_balance, \
                    "Bot balance should be rolled back to initial value"
        
        finally:
            cleanup_repository(repository, db_path)
    
    @given(user_data=user_and_accrual_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_profile_rollback_on_last_balance_update_failure(self, user_data):
        """
        Test that if last_balance update fails during profile processing,
        all changes (including bank balance update) are rolled back.
        
        Scenario: Process a profile update with a delta, but simulate a failure
        when updating last_balance. The bank balance should not be updated.
        """
        user_name, initial_orbs = user_data
        
        # Create repository
        repository, db_path = create_temp_repository()
        
        try:
            # Create balance manager
            balance_manager = create_balance_manager(repository)
            
            # Initialize user with first profile
            user = repository.get_or_create_user(user_name)
            repository.create_bot_balance(
                user_id=user.user_id,
                game="GD Cards",
                last_balance=initial_orbs,
                current_bot_balance=Decimal(0)
            )
            
            # Get initial state
            initial_bank_balance = user.bank_balance
            initial_bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
            
            # Create a profile with increased orbs
            new_orbs = initial_orbs + Decimal("50")
            
            # Begin transaction
            repository.begin_transaction()
            
            try:
                # Calculate delta and update bank balance
                delta = new_orbs - initial_orbs
                coefficient = 2  # GD Cards coefficient
                bank_change = delta * coefficient
                new_bank_balance = initial_bank_balance + bank_change
                
                # Update bank balance
                repository.update_user_balance(user.user_id, new_bank_balance)
                
                # Simulate failure before updating last_balance
                raise sqlite3.OperationalError("Simulated database error")
                
            except sqlite3.OperationalError:
                # Rollback on error
                repository.rollback_transaction()
            
            # Verify rollback: Check that no changes persisted
            user_after = repository.get_or_create_user(user_name)
            bot_balance_after = repository.get_bot_balance(user.user_id, "GD Cards")
            
            # Bank balance should be unchanged
            assert user_after.bank_balance == initial_bank_balance, \
                f"Bank balance should be rolled back to {initial_bank_balance}, got {user_after.bank_balance}"
            
            # Last balance should be unchanged
            assert bot_balance_after.last_balance == initial_bot_balance.last_balance, \
                f"Last balance should be rolled back to {initial_bot_balance.last_balance}, got {bot_balance_after.last_balance}"
        
        finally:
            cleanup_repository(repository, db_path)
    
    @given(
        user_name=st.text(
            min_size=1,
            max_size=30,
            alphabet='abcdefghijklmnopqrstuvwxyz'
        ),
        num_operations=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=100, deadline=5000)
    def test_multiple_operations_rollback_together(self, user_name, num_operations):
        """
        Test that multiple balance operations in a single transaction
        are all rolled back together if any operation fails.
        
        Scenario: Perform multiple balance updates in a transaction,
        then simulate a failure. All updates should be rolled back.
        """
        # Create repository
        repository, db_path = create_temp_repository()
        
        try:
            # Create user
            user = repository.get_or_create_user(user_name)
            initial_bank_balance = user.bank_balance
            
            # Begin transaction
            repository.begin_transaction()
            
            try:
                # Perform multiple balance updates
                for i in range(num_operations):
                    amount = Decimal(str(10 * (i + 1)))
                    new_balance = user.bank_balance + amount
                    repository.update_user_balance(user.user_id, new_balance)
                    # Re-fetch user to get updated balance for next iteration
                    user = repository.get_or_create_user(user_name)
                
                # Simulate failure after all operations
                raise sqlite3.OperationalError("Simulated database error")
                
            except sqlite3.OperationalError:
                # Rollback on error
                repository.rollback_transaction()
            
            # Verify rollback: Bank balance should be unchanged
            user_after = repository.get_or_create_user(user_name)
            assert user_after.bank_balance == initial_bank_balance, \
                f"All operations should be rolled back. Expected {initial_bank_balance}, got {user_after.bank_balance}"
        
        finally:
            cleanup_repository(repository, db_path)
    
    @given(user_data=user_and_accrual_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_successful_transaction_commits_all_changes(self, user_data):
        """
        Test that when a transaction completes successfully without errors,
        all changes are committed and visible in the database.
        
        This is the positive case: verify that atomicity works both ways.
        """
        user_name, points = user_data
        
        # Create repository
        repository, db_path = create_temp_repository()
        
        try:
            # Create balance manager
            balance_manager = create_balance_manager(repository)
            
            # Create parsed accrual
            parsed = ParsedAccrual(
                player_name=user_name,
                points=points,
                game="GD Cards"
            )
            
            # Get initial state
            user = repository.get_or_create_user(user_name)
            initial_bank_balance = user.bank_balance
            
            # Begin transaction
            repository.begin_transaction()
            
            try:
                # Process accrual completely
                bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
                
                if bot_balance is None:
                    repository.create_bot_balance(
                        user_id=user.user_id,
                        game="GD Cards",
                        last_balance=Decimal(0),
                        current_bot_balance=points
                    )
                else:
                    new_bot_balance = bot_balance.current_bot_balance + points
                    repository.update_bot_current_balance(
                        user.user_id,
                        "GD Cards",
                        new_bot_balance
                    )
                
                # Update bank balance
                coefficient = 2  # GD Cards coefficient
                bank_change = points * coefficient
                new_bank_balance = initial_bank_balance + bank_change
                repository.update_user_balance(user.user_id, new_bank_balance)
                
                # Commit transaction
                repository.commit_transaction()
                
            except Exception as e:
                repository.rollback_transaction()
                raise
            
            # Verify commit: All changes should be visible
            user_after = repository.get_or_create_user(user_name)
            bot_balance_after = repository.get_bot_balance(user.user_id, "GD Cards")
            
            # Bank balance should be updated
            expected_bank_balance = initial_bank_balance + (points * 2)
            assert user_after.bank_balance == expected_bank_balance, \
                f"Bank balance should be updated to {expected_bank_balance}, got {user_after.bank_balance}"
            
            # Bot balance should be created/updated
            assert bot_balance_after is not None, \
                "Bot balance should exist after commit"
            assert bot_balance_after.current_bot_balance == points, \
                f"Bot balance should be {points}, got {bot_balance_after.current_bot_balance}"
        
        finally:
            cleanup_repository(repository, db_path)
    
    @given(user_data=user_and_accrual_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_no_partial_updates_visible_during_rollback(self, user_data):
        """
        Test that during a rollback, no partial updates are visible
        when querying the database.
        
        This verifies that the transaction isolation works correctly.
        """
        user_name, points = user_data
        
        # Create repository
        repository, db_path = create_temp_repository()
        
        try:
            # Create user
            user = repository.get_or_create_user(user_name)
            initial_bank_balance = user.bank_balance
            
            # Begin transaction
            repository.begin_transaction()
            
            try:
                # Create bot balance
                repository.create_bot_balance(
                    user_id=user.user_id,
                    game="GD Cards",
                    last_balance=Decimal(0),
                    current_bot_balance=points
                )
                
                # Update bank balance
                new_bank_balance = initial_bank_balance + points * 2
                repository.update_user_balance(user.user_id, new_bank_balance)
                
                # Before committing, simulate a failure
                raise sqlite3.OperationalError("Simulated database error")
                
            except sqlite3.OperationalError:
                # Rollback
                repository.rollback_transaction()
            
            # Open a new connection to verify no partial updates are visible
            new_conn = sqlite3.connect(db_path)
            cursor = new_conn.cursor()
            
            # Check user balance
            cursor.execute(
                "SELECT bank_balance FROM user_balances WHERE user_name = ?",
                (user_name,)
            )
            row = cursor.fetchone()
            if row:
                actual_balance = Decimal(row[0])
                assert actual_balance == initial_bank_balance, \
                    f"No partial bank balance update should be visible. Expected {initial_bank_balance}, got {actual_balance}"
            
            # Check bot balance
            cursor.execute(
                "SELECT current_bot_balance FROM bot_balances WHERE user_id = ? AND game = ?",
                (user.user_id, "GD Cards")
            )
            row = cursor.fetchone()
            assert row is None, \
                "No partial bot balance should be visible after rollback"
            
            new_conn.close()
        
        finally:
            cleanup_repository(repository, db_path)
