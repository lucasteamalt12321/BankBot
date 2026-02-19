"""Balance manager for processing profile and accrual messages."""

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.audit_logger import AuditLogger

# Правильный импорт из src.repository (файл repository.py в папке src)
import sys
import os

# Добавляем корневую директорию в путь, если её там нет
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Теперь импортируем из src.repository (это файл src/repository.py)
from src.repository import DatabaseRepository
from src.coefficient_provider import CoefficientProvider
from src.parsers import (
    ParsedProfile, ParsedAccrual, ParsedFishing, ParsedKarma,
    ParsedMafiaWinners, ParsedMafiaProfile, ParsedBunkerWinners, ParsedBunkerProfile
)


class BalanceManager:
    """Manages balance updates with business logic."""
    
    def __init__(
        self,
        repository: DatabaseRepository,
        coefficient_provider: CoefficientProvider,
        logger: 'AuditLogger'
    ):
        """
        Initialize balance manager with dependencies.
        
        Args:
            repository: Database repository for persistence
            coefficient_provider: Provider for game-specific coefficients
            logger: Audit logger for tracking operations
        """
        self.repository = repository
        self.coefficient_provider = coefficient_provider
        self.logger = logger
    
    def process_profile(self, parsed: ParsedProfile) -> None:
        """
        Process profile message and update balances.
        
        Args:
            parsed: Parsed profile data
        """
        game = parsed.game
        coefficient = self.coefficient_provider.get_coefficient(game)
        
        # Get or create user
        user = self.repository.get_or_create_user(parsed.player_name)
        
        # Check if bot balance exists
        bot_balance = self.repository.get_bot_balance(user.user_id, game)
        
        if bot_balance is None:
            # First time seeing this profile - initialize tracking
            self.repository.create_bot_balance(
                user_id=user.user_id,
                game=game,
                last_balance=parsed.orbs,
                current_bot_balance=Decimal(0)
            )
            self.logger.log_profile_init(user.user_name, game, parsed.orbs)
        else:
            # Calculate delta and update balances
            delta = parsed.orbs - bot_balance.last_balance
            
            if delta != 0:
                bank_change = delta * coefficient
                
                # Update bank balance
                new_bank_balance = user.bank_balance + bank_change
                self.repository.update_user_balance(user.user_id, new_bank_balance)
                
                # Update last_balance
                self.repository.update_bot_last_balance(
                    user.user_id,
                    game,
                    parsed.orbs
                )
                
                self.logger.log_profile_update(
                    user.user_name,
                    game,
                    bot_balance.last_balance,
                    parsed.orbs,
                    delta,
                    bank_change,
                    coefficient
                )
    
    def process_accrual(self, parsed: ParsedAccrual) -> None:
        """
        Process accrual message and update balances.
        
        Args:
            parsed: Parsed accrual data
        """
        game = parsed.game
        coefficient = self.coefficient_provider.get_coefficient(game)
        
        # Get or create user
        user = self.repository.get_or_create_user(parsed.player_name)
        
        # Get or create bot balance
        bot_balance = self.repository.get_bot_balance(user.user_id, game)
        
        if bot_balance is None:
            # Create new bot balance with initial points
            self.repository.create_bot_balance(
                user_id=user.user_id,
                game=game,
                last_balance=Decimal(0),
                current_bot_balance=parsed.points
            )
        else:
            # Add points to current bot balance
            new_bot_balance = bot_balance.current_bot_balance + parsed.points
            self.repository.update_bot_current_balance(
                user.user_id,
                game,
                new_bot_balance
            )
        
        # Add to bank balance with coefficient
        bank_change = parsed.points * coefficient
        new_bank_balance = user.bank_balance + bank_change
        self.repository.update_user_balance(user.user_id, new_bank_balance)
        
        self.logger.log_accrual(
            user.user_name,
            game,
            parsed.points,
            bank_change,
            coefficient
        )
    
    def process_fishing(self, parsed: ParsedFishing) -> None:
        """
        Process Shmalala fishing message and update balances.
        
        Args:
            parsed: Parsed fishing data
        """
        game = parsed.game
        coefficient = self.coefficient_provider.get_coefficient(game)
        
        # Get or create user
        user = self.repository.get_or_create_user(parsed.player_name)
        
        # Get or create bot balance
        bot_balance = self.repository.get_bot_balance(user.user_id, game)
        
        if bot_balance is None:
            # Create new bot balance with initial coins
            self.repository.create_bot_balance(
                user_id=user.user_id,
                game=game,
                last_balance=Decimal(0),
                current_bot_balance=parsed.coins
            )
        else:
            # Add coins to current bot balance
            new_bot_balance = bot_balance.current_bot_balance + parsed.coins
            self.repository.update_bot_current_balance(
                user.user_id,
                game,
                new_bot_balance
            )
        
        # Add to bank balance with coefficient
        bank_change = parsed.coins * coefficient
        new_bank_balance = user.bank_balance + bank_change
        self.repository.update_user_balance(user.user_id, new_bank_balance)
        
        self.logger.log_accrual(
            user.user_name,
            game,
            parsed.coins,
            bank_change,
            coefficient
        )
    
    def process_karma(self, parsed: ParsedKarma) -> None:
        """
        Process Shmalala karma message and update balances.
        Karma accruals are always +1 regardless of displayed total.
        
        Args:
            parsed: Parsed karma data
        """
        game = parsed.game
        coefficient = self.coefficient_provider.get_coefficient(game)
        
        # Get or create user
        user = self.repository.get_or_create_user(parsed.player_name)
        
        # Karma accrual is always +1
        karma_accrual = Decimal(1)
        
        # Get or create bot balance
        bot_balance = self.repository.get_bot_balance(user.user_id, game)
        
        if bot_balance is None:
            # Create new bot balance with initial karma
            self.repository.create_bot_balance(
                user_id=user.user_id,
                game=game,
                last_balance=Decimal(0),
                current_bot_balance=karma_accrual
            )
        else:
            # Add karma to current bot balance
            new_bot_balance = bot_balance.current_bot_balance + karma_accrual
            self.repository.update_bot_current_balance(
                user.user_id,
                game,
                new_bot_balance
            )
        
        # Add to bank balance with coefficient
        bank_change = karma_accrual * coefficient
        new_bank_balance = user.bank_balance + bank_change
        self.repository.update_user_balance(user.user_id, new_bank_balance)
        
        self.logger.log_accrual(
            user.user_name,
            game,
            karma_accrual,
            bank_change,
            coefficient
        )
    
    def process_game_winners(self, winners: list, game: str, fixed_amount: Decimal) -> None:
        """
        Process game end message with multiple winners getting fixed amounts.
        Used for True Mafia (10 money) and BunkerRP (30 money).
        
        Args:
            winners: List of winner names
            game: Game name
            fixed_amount: Fixed amount each winner receives (in game currency)
        """
        coefficient = self.coefficient_provider.get_coefficient(game)
        bank_change = fixed_amount * coefficient
        
        for winner_name in winners:
            # Get or create user
            user = self.repository.get_or_create_user(winner_name)
            
            # Get or create bot balance
            bot_balance = self.repository.get_bot_balance(user.user_id, game)
            
            if bot_balance is None:
                # Create new bot balance with initial amount
                self.repository.create_bot_balance(
                    user_id=user.user_id,
                    game=game,
                    last_balance=Decimal(0),
                    current_bot_balance=fixed_amount
                )
            else:
                # Add amount to current bot balance
                new_bot_balance = bot_balance.current_bot_balance + fixed_amount
                self.repository.update_bot_current_balance(
                    user.user_id,
                    game,
                    new_bot_balance
                )
            
            # Add to bank balance with coefficient
            new_bank_balance = user.bank_balance + bank_change
            self.repository.update_user_balance(user.user_id, new_bank_balance)
            
            self.logger.log_accrual(
                user.user_name,
                game,
                fixed_amount,
                bank_change,
                coefficient
            )
    
    def process_mafia_profile(self, parsed: ParsedMafiaProfile) -> None:
        """
        Process True Mafia profile message and update balances.
        
        Args:
            parsed: Parsed True Mafia profile data
        """
        game = parsed.game
        coefficient = self.coefficient_provider.get_coefficient(game)
        
        # Get or create user
        user = self.repository.get_or_create_user(parsed.player_name)
        
        # Check if bot balance exists
        bot_balance = self.repository.get_bot_balance(user.user_id, game)
        
        if bot_balance is None:
            # First time seeing this profile - initialize tracking
            self.repository.create_bot_balance(
                user_id=user.user_id,
                game=game,
                last_balance=parsed.money,
                current_bot_balance=Decimal(0)
            )
            self.logger.log_profile_init(user.user_name, game, parsed.money)
        else:
            # Calculate delta and update balances
            delta = parsed.money - bot_balance.last_balance
            
            if delta != 0:
                bank_change = delta * coefficient
                
                # Update bank balance
                new_bank_balance = user.bank_balance + bank_change
                self.repository.update_user_balance(user.user_id, new_bank_balance)
                
                # Update last_balance
                self.repository.update_bot_last_balance(
                    user.user_id,
                    game,
                    parsed.money
                )
                
                self.logger.log_profile_update(
                    user.user_name,
                    game,
                    bot_balance.last_balance,
                    parsed.money,
                    delta,
                    bank_change,
                    coefficient
                )
    
    def process_bunker_profile(self, parsed: ParsedBunkerProfile) -> None:
        """
        Process BunkerRP profile message and update balances.
        
        Args:
            parsed: Parsed BunkerRP profile data
        """
        game = parsed.game
        coefficient = self.coefficient_provider.get_coefficient(game)
        
        # Get or create user
        user = self.repository.get_or_create_user(parsed.player_name)
        
        # Check if bot balance exists
        bot_balance = self.repository.get_bot_balance(user.user_id, game)
        
        if bot_balance is None:
            # First time seeing this profile - initialize tracking
            self.repository.create_bot_balance(
                user_id=user.user_id,
                game=game,
                last_balance=parsed.money,
                current_bot_balance=Decimal(0)
            )
            self.logger.log_profile_init(user.user_name, game, parsed.money)
        else:
            # Calculate delta and update balances
            delta = parsed.money - bot_balance.last_balance
            
            if delta != 0:
                bank_change = delta * coefficient
                
                # Update bank balance
                new_bank_balance = user.bank_balance + bank_change
                self.repository.update_user_balance(user.user_id, new_bank_balance)
                
                # Update last_balance
                self.repository.update_bot_last_balance(
                    user.user_id,
                    game,
                    parsed.money
                )
                
                self.logger.log_profile_update(
                    user.user_name,
                    game,
                    bot_balance.last_balance,
                    parsed.money,
                    delta,
                    bank_change,
                    coefficient
                )
