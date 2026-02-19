"""Property-based tests for balance operations."""

import tempfile
import os
from decimal import Decimal
from hypothesis import given, strategies as st, assume, settings
from unittest.mock import Mock

from src.balance_manager import BalanceManager
from src.repository import SQLiteRepository
from src.coefficient_provider import CoefficientProvider
from src.parsers import ParsedProfile, ParsedAccrual


# Strategies for generating test data
player_names = st.text(min_size=1, max_size=50, alphabet=st.characters(
    whitelist_categories=('Lu', 'Ll', 'Nd'),
    whitelist_characters=' _-'
))

# Positive decimal values for balances (0 to 10000 with 2 decimal places)
balance_values = st.decimals(
    min_value=0,
    max_value=10000,
    places=2,
    allow_nan=False,
    allow_infinity=False
)

# Game names from the spec
game_names = st.sampled_from(["GD Cards", "Shmalala", "Shmalala Karma", "True Mafia", "Bunker RP"])


@settings(deadline=None)  # Disable deadline for database operations
@given(
    player_name=player_names,
    orbs=balance_values,
    game=game_names
)
def test_property_12_profile_first_parse_initialization(
    player_name, orbs, game
):
    """
    Feature: message-parsing-system, Property 12: Profile First Parse Initialization
    
    For any player with no existing bot_balance record, processing their first 
    profile message should create a bot_balance record with last_balance equal 
    to the current orbs value, current_bot_balance equal to zero, the correct 
    game identifier, and should NOT modify the player's bank_balance.
    
    Validates: Requirements 10.1, 10.2, 10.3, 10.4
    """
    # Arrange - create fresh components for each test with temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name
    
    try:
        repository = SQLiteRepository(test_db_path)
        coefficient_provider = CoefficientProvider({
            "GD Cards": 2,
            "Shmalala": 1,
            "Shmalala Karma": 10,
            "True Mafia": 15,
            "Bunker RP": 20
        })
        mock_logger = Mock()
        balance_manager = BalanceManager(repository, coefficient_provider, mock_logger)
        
        # Get initial bank balance (should be 0 for new user)
        user = repository.get_or_create_user(player_name)
        initial_bank_balance = user.bank_balance
        
        # Act
        parsed = ParsedProfile(player_name=player_name, orbs=orbs, game=game)
        balance_manager.process_profile(parsed)
        
        # Assert
        user = repository.get_or_create_user(player_name)
        bot_balance = repository.get_bot_balance(user.user_id, game)
        
        assert bot_balance is not None, "Bot balance should be created"
        assert bot_balance.last_balance == orbs, f"Last balance should equal orbs: {orbs}"
        assert bot_balance.current_bot_balance == Decimal(0), "Current bot balance should be zero"
        assert bot_balance.game == game, f"Game should be {game}"
        assert user.bank_balance == initial_bank_balance, "Bank balance should not be modified"
        
        # Close the database connection before cleanup
        repository.conn.close()
    finally:
        # Clean up temporary database
        if os.path.exists(test_db_path):
            try:
                os.unlink(test_db_path)
            except PermissionError:
                pass  # Ignore cleanup errors on Windows


