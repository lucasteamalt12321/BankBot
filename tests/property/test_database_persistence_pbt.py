"""
Property-based tests for database data persistence.

Tests Properties 21, 22, and 23 from the message-parsing-system design:
- Property 21: Data Persistence Round-Trip
- Property 22: User Name Uniqueness
- Property 23: Bot Balance Composite Key Uniqueness
"""

import pytest
import tempfile
import os
from decimal import Decimal
from hypothesis import given, strategies as st, settings, assume
import sqlite3

from src.repository import SQLiteRepository
from src.models import UserBalance, BotBalance


# Hypothesis strategies for generating test data
@st.composite
def user_balance_strategy(draw):
    """Generate a valid UserBalance for testing."""
    user_name = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
        blacklist_categories=('Cs', 'Cc'),  # Exclude control characters
        min_codepoint=32,
        max_codepoint=1000
    )))
    # Filter out names that are just whitespace
    assume(user_name.strip() != "")
    
    bank_balance = draw(st.decimals(
        min_value=Decimal("-999999.99"),
        max_value=Decimal("999999.99"),
        allow_nan=False,
        allow_infinity=False,
        places=2
    ))
    
    return user_name, bank_balance


@st.composite
def bot_balance_strategy(draw):
    """Generate a valid BotBalance for testing."""
    game = draw(st.sampled_from([
        "GD Cards",
        "Shmalala",
        "Shmalala Karma",
        "True Mafia",
        "Bunker RP"
    ]))
    
    last_balance = draw(st.decimals(
        min_value=Decimal("-999999.99"),
        max_value=Decimal("999999.99"),
        allow_nan=False,
        allow_infinity=False,
        places=2
    ))
    
    current_bot_balance = draw(st.decimals(
        min_value=Decimal("-999999.99"),
        max_value=Decimal("999999.99"),
        allow_nan=False,
        allow_infinity=False,
        places=2
    ))
    
    return game, last_balance, current_bot_balance


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


