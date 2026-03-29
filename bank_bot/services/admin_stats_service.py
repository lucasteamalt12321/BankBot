"""Admin stats service for business logic related to admin statistics."""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from decimal import Decimal

from database.database import User, ParsedTransaction, ParsingRule, UserPurchase, ShopItem
from core.models.advanced_models import UserStats, ParsingStats
import structlog

logger = structlog.get_logger()


class AdminStatsService:
    """
    Сервис для получения статистики администратора.
    
    Содержит бизнес-логику связанную с получением статистики пользователей и парсинга.
    """

    def __init__(self, db_session: Session):
        """
        Инициализация сервиса статистики администратора.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session

    async def get_user_stats(self, username: str) -> Optional[UserStats]:
        """
        Получить комплексную статистику пользователя для административного обзора.

        Args:
            username: Username для поиска (с или без @)

        Returns:
            UserStats object with comprehensive user information or None if user not found
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
            
            # Get current balance and basic info
            current_balance = user.balance or 0
            total_purchases = user.total_purchases or 0
            last_activity = user.last_activity or user.created_at
            
            # Get active subscriptions/permissions
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
            
            # Get parsing transaction history
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
        Получить статистику парсинга для административного мониторинга.

        Args:
            timeframe: Time period for statistics ("24h", "7d", "30d")

        Returns:
            ParsingStats object with parsing system statistics
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
            
            # Calculate statistics by source bot
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
                
                if hasattr(original_amount, '__add__'):
                    stats_by_bot[bot_name]['total_original_amount'] += original_amount
                if hasattr(converted_amount, '__add__'):
                    stats_by_bot[bot_name]['total_converted_amount'] += converted_amount
                    total_amount_converted += converted_amount
                
                stats_by_bot[bot_name]['successful_parses'] += 1
                successful_parses += 1
            
            # Get parsing rules for context
            active_rules = self.db.query(ParsingRule).filter(
                ParsingRule.is_active
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
            
            # Calculate success rate and percentages
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
                failed_parses=0,
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

    def get_system_stats(self) -> Dict[str, Any]:
        """
        Получить общую статистику системы для административного обзора.

        Returns:
            Dictionary with system statistics
        """
        try:
            # Get user counts
            total_users = self.db.query(User).count()
            admin_users = self.db.query(User).filter(User.is_admin).count()
            vip_users = self.db.query(User).filter(User.is_vip).count()
            
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
