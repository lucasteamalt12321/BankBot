"""
ShopHandler class for displaying shop items in the Telegram Bot Shop System
Implements shop display formatting with Russian text and command handling
"""

import os
import sys
from typing import List, Optional

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database.database import ShopItem, ShopCategory, get_db
import structlog

logger = structlog.get_logger()


class ShopHandler:
    """Handler for shop display and item management"""
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize ShopHandler with database session"""
        self.db = db_session
    
    def display_shop(self, user_id: int) -> str:
        """
        Generate formatted shop display message with Russian text
        
        Args:
            user_id: Telegram user ID (for potential future user-specific features)
            
        Returns:
            Formatted shop display string
        """
        try:
            # Get database session if not provided
            if not self.db:
                self.db = next(get_db())
            
            # Get all active shop items
            shop_items = self.get_shop_items()
            
            if not shop_items:
                return "🛒 МАГАЗИН\n\nМагазин временно пуст. Попробуйте позже."
            
            # Build the shop display message
            message_lines = ["🛒 МАГАЗИН\n"]
            
            for i, item in enumerate(shop_items, 1):
                # Format each item with number, name, description, and price
                item_text = f"{i}. {item.name} - {item.price} монет"
                message_lines.append(item_text)
                
                # Add description if available
                if item.description:
                    message_lines.append(f"   {item.description}")
                
                # Add purchase command
                message_lines.append(f"   Для покупки: /buy_{i}")
                message_lines.append("")  # Empty line for spacing
            
            # Add general instructions
            message_lines.append("💡 Используйте команды /buy_1, /buy_2, /buy_3 для покупки товаров")
            
            return "\n".join(message_lines)
            
        except Exception as e:
            logger.error(f"Error generating shop display: {e}")
            return "🛒 МАГАЗИН\n\n❌ Произошла ошибка при загрузке магазина. Попробуйте позже."
    
    def get_shop_items(self) -> List[ShopItem]:
        """
        Retrieve all available shop items
        
        Returns:
            List of active shop items
        """
        try:
            # Get database session if not provided
            if not self.db:
                self.db = next(get_db())
                
            # Query active shop items using SQLAlchemy
            items = self.db.query(ShopItem).filter(ShopItem.is_active == True).all()
            return items
        except Exception as e:
            logger.error(f"Error retrieving shop items: {e}")
            return []
    
    def get_shop_item_by_number(self, item_number: int) -> Optional[ShopItem]:
        """
        Get shop item by its display number (1-based)
        
        Args:
            item_number: Item number as displayed in shop (1, 2, 3, etc.)
            
        Returns:
            ShopItem if found, None otherwise
        """
        try:
            shop_items = self.get_shop_items()
            if 1 <= item_number <= len(shop_items):
                return shop_items[item_number - 1]
            return None
        except Exception as e:
            logger.error(f"Error getting shop item by number {item_number}: {e}")
            return None
    
    def get_shop_item_by_id(self, item_id: int) -> Optional[ShopItem]:
        """
        Get shop item by its database ID
        
        Args:
            item_id: Database ID of the item
            
        Returns:
            ShopItem if found, None otherwise
        """
        try:
            return self.db.get_shop_item(item_id)
        except Exception as e:
            logger.error(f"Error getting shop item by ID {item_id}: {e}")
            return None
    
    def format_shop_item(self, item: ShopItem, item_number: int) -> str:
        """
        Format a single shop item for display
        
        Args:
            item: ShopItem to format
            item_number: Display number for the item
            
        Returns:
            Formatted item string
        """
        lines = [f"{item_number}. {item.name} - {item.price} монет"]
        
        if item.description:
            lines.append(f"   {item.description}")
        
        lines.append(f"   Для покупки: /buy_{item_number}")
        
        return "\n".join(lines)
    
    def validate_shop_display(self) -> bool:
        """
        Validate that shop display meets requirements
        
        Returns:
            True if shop display is valid, False otherwise
        """
        try:
            # Test display generation
            display = self.display_shop(12345)  # Test user ID
            
            # Check required elements
            required_elements = [
                "🛒 МАГАЗИН",
                "монет",
                "/buy_"
            ]
            
            for element in required_elements:
                if element not in display:
                    logger.error(f"Shop display missing required element: {element}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating shop display: {e}")
            return False