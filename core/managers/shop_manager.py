"""
ShopManager class for Advanced Telegram Bot Features
Implements purchase validation logic and item activation for the enhanced shop system
"""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import User, ShopItem, UserPurchase
from core.models.advanced_models import PurchaseResult, ShopItem as AdvancedShopItem
import structlog

logger = structlog.get_logger()


class ShopManager:
    """
    Enhanced shop manager for processing purchases with validation and item activation
    Implements Requirements 1.1, 1.2, 1.3, 1.4 from the advanced features specification
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize ShopManager with database session
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
    
    async def process_purchase(self, user_id: int, item_number: int) -> PurchaseResult:
        """
        Process a purchase request with complete validation and activation
        
        Args:
            user_id: Telegram user ID making the purchase
            item_number: Shop item number (1-based index from shop display)
            
        Returns:
            PurchaseResult with success status, message, and transaction details
            
        Validates: Requirements 1.1, 1.2, 1.3, 1.4
        """
        try:
            logger.info("Processing purchase", user_id=user_id, item_number=item_number)
            
            # Get user from database
            user = self.db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                return PurchaseResult(
                    success=False,
                    message="Пользователь не найден в системе",
                    error_code="USER_NOT_FOUND"
                )
            
            # Get shop items to find the requested item by number
            shop_items = self.db.query(ShopItem).filter(ShopItem.is_active == True).all()
            if not shop_items or item_number < 1 or item_number > len(shop_items):
                return PurchaseResult(
                    success=False,
                    message=f"Товар с номером {item_number} не найден",
                    error_code="ITEM_NOT_FOUND"
                )
            
            # Get the specific item (convert 1-based to 0-based index)
            item = shop_items[item_number - 1]
            
            # Convert price to Decimal for precise calculations
            item_price = Decimal(str(item.price))
            user_balance = Decimal(str(user.balance))
            
            # Validate user balance (Requirement 1.1, 1.2)
            if not await self.validate_balance(user_id, item_price):
                return PurchaseResult(
                    success=False,
                    message=f"Недостаточно средств. Нужно {item_price}, у вас {user_balance}",
                    error_code="INSUFFICIENT_BALANCE"
                )
            
            # Deduct the price from user balance (Requirement 1.3)
            user.balance = int(user_balance - item_price)
            user.total_purchases += 1
            
            # Create purchase record
            purchase = UserPurchase(
                user_id=user.id,
                item_id=item.id,
                purchase_price=int(item_price),
                purchased_at=datetime.utcnow()
            )
            
            # Set expiration for time-limited items
            if item.meta_data and isinstance(item.meta_data, dict):
                duration_hours = item.meta_data.get('duration_hours')
                if duration_hours:
                    purchase.expires_at = datetime.utcnow() + timedelta(hours=duration_hours)
            
            self.db.add(purchase)
            
            # Activate the item (Requirement 1.4)
            activation_result = await self.activate_item(user_id, item)
            
            # Update purchase metadata with activation result
            purchase.meta_data = {
                'activation_result': activation_result,
                'activated_at': datetime.utcnow().isoformat()
            }
            
            # Commit the transaction
            self.db.commit()
            self.db.refresh(purchase)
            
            # Update purchase_id in activation result if it was an admin item
            if activation_result.get('feature_type') == 'admin_notification':
                # Update the purchase info with the actual purchase_id for admin notifications
                try:
                    from core.systems.broadcast_system import BroadcastSystem
                    from telegram import Bot
                    from utils.core.config import settings
                    
                    bot = Bot(token=settings.telegram_token)
                    broadcast_system = BroadcastSystem(self.db, bot)
                    
                    # Send updated notification with purchase_id
                    purchase_info = {
                        'item_name': item.name,
                        'item_price': item_price,
                        'purchase_id': purchase.id,
                        'user_id': user.telegram_id,
                        'username': user.username,
                        'first_name': user.first_name
                    }
                    
                    # Send updated purchase confirmation with purchase_id
                    await broadcast_system.send_purchase_confirmation(
                        user_id=user_id,
                        purchase_info=purchase_info
                    )
                    
                except Exception as e:
                    logger.warning(f"Failed to send updated purchase confirmation: {e}")
            
            logger.info(
                "Purchase completed successfully",
                user_id=user_id,
                item_id=item.id,
                item_name=item.name,
                price=item_price,
                new_balance=user.balance,
                purchase_id=purchase.id
            )
            
            return PurchaseResult(
                success=True,
                message=f"Покупка успешна! {item.name} активирован. {activation_result.get('message', '')}",
                purchase_id=purchase.id,
                new_balance=Decimal(str(user.balance))
            )
            
        except Exception as e:
            logger.error("Error processing purchase", error=str(e), user_id=user_id, item_number=item_number)
            self.db.rollback()
            return PurchaseResult(
                success=False,
                message="Произошла ошибка при обработке покупки",
                error_code="PROCESSING_ERROR"
            )
    
    async def validate_balance(self, user_id: int, item_price: Decimal) -> bool:
        """
        Validate that user has sufficient balance for purchase
        
        Args:
            user_id: Telegram user ID
            item_price: Price of the item as Decimal
            
        Returns:
            True if user has sufficient balance, False otherwise
            
        Validates: Requirements 1.1, 1.2
        """
        try:
            user = self.db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                logger.warning("User not found for balance validation", user_id=user_id)
                return False
            
            user_balance = Decimal(str(user.balance))
            has_sufficient_balance = user_balance >= item_price
            
            logger.debug(
                "Balance validation",
                user_id=user_id,
                user_balance=user_balance,
                item_price=item_price,
                sufficient=has_sufficient_balance
            )
            
            return has_sufficient_balance
            
        except Exception as e:
            logger.error("Error validating balance", error=str(e), user_id=user_id)
            return False
    
    async def activate_item(self, user_id: int, item: ShopItem) -> Dict[str, Any]:
        """
        Activate purchased item with item-specific behaviors
        
        Args:
            user_id: Telegram user ID who purchased the item
            item: ShopItem that was purchased
            
        Returns:
            Dictionary with activation result and details
            
        Validates: Requirements 1.4, 2.1, 3.1, 4.1
        """
        try:
            logger.info("Activating item", user_id=user_id, item_id=item.id, item_type=item.item_type)
            
            # Get user for activation
            user = self.db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                return {
                    "activated": False,
                    "message": "Пользователь не найден для активации"
                }
            
            # Route to specific activation handler based on item type
            activation_handlers = {
                "sticker": self._activate_sticker_item,
                "admin": self._activate_admin_item,
                "mention_all": self._activate_mention_all_item,
                "custom": self._activate_custom_item
            }
            
            handler = activation_handlers.get(item.item_type)
            if handler:
                result = await handler(user, item)
            else:
                # Default activation for unknown types
                result = {
                    "activated": True,
                    "message": f"Товар '{item.name}' активирован"
                }
            
            logger.info(
                "Item activation completed",
                user_id=user_id,
                item_id=item.id,
                item_type=item.item_type,
                result=result
            )
            
            return result
            
        except Exception as e:
            logger.error("Error activating item", error=str(e), user_id=user_id, item_id=item.id)
            return {
                "activated": False,
                "message": "Ошибка при активации товара"
            }
    
    async def _activate_sticker_item(self, user: User, item: ShopItem) -> Dict[str, Any]:
        """
        Activate sticker-related items (Requirement 2.1)
        Sets unlimited sticker access for 24 hours
        """
        try:
            # Set unlimited sticker access
            user.sticker_unlimited = True
            user.sticker_unlimited_until = datetime.utcnow() + timedelta(hours=24)
            
            self.db.commit()
            
            logger.info(
                "Sticker access activated",
                user_id=user.telegram_id,
                expires_at=user.sticker_unlimited_until
            )
            
            return {
                "activated": True,
                "message": "Безлимитные стикеры активированы на 24 часа",
                "expires_at": user.sticker_unlimited_until.isoformat(),
                "feature_type": "unlimited_stickers"
            }
            
        except Exception as e:
            logger.error("Error activating sticker item", error=str(e), user_id=user.telegram_id)
            return {
                "activated": False,
                "message": "Ошибка при активации стикеров"
            }
    
    async def _activate_admin_item(self, user: User, item: ShopItem) -> Dict[str, Any]:
        """
        Activate admin-related items (Requirement 3.1)
        Sends notification to all administrators
        """
        try:
            # Import BroadcastSystem here to avoid circular imports
            from core.systems.broadcast_system import BroadcastSystem
            from telegram import Bot
            from utils.core.config import settings
            
            # Create BroadcastSystem instance for notifications
            bot = Bot(token=settings.telegram_token)
            broadcast_system = BroadcastSystem(self.db, bot)
            
            # Prepare purchase information for notification (Requirement 3.2)
            purchase_info = {
                'item_name': item.name,
                'item_price': item.price,
                'purchase_id': None,  # Will be set by the calling method
                'user_id': user.telegram_id,
                'username': user.username,
                'first_name': user.first_name
            }
            
            # Send notification to administrators (Requirement 3.1)
            notification_message = f"Приобретен админ-товар: {item.name}"
            notification_result = await broadcast_system.notify_admins(
                notification=notification_message,
                sender_id=user.telegram_id,
                purchase_info=purchase_info
            )
            
            # Send purchase confirmation to user (Requirement 3.4)
            confirmation_sent = await broadcast_system.send_purchase_confirmation(
                user_id=user.telegram_id,
                purchase_info=purchase_info
            )
            
            logger.info(
                "Admin item activated with notifications",
                user_id=user.telegram_id,
                username=user.username,
                item_name=item.name,
                admins_notified=notification_result.notified_admins,
                confirmation_sent=confirmation_sent
            )
            
            return {
                "activated": True,
                "message": "Админ-товар активирован, администраторы уведомлены",
                "notification_sent": notification_result.success,
                "admins_notified": notification_result.notified_admins,
                "confirmation_sent": confirmation_sent,
                "feature_type": "admin_notification"
            }
            
        except Exception as e:
            logger.error("Error activating admin item", error=str(e), user_id=user.telegram_id)
            return {
                "activated": False,
                "message": "Ошибка при активации админ-товара",
                "notification_sent": False,
                "admins_notified": 0,
                "confirmation_sent": False
            }
    
    async def _activate_mention_all_item(self, user: User, item: ShopItem) -> Dict[str, Any]:
        """
        Activate mention-all broadcast items (Requirement 4.1)
        Prompts user to provide broadcast message text
        """
        try:
            logger.info(
                "Mention-all item purchased",
                user_id=user.telegram_id,
                item_name=item.name
            )
            
            return {
                "activated": True,
                "message": "Право на рассылку активировано! Отправьте текст сообщения для рассылки всем пользователям.",
                "requires_input": True,
                "input_type": "broadcast_message",
                "feature_type": "mention_all_broadcast"
            }
            
        except Exception as e:
            logger.error("Error activating mention-all item", error=str(e), user_id=user.telegram_id)
            return {
                "activated": False,
                "message": "Ошибка при активации права на рассылку"
            }
    
    async def _activate_custom_item(self, user: User, item: ShopItem) -> Dict[str, Any]:
        """
        Activate custom items with generic behavior
        """
        try:
            logger.info(
                "Custom item activated",
                user_id=user.telegram_id,
                item_name=item.name
            )
            
            return {
                "activated": True,
                "message": f"Кастомный товар '{item.name}' активирован",
                "feature_type": "custom"
            }
            
        except Exception as e:
            logger.error("Error activating custom item", error=str(e), user_id=user.telegram_id)
            return {
                "activated": False,
                "message": "Ошибка при активации кастомного товара"
            }
    
    def get_user_balance(self, user_id: int) -> Optional[Decimal]:
        """
        Get current user balance
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            User balance as Decimal or None if user not found
        """
        try:
            user = self.db.query(User).filter(User.telegram_id == user_id).first()
            if user:
                return Decimal(str(user.balance))
            return None
        except Exception as e:
            logger.error("Error getting user balance", error=str(e), user_id=user_id)
            return None
    
    def get_shop_items(self) -> list[ShopItem]:
        """
        Get all active shop items
        
        Returns:
            List of active ShopItem objects
        """
        try:
            return self.db.query(ShopItem).filter(ShopItem.is_active == True).all()
        except Exception as e:
            logger.error("Error getting shop items", error=str(e))
            return []
    
    async def add_item(self, name: str, price: Decimal, item_type: str) -> Dict[str, Any]:
        """
        Add a new item to the shop dynamically
        
        Args:
            name: Name of the new shop item (must be unique)
            price: Price of the item as Decimal
            item_type: Type of item (sticker, admin, mention_all, custom)
            
        Returns:
            Dictionary with creation result and item details
            
        Validates: Requirements 9.1, 9.2, 9.3, 9.4
        """
        try:
            logger.info("Adding new shop item", name=name, price=price, item_type=item_type)
            
            # Validate item type (Requirement 9.3)
            valid_item_types = {"sticker", "admin", "mention_all", "custom"}
            if item_type not in valid_item_types:
                return {
                    "success": False,
                    "message": f"Недопустимый тип товара. Допустимые типы: {', '.join(valid_item_types)}",
                    "error_code": "INVALID_ITEM_TYPE"
                }
            
            # Check for unique name constraint (Requirement 9.2)
            existing_item = self.db.query(ShopItem).filter(ShopItem.name == name).first()
            if existing_item:
                return {
                    "success": False,
                    "message": f"Товар с названием '{name}' уже существует",
                    "error_code": "DUPLICATE_NAME"
                }
            
            # Validate price
            if price <= 0:
                return {
                    "success": False,
                    "message": "Цена должна быть больше нуля",
                    "error_code": "INVALID_PRICE"
                }
            
            # Create the new shop item (Requirement 9.1)
            new_item = ShopItem(
                name=name,
                description=f"Динамически созданный товар типа {item_type}",
                price=int(price),
                item_type=item_type,
                is_active=True,
                meta_data=self._get_default_meta_data(item_type)
            )
            
            # Add to database and commit (Requirement 9.4 - immediate availability)
            self.db.add(new_item)
            self.db.commit()
            self.db.refresh(new_item)
            
            logger.info(
                "Shop item created successfully",
                item_id=new_item.id,
                name=name,
                price=price,
                item_type=item_type
            )
            
            return {
                "success": True,
                "message": f"Товар '{name}' успешно добавлен в магазин",
                "item_id": new_item.id,
                "item": {
                    "id": new_item.id,
                    "name": new_item.name,
                    "price": new_item.price,
                    "item_type": new_item.item_type,
                    "description": new_item.description,
                    "is_active": new_item.is_active
                }
            }
            
        except Exception as e:
            logger.error("Error adding shop item", error=str(e), name=name, price=price, item_type=item_type)
            self.db.rollback()
            return {
                "success": False,
                "message": "Произошла ошибка при добавлении товара",
                "error_code": "CREATION_ERROR"
            }
    
    def _get_default_meta_data(self, item_type: str) -> Dict[str, Any]:
        """
        Get default metadata for different item types
        
        Args:
            item_type: Type of the item
            
        Returns:
            Dictionary with default metadata for the item type
        """
        meta_data_defaults = {
            "sticker": {
                "duration_hours": 24,
                "feature_type": "unlimited_stickers"
            },
            "admin": {
                "feature_type": "admin_notification",
                "notify_admins": True
            },
            "mention_all": {
                "feature_type": "mention_all_broadcast",
                "requires_input": True,
                "input_type": "broadcast_message"
            },
            "custom": {
                "feature_type": "custom"
            }
        }
        
        return meta_data_defaults.get(item_type, {})