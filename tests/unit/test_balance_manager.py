"""Unit tests for BalanceManager.process_profile() method."""

import pytest
from decimal import Decimal
from unittest.mock import Mock

from src.balance_manager import BalanceManager
from src.repository import SQLiteRepository
from src.coefficient_provider import CoefficientProvider
from src.parsers import ParsedProfile


@pytest.fixture
def test_db_path(tmp_path):
    """Create a temporary database path."""
    return str(tmp_path / "test.db")


@pytest.fixture
def repository(test_db_path):
    """Create a SQLite repository for testing."""
    return SQLiteRepository(test_db_path)


@pytest.fixture
def coefficient_provider():
    """Create a coefficient provider with test coefficients."""
    return CoefficientProvider({
        "GD Cards": 2,
        "Shmalala": 1,
        "Shmalala Karma": 10,
        "True Mafia": 15,
        "Bunker RP": 20
    })


@pytest.fixture
def mock_logger():
    """Create a mock audit logger."""
    logger = Mock()
    logger.log_profile_init = Mock()
    logger.log_profile_update = Mock()
    return logger


@pytest.fixture
def balance_manager(repository, coefficient_provider, mock_logger):
    """Create a balance manager for testing."""
    return BalanceManager(repository, coefficient_provider, mock_logger)


