"""
Example demonstrating the Admin Notification System
Shows how admin notifications work when users purchase admin items
"""

import asyncio
import os
import sys
from datetime import datetime
from unittest.mock import Mock, AsyncMock

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.systems.broadcast_system import BroadcastSystem
from core.managers.shop_manager import ShopManager
from database.database import User, ShopItem
from core.models.advanced_models import NotificationResult


async def demonstrate_admin_notification_system():
    """
    Demonstrate the admin notification system functionality
    """
    print("🔔 Admin Notification System Demo")
    print("=" * 50)
    
    # Mock database and bot for demonstration
    mock_db = Mock()
    mock_bot = Mock()
    mock_bot.send_message = AsyncMock()
    
    # Create sample users
    admin_user = User(
        id=1, 
        telegram_id=111, 
        first_name="AdminUser", 
        username="admin", 
        is_admin=True,
        balance=1000
    )
    
    regular_user = User(
        id=2, 
        telegram_id=222, 
        first_name="RegularUser", 
        username="user", 
        is_admin=False,
        balance=500
    )
    
    # Create sample admin item
    admin_item = ShopItem(
        id=1,
        name="Admin Support",
        description="Get admin assistance",
        price=100,
        item_type="admin",
        is_active=True
    )
    
    # Setup mock database responses
    def mock_query_filter_chain(*args, **kwargs):
        """Mock the query().filter().all() chain"""
        mock_result = Mock()
        
        # For admin users query
        if hasattr(args[0], '__name__') and 'is_admin' in str(args[0]):
            mock_result.all.return_value = [admin_user]
        else:
            mock_result.all.return_value = [regular_user, admin_user]
        
        # For single user query
        mock_result.first.return_value = regular_user
        
        return mock_result
    
    mock_db.query.return_value.filter.side_effect = mock_query_filter_chain
    
    # Create BroadcastSystem instance
    broadcast_system = BroadcastSystem(mock_db, mock_bot)
    
    print("\n1. Testing Admin User ID Management")
    print("-" * 30)
    
    # Test getting admin user IDs
    admin_ids = broadcast_system.get_admin_user_ids()
    print(f"✅ Admin user IDs: {admin_ids}")
    
    # Test adding admin user
    success = broadcast_system.add_admin_user(333)
    print(f"✅ Add admin user result: {success}")
    
    print("\n2. Testing Admin Notification with Purchase Info")
    print("-" * 30)
    
    # Prepare purchase information
    purchase_info = {
        'item_name': admin_item.name,
        'item_price': admin_item.price,
        'purchase_id': 123,
        'user_id': regular_user.telegram_id,
        'username': regular_user.username,
        'first_name': regular_user.first_name
    }
    
    # Send admin notification
    notification_result = await broadcast_system.notify_admins(
        notification="Admin item purchased",
        sender_id=regular_user.telegram_id,
        purchase_info=purchase_info
    )
    
    print(f"✅ Notification sent: {notification_result.success}")
    print(f"✅ Admins notified: {notification_result.notified_admins}")
    print(f"✅ Failed notifications: {notification_result.failed_notifications}")
    
    # Check the message that would be sent
    if mock_bot.send_message.called:
        call_args = mock_bot.send_message.call_args
        message_text = call_args[1]['text']
        print(f"\n📧 Notification message preview:")
        print("-" * 30)
        print(message_text)
    
    print("\n3. Testing Purchase Confirmation")
    print("-" * 30)
    
    # Send purchase confirmation
    confirmation_sent = await broadcast_system.send_purchase_confirmation(
        user_id=regular_user.telegram_id,
        purchase_info=purchase_info
    )
    
    print(f"✅ Purchase confirmation sent: {confirmation_sent}")
    
    # Show confirmation message
    if mock_bot.send_message.call_count > 1:
        # Get the second call (confirmation message)
        confirmation_call = mock_bot.send_message.call_args_list[1]
        confirmation_text = confirmation_call[1]['text']
        print(f"\n📧 Confirmation message preview:")
        print("-" * 30)
        print(confirmation_text)
    
    print("\n4. Testing Message Formatting")
    print("-" * 30)
    
    # Test notification formatting
    formatted_message = broadcast_system._format_admin_notification(
        notification="Test notification",
        sender_id=regular_user.telegram_id,
        purchase_info=purchase_info
    )
    
    print("📧 Formatted notification:")
    print("-" * 30)
    print(formatted_message)
    
    print("\n✅ Admin Notification System Demo Complete!")
    print("=" * 50)


async def demonstrate_shop_integration():
    """
    Demonstrate integration between ShopManager and admin notifications
    """
    print("\n🛒 Shop Integration Demo")
    print("=" * 50)
    
    # This would normally be done with real database and bot instances
    print("📝 Integration Points:")
    print("1. ShopManager._activate_admin_item() calls BroadcastSystem.notify_admins()")
    print("2. Purchase information is formatted and sent to all admins")
    print("3. Purchase confirmation is sent to the buyer")
    print("4. Admin user management is handled by BroadcastSystem")
    
    print("\n🔄 Workflow:")
    print("1. User purchases admin item via /buy command")
    print("2. ShopManager processes purchase and validates balance")
    print("3. ShopManager activates admin item")
    print("4. BroadcastSystem sends notifications to all admins")
    print("5. BroadcastSystem sends confirmation to purchaser")
    print("6. Purchase is logged with notification status")
    
    print("\n✅ Shop Integration Demo Complete!")


if __name__ == "__main__":
    print("🚀 Starting Admin Notification System Demonstration")
    
    # Run the demonstrations
    asyncio.run(demonstrate_admin_notification_system())
    asyncio.run(demonstrate_shop_integration())
    
    print("\n🎉 All demonstrations completed successfully!")