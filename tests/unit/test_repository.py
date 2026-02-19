"""Unit tests for SQLiteRepository implementation."""

import pytest
import tempfile
import os
from decimal import Decimal

from src.repository import SQLiteRepository
from src.models import UserBalance, BotBalance


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        try:
            os.remove(path)
        except PermissionError:
            # On Windows, file might still be locked
            pass


@pytest.fixture
def repository(temp_db):
    """Create a SQLiteRepository instance with temporary database."""
    repo = SQLiteRepository(temp_db)
    yield repo
    # Close connection before cleanup
    repo.conn.close()


class TestSQLiteRepositoryInitialization:
    """Test repository initialization and schema creation."""
    
    def test_init_creates_database_file(self, temp_db):
        """Test that initialization creates the database file."""
        repo = SQLiteRepository(temp_db)
        assert os.path.exists(temp_db)
        repo.conn.close()
    
    def test_init_creates_user_balances_table(self, repository):
        """Test that user_balances table is created."""
        cursor = repository.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_balances'"
        )
        assert cursor.fetchone() is not None
    
    def test_init_creates_bot_balances_table(self, repository):
        """Test that bot_balances table is created."""
        cursor = repository.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='bot_balances'"
        )
        assert cursor.fetchone() is not None
    
    def test_init_creates_processed_messages_table(self, repository):
        """Test that processed_messages table is created."""
        cursor = repository.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_messages'"
        )
        assert cursor.fetchone() is not None
    
    def test_processed_messages_index_exists(self, repository):
        """Test that index on processed_at exists."""
        cursor = repository.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_processed_messages_timestamp'"
        )
        assert cursor.fetchone() is not None
    
    def test_user_balances_schema(self, repository):
        """Test that user_balances table has correct columns."""
        cursor = repository.conn.cursor()
        cursor.execute("PRAGMA table_info(user_balances)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        assert 'user_id' in columns
        assert 'user_name' in columns
        assert 'bank_balance' in columns
        assert columns['user_id'] == 'TEXT'
        assert columns['user_name'] == 'TEXT'
        assert columns['bank_balance'] == 'TEXT'
    
    def test_bot_balances_schema(self, repository):
        """Test that bot_balances table has correct columns."""
        cursor = repository.conn.cursor()
        cursor.execute("PRAGMA table_info(bot_balances)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        assert 'user_id' in columns
        assert 'game' in columns
        assert 'last_balance' in columns
        assert 'current_bot_balance' in columns
        assert columns['user_id'] == 'TEXT'
        assert columns['game'] == 'TEXT'
        assert columns['last_balance'] == 'TEXT'
        assert columns['current_bot_balance'] == 'TEXT'


class TestUserOperations:
    """Test user balance operations."""
    
    def test_get_or_create_user_creates_new_user(self, repository):
        """Test creating a new user with zero balance."""
        user = repository.get_or_create_user("TestPlayer")
        
        assert user.user_name == "TestPlayer"
        assert user.bank_balance == Decimal(0)
        assert user.user_id is not None
    
    def test_get_or_create_user_returns_existing_user(self, repository):
        """Test retrieving an existing user."""
        user1 = repository.get_or_create_user("TestPlayer")
        user2 = repository.get_or_create_user("TestPlayer")
        
        assert user1.user_id == user2.user_id
        assert user1.user_name == user2.user_name
        assert user1.bank_balance == user2.bank_balance
    
    def test_update_user_balance(self, repository):
        """Test updating user's bank balance."""
        user = repository.get_or_create_user("TestPlayer")
        new_balance = Decimal("100.50")
        
        repository.update_user_balance(user.user_id, new_balance)
        
        updated_user = repository.get_or_create_user("TestPlayer")
        assert updated_user.bank_balance == new_balance
    
    def test_user_name_uniqueness(self, repository):
        """Test that user_name is unique."""
        user1 = repository.get_or_create_user("TestPlayer")
        
        # Try to manually insert duplicate user_name
        cursor = repository.conn.cursor()
        with pytest.raises(Exception):  # Should raise UNIQUE constraint error
            cursor.execute(
                "INSERT INTO user_balances (user_id, user_name, bank_balance) VALUES (?, ?, ?)",
                ("different_id", "TestPlayer", "0")
            )
            repository.conn.commit()


class TestBotBalanceOperations:
    """Test bot balance operations."""
    
    def test_get_bot_balance_returns_none_when_not_exists(self, repository):
        """Test that get_bot_balance returns None for non-existent record."""
        user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        
        assert bot_balance is None
    
    def test_create_bot_balance(self, repository):
        """Test creating a new bot balance record."""
        user = repository.get_or_create_user("TestPlayer")
        
        repository.create_bot_balance(
            user_id=user.user_id,
            game="GD Cards",
            last_balance=Decimal("100.5"),
            current_bot_balance=Decimal("50.25")
        )
        
        bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        assert bot_balance is not None
        assert bot_balance.user_id == user.user_id
        assert bot_balance.game == "GD Cards"
        assert bot_balance.last_balance == Decimal("100.5")
        assert bot_balance.current_bot_balance == Decimal("50.25")
    
    def test_update_bot_last_balance(self, repository):
        """Test updating last_balance field."""
        user = repository.get_or_create_user("TestPlayer")
        repository.create_bot_balance(
            user_id=user.user_id,
            game="GD Cards",
            last_balance=Decimal("100"),
            current_bot_balance=Decimal("50")
        )
        
        new_last_balance = Decimal("150.75")
        repository.update_bot_last_balance(user.user_id, "GD Cards", new_last_balance)
        
        bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        assert bot_balance.last_balance == new_last_balance
        assert bot_balance.current_bot_balance == Decimal("50")  # Should not change
    
    def test_update_bot_current_balance(self, repository):
        """Test updating current_bot_balance field."""
        user = repository.get_or_create_user("TestPlayer")
        repository.create_bot_balance(
            user_id=user.user_id,
            game="GD Cards",
            last_balance=Decimal("100"),
            current_bot_balance=Decimal("50")
        )
        
        new_current_balance = Decimal("75.5")
        repository.update_bot_current_balance(user.user_id, "GD Cards", new_current_balance)
        
        bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        assert bot_balance.current_bot_balance == new_current_balance
        assert bot_balance.last_balance == Decimal("100")  # Should not change
    
    def test_bot_balance_composite_key_uniqueness(self, repository):
        """Test that (user_id, game) combination is unique."""
        user = repository.get_or_create_user("TestPlayer")
        repository.create_bot_balance(
            user_id=user.user_id,
            game="GD Cards",
            last_balance=Decimal("100"),
            current_bot_balance=Decimal("50")
        )
        
        # Try to create duplicate
        with pytest.raises(Exception):  # Should raise UNIQUE constraint error
            repository.create_bot_balance(
                user_id=user.user_id,
                game="GD Cards",
                last_balance=Decimal("200"),
                current_bot_balance=Decimal("100")
            )
    
    def test_multiple_games_per_user(self, repository):
        """Test that a user can have bot balances for multiple games."""
        user = repository.get_or_create_user("TestPlayer")
        
        repository.create_bot_balance(
            user_id=user.user_id,
            game="GD Cards",
            last_balance=Decimal("100"),
            current_bot_balance=Decimal("50")
        )
        
        repository.create_bot_balance(
            user_id=user.user_id,
            game="True Mafia",
            last_balance=Decimal("200"),
            current_bot_balance=Decimal("75")
        )
        
        gd_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        mafia_balance = repository.get_bot_balance(user.user_id, "True Mafia")
        
        assert gd_balance.last_balance == Decimal("100")
        assert mafia_balance.last_balance == Decimal("200")


class TestDecimalPrecision:
    """Test that Decimal precision is preserved."""
    
    def test_user_balance_decimal_precision(self, repository):
        """Test that user balance preserves decimal precision."""
        user = repository.get_or_create_user("TestPlayer")
        
        # Test with various decimal values
        test_values = [
            Decimal("123.45"),
            Decimal("0.01"),
            Decimal("999999.99"),
            Decimal("0.001"),
        ]
        
        for value in test_values:
            repository.update_user_balance(user.user_id, value)
            updated_user = repository.get_or_create_user("TestPlayer")
            assert updated_user.bank_balance == value
    
    def test_bot_balance_decimal_precision(self, repository):
        """Test that bot balance preserves decimal precision."""
        user = repository.get_or_create_user("TestPlayer")
        
        last_balance = Decimal("123.456")
        current_balance = Decimal("789.012")
        
        repository.create_bot_balance(
            user_id=user.user_id,
            game="GD Cards",
            last_balance=last_balance,
            current_bot_balance=current_balance
        )
        
        bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        assert bot_balance.last_balance == last_balance
        assert bot_balance.current_bot_balance == current_balance


class TestTransactions:
    """Test transaction support."""
    
    def test_begin_transaction(self, repository):
        """Test that begin_transaction works."""
        repository.begin_transaction()
        # Should not raise an error
    
    def test_commit_transaction(self, repository):
        """Test that commit_transaction persists changes."""
        user = repository.get_or_create_user("TestPlayer")
        
        repository.begin_transaction()
        repository.update_user_balance(user.user_id, Decimal("100"))
        repository.commit_transaction()
        
        updated_user = repository.get_or_create_user("TestPlayer")
        assert updated_user.bank_balance == Decimal("100")
    
    def test_rollback_transaction(self, repository):
        """Test that rollback_transaction reverts changes."""
        user = repository.get_or_create_user("TestPlayer")
        initial_balance = user.bank_balance
        
        repository.begin_transaction()
        repository.update_user_balance(user.user_id, Decimal("100"))
        repository.rollback_transaction()
        
        updated_user = repository.get_or_create_user("TestPlayer")
        assert updated_user.bank_balance == initial_balance


class TestIdempotency:
    """Test message idempotency operations."""
    
    def test_message_id_exists_returns_false_for_new_id(self, repository):
        """Test that message_id_exists returns False for unprocessed message."""
        message_id = "test_message_123"
        assert repository.message_id_exists(message_id) is False
    
    def test_store_message_id(self, repository):
        """Test storing a message ID."""
        message_id = "test_message_123"
        repository.store_message_id(message_id)
        
        # Verify it was stored
        cursor = repository.conn.cursor()
        cursor.execute(
            "SELECT message_id FROM processed_messages WHERE message_id = ?",
            (message_id,)
        )
        assert cursor.fetchone() is not None
    
    def test_message_id_exists_returns_true_after_storing(self, repository):
        """Test that message_id_exists returns True after storing."""
        message_id = "test_message_123"
        repository.store_message_id(message_id)
        
        assert repository.message_id_exists(message_id) is True
    
    def test_store_duplicate_message_id_raises_error(self, repository):
        """Test that storing duplicate message ID raises error."""
        message_id = "test_message_123"
        repository.store_message_id(message_id)
        
        with pytest.raises(Exception):  # Should raise UNIQUE constraint error
            repository.store_message_id(message_id)
    
    def test_processed_at_timestamp_is_set(self, repository):
        """Test that processed_at timestamp is automatically set."""
        message_id = "test_message_123"
        repository.store_message_id(message_id)
        
        cursor = repository.conn.cursor()
        cursor.execute(
            "SELECT processed_at FROM processed_messages WHERE message_id = ?",
            (message_id,)
        )
        result = cursor.fetchone()
        assert result is not None
        assert result[0] is not None  # Timestamp should be set


class TestTransactionIsolation:
    """Test transaction isolation and atomicity."""
    
    def test_multiple_operations_in_transaction(self, repository):
        """Test that multiple operations in a transaction are atomic."""
        user = repository.get_or_create_user("TestPlayer")
        
        repository.begin_transaction()
        repository.update_user_balance(user.user_id, Decimal("100"))
        repository.create_bot_balance(
            user_id=user.user_id,
            game="GD Cards",
            last_balance=Decimal("50"),
            current_bot_balance=Decimal("25")
        )
        repository.commit_transaction()
        
        # Verify both operations succeeded
        updated_user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        
        assert updated_user.bank_balance == Decimal("100")
        assert bot_balance is not None
        assert bot_balance.last_balance == Decimal("50")
    
    def test_rollback_reverts_all_operations(self, repository):
        """Test that rollback reverts all operations in a transaction."""
        user = repository.get_or_create_user("TestPlayer")
        initial_balance = user.bank_balance
        
        repository.begin_transaction()
        repository.update_user_balance(user.user_id, Decimal("100"))
        repository.create_bot_balance(
            user_id=user.user_id,
            game="GD Cards",
            last_balance=Decimal("50"),
            current_bot_balance=Decimal("25")
        )
        repository.rollback_transaction()
        
        # Verify both operations were rolled back
        updated_user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        
        assert updated_user.bank_balance == initial_balance
        assert bot_balance is None
    
    def test_transaction_with_message_id_storage(self, repository):
        """Test that message ID storage works within transactions."""
        message_id = "test_message_123"
        
        repository.begin_transaction()
        repository.store_message_id(message_id)
        repository.commit_transaction()
        
        assert repository.message_id_exists(message_id) is True
    
    def test_rollback_message_id_storage(self, repository):
        """Test that message ID storage is rolled back on transaction rollback."""
        message_id = "test_message_123"
        
        repository.begin_transaction()
        repository.store_message_id(message_id)
        repository.rollback_transaction()
        
        assert repository.message_id_exists(message_id) is False


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_user_with_special_characters(self, repository):
        """Test creating user with special characters in name."""
        special_names = [
            "Player@123",
            "Player_Test",
            "Игрок",  # Cyrillic
            "Player-Name",
            "Player.Name"
        ]
        
        for name in special_names:
            user = repository.get_or_create_user(name)
            assert user.user_name == name
            assert user.bank_balance == Decimal(0)
    
    def test_negative_balance(self, repository):
        """Test that negative balances can be stored."""
        user = repository.get_or_create_user("TestPlayer")
        
        negative_balance = Decimal("-50.25")
        repository.update_user_balance(user.user_id, negative_balance)
        
        updated_user = repository.get_or_create_user("TestPlayer")
        assert updated_user.bank_balance == negative_balance
    
    def test_zero_balance(self, repository):
        """Test that zero balance is handled correctly."""
        user = repository.get_or_create_user("TestPlayer")
        
        repository.update_user_balance(user.user_id, Decimal("100"))
        repository.update_user_balance(user.user_id, Decimal("0"))
        
        updated_user = repository.get_or_create_user("TestPlayer")
        assert updated_user.bank_balance == Decimal("0")
    
    def test_very_large_balance(self, repository):
        """Test that very large balances are handled correctly."""
        user = repository.get_or_create_user("TestPlayer")
        
        large_balance = Decimal("999999999999.99")
        repository.update_user_balance(user.user_id, large_balance)
        
        updated_user = repository.get_or_create_user("TestPlayer")
        assert updated_user.bank_balance == large_balance
    
    def test_very_small_decimal(self, repository):
        """Test that very small decimal values are preserved."""
        user = repository.get_or_create_user("TestPlayer")
        
        small_balance = Decimal("0.0001")
        repository.update_user_balance(user.user_id, small_balance)
        
        updated_user = repository.get_or_create_user("TestPlayer")
        assert updated_user.bank_balance == small_balance
    
    def test_bot_balance_with_negative_values(self, repository):
        """Test that bot balance can store negative values."""
        user = repository.get_or_create_user("TestPlayer")
        
        repository.create_bot_balance(
            user_id=user.user_id,
            game="GD Cards",
            last_balance=Decimal("-10.5"),
            current_bot_balance=Decimal("-5.25")
        )
        
        bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        assert bot_balance.last_balance == Decimal("-10.5")
        assert bot_balance.current_bot_balance == Decimal("-5.25")
    
    def test_game_name_with_special_characters(self, repository):
        """Test that game names with special characters work."""
        user = repository.get_or_create_user("TestPlayer")
        
        game_names = [
            "GD Cards",
            "True Mafia",
            "Bunker RP",
            "Shmalala Karma",
            "Game-Name_123"
        ]
        
        for game in game_names:
            repository.create_bot_balance(
                user_id=user.user_id,
                game=game,
                last_balance=Decimal("10"),
                current_bot_balance=Decimal("5")
            )
            
            bot_balance = repository.get_bot_balance(user.user_id, game)
            assert bot_balance is not None
            assert bot_balance.game == game
    
    def test_long_message_id(self, repository):
        """Test that long message IDs (like SHA-256 hashes) work."""
        # SHA-256 hash is 64 characters
        message_id = "a" * 64
        repository.store_message_id(message_id)
        
        assert repository.message_id_exists(message_id) is True
    
    def test_message_id_with_special_characters(self, repository):
        """Test that message IDs with special characters work."""
        message_ids = [
            "message-123",
            "message_456",
            "message.789",
            "abc123def456"
        ]
        
        for msg_id in message_ids:
            repository.store_message_id(msg_id)
            assert repository.message_id_exists(msg_id) is True


class TestConcurrentOperations:
    """Test behavior with multiple users and games."""
    
    def test_multiple_users_independent(self, repository):
        """Test that multiple users are independent."""
        user1 = repository.get_or_create_user("Player1")
        user2 = repository.get_or_create_user("Player2")
        
        repository.update_user_balance(user1.user_id, Decimal("100"))
        repository.update_user_balance(user2.user_id, Decimal("200"))
        
        updated_user1 = repository.get_or_create_user("Player1")
        updated_user2 = repository.get_or_create_user("Player2")
        
        assert updated_user1.bank_balance == Decimal("100")
        assert updated_user2.bank_balance == Decimal("200")
    
    def test_same_game_different_users(self, repository):
        """Test that same game can have different balances for different users."""
        user1 = repository.get_or_create_user("Player1")
        user2 = repository.get_or_create_user("Player2")
        
        repository.create_bot_balance(
            user_id=user1.user_id,
            game="GD Cards",
            last_balance=Decimal("100"),
            current_bot_balance=Decimal("50")
        )
        
        repository.create_bot_balance(
            user_id=user2.user_id,
            game="GD Cards",
            last_balance=Decimal("200"),
            current_bot_balance=Decimal("75")
        )
        
        balance1 = repository.get_bot_balance(user1.user_id, "GD Cards")
        balance2 = repository.get_bot_balance(user2.user_id, "GD Cards")
        
        assert balance1.last_balance == Decimal("100")
        assert balance2.last_balance == Decimal("200")
    
    def test_multiple_message_ids(self, repository):
        """Test storing and checking multiple message IDs."""
        message_ids = [f"message_{i}" for i in range(10)]
        
        for msg_id in message_ids:
            repository.store_message_id(msg_id)
        
        for msg_id in message_ids:
            assert repository.message_id_exists(msg_id) is True
        
        # Check that non-existent ID returns False
        assert repository.message_id_exists("non_existent") is False

