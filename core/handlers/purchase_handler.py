"""
PurchaseHandler class for processing purchases in the Telegram Bot Shop System
Implements balance validation, deduction logic, and purchase command handling
"""

import os
import sys
from typing import Optional, Dict, Any

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database.shop_database import ShopDatabaseManager
from core.models.shop_models import (
    PurchaseResult, ShopItem, User, InsufficientBalanceError, 
    ItemNotFoundError, UserNotFoundError
)
import structlog

logger = structlog.get_logger()


class PurchaseHandler:
    """Handler for processing shop purchases with balance validation"""
    
    def __init__(self, db_manager: Optional[ShopDatabaseManager] = None):
        """Initialize PurchaseHandler with database manager"""
        self.db = db_manager or ShopDatabaseManager()
    
    def process_purchase(self, user_id: int, item_number: int) -> PurchaseResult:
        """
        Process a purchase request with balance validation
        
        Args:
            user_id: Telegram user ID
            item_number: Item number as displayed in shop (1, 2, 3)
            
        Returns:
            PurchaseResult with success status and details
        """
        try:
            # Get user information
            user = self.db.get_user_by_telegram_id(user_id)
            if not user:
                logger.error(f"User {user_id} not found")
                return PurchaseResult(
                    success=False,
                    message="Пользователь не найден. Используйте /start для регистрации.",
                    error_code="user_not_found"
                )
            
            # Get shop item by number
            shop_items = self.db.get_shop_items()
            if not shop_items or item_number < 1 or item_number > len(shop_items):
                logger.error(f"Invalid item number {item_number}")
                return PurchaseResult(
                    success=False,
                    message=f"Товар с номером {item_number} не найден.",
                    error_code="item_not_found"
                )
            
            item = shop_items[item_number - 1]  # Convert to 0-based index
            
            # Validate balance
            if not self.validate_balance(user, item.price):
                return PurchaseResult(
                    success=False,
                    message=f"Недостаточно средств! Ваш баланс: {user.balance}",
                    error_code="insufficient_balance",
                    new_balance=user.balance
                )
            
            # Deduct balance
            new_balance = self.deduct_balance(user, item.price)
            if new_balance is None:
                logger.error(f"Failed to deduct balance for user {user_id}")
                return PurchaseResult(
                    success=False,
                    message="Ошибка при обработке платежа. Попробуйте позже.",
                    error_code="payment_error"
                )
            
            # Create purchase record
            purchase_id = self.db.create_purchase(user.id, item.id)
            
            # Log transaction
            self.db.add_transaction(
                user.id, 
                -item.price, 
                'shop_purchase', 
                f"Покупка: {item.name}"
            )
            
            logger.info(f"Purchase successful: user {user_id}, item {item.id}, purchase {purchase_id}")
            
            return PurchaseResult(
                success=True,
                message=f"Покупка успешна! Вы приобрели: {item.name}",
                purchase_id=purchase_id,
                new_balance=new_balance
            )
            
        except InsufficientBalanceError as e:
            return PurchaseResult(
                success=False,
                message=f"Недостаточно средств! Ваш баланс: {e.current_balance}",
                error_code="insufficient_balance",
                new_balance=e.current_balance
            )
        except ItemNotFoundError as e:
            return PurchaseResult(
                success=False,
                message=f"Товар не найден.",
                error_code="item_not_found"
            )
        except UserNotFoundError as e:
            return PurchaseResult(
                success=False,
                message="Пользователь не найден. Используйте /start для регистрации.",
                error_code="user_not_found"
            )
        except Exception as e:
            logger.error(f"Unexpected error in purchase processing: {e}")
            return PurchaseResult(
                success=False,
                message="Произошла ошибка при обработке покупки. Попробуйте позже.",
                error_code="system_error"
            )
    
    def validate_balance(self, user: User, required_amount: int) -> bool:
        """
        Check if user has sufficient balance
        
        Args:
            user: User object
            required_amount: Required amount for purchase
            
        Returns:
            True if user has sufficient balance, False otherwise
        """
        try:
            return user.balance >= required_amount
        except Exception as e:
            logger.error(f"Error validating balance for user {user.id}: {e}")
            return False
    
    def deduct_balance(self, user: User, amount: int) -> Optional[int]:
        """
        Deduct coins from user balance
        
        Args:
            user: User object
            amount: Amount to deduct
            
        Returns:
            New balance if successful, None if failed
        """
        try:
            if user.balance < amount:
                raise InsufficientBalanceError(user.id, user.balance, amount)
            
            new_balance = user.balance - amount
            self.db.update_user_balance(user.id, new_balance)
            
            logger.info(f"Balance deducted: user {user.id}, amount {amount}, new balance {new_balance}")
            return new_balance
            
        except Exception as e:
            logger.error(f"Error deducting balance for user {user.id}: {e}")
            return None
    
    def get_purchase_commands_info(self) -> Dict[str, Any]:
        """
        Get information about available purchase commands
        
        Returns:
            Dictionary with command information
        """
        try:
            shop_items = self.db.get_shop_items()
            commands = {}
            
            for i, item in enumerate(shop_items, 1):
                commands[f"/buy_{i}"] = {
                    "item_id": item.id,
                    "item_name": item.name,
                    "price": item.price,
                    "description": item.description
                }
            
            return commands
            
        except Exception as e:
            logger.error(f"Error getting purchase commands info: {e}")
            return {}
    
    def process_buy_command(self, user_id: int, command: str) -> PurchaseResult:
        """
        Process a buy command (/buy_1, /buy_2, /buy_3)
        
        Args:
            user_id: Telegram user ID
            command: Command string (e.g., "/buy_1")
            
        Returns:
            PurchaseResult with purchase outcome
        """
        try:
            # Extract item number from command
            if not command.startswith("/buy_"):
                return PurchaseResult(
                    success=False,
                    message="Неверная команда покупки.",
                    error_code="invalid_command"
                )
            
            try:
                item_number = int(command.split("_")[1])
            except (IndexError, ValueError):
                return PurchaseResult(
                    success=False,
                    message="Неверный номер товара.",
                    error_code="invalid_item_number"
                )
            
            # Process the purchase
            return self.process_purchase(user_id, item_number)
            
        except Exception as e:
            logger.error(f"Error processing buy command {command} for user {user_id}: {e}")
            return PurchaseResult(
                success=False,
                message="Произошла ошибка при обработке команды покупки.",
                error_code="command_error"
            )
    
    def get_user_purchase_history(self, user_id: int, limit: int = 10) -> list:
        """
        Get user's purchase history
        
        Args:
            user_id: Telegram user ID
            limit: Maximum number of purchases to return
            
        Returns:
            List of purchase records
        """
        try:
            user = self.db.get_user_by_telegram_id(user_id)
            if not user:
                return []
            
            purchases = self.db.get_user_purchases(user.id)
            return purchases[:limit]
            
        except Exception as e:
            logger.error(f"Error getting purchase history for user {user_id}: {e}")
            return []
    
    def validate_purchase_request(self, user_id: int, item_number: int) -> Dict[str, Any]:
        """
        Validate a purchase request without processing it
        
        Args:
            user_id: Telegram user ID
            item_number: Item number to validate
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Get user
            user = self.db.get_user_by_telegram_id(user_id)
            if not user:
                return {
                    "valid": False,
                    "error": "user_not_found",
                    "message": "Пользователь не найден"
                }
            
            # Get item
            shop_items = self.db.get_shop_items()
            if not shop_items or item_number < 1 or item_number > len(shop_items):
                return {
                    "valid": False,
                    "error": "item_not_found",
                    "message": "Товар не найден"
                }
            
            item = shop_items[item_number - 1]
            
            # Check balance
            if user.balance < item.price:
                return {
                    "valid": False,
                    "error": "insufficient_balance",
                    "message": f"Недостаточно средств! Ваш баланс: {user.balance}",
                    "current_balance": user.balance,
                    "required": item.price
                }
            
            return {
                "valid": True,
                "user": user,
                "item": item,
                "message": "Покупка возможна"
            }
            
        except Exception as e:
            logger.error(f"Error validating purchase request: {e}")
            return {
                "valid": False,
                "error": "system_error",
                "message": "Ошибка валидации"
            }