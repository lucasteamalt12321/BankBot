"""User repository for specialized user data access operations."""

from typing import Optional
from src.repository.base import BaseRepository
from database.database import User


class UserRepository(BaseRepository[User]):
    """
    Repository for User model with specialized query methods.
    
    Extends BaseRepository to provide user-specific data access operations
    such as finding users by Telegram ID, username, or creating users
    with get-or-create pattern.
    
    Example:
        >>> from database.database import SessionLocal
        >>> session = SessionLocal()
        >>> user_repo = UserRepository(User, session)
        >>> user = user_repo.get_by_telegram_id(123456789)
        >>> user = user_repo.get_or_create(telegram_id=123456789, username="john")
    """
    
    def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """
        Get a user by their Telegram ID.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            User instance if found, None otherwise
            
        Example:
            >>> user = user_repo.get_by_telegram_id(123456789)
            >>> if user:
            ...     print(f"Found user: {user.username}")
        """
        return self.session.query(self.model).filter_by(
            telegram_id=telegram_id
        ).first()
    
    def get_by_username(self, username: str) -> Optional[User]:
        """
        Get a user by their username.
        
        Args:
            username: Username to search for
            
        Returns:
            User instance if found, None otherwise
            
        Example:
            >>> user = user_repo.get_by_username("john_doe")
            >>> if user:
            ...     print(f"User ID: {user.telegram_id}")
        """
        return self.session.query(self.model).filter_by(
            username=username
        ).first()
    
    def get_or_create(self, telegram_id: int, **kwargs) -> User:
        """
        Get an existing user by Telegram ID or create a new one.
        
        This method implements the get-or-create pattern, which is useful
        for user registration where we want to ensure a user exists without
        creating duplicates.
        
        Args:
            telegram_id: Telegram user ID (required)
            **kwargs: Additional fields for user creation (username, first_name, etc.)
            
        Returns:
            Existing or newly created User instance
            
        Example:
            >>> user = user_repo.get_or_create(
            ...     telegram_id=123456789,
            ...     username="john_doe",
            ...     first_name="John"
            ... )
            >>> # If user exists, returns existing user
            >>> # If user doesn't exist, creates and returns new user
        """
        user = self.get_by_telegram_id(telegram_id)
        if not user:
            user = self.create(telegram_id=telegram_id, **kwargs)
        return user
    
    def get_all_admins(self):
        """
        Get all users with admin privileges.
        
        Returns:
            List of User instances with is_admin=True
            
        Example:
            >>> admins = user_repo.get_all_admins()
            >>> for admin in admins:
            ...     print(f"Admin: {admin.username}")
        """
        return self.session.query(self.model).filter_by(is_admin=True).all()
    
    def get_all_vips(self):
        """
        Get all users with active VIP status.
        
        Returns:
            List of User instances with is_vip=True
            
        Example:
            >>> vips = user_repo.get_all_vips()
            >>> for vip in vips:
            ...     print(f"VIP: {vip.username}, expires: {vip.vip_until}")
        """
        return self.session.query(self.model).filter_by(is_vip=True).all()
    
    def get_users_with_balance_above(self, min_balance: int):
        """
        Get all users with balance greater than or equal to specified amount.
        
        Args:
            min_balance: Minimum balance threshold
            
        Returns:
            List of User instances with balance >= min_balance
            
        Example:
            >>> rich_users = user_repo.get_users_with_balance_above(1000)
            >>> for user in rich_users:
            ...     print(f"{user.username}: {user.balance}")
        """
        return self.session.query(self.model).filter(
            self.model.balance >= min_balance
        ).all()
    
    def get_active_users_since(self, since_datetime):
        """
        Get all users who were active since the specified datetime.
        
        Args:
            since_datetime: Datetime threshold for last activity
            
        Returns:
            List of User instances with last_activity >= since_datetime
            
        Example:
            >>> from datetime import datetime, timedelta
            >>> yesterday = datetime.utcnow() - timedelta(days=1)
            >>> active_users = user_repo.get_active_users_since(yesterday)
            >>> print(f"Active users in last 24h: {len(active_users)}")
        """
        return self.session.query(self.model).filter(
            self.model.last_activity >= since_datetime
        ).all()
    
    def get_users_with_expired_vip(self, current_time):
        """
        Get all users with expired VIP status.
        
        Args:
            current_time: Current datetime to compare against vip_until
            
        Returns:
            List of User instances with is_vip=True and vip_until <= current_time
            
        Example:
            >>> from datetime import datetime
            >>> now = datetime.utcnow()
            >>> expired_vips = user_repo.get_users_with_expired_vip(now)
            >>> for user in expired_vips:
            ...     print(f"Expired VIP: {user.username}")
        """
        return self.session.query(self.model).filter(
            self.model.is_vip == True,
            self.model.vip_until <= current_time
        ).all()
    
    def get_users_with_expired_stickers(self, current_time):
        """
        Get all users with expired unlimited sticker access.
        
        Args:
            current_time: Current datetime to compare against sticker_unlimited_until
            
        Returns:
            List of User instances with sticker_unlimited=True and expired access
            
        Example:
            >>> from datetime import datetime
            >>> now = datetime.utcnow()
            >>> expired_stickers = user_repo.get_users_with_expired_stickers(now)
            >>> for user in expired_stickers:
            ...     print(f"Expired stickers: {user.username}")
        """
        return self.session.query(self.model).filter(
            self.model.sticker_unlimited == True,
            self.model.sticker_unlimited_until <= current_time
        ).all()
    
    def count_total_users(self) -> int:
        """
        Get total count of all users.
        
        Returns:
            Total number of users in the database
            
        Example:
            >>> total = user_repo.count_total_users()
            >>> print(f"Total users: {total}")
        """
        return self.session.query(self.model).count()
    
    def count_admins(self) -> int:
        """
        Get count of admin users.
        
        Returns:
            Number of users with is_admin=True
            
        Example:
            >>> admin_count = user_repo.count_admins()
            >>> print(f"Total admins: {admin_count}")
        """
        return self.session.query(self.model).filter_by(is_admin=True).count()
    
    def count_vips(self) -> int:
        """
        Get count of VIP users.
        
        Returns:
            Number of users with is_vip=True
            
        Example:
            >>> vip_count = user_repo.count_vips()
            >>> print(f"Total VIPs: {vip_count}")
        """
        return self.session.query(self.model).filter_by(is_vip=True).count()
    
    def get_top_users_by_balance(self, limit: int = 10):
        """
        Get top users ordered by balance (highest first).
        
        Args:
            limit: Maximum number of users to return (default: 10)
            
        Returns:
            List of User instances ordered by balance descending
            
        Example:
            >>> top_users = user_repo.get_top_users_by_balance(5)
            >>> for i, user in enumerate(top_users, 1):
            ...     print(f"{i}. {user.username}: {user.balance}")
        """
        return self.session.query(self.model).order_by(
            self.model.balance.desc()
        ).limit(limit).all()
    
    def get_top_users_by_earnings(self, limit: int = 10):
        """
        Get top users ordered by total earnings (highest first).
        
        Args:
            limit: Maximum number of users to return (default: 10)
            
        Returns:
            List of User instances ordered by total_earned descending
            
        Example:
            >>> top_earners = user_repo.get_top_users_by_earnings(5)
            >>> for i, user in enumerate(top_earners, 1):
            ...     print(f"{i}. {user.username}: {user.total_earned}")
        """
        return self.session.query(self.model).order_by(
            self.model.total_earned.desc()
        ).limit(limit).all()
    
    def bulk_update_balance(self, user_ids: list, amount: int):
        """
        Update balance for multiple users at once.
        
        Args:
            user_ids: List of user IDs to update
            amount: Amount to add to each user's balance (can be negative)
            
        Returns:
            Number of users updated
            
        Example:
            >>> updated = user_repo.bulk_update_balance([1, 2, 3], 100)
            >>> print(f"Updated {updated} users")
        """
        count = self.session.query(self.model).filter(
            self.model.id.in_(user_ids)
        ).update(
            {self.model.balance: self.model.balance + amount},
            synchronize_session=False
        )
        self.session.commit()
        return count