class TestDataPersistenceRoundTrip:
    """
    Property 21: Data Persistence Round-Trip
    
    For any user_balance or bot_balance record, storing it to the database
    and then retrieving it should return an equivalent record with all fields preserved.
    
    **Validates: Requirements 10.1, 10.2, 10.5**
    """
    
    @given(user_data=user_balance_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_user_balance_round_trip(self, user_data):
        """
        Test that user balance data persists correctly through store and retrieve.
        
        For any user_name and bank_balance, creating a user and retrieving it
        should return the same values.
        """
        user_name, bank_balance = user_data
        
        # Create repository for this test
        repository, db_path = create_temp_repository()
        
        try:
            # Store: Create user with specific balance
            user = repository.get_or_create_user(user_name)
            repository.update_user_balance(user.user_id, bank_balance)
            
            # Retrieve: Get the user back
            retrieved_user = repository.get_or_create_user(user_name)
            
            # Assert: All fields should be preserved
            assert retrieved_user.user_name == user_name, \
                f"User name not preserved: expected {user_name}, got {retrieved_user.user_name}"
            assert retrieved_user.bank_balance == bank_balance, \
                f"Bank balance not preserved: expected {bank_balance}, got {retrieved_user.bank_balance}"
            assert retrieved_user.user_id == user.user_id, \
                f"User ID changed: expected {user.user_id}, got {retrieved_user.user_id}"
        finally:
            cleanup_repository(repository, db_path)
    
    @given(
        user_data=user_balance_strategy(),
        bot_data=bot_balance_strategy()
    )
    @settings(max_examples=100, deadline=5000)
    def test_bot_balance_round_trip(self, user_data, bot_data):
        """
        Test that bot balance data persists correctly through store and retrieve.
        
        For any user, game, last_balance, and current_bot_balance, creating a
        bot balance record and retrieving it should return the same values.
        """
        user_name, _ = user_data
        game, last_balance, current_bot_balance = bot_data
        
        # Create repository for this test
        repository, db_path = create_temp_repository()
        
        try:
            # Store: Create user and bot balance
            user = repository.get_or_create_user(user_name)
            repository.create_bot_balance(
                user_id=user.user_id,
                game=game,
                last_balance=last_balance,
                current_bot_balance=current_bot_balance
            )
            
            # Retrieve: Get the bot balance back
            retrieved_bot_balance = repository.get_bot_balance(user.user_id, game)
            
            # Assert: All fields should be preserved
            assert retrieved_bot_balance is not None, \
                "Bot balance should exist after creation"
            assert retrieved_bot_balance.user_id == user.user_id, \
                f"User ID not preserved: expected {user.user_id}, got {retrieved_bot_balance.user_id}"
            assert retrieved_bot_balance.game == game, \
                f"Game not preserved: expected {game}, got {retrieved_bot_balance.game}"
            assert retrieved_bot_balance.last_balance == last_balance, \
                f"Last balance not preserved: expected {last_balance}, got {retrieved_bot_balance.last_balance}"
            assert retrieved_bot_balance.current_bot_balance == current_bot_balance, \
                f"Current bot balance not preserved: expected {current_bot_balance}, got {retrieved_bot_balance.current_bot_balance}"
        finally:
            cleanup_repository(repository, db_path)
    
    @given(
        user_data=user_balance_strategy(),
        bot_data_list=st.lists(bot_balance_strategy(), min_size=1, max_size=5)
    )
    @settings(max_examples=50, deadline=10000)
    def test_multiple_bot_balances_round_trip(self, user_data, bot_data_list):
        """
        Test that multiple bot balance records for the same user persist correctly.
        
        A user can have bot balances for multiple games, and all should be
        retrievable with correct values.
        """
        user_name, _ = user_data
        
        # Create repository for this test
        repository, db_path = create_temp_repository()
        
        try:
            # Store: Create user and multiple bot balances
            user = repository.get_or_create_user(user_name)
            
            # Use unique games to avoid duplicate key errors
            unique_games = {}
            for game, last_balance, current_bot_balance in bot_data_list:
                if game not in unique_games:
                    unique_games[game] = (last_balance, current_bot_balance)
                    repository.create_bot_balance(
                        user_id=user.user_id,
                        game=game,
                        last_balance=last_balance,
                        current_bot_balance=current_bot_balance
                    )
            
            # Retrieve: Get all bot balances back and verify
            for game, (expected_last, expected_current) in unique_games.items():
                retrieved = repository.get_bot_balance(user.user_id, game)
                
                assert retrieved is not None, \
                    f"Bot balance for game {game} should exist"
                assert retrieved.last_balance == expected_last, \
                    f"Last balance for {game} not preserved"
                assert retrieved.current_bot_balance == expected_current, \
                    f"Current bot balance for {game} not preserved"
        finally:
            cleanup_repository(repository, db_path)


class TestUserNameUniqueness:
    """
    Property 22: User Name Uniqueness
    
    For any two user_balance records with the same user_name, attempting to
    store both should result in a uniqueness constraint error.
    
    **Validates: Requirements 10.3**
    """
    
    @given(
        user_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            min_codepoint=32,
            max_codepoint=1000
        )),
        balance1=st.decimals(min_value=0, max_value=1000, places=2, allow_nan=False, allow_infinity=False),
        balance2=st.decimals(min_value=0, max_value=1000, places=2, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=5000)
    def test_duplicate_user_name_causes_constraint_error(self, user_name, balance1, balance2):
        """
        Test that duplicate user_name values cause a constraint error.
        
        Creating two users with the same user_name should fail on the second attempt.
        """
        assume(user_name.strip() != "")
        assume(balance1 != balance2)  # Make sure we're testing different records
        
        # Create repository for this test
        repository, db_path = create_temp_repository()
        
        try:
            # Create first user
            user1 = repository.get_or_create_user(user_name)
            repository.update_user_balance(user1.user_id, balance1)
            
            # Try to manually insert a duplicate user_name with different user_id
            cursor = repository.conn.cursor()
            
            with pytest.raises(sqlite3.IntegrityError) as exc_info:
                cursor.execute(
                    "INSERT INTO user_balances (user_id, user_name, bank_balance) VALUES (?, ?, ?)",
                    ("different_id_" + user1.user_id, user_name, str(balance2))
                )
                repository.conn.commit()
            
            # Verify the error is about uniqueness
            assert "UNIQUE constraint failed" in str(exc_info.value) or "unique" in str(exc_info.value).lower(), \
                f"Expected UNIQUE constraint error, got: {exc_info.value}"
        finally:
            cleanup_repository(repository, db_path)
    
    @given(
        base_name=st.text(min_size=1, max_size=40, alphabet='abcdefghijklmnopqrstuvwxyz'),
        num_users=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=50, deadline=5000)
    def test_multiple_unique_users_succeed(self, base_name, num_users):
        """
        Test that multiple users with different names can be created successfully.
        
        This is the positive case: unique names should work fine.
        """
        # Create repository for this test
        repository, db_path = create_temp_repository()
        
        try:
            created_users = []
            
            for i in range(num_users):
                user_name = f"{base_name}_{i}"
                user = repository.get_or_create_user(user_name)
                created_users.append(user)
            
            # Verify all users were created with unique IDs
            user_ids = [u.user_id for u in created_users]
            assert len(user_ids) == len(set(user_ids)), \
                "All users should have unique IDs"
            
            # Verify all users can be retrieved
            for i, user in enumerate(created_users):
                user_name = f"{base_name}_{i}"
                retrieved = repository.get_or_create_user(user_name)
                assert retrieved.user_id == user.user_id, \
                    f"Retrieved user should have same ID as created user"
        finally:
            cleanup_repository(repository, db_path)


