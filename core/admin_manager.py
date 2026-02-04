"""
AdminManager class for Advanced Telegram Bot Features
Implements administrative functions including user statistics, parsing statistics, and admin broadcasts
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from decimal import Decimal

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import User, ParsedTransaction, ParsingRule, UserPurchase, ShopItem
from core.advanced_models import UserStats, ParsingStats, BroadcastResult
from core.broadcast_system import BroadcastSystem
from utils.admin_system import AdminSystem
import structlog

logger = structlog.get_logger()


class AdminManager:
    """
    Administrative management system for advanced bot features
    Implements Requirements 7.1, 7.2, 7.3, 8.2, 10.1, 10.2, 10.3
    """
    
    def __init__(self, db_session: Session, broadcast_system: BroadcastSystem = None, admin_system: AdminSystem = None):
        """
        Initialize AdminManager with database session and optional systems
        
        Args:
            db_session: SQLAlchemy database session
            broadcast_system: BroadcastSystem instance for admin broadcasts
            admin_system: AdminSystem instance for privilege checking
        """
        self.db = db_session
        self.broadcast_system = broadcast_system
        self.admin_system = admin_system  # Don't create default AdminSystem
        
        # Admin user IDs for fallback (Requirement 7.4, 8.2, 10.5)
        self.fallback_admin_ids = [2091908459]  # LucasTeamLuke
    
    async def get_user_stats(self, username: str) -> Optional[UserStats]:
        """
        Get comprehensive user statistics for administrative review
        
        Args:
            username: Username to look up (with or without @)
            
        Returns:
            UserStats object with comprehensive user information or None if user not found
            
        Validates: Requirements 10.1, 10.2, 10.3, 10.4
        """
        try:
            logger.info("Retrieving user statistics", username=username)
            
            # Clean username (remove @ if present)
            clean_username = username.lstrip('@')
            
            # Find user by username or first_name
            user = self.db.query(User).filter(
                or_(
                    User.username == clean_username,
                    User.first_name == clean_username,
                    User.username.like(f"%{clean_username}%"),
                    User.first_name.like(f"%{clean_username}%")
                )
            ).first()
            
            if not user:
                logger.warning("User not found for statistics", username=username)
                return None
            
            # Get current balance and basic info (Requirement 10.2)
            current_balance = user.balance or 0
            total_purchases = user.total_purchases or 0
            last_activity = user.last_activity or user.created_at
            
            # Get active subscriptions/permissions (Requirement 10.2)
            active_subscriptions = []
            if user.sticker_unlimited and user.sticker_unlimited_until:
                if user.sticker_unlimited_until > datetime.utcnow():
                    active_subscriptions.append({
                        'type': 'sticker_unlimited',
                        'expires_at': user.sticker_unlimited_until.isoformat(),
                        'description': 'Unlimited Sticker Access'
                    })
            
            if user.is_vip and user.vip_until:
                if user.vip_until > datetime.utcnow():
                    active_subscriptions.append({
                        'type': 'vip',
                        'expires_at': user.vip_until.isoformat(),
                        'description': 'VIP Status'
                    })
            
            if user.is_admin:
                active_subscriptions.append({
                    'type': 'admin',
                    'expires_at': None,
                    'description': 'Administrator'
                })
            
            # Get parsing transaction history (Requirement 10.3)
            parsing_transactions = self.db.query(ParsedTransaction).filter(
                ParsedTransaction.user_id == user.id
            ).order_by(ParsedTransaction.parsed_at.desc()).limit(10).all()
            
            parsing_history = []
            for transaction in parsing_transactions:
                parsing_history.append({
                    'id': transaction.id,
                    'source_bot': transaction.source_bot,
                    'original_amount': float(transaction.original_amount),
                    'converted_amount': float(transaction.converted_amount),
                    'currency_type': transaction.currency_type,
                    'parsed_at': transaction.parsed_at.isoformat(),
                    'message_preview': transaction.message_text[:100] if transaction.message_text else None
                })
            
            # Get recent purchases
            recent_purchases = self.db.query(UserPurchase).filter(
                UserPurchase.user_id == user.id
            ).order_by(UserPurchase.purchased_at.desc()).limit(5).all()
            
            purchase_history = []
            for purchase in recent_purchases:
                item = self.db.query(ShopItem).filter(ShopItem.id == purchase.item_id).first()
                purchase_history.append({
                    'id': purchase.id,
                    'item_name': item.name if item else 'Unknown Item',
                    'price_paid': purchase.purchase_price,
                    'purchased_at': purchase.purchased_at.isoformat(),
                    'expires_at': purchase.expires_at.isoformat() if purchase.expires_at else None,
                    'is_active': purchase.is_active
                })
            
            # Calculate total parsing earnings
            total_parsing_earnings = self.db.query(
                func.sum(ParsedTransaction.converted_amount)
            ).filter(ParsedTransaction.user_id == user.id).scalar() or Decimal('0')
            
            # Create UserStats object
            user_stats = UserStats(
                user_id=user.telegram_id,
                username=user.username,
                first_name=user.first_name,
                current_balance=current_balance,
                total_purchases=total_purchases,
                total_earned=user.total_earned or 0,
                total_parsing_earnings=float(total_parsing_earnings),
                last_activity=last_activity.isoformat(),
                created_at=user.created_at.isoformat(),
                active_subscriptions=active_subscriptions,
                parsing_transaction_history=parsing_history,
                recent_purchases=purchase_history,
                is_admin=user.is_admin or False,
                is_vip=user.is_vip or False,
                daily_streak=user.daily_streak or 0
            )
            
            logger.info(
                "User statistics retrieved successfully",
                username=username,
                user_id=user.telegram_id,
                balance=current_balance,
                total_purchases=total_purchases
            )
            
            return user_stats
            
        except Exception as e:
            logger.error("Error retrieving user statistics", error=str(e), username=username)
            return None
    
    async def get_parsing_stats(self, timeframe: str = "24h") -> Optional[ParsingStats]:
        """
        Get parsing statistics for administrative monitoring
        
        Args:
            timeframe: Time period for statistics ("24h", "7d", "30d")
            
        Returns:
            ParsingStats object with parsing system statistics
            
        Validates: Requirements 7.1, 7.2, 7.3
        """
        try:
            logger.info("Retrieving parsing statistics", timeframe=timeframe)
            
            # Calculate time boundaries
            now = datetime.utcnow()
            if timeframe == "24h":
                start_time = now - timedelta(hours=24)
                period_name = "Last 24 Hours"
            elif timeframe == "7d":
                start_time = now - timedelta(days=7)
                period_name = "Last 7 Days"
            elif timeframe == "30d":
                start_time = now - timedelta(days=30)
                period_name = "Last 30 Days"
            else:
                start_time = now - timedelta(hours=24)
                period_name = "Last 24 Hours"
                timeframe = "24h"
            
            # Get transactions within timeframe
            transactions = self.db.query(ParsedTransaction).filter(
                ParsedTransaction.parsed_at >= start_time
            ).all()
            
            # Calculate statistics by source bot (Requirement 7.2)
            stats_by_bot = {}
            total_transactions = len(transactions)
            total_amount_converted = Decimal('0')
            successful_parses = 0
            
            for transaction in transactions:
                bot_name = transaction.source_bot
                if bot_name not in stats_by_bot:
                    stats_by_bot[bot_name] = {
                        'bot_name': bot_name,
                        'transaction_count': 0,
                        'total_original_amount': Decimal('0'),
                        'total_converted_amount': Decimal('0'),
                        'successful_parses': 0,
                        'failed_parses': 0,
                        'currency_type': getattr(transaction, 'currency_type', 'unknown')
                    }
                
                stats_by_bot[bot_name]['transaction_count'] += 1
                
                # Handle both Decimal and Mock objects for testing
                original_amount = getattr(transaction, 'original_amount', Decimal('0'))
                converted_amount = getattr(transaction, 'converted_amount', Decimal('0'))
                
                if hasattr(original_amount, '__add__'):  # Check if it's a proper number
                    stats_by_bot[bot_name]['total_original_amount'] += original_amount
                if hasattr(converted_amount, '__add__'):  # Check if it's a proper number
                    stats_by_bot[bot_name]['total_converted_amount'] += converted_amount
                    total_amount_converted += converted_amount
                
                stats_by_bot[bot_name]['successful_parses'] += 1
                successful_parses += 1
            
            # Get parsing rules for context
            active_rules = self.db.query(ParsingRule).filter(
                ParsingRule.is_active == True
            ).all()
            
            parsing_rules_info = []
            for rule in active_rules:
                parsing_rules_info.append({
                    'id': rule.id,
                    'bot_name': rule.bot_name,
                    'pattern': rule.pattern,
                    'multiplier': float(rule.multiplier),
                    'currency_type': rule.currency_type,
                    'is_active': rule.is_active
                })
            
            # Calculate success rate and percentages (Requirement 7.3)
            total_configured_bots = len(active_rules)
            active_bots = len(stats_by_bot)
            success_rate = (successful_parses / max(total_transactions, 1)) * 100
            
            # Convert stats_by_bot to list for JSON serialization
            bot_statistics = []
            for bot_stats in stats_by_bot.values():
                bot_percentage = (bot_stats['transaction_count'] / max(total_transactions, 1)) * 100
                bot_statistics.append({
                    'bot_name': bot_stats['bot_name'],
                    'transaction_count': bot_stats['transaction_count'],
                    'total_original_amount': float(bot_stats['total_original_amount']),
                    'total_converted_amount': float(bot_stats['total_converted_amount']),
                    'successful_parses': bot_stats['successful_parses'],
                    'failed_parses': bot_stats['failed_parses'],
                    'currency_type': bot_stats['currency_type'],
                    'percentage_of_total': round(bot_percentage, 2)
                })
            
            # Create ParsingStats object
            parsing_stats = ParsingStats(
                timeframe=timeframe,
                period_name=period_name,
                start_time=start_time.isoformat(),
                end_time=now.isoformat(),
                total_transactions=total_transactions,
                successful_parses=successful_parses,
                failed_parses=0,  # We don't track failed parses separately yet
                total_amount_converted=float(total_amount_converted),
                success_rate=round(success_rate, 2),
                active_bots=active_bots,
                total_configured_bots=total_configured_bots,
                bot_statistics=bot_statistics,
                parsing_rules=parsing_rules_info
            )
            
            logger.info(
                "Parsing statistics retrieved successfully",
                timeframe=timeframe,
                total_transactions=total_transactions,
                total_amount=float(total_amount_converted),
                active_bots=active_bots
            )
            
            return parsing_stats
            
        except Exception as e:
            logger.error("Error retrieving parsing statistics", error=str(e), timeframe=timeframe)
            return None
    
    def is_admin(self, user_id: int) -> bool:
        """
        Check if user has administrator privileges
        
        Args:
            user_id: Telegram user ID to check
            
        Returns:
            True if user is an administrator, False otherwise
            
        Validates: Requirements 7.4, 8.2, 9.5, 10.5
        """
        try:
            # Check fallback admin IDs first
            if user_id in self.fallback_admin_ids:
                return True
            
            # Use AdminSystem if available
            if self.admin_system:
                return self.admin_system.is_admin(user_id)
            
            # Fallback to database check only if AdminSystem is not available
            user = self.db.query(User).filter(User.telegram_id == user_id).first()
            if user and user.is_admin:
                return True
            
            return False
            
        except Exception as e:
            logger.error("Error checking admin status", error=str(e), user_id=user_id)
            # Fallback to hardcoded admin IDs on error
            return user_id in self.fallback_admin_ids
    
    async def broadcast_admin_message(self, message: str, admin_id: int) -> Optional[BroadcastResult]:
        """
        Broadcast message to all users with admin verification
        
        Args:
            message: Message text to broadcast
            admin_id: ID of the admin sending the broadcast
            
        Returns:
            BroadcastResult if successful, None if unauthorized or failed
            
        Validates: Requirements 8.1, 8.2, 8.4, 8.5
        """
        try:
            logger.info("Processing admin broadcast request", admin_id=admin_id)
            
            # Verify admin privileges (Requirement 8.2)
            if not self.is_admin(admin_id):
                logger.warning("Unauthorized broadcast attempt", user_id=admin_id)
                return None
            
            # Use BroadcastSystem if available
            if self.broadcast_system:
                result = await self.broadcast_system.broadcast_to_all(message, admin_id)
                
                logger.info(
                    "Admin broadcast completed via BroadcastSystem",
                    admin_id=admin_id,
                    successful_sends=result.successful_sends,
                    failed_sends=result.failed_sends
                )
                
                return result
            else:
                logger.warning("BroadcastSystem not available for admin broadcast")
                return None
                
        except Exception as e:
            logger.error("Error in admin broadcast", error=str(e), admin_id=admin_id)
            return None
    
    def get_admin_user_ids(self) -> List[int]:
        """
        Get list of all administrator user IDs
        
        Returns:
            List of admin user Telegram IDs
        """
        try:
            # Get admins from database
            admin_users = self.db.query(User).filter(
                User.is_admin == True,
                User.telegram_id.isnot(None)
            ).all()
            
            admin_ids = [user.telegram_id for user in admin_users]
            
            # Add fallback admin IDs if no admins found
            if not admin_ids:
                admin_ids = self.fallback_admin_ids.copy()
            
            logger.info(f"Retrieved {len(admin_ids)} admin user IDs")
            return admin_ids
            
        except Exception as e:
            logger.error("Error getting admin user IDs", error=str(e))
            return self.fallback_admin_ids.copy()
    
    def add_admin_user(self, user_id: int) -> bool:
        """
        Add a user to the admin list
        
        Args:
            user_id: Telegram user ID to add as admin
            
        Returns:
            True if user was added successfully, False otherwise
        """
        try:
            user = self.db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                logger.warning("User not found for admin addition", user_id=user_id)
                return False
            
            if user.is_admin:
                logger.info("User is already an admin", user_id=user_id)
                return True
            
            user.is_admin = True
            self.db.commit()
            
            logger.info("User added as admin", user_id=user_id)
            return True
            
        except Exception as e:
            logger.error("Error adding admin user", error=str(e), user_id=user_id)
            self.db.rollback()
            return False
    
    def remove_admin_user(self, user_id: int) -> bool:
        """
        Remove a user from the admin list
        
        Args:
            user_id: Telegram user ID to remove from admin
            
        Returns:
            True if user was removed successfully, False otherwise
        """
        try:
            user = self.db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                logger.warning("User not found for admin removal", user_id=user_id)
                return False
            
            if not user.is_admin:
                logger.info("User is not an admin", user_id=user_id)
                return True
            
            user.is_admin = False
            self.db.commit()
            
            logger.info("User removed from admin", user_id=user_id)
            return True
            
        except Exception as e:
            logger.error("Error removing admin user", error=str(e), user_id=user_id)
            self.db.rollback()
            return False
    
    def get_system_stats(self) -> Dict[str, Any]:
        """
        Get general system statistics for admin overview
        
        Returns:
            Dictionary with system statistics
        """
        try:
            # Get user counts
            total_users = self.db.query(User).count()
            admin_users = self.db.query(User).filter(User.is_admin == True).count()
            vip_users = self.db.query(User).filter(User.is_vip == True).count()
            
            # Get recent activity (last 24 hours)
            yesterday = datetime.utcnow() - timedelta(hours=24)
            active_users_24h = self.db.query(User).filter(
                User.last_activity >= yesterday
            ).count()
            
            # Get parsing statistics
            total_parsed_transactions = self.db.query(ParsedTransaction).count()
            parsed_24h = self.db.query(ParsedTransaction).filter(
                ParsedTransaction.parsed_at >= yesterday
            ).count()
            
            # Get shop statistics
            total_purchases = self.db.query(UserPurchase).count()
            purchases_24h = self.db.query(UserPurchase).filter(
                UserPurchase.purchased_at >= yesterday
            ).count()
            
            return {
                'total_users': total_users,
                'admin_users': admin_users,
                'vip_users': vip_users,
                'active_users_24h': active_users_24h,
                'total_parsed_transactions': total_parsed_transactions,
                'parsed_transactions_24h': parsed_24h,
                'total_purchases': total_purchases,
                'purchases_24h': purchases_24h,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Error getting system statistics", error=str(e))
            return {
                'error': str(e),
                'generated_at': datetime.utcnow().isoformat()
            }