@settings(deadline=None)  # Disable deadline for database operations
@given(
    player_name=player_names,
    initial_orbs=balance_values,
    new_orbs=balance_values,
    game=game_names
)
def test_property_13_profile_update_with_positive_delta(
    player_name, initial_orbs, new_orbs, game
):
    """
    Feature: message-parsing-system, Property 13: Profile Update with Positive Delta
    
    For any player with an existing bot_balance record, when processing a profile 
    message where current orbs > last_balance, the system should add 
    (delta * coefficient) to bank_balance and update last_balance to current orbs.
    
    Validates: Requirements 11.1, 11.2, 11.5
    """
    # Ensure positive delta
    assume(new_orbs > initial_orbs)
    
    # Arrange - create fresh components for each test with temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name
    
    try:
        repository = SQLiteRepository(test_db_path)
        coefficients = {
            "GD Cards": 2,
            "Shmalala": 1,
            "Shmalala Karma": 10,
            "True Mafia": 15,
            "Bunker RP": 20
        }
        coefficient_provider = CoefficientProvider(coefficients)
        mock_logger = Mock()
        balance_manager = BalanceManager(repository, coefficient_provider, mock_logger)
        
        # Initialize with first profile
        parsed_first = ParsedProfile(player_name=player_name, orbs=initial_orbs, game=game)
        balance_manager.process_profile(parsed_first)
        
        # Act - process second profile with higher orbs
        parsed_second = ParsedProfile(player_name=player_name, orbs=new_orbs, game=game)
        balance_manager.process_profile(parsed_second)
        
        # Assert
        user = repository.get_or_create_user(player_name)
        bot_balance = repository.get_bot_balance(user.user_id, game)
        
        delta = new_orbs - initial_orbs
        coefficient = coefficients[game]
        expected_bank_change = delta * coefficient
        
        assert bot_balance.last_balance == new_orbs, f"Last balance should be updated to {new_orbs}"
        assert user.bank_balance == expected_bank_change, \
            f"Bank balance should be {expected_bank_change} (delta {delta} * coefficient {coefficient})"
        
        # Close the database connection before cleanup
        repository.conn.close()
    finally:
        # Clean up temporary database
        if os.path.exists(test_db_path):
            try:
                os.unlink(test_db_path)
            except PermissionError:
                pass  # Ignore cleanup errors on Windows


@settings(deadline=None)  # Disable deadline for database operations
@given(
    player_name=player_names,
    initial_orbs=balance_values,
    new_orbs=balance_values,
    game=game_names
)
def test_property_14_profile_update_with_negative_delta(
    player_name, initial_orbs, new_orbs, game
):
    """
    Feature: message-parsing-system, Property 14: Profile Update with Negative Delta
    
    For any player with an existing bot_balance record, when processing a profile 
    message where current orbs < last_balance, the system should subtract 
    (|delta| * coefficient) from bank_balance and update last_balance to current orbs.
    
    Validates: Requirements 11.1, 11.3, 11.5
    """
    # Ensure negative delta
    assume(new_orbs < initial_orbs)
    
    # Arrange - create fresh components for each test with temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name
    
    try:
        repository = SQLiteRepository(test_db_path)
        coefficients = {
            "GD Cards": 2,
            "Shmalala": 1,
            "Shmalala Karma": 10,
            "True Mafia": 15,
            "Bunker RP": 20
        }
        coefficient_provider = CoefficientProvider(coefficients)
        mock_logger = Mock()
        balance_manager = BalanceManager(repository, coefficient_provider, mock_logger)
        
        # Initialize with first profile
        parsed_first = ParsedProfile(player_name=player_name, orbs=initial_orbs, game=game)
        balance_manager.process_profile(parsed_first)
        
        # Act - process second profile with lower orbs
        parsed_second = ParsedProfile(player_name=player_name, orbs=new_orbs, game=game)
        balance_manager.process_profile(parsed_second)
        
        # Assert
        user = repository.get_or_create_user(player_name)
        bot_balance = repository.get_bot_balance(user.user_id, game)
        
        delta = new_orbs - initial_orbs  # This will be negative
        coefficient = coefficients[game]
        expected_bank_change = delta * coefficient  # This will be negative
        
        assert bot_balance.last_balance == new_orbs, f"Last balance should be updated to {new_orbs}"
        assert user.bank_balance == expected_bank_change, \
            f"Bank balance should be {expected_bank_change} (delta {delta} * coefficient {coefficient})"
        
        # Close the database connection before cleanup
        repository.conn.close()
    finally:
        # Clean up temporary database
        if os.path.exists(test_db_path):
            try:
                os.unlink(test_db_path)
            except PermissionError:
                pass  # Ignore cleanup errors on Windows