class TestBotBalanceCompositeKeyUniqueness:
    """
    Property 23: Bot Balance Composite Key Uniqueness
    
    For any two bot_balance records with the same (user_id, game) combination,
    attempting to store both should result in a uniqueness constraint error.
    
    **Validates: Requirements 10.4**
    """
    
    @given(
        user_name=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz'),
        game=st.sampled_from(["GD Cards", "Shmalala", "True Mafia", "Bunker RP"]),
        balance1=st.decimals(min_value=0, max_value=1000, places=2, allow_nan=False, allow_infinity=False),
        balance2=st.decimals(min_value=0, max_value=1000, places=2, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=5000)
    def test_duplicate_user_game_combination_causes_constraint_error(
        self, user_name, game, balance1, balance2
    ):
        """
        Test that duplicate (user_id, game) combinations cause a constraint error.
        
        Creating two bot balance records for the same user and game should fail
        on the second attempt.
        """
        assume(balance1 != balance2)  # Make sure we're testing different records
        
        # Create repository for this test
        repository, db_path = create_temp_repository()
        
        try:
            # Create user and first bot balance
            user = repository.get_or_create_user(user_name)
            repository.create_bot_balance(
                user_id=user.user_id,
                game=game,
                last_balance=balance1,
                current_bot_balance=Decimal("0")
            )
            
            # Try to create duplicate bot balance for same user and game
            with pytest.raises(sqlite3.IntegrityError) as exc_info:
                repository.create_bot_balance(
                    user_id=user.user_id,
                    game=game,
                    last_balance=balance2,
                    current_bot_balance=Decimal("0")
                )
            
            # Verify the error is about uniqueness/primary key
            error_msg = str(exc_info.value).lower()
            assert "unique" in error_msg or "primary key" in error_msg, \
                f"Expected UNIQUE/PRIMARY KEY constraint error, got: {exc_info.value}"
        finally:
            cleanup_repository(repository, db_path)
    
    @given(
        user_name=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz'),
        games=st.lists(
            st.sampled_from(["GD Cards", "Shmalala", "Shmalala Karma", "True Mafia", "Bunker RP"]),
            min_size=2,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=50, deadline=5000)
    def test_same_user_different_games_succeed(self, user_name, games):
        """
        Test that the same user can have bot balances for different games.
        
        This is the positive case: same user_id with different games should work fine.
        """
        # Create repository for this test
        repository, db_path = create_temp_repository()
        
        try:
            user = repository.get_or_create_user(user_name)
            
            # Create bot balances for different games
            for i, game in enumerate(games):
                balance = Decimal(str(10 * (i + 1)))
                repository.create_bot_balance(
                    user_id=user.user_id,
                    game=game,
                    last_balance=balance,
                    current_bot_balance=Decimal("0")
                )
            
            # Verify all bot balances were created and can be retrieved
            for i, game in enumerate(games):
                expected_balance = Decimal(str(10 * (i + 1)))
                retrieved = repository.get_bot_balance(user.user_id, game)
                
                assert retrieved is not None, \
                    f"Bot balance for game {game} should exist"
                assert retrieved.last_balance == expected_balance, \
                    f"Last balance for {game} should be {expected_balance}"
        finally:
            cleanup_repository(repository, db_path)
    
    @given(
        user_names=st.lists(
            st.text(min_size=1, max_size=30, alphabet='abcdefghijklmnopqrstuvwxyz'),
            min_size=2,
            max_size=5,
            unique=True
        ),
        game=st.sampled_from(["GD Cards", "Shmalala", "True Mafia"])
    )
    @settings(max_examples=50, deadline=5000)
    def test_different_users_same_game_succeed(self, user_names, game):
        """
        Test that different users can have bot balances for the same game.
        
        This is the positive case: different user_ids with same game should work fine.
        """
        # Create repository for this test
        repository, db_path = create_temp_repository()
        
        try:
            # Create bot balances for different users with same game
            for i, user_name in enumerate(user_names):
                user = repository.get_or_create_user(user_name)
                balance = Decimal(str(100 * (i + 1)))
                repository.create_bot_balance(
                    user_id=user.user_id,
                    game=game,
                    last_balance=balance,
                    current_bot_balance=Decimal("0")
                )
            
            # Verify all bot balances were created correctly
            for i, user_name in enumerate(user_names):
                user = repository.get_or_create_user(user_name)
                expected_balance = Decimal(str(100 * (i + 1)))
                retrieved = repository.get_bot_balance(user.user_id, game)
                
                assert retrieved is not None, \
                    f"Bot balance for user {user_name} should exist"
                assert retrieved.last_balance == expected_balance, \
                    f"Last balance for user {user_name} should be {expected_balance}"
        finally:
            cleanup_repository(repository, db_path)