class TestProcessProfileFirstTime:
    """Tests for first-time profile processing (initialization)."""
    
    def test_first_profile_creates_bot_balance(self, balance_manager, repository, mock_logger):
        """Test that first profile creates bot_balance with correct values."""
        # Arrange
        parsed = ParsedProfile(player_name="TestPlayer", orbs=Decimal("100.5"), game="GD Cards")
        
        # Act
        balance_manager.process_profile(parsed)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        
        assert bot_balance is not None
        assert bot_balance.last_balance == Decimal("100.5")
        assert bot_balance.current_bot_balance == Decimal("0")
        assert bot_balance.game == "GD Cards"
    
    def test_first_profile_does_not_modify_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that first profile does NOT modify bank_balance."""
        # Arrange
        parsed = ParsedProfile(player_name="TestPlayer", orbs=Decimal("100.5"), game="GD Cards")
        
        # Act
        balance_manager.process_profile(parsed)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        assert user.bank_balance == Decimal("0")
    
    def test_first_profile_logs_initialization(self, balance_manager, repository, mock_logger):
        """Test that first profile logs initialization."""
        # Arrange
        parsed = ParsedProfile(player_name="TestPlayer", orbs=Decimal("100.5"), game="GD Cards")
        
        # Act
        balance_manager.process_profile(parsed)
        
        # Assert
        mock_logger.log_profile_init.assert_called_once_with(
            "TestPlayer", "GD Cards", Decimal("100.5")
        )


class TestProcessProfileSubsequent:
    """Tests for subsequent profile processing (delta calculation)."""
    
    def test_positive_delta_increases_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that positive delta increases bank_balance by delta * coefficient."""
        # Arrange
        parsed_first = ParsedProfile(player_name="TestPlayer", orbs=Decimal("100"), game="GD Cards")
        balance_manager.process_profile(parsed_first)
        
        # Act - second profile with higher orbs
        parsed_second = ParsedProfile(player_name="TestPlayer", orbs=Decimal("150"), game="GD Cards")
        balance_manager.process_profile(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # Delta = 150 - 100 = 50, coefficient = 2, bank_change = 50 * 2 = 100
        assert user.bank_balance == Decimal("100")
    
    def test_negative_delta_decreases_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that negative delta decreases bank_balance by |delta| * coefficient."""
        # Arrange
        parsed_first = ParsedProfile(player_name="TestPlayer", orbs=Decimal("100"), game="GD Cards")
        balance_manager.process_profile(parsed_first)
        
        # Act - second profile with lower orbs
        parsed_second = ParsedProfile(player_name="TestPlayer", orbs=Decimal("60"), game="GD Cards")
        balance_manager.process_profile(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # Delta = 60 - 100 = -40, coefficient = 2, bank_change = -40 * 2 = -80
        assert user.bank_balance == Decimal("-80")
    
    def test_zero_delta_does_not_modify_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that zero delta does NOT modify bank_balance."""
        # Arrange
        parsed_first = ParsedProfile(player_name="TestPlayer", orbs=Decimal("100"), game="GD Cards")
        balance_manager.process_profile(parsed_first)
        
        # Act - second profile with same orbs
        parsed_second = ParsedProfile(player_name="TestPlayer", orbs=Decimal("100"), game="GD Cards")
        balance_manager.process_profile(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        assert user.bank_balance == Decimal("0")
        # log_profile_update should not be called for zero delta
        mock_logger.log_profile_update.assert_not_called()
    
    def test_updates_last_balance(self, balance_manager, repository, mock_logger):
        """Test that last_balance is updated to current orbs value."""
        # Arrange
        parsed_first = ParsedProfile(player_name="TestPlayer", orbs=Decimal("100"), game="GD Cards")
        balance_manager.process_profile(parsed_first)
        
        # Act
        parsed_second = ParsedProfile(player_name="TestPlayer", orbs=Decimal("150"), game="GD Cards")
        balance_manager.process_profile(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        assert bot_balance.last_balance == Decimal("150")
    
    def test_logs_profile_update(self, balance_manager, repository, mock_logger):
        """Test that profile update is logged with all details."""
        # Arrange
        parsed_first = ParsedProfile(player_name="TestPlayer", orbs=Decimal("100"), game="GD Cards")
        balance_manager.process_profile(parsed_first)
        mock_logger.reset_mock()
        
        # Act
        parsed_second = ParsedProfile(player_name="TestPlayer", orbs=Decimal("150"), game="GD Cards")
        balance_manager.process_profile(parsed_second)
        
        # Assert
        mock_logger.log_profile_update.assert_called_once_with(
            "TestPlayer",
            "GD Cards",
            Decimal("100"),  # old_balance
            Decimal("150"),  # new_balance
            Decimal("50"),   # delta
            Decimal("100"),  # bank_change (50 * 2)
            2                # coefficient
        )


class TestProcessProfileWithDifferentGames:
    """Tests for profile processing with different games and coefficients."""
    
    def test_different_coefficient_applied(self, balance_manager, repository, mock_logger):
        """Test that different game coefficients are applied correctly."""
        # Arrange - True Mafia has coefficient 15
        parsed_first = ParsedProfile(player_name="TestPlayer", orbs=Decimal("100"), game="True Mafia")
        balance_manager.process_profile(parsed_first)
        
        # Act
        parsed_second = ParsedProfile(player_name="TestPlayer", orbs=Decimal("110"), game="True Mafia")
        balance_manager.process_profile(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # Delta = 10, coefficient = 15, bank_change = 10 * 15 = 150
        assert user.bank_balance == Decimal("150")
    
    def test_multiple_games_tracked_separately(self, balance_manager, repository, mock_logger):
        """Test that different games are tracked separately for the same user."""
        # Arrange
        parsed_gd = ParsedProfile(player_name="TestPlayer", orbs=Decimal("100"), game="GD Cards")
        parsed_mafia = ParsedProfile(player_name="TestPlayer", orbs=Decimal("50"), game="True Mafia")
        
        # Act
        balance_manager.process_profile(parsed_gd)
        balance_manager.process_profile(parsed_mafia)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        bot_balance_gd = repository.get_bot_balance(user.user_id, "GD Cards")
        bot_balance_mafia = repository.get_bot_balance(user.user_id, "True Mafia")
        
        assert bot_balance_gd.last_balance == Decimal("100")
        assert bot_balance_mafia.last_balance == Decimal("50")
        # Bank balance should still be 0 (both are first-time profiles)
        assert user.bank_balance == Decimal("0")


class TestProcessProfileDecimalPrecision:
    """Tests for decimal precision handling."""
    
    def test_decimal_precision_preserved(self, balance_manager, repository, mock_logger):
        """Test that decimal precision is preserved in calculations."""
        # Arrange
        parsed_first = ParsedProfile(player_name="TestPlayer", orbs=Decimal("100.25"), game="GD Cards")
        balance_manager.process_profile(parsed_first)
        
        # Act
        parsed_second = ParsedProfile(player_name="TestPlayer", orbs=Decimal("150.75"), game="GD Cards")
        balance_manager.process_profile(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # Delta = 150.75 - 100.25 = 50.5, coefficient = 2, bank_change = 50.5 * 2 = 101
        assert user.bank_balance == Decimal("101")



class TestProcessAccrualFirstTime:
    """Tests for first-time accrual processing (initialization)."""
    
    def test_first_accrual_creates_bot_balance(self, balance_manager, repository, mock_logger):
        """Test that first accrual creates bot_balance with correct values."""
        # Arrange
        from src.parsers import ParsedAccrual
        parsed = ParsedAccrual(player_name="TestPlayer", points=Decimal("50"), game="GD Cards")
        
        # Act
        balance_manager.process_accrual(parsed)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        
        assert bot_balance is not None
        assert bot_balance.last_balance == Decimal("0")
        assert bot_balance.current_bot_balance == Decimal("50")
        assert bot_balance.game == "GD Cards"
    
    def test_first_accrual_updates_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that first accrual updates bank_balance with coefficient."""
        # Arrange
        from src.parsers import ParsedAccrual
        parsed = ParsedAccrual(player_name="TestPlayer", points=Decimal("50"), game="GD Cards")
        
        # Act
        balance_manager.process_accrual(parsed)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # Points = 50, coefficient = 2, bank_change = 50 * 2 = 100
        assert user.bank_balance == Decimal("100")
    
    def test_first_accrual_logs_accrual(self, balance_manager, repository, mock_logger):
        """Test that first accrual logs the operation."""
        # Arrange
        from src.parsers import ParsedAccrual
        parsed = ParsedAccrual(player_name="TestPlayer", points=Decimal("50"), game="GD Cards")
        
        # Act
        balance_manager.process_accrual(parsed)
        
        # Assert
        mock_logger.log_accrual.assert_called_once_with(
            "TestPlayer",
            "GD Cards",
            Decimal("50"),
            Decimal("100"),  # bank_change (50 * 2)
            2                # coefficient
        )


class TestProcessAccrualSubsequent:
    """Tests for subsequent accrual processing (accumulation)."""
    
    def test_subsequent_accrual_adds_to_current_bot_balance(self, balance_manager, repository, mock_logger):
        """Test that subsequent accruals add to current_bot_balance."""
        # Arrange
        from src.parsers import ParsedAccrual
        parsed_first = ParsedAccrual(player_name="TestPlayer", points=Decimal("50"), game="GD Cards")
        balance_manager.process_accrual(parsed_first)
        
        # Act
        parsed_second = ParsedAccrual(player_name="TestPlayer", points=Decimal("30"), game="GD Cards")
        balance_manager.process_accrual(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        assert bot_balance.current_bot_balance == Decimal("80")  # 50 + 30
    
    def test_subsequent_accrual_adds_to_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that subsequent accruals add to bank_balance with coefficient."""
        # Arrange
        from src.parsers import ParsedAccrual
        parsed_first = ParsedAccrual(player_name="TestPlayer", points=Decimal("50"), game="GD Cards")
        balance_manager.process_accrual(parsed_first)
        
        # Act
        parsed_second = ParsedAccrual(player_name="TestPlayer", points=Decimal("30"), game="GD Cards")
        balance_manager.process_accrual(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # First: 50 * 2 = 100, Second: 30 * 2 = 60, Total = 160
        assert user.bank_balance == Decimal("160")
    
    def test_accrual_does_not_modify_last_balance(self, balance_manager, repository, mock_logger):
        """Test that accrual does NOT modify last_balance field."""
        # Arrange
        from src.parsers import ParsedAccrual
        parsed = ParsedAccrual(player_name="TestPlayer", points=Decimal("50"), game="GD Cards")
        balance_manager.process_accrual(parsed)
        
        # Act
        parsed_second = ParsedAccrual(player_name="TestPlayer", points=Decimal("30"), game="GD Cards")
        balance_manager.process_accrual(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        # last_balance should remain 0 (not modified by accruals)
        assert bot_balance.last_balance == Decimal("0")


class TestProcessAccrualWithDifferentGames:
    """Tests for accrual processing with different games and coefficients."""
    
    def test_different_coefficient_applied(self, balance_manager, repository, mock_logger):
        """Test that different game coefficients are applied correctly."""
        # Arrange - True Mafia has coefficient 15
        from src.parsers import ParsedAccrual
        parsed = ParsedAccrual(player_name="TestPlayer", points=Decimal("10"), game="True Mafia")
        
        # Act
        balance_manager.process_accrual(parsed)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # Points = 10, coefficient = 15, bank_change = 10 * 15 = 150
        assert user.bank_balance == Decimal("150")
    
    def test_multiple_games_tracked_separately(self, balance_manager, repository, mock_logger):
        """Test that different games are tracked separately for the same user."""
        # Arrange
        from src.parsers import ParsedAccrual
        parsed_gd = ParsedAccrual(player_name="TestPlayer", points=Decimal("50"), game="GD Cards")
        parsed_mafia = ParsedAccrual(player_name="TestPlayer", points=Decimal("10"), game="True Mafia")
        
        # Act
        balance_manager.process_accrual(parsed_gd)
        balance_manager.process_accrual(parsed_mafia)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        bot_balance_gd = repository.get_bot_balance(user.user_id, "GD Cards")
        bot_balance_mafia = repository.get_bot_balance(user.user_id, "True Mafia")
        
        assert bot_balance_gd.current_bot_balance == Decimal("50")
        assert bot_balance_mafia.current_bot_balance == Decimal("10")
        # Bank balance = (50 * 2) + (10 * 15) = 100 + 150 = 250
        assert user.bank_balance == Decimal("250")


class TestProcessAccrualDecimalPrecision:
    """Tests for decimal precision handling in accruals."""
    
    def test_decimal_precision_preserved(self, balance_manager, repository, mock_logger):
        """Test that decimal precision is preserved in accrual calculations."""
        # Arrange
        from src.parsers import ParsedAccrual
        parsed = ParsedAccrual(player_name="TestPlayer", points=Decimal("25.5"), game="GD Cards")
        
        # Act
        balance_manager.process_accrual(parsed)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # Points = 25.5, coefficient = 2, bank_change = 25.5 * 2 = 51
        assert user.bank_balance == Decimal("51")
        
        bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        assert bot_balance.current_bot_balance == Decimal("25.5")


class TestProcessFishingFirstTime:
    """Tests for first-time fishing processing (initialization)."""
    
    def test_first_fishing_creates_bot_balance(self, balance_manager, repository, mock_logger):
        """Test that first fishing creates bot_balance with correct values."""
        # Arrange
        from src.parsers import ParsedFishing
        parsed = ParsedFishing(player_name="TestPlayer", coins=Decimal("25"), game="Shmalala")
        
        # Act
        balance_manager.process_fishing(parsed)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "Shmalala")
        
        assert bot_balance is not None
        assert bot_balance.last_balance == Decimal("0")
        assert bot_balance.current_bot_balance == Decimal("25")
        assert bot_balance.game == "Shmalala"
    
    def test_first_fishing_updates_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that first fishing updates bank_balance with coefficient."""
        # Arrange
        from src.parsers import ParsedFishing
        parsed = ParsedFishing(player_name="TestPlayer", coins=Decimal("25"), game="Shmalala")
        
        # Act
        balance_manager.process_fishing(parsed)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # Coins = 25, coefficient = 1, bank_change = 25 * 1 = 25
        assert user.bank_balance == Decimal("25")
    
    def test_first_fishing_logs_accrual(self, balance_manager, repository, mock_logger):
        """Test that first fishing logs the operation."""
        # Arrange
        from src.parsers import ParsedFishing
        parsed = ParsedFishing(player_name="TestPlayer", coins=Decimal("25"), game="Shmalala")
        
        # Act
        balance_manager.process_fishing(parsed)
        
        # Assert
        mock_logger.log_accrual.assert_called_once_with(
            "TestPlayer",
            "Shmalala",
            Decimal("25"),
            Decimal("25"),  # bank_change (25 * 1)
            1               # coefficient
        )


class TestProcessFishingSubsequent:
    """Tests for subsequent fishing processing (accumulation)."""
    
    def test_subsequent_fishing_adds_to_current_bot_balance(self, balance_manager, repository, mock_logger):
        """Test that subsequent fishing adds to current_bot_balance."""
        # Arrange
        from src.parsers import ParsedFishing
        parsed_first = ParsedFishing(player_name="TestPlayer", coins=Decimal("25"), game="Shmalala")
        balance_manager.process_fishing(parsed_first)
        
        # Act
        parsed_second = ParsedFishing(player_name="TestPlayer", coins=Decimal("15"), game="Shmalala")
        balance_manager.process_fishing(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "Shmalala")
        assert bot_balance.current_bot_balance == Decimal("40")  # 25 + 15
    
    def test_subsequent_fishing_adds_to_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that subsequent fishing adds to bank_balance with coefficient."""
        # Arrange
        from src.parsers import ParsedFishing
        parsed_first = ParsedFishing(player_name="TestPlayer", coins=Decimal("25"), game="Shmalala")
        balance_manager.process_fishing(parsed_first)
        
        # Act
        parsed_second = ParsedFishing(player_name="TestPlayer", coins=Decimal("15"), game="Shmalala")
        balance_manager.process_fishing(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # First: 25 * 1 = 25, Second: 15 * 1 = 15, Total = 40
        assert user.bank_balance == Decimal("40")


class TestProcessKarmaFirstTime:
    """Tests for first-time karma processing (initialization)."""
    
    def test_first_karma_creates_bot_balance(self, balance_manager, repository, mock_logger):
        """Test that first karma creates bot_balance with correct values."""
        # Arrange
        from src.parsers import ParsedKarma
        parsed = ParsedKarma(player_name="TestPlayer", karma=Decimal("1"), game="Shmalala Karma")
        
        # Act
        balance_manager.process_karma(parsed)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "Shmalala Karma")
        
        assert bot_balance is not None
        assert bot_balance.last_balance == Decimal("0")
        assert bot_balance.current_bot_balance == Decimal("1")
        assert bot_balance.game == "Shmalala Karma"
    
    def test_first_karma_updates_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that first karma updates bank_balance with coefficient."""
        # Arrange
        from src.parsers import ParsedKarma
        parsed = ParsedKarma(player_name="TestPlayer", karma=Decimal("1"), game="Shmalala Karma")
        
        # Act
        balance_manager.process_karma(parsed)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # Karma = 1, coefficient = 10, bank_change = 1 * 10 = 10
        assert user.bank_balance == Decimal("10")
    
    def test_karma_always_adds_one(self, balance_manager, repository, mock_logger):
        """Test that karma accrual is always +1 regardless of parsed value."""
        # Arrange
        from src.parsers import ParsedKarma
        # Even if parsed karma shows different value, accrual should be 1
        parsed = ParsedKarma(player_name="TestPlayer", karma=Decimal("5"), game="Shmalala Karma")
        
        # Act
        balance_manager.process_karma(parsed)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "Shmalala Karma")
        # Should always be 1, not 5
        assert bot_balance.current_bot_balance == Decimal("1")
        # Bank balance should be 1 * 10 = 10
        assert user.bank_balance == Decimal("10")


class TestProcessKarmaSubsequent:
    """Tests for subsequent karma processing (accumulation)."""
    
    def test_subsequent_karma_adds_one_to_current_bot_balance(self, balance_manager, repository, mock_logger):
        """Test that subsequent karma adds 1 to current_bot_balance."""
        # Arrange
        from src.parsers import ParsedKarma
        parsed_first = ParsedKarma(player_name="TestPlayer", karma=Decimal("1"), game="Shmalala Karma")
        balance_manager.process_karma(parsed_first)
        
        # Act
        parsed_second = ParsedKarma(player_name="TestPlayer", karma=Decimal("1"), game="Shmalala Karma")
        balance_manager.process_karma(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "Shmalala Karma")
        assert bot_balance.current_bot_balance == Decimal("2")  # 1 + 1
    
    def test_subsequent_karma_adds_to_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that subsequent karma adds to bank_balance with coefficient."""
        # Arrange
        from src.parsers import ParsedKarma
        parsed_first = ParsedKarma(player_name="TestPlayer", karma=Decimal("1"), game="Shmalala Karma")
        balance_manager.process_karma(parsed_first)
        
        # Act
        parsed_second = ParsedKarma(player_name="TestPlayer", karma=Decimal("1"), game="Shmalala Karma")
        balance_manager.process_karma(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # First: 1 * 10 = 10, Second: 1 * 10 = 10, Total = 20
        assert user.bank_balance == Decimal("20")


class TestProcessGameWinnersTrueMafia:
    """Tests for True Mafia game winners processing."""
    
    def test_single_winner_receives_fixed_amount(self, balance_manager, repository, mock_logger):
        """Test that a single winner receives the fixed amount."""
        # Arrange
        winners = ["Winner1"]
        game = "True Mafia"
        fixed_amount = Decimal("10")
        
        # Act
        balance_manager.process_game_winners(winners, game, fixed_amount)
        
        # Assert
        user = repository.get_or_create_user("Winner1")
        bot_balance = repository.get_bot_balance(user.user_id, game)
        
        assert bot_balance.current_bot_balance == Decimal("10")
        # Bank balance = 10 * 15 = 150
        assert user.bank_balance == Decimal("150")
    
    def test_multiple_winners_all_receive_fixed_amount(self, balance_manager, repository, mock_logger):
        """Test that all winners receive the fixed amount."""
        # Arrange
        winners = ["Winner1", "Winner2", "Winner3"]
        game = "True Mafia"
        fixed_amount = Decimal("10")
        
        # Act
        balance_manager.process_game_winners(winners, game, fixed_amount)
        
        # Assert
        for winner_name in winners:
            user = repository.get_or_create_user(winner_name)
            bot_balance = repository.get_bot_balance(user.user_id, game)
            assert bot_balance.current_bot_balance == Decimal("10")
            assert user.bank_balance == Decimal("150")  # 10 * 15
    
    def test_winner_with_existing_balance_accumulates(self, balance_manager, repository, mock_logger):
        """Test that winner with existing balance accumulates the reward."""
        # Arrange
        from src.parsers import ParsedMafiaProfile
        # First, create existing balance
        parsed = ParsedMafiaProfile(player_name="Winner1", money=Decimal("50"), game="True Mafia")
        balance_manager.process_mafia_profile(parsed)
        
        # Act - winner gets 10 money
        winners = ["Winner1"]
        balance_manager.process_game_winners(winners, "True Mafia", Decimal("10"))
        
        # Assert
        user = repository.get_or_create_user("Winner1")
        bot_balance = repository.get_bot_balance(user.user_id, "True Mafia")
        assert bot_balance.current_bot_balance == Decimal("10")  # Accrual balance
        # Bank balance should still be 0 (first profile doesn't change bank)
        # Plus 10 * 15 = 150 from winning
        assert user.bank_balance == Decimal("150")
    
    def test_logs_accrual_for_each_winner(self, balance_manager, repository, mock_logger):
        """Test that accrual is logged for each winner."""
        # Arrange
        winners = ["Winner1", "Winner2"]
        game = "True Mafia"
        fixed_amount = Decimal("10")
        
        # Act
        balance_manager.process_game_winners(winners, game, fixed_amount)
        
        # Assert
        assert mock_logger.log_accrual.call_count == 2


class TestProcessGameWinnersBunkerRP:
    """Tests for BunkerRP game winners processing."""
    
    def test_single_winner_receives_fixed_amount(self, balance_manager, repository, mock_logger):
        """Test that a single BunkerRP winner receives the fixed amount."""
        # Arrange
        winners = ["Winner1"]
        game = "Bunker RP"
        fixed_amount = Decimal("30")
        
        # Act
        balance_manager.process_game_winners(winners, game, fixed_amount)
        
        # Assert
        user = repository.get_or_create_user("Winner1")
        bot_balance = repository.get_bot_balance(user.user_id, game)
        
        assert bot_balance.current_bot_balance == Decimal("30")
        # Bank balance = 30 * 20 = 600
        assert user.bank_balance == Decimal("600")
    
    def test_multiple_winners_all_receive_fixed_amount(self, balance_manager, repository, mock_logger):
        """Test that all BunkerRP winners receive the fixed amount."""
        # Arrange
        winners = ["Winner1", "Winner2"]
        game = "Bunker RP"
        fixed_amount = Decimal("30")
        
        # Act
        balance_manager.process_game_winners(winners, game, fixed_amount)
        
        # Assert
        for winner_name in winners:
            user = repository.get_or_create_user(winner_name)
            bot_balance = repository.get_bot_balance(user.user_id, game)
            assert bot_balance.current_bot_balance == Decimal("30")
            assert user.bank_balance == Decimal("600")  # 30 * 20


class TestProcessMafiaProfileFirstTime:
    """Tests for first-time True Mafia profile processing."""
    
    def test_first_profile_creates_bot_balance(self, balance_manager, repository, mock_logger):
        """Test that first True Mafia profile creates bot_balance with correct values."""
        # Arrange
        from src.parsers import ParsedMafiaProfile
        parsed = ParsedMafiaProfile(player_name="TestPlayer", money=Decimal("100"), game="True Mafia")
        
        # Act
        balance_manager.process_mafia_profile(parsed)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "True Mafia")
        
        assert bot_balance is not None
        assert bot_balance.last_balance == Decimal("100")
        assert bot_balance.current_bot_balance == Decimal("0")
        assert bot_balance.game == "True Mafia"
    
    def test_first_profile_does_not_modify_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that first True Mafia profile does NOT modify bank_balance."""
        # Arrange
        from src.parsers import ParsedMafiaProfile
        parsed = ParsedMafiaProfile(player_name="TestPlayer", money=Decimal("100"), game="True Mafia")
        
        # Act
        balance_manager.process_mafia_profile(parsed)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        assert user.bank_balance == Decimal("0")
    
    def test_first_profile_logs_initialization(self, balance_manager, repository, mock_logger):
        """Test that first True Mafia profile logs initialization."""
        # Arrange
        from src.parsers import ParsedMafiaProfile
        parsed = ParsedMafiaProfile(player_name="TestPlayer", money=Decimal("100"), game="True Mafia")
        
        # Act
        balance_manager.process_mafia_profile(parsed)
        
        # Assert
        mock_logger.log_profile_init.assert_called_once_with(
            "TestPlayer", "True Mafia", Decimal("100")
        )


class TestProcessMafiaProfileSubsequent:
    """Tests for subsequent True Mafia profile processing."""
    
    def test_positive_delta_increases_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that positive delta increases bank_balance by delta * coefficient."""
        # Arrange
        from src.parsers import ParsedMafiaProfile
        parsed_first = ParsedMafiaProfile(player_name="TestPlayer", money=Decimal("100"), game="True Mafia")
        balance_manager.process_mafia_profile(parsed_first)
        
        # Act
        parsed_second = ParsedMafiaProfile(player_name="TestPlayer", money=Decimal("120"), game="True Mafia")
        balance_manager.process_mafia_profile(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # Delta = 120 - 100 = 20, coefficient = 15, bank_change = 20 * 15 = 300
        assert user.bank_balance == Decimal("300")
    
    def test_negative_delta_decreases_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that negative delta decreases bank_balance."""
        # Arrange
        from src.parsers import ParsedMafiaProfile
        parsed_first = ParsedMafiaProfile(player_name="TestPlayer", money=Decimal("100"), game="True Mafia")
        balance_manager.process_mafia_profile(parsed_first)
        
        # Act
        parsed_second = ParsedMafiaProfile(player_name="TestPlayer", money=Decimal("80"), game="True Mafia")
        balance_manager.process_mafia_profile(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # Delta = 80 - 100 = -20, coefficient = 15, bank_change = -20 * 15 = -300
        assert user.bank_balance == Decimal("-300")
    
    def test_zero_delta_does_not_modify_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that zero delta does NOT modify bank_balance."""
        # Arrange
        from src.parsers import ParsedMafiaProfile
        parsed_first = ParsedMafiaProfile(player_name="TestPlayer", money=Decimal("100"), game="True Mafia")
        balance_manager.process_mafia_profile(parsed_first)
        
        # Act
        parsed_second = ParsedMafiaProfile(player_name="TestPlayer", money=Decimal("100"), game="True Mafia")
        balance_manager.process_mafia_profile(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        assert user.bank_balance == Decimal("0")
        mock_logger.log_profile_update.assert_not_called()
    
    def test_updates_last_balance(self, balance_manager, repository, mock_logger):
        """Test that last_balance is updated to current money value."""
        # Arrange
        from src.parsers import ParsedMafiaProfile
        parsed_first = ParsedMafiaProfile(player_name="TestPlayer", money=Decimal("100"), game="True Mafia")
        balance_manager.process_mafia_profile(parsed_first)
        
        # Act
        parsed_second = ParsedMafiaProfile(player_name="TestPlayer", money=Decimal("120"), game="True Mafia")
        balance_manager.process_mafia_profile(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "True Mafia")
        assert bot_balance.last_balance == Decimal("120")


class TestProcessBunkerProfileFirstTime:
    """Tests for first-time BunkerRP profile processing."""
    
    def test_first_profile_creates_bot_balance(self, balance_manager, repository, mock_logger):
        """Test that first BunkerRP profile creates bot_balance with correct values."""
        # Arrange
        from src.parsers import ParsedBunkerProfile
        parsed = ParsedBunkerProfile(player_name="TestPlayer", money=Decimal("200"), game="Bunker RP")
        
        # Act
        balance_manager.process_bunker_profile(parsed)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "Bunker RP")
        
        assert bot_balance is not None
        assert bot_balance.last_balance == Decimal("200")
        assert bot_balance.current_bot_balance == Decimal("0")
        assert bot_balance.game == "Bunker RP"
    
    def test_first_profile_does_not_modify_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that first BunkerRP profile does NOT modify bank_balance."""
        # Arrange
        from src.parsers import ParsedBunkerProfile
        parsed = ParsedBunkerProfile(player_name="TestPlayer", money=Decimal("200"), game="Bunker RP")
        
        # Act
        balance_manager.process_bunker_profile(parsed)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        assert user.bank_balance == Decimal("0")
    
    def test_first_profile_logs_initialization(self, balance_manager, repository, mock_logger):
        """Test that first BunkerRP profile logs initialization."""
        # Arrange
        from src.parsers import ParsedBunkerProfile
        parsed = ParsedBunkerProfile(player_name="TestPlayer", money=Decimal("200"), game="Bunker RP")
        
        # Act
        balance_manager.process_bunker_profile(parsed)
        
        # Assert
        mock_logger.log_profile_init.assert_called_once_with(
            "TestPlayer", "Bunker RP", Decimal("200")
        )


class TestProcessBunkerProfileSubsequent:
    """Tests for subsequent BunkerRP profile processing."""
    
    def test_positive_delta_increases_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that positive delta increases bank_balance by delta * coefficient."""
        # Arrange
        from src.parsers import ParsedBunkerProfile
        parsed_first = ParsedBunkerProfile(player_name="TestPlayer", money=Decimal("200"), game="Bunker RP")
        balance_manager.process_bunker_profile(parsed_first)
        
        # Act
        parsed_second = ParsedBunkerProfile(player_name="TestPlayer", money=Decimal("210"), game="Bunker RP")
        balance_manager.process_bunker_profile(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # Delta = 210 - 200 = 10, coefficient = 20, bank_change = 10 * 20 = 200
        assert user.bank_balance == Decimal("200")
    
    def test_negative_delta_decreases_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that negative delta decreases bank_balance."""
        # Arrange
        from src.parsers import ParsedBunkerProfile
        parsed_first = ParsedBunkerProfile(player_name="TestPlayer", money=Decimal("200"), game="Bunker RP")
        balance_manager.process_bunker_profile(parsed_first)
        
        # Act
        parsed_second = ParsedBunkerProfile(player_name="TestPlayer", money=Decimal("190"), game="Bunker RP")
        balance_manager.process_bunker_profile(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # Delta = 190 - 200 = -10, coefficient = 20, bank_change = -10 * 20 = -200
        assert user.bank_balance == Decimal("-200")
    
    def test_zero_delta_does_not_modify_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that zero delta does NOT modify bank_balance."""
        # Arrange
        from src.parsers import ParsedBunkerProfile
        parsed_first = ParsedBunkerProfile(player_name="TestPlayer", money=Decimal("200"), game="Bunker RP")
        balance_manager.process_bunker_profile(parsed_first)
        
        # Act
        parsed_second = ParsedBunkerProfile(player_name="TestPlayer", money=Decimal("200"), game="Bunker RP")
        balance_manager.process_bunker_profile(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        assert user.bank_balance == Decimal("0")
        mock_logger.log_profile_update.assert_not_called()
    
    def test_updates_last_balance(self, balance_manager, repository, mock_logger):
        """Test that last_balance is updated to current money value."""
        # Arrange
        from src.parsers import ParsedBunkerProfile
        parsed_first = ParsedBunkerProfile(player_name="TestPlayer", money=Decimal("200"), game="Bunker RP")
        balance_manager.process_bunker_profile(parsed_first)
        
        # Act
        parsed_second = ParsedBunkerProfile(player_name="TestPlayer", money=Decimal("210"), game="Bunker RP")
        balance_manager.process_bunker_profile(parsed_second)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        bot_balance = repository.get_bot_balance(user.user_id, "Bunker RP")
        assert bot_balance.last_balance == Decimal("210")


class TestCrossGameInteractions:
    """Tests for interactions between different games."""
    
    def test_multiple_games_accumulate_bank_balance(self, balance_manager, repository, mock_logger):
        """Test that rewards from multiple games accumulate in bank_balance."""
        # Arrange
        from src.parsers import ParsedAccrual, ParsedFishing, ParsedKarma
        
        # Act - Process rewards from different games
        gd_accrual = ParsedAccrual(player_name="TestPlayer", points=Decimal("50"), game="GD Cards")
        balance_manager.process_accrual(gd_accrual)
        
        fishing = ParsedFishing(player_name="TestPlayer", coins=Decimal("30"), game="Shmalala")
        balance_manager.process_fishing(fishing)
        
        karma = ParsedKarma(player_name="TestPlayer", karma=Decimal("1"), game="Shmalala Karma")
        balance_manager.process_karma(karma)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        # GD Cards: 50 * 2 = 100
        # Shmalala: 30 * 1 = 30
        # Karma: 1 * 10 = 10
        # Total = 140
        assert user.bank_balance == Decimal("140")
    
    def test_each_game_maintains_separate_bot_balance(self, balance_manager, repository, mock_logger):
        """Test that each game maintains separate bot_balance records."""
        # Arrange
        from src.parsers import ParsedAccrual, ParsedFishing, ParsedKarma
        
        # Act
        gd_accrual = ParsedAccrual(player_name="TestPlayer", points=Decimal("50"), game="GD Cards")
        balance_manager.process_accrual(gd_accrual)
        
        fishing = ParsedFishing(player_name="TestPlayer", coins=Decimal("30"), game="Shmalala")
        balance_manager.process_fishing(fishing)
        
        karma = ParsedKarma(player_name="TestPlayer", karma=Decimal("1"), game="Shmalala Karma")
        balance_manager.process_karma(karma)
        
        # Assert
        user = repository.get_or_create_user("TestPlayer")
        
        gd_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        assert gd_balance.current_bot_balance == Decimal("50")
        
        shmalala_balance = repository.get_bot_balance(user.user_id, "Shmalala")
        assert shmalala_balance.current_bot_balance == Decimal("30")
        
        karma_balance = repository.get_bot_balance(user.user_id, "Shmalala Karma")
        assert karma_balance.current_bot_balance == Decimal("1")