@settings(deadline=None)  # Disable deadline for database operations
@given(
    player_name=player_names,
    points=balance_values,
    game=game_names
)
def test_property_15_accrual_processing(
    player_name, points, game
):
    """
    Feature: message-parsing-system, Property 15: Accrual Processing
    
    For any accrual message, processing should add points to current_bot_balance 
    (without coefficient), add (points * coefficient) to bank_balance, and should 
    NOT modify last_balance.
    
    Validates: Requirements 12.1, 12.2, 12.4
    """
    # Arrange - create fresh components for each test with temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name
    
    try:
        repository = SQLiteRepository(test_db_path)
        coefficients = {
            "GD Cards": 2,
            "Shmalala": 1,
            "Shmalala Karma": 10,
            "True Mafia": 15,
            "Bunker RP": 20
        }
        coefficient_provider = CoefficientProvider(coefficients)
        mock_logger = Mock()
        balance_manager = BalanceManager(repository, coefficient_provider, mock_logger)
        
        # Act
        parsed = ParsedAccrual(player_name=player_name, points=points, game=game)
        balance_manager.process_accrual(parsed)
        
        # Assert
        user = repository.get_or_create_user(player_name)
        bot_balance = repository.get_bot_balance(user.user_id, game)
        
        coefficient = coefficients[game]
        expected_bank_balance = points * coefficient
        
        assert bot_balance is not None, "Bot balance should be created"
        assert bot_balance.current_bot_balance == points, \
            f"Current bot balance should equal points: {points}"
        assert bot_balance.last_balance == Decimal(0), \
            "Last balance should not be modified (should remain 0)"
        assert user.bank_balance == expected_bank_balance, \
            f"Bank balance should be {expected_bank_balance} (points {points} * coefficient {coefficient})"
        
        # Close the database connection before cleanup
        repository.conn.close()
    finally:
        # Clean up temporary database
        if os.path.exists(test_db_path):
            try:
                os.unlink(test_db_path)
            except PermissionError:
                pass  # Ignore cleanup errors on Windows


@settings(deadline=None)  # Disable deadline for database operations
@given(
    player_name=player_names,
    points=balance_values,
    game=game_names
)
def test_property_16_accrual_first_time_initialization(
    player_name, points, game
):
    """
    Feature: message-parsing-system, Property 16: Accrual First Time Initialization
    
    For any player with no existing bot_balance record for a game, processing 
    their first accrual should create a bot_balance record with current_bot_balance 
    equal to the points value and last_balance equal to zero.
    
    Validates: Requirements 12.3
    """
    # Arrange - create fresh components for each test with temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name
    
    try:
        repository = SQLiteRepository(test_db_path)
        coefficient_provider = CoefficientProvider({
            "GD Cards": 2,
            "Shmalala": 1,
            "Shmalala Karma": 10,
            "True Mafia": 15,
            "Bunker RP": 20
        })
        mock_logger = Mock()
        balance_manager = BalanceManager(repository, coefficient_provider, mock_logger)
        
        # Verify no bot balance exists initially
        user = repository.get_or_create_user(player_name)
        initial_bot_balance = repository.get_bot_balance(user.user_id, game)
        assert initial_bot_balance is None, "Bot balance should not exist initially"
        
        # Act
        parsed = ParsedAccrual(player_name=player_name, points=points, game=game)
        balance_manager.process_accrual(parsed)
        
        # Assert
        bot_balance = repository.get_bot_balance(user.user_id, game)
        
        assert bot_balance is not None, "Bot balance should be created"
        assert bot_balance.current_bot_balance == points, \
            f"Current bot balance should equal points: {points}"
        assert bot_balance.last_balance == Decimal(0), \
            "Last balance should be initialized to zero"
        assert bot_balance.game == game, f"Game should be {game}"
        
        # Close the database connection before cleanup
        repository.conn.close()
    finally:
        # Clean up temporary database
        if os.path.exists(test_db_path):
            try:
                os.unlink(test_db_path)
            except PermissionError:
                pass  # Ignore cleanup errors on Windows
