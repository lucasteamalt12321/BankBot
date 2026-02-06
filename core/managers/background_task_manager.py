"""
BackgroundTaskManager class for Advanced Telegram Bot Features
Implements background task management with periodic cleanup and system monitoring
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import User, ParsedTransaction, ParsingRule
from core.models.advanced_models import CleanupResult, HealthStatus, BackgroundTaskError
from core.managers.sticker_manager import StickerManager
import structlog

logger = structlog.get_logger()


class BackgroundTaskManager:
    """
    Manages background tasks for the advanced bot features
    Implements Requirements 12.1, 12.2, 12.3, 12.4, 12.5
    """
    
    def __init__(self, db_session: Session, sticker_manager: Optional[StickerManager] = None):
        """
        Initialize BackgroundTaskManager with database session
        
        Args:
            db_session: SQLAlchemy database session
            sticker_manager: Optional StickerManager instance for sticker cleanup
        """
        self.db = db_session
        self.sticker_manager = sticker_manager or StickerManager(db_session)
        self.is_running = False
        self.cleanup_task = None
        self.monitoring_task = None
        
        # Configuration from requirements
        self.cleanup_interval_seconds = 300  # 5 minutes (Requirement 12.1)
        self.monitoring_interval_seconds = 60  # 1 minute for health monitoring
        
        logger.info("BackgroundTaskManager initialized", 
                   cleanup_interval=self.cleanup_interval_seconds,
                   monitoring_interval=self.monitoring_interval_seconds)
    
    async def start_periodic_cleanup(self) -> None:
        """
        Start periodic cleanup tasks with 5-minute intervals
        
        Validates: Requirements 12.1, 12.4, 12.5
        """
        if self.is_running:
            logger.warning("Background tasks are already running")
            return
        
        try:
            logger.info("Starting periodic background cleanup tasks")
            self.is_running = True
            
            # Start cleanup task
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup_loop())
            
            # Start monitoring task
            self.monitoring_task = asyncio.create_task(self._periodic_monitoring_loop())
            
            logger.info("Background tasks started successfully")
            
        except Exception as e:
            logger.error("Failed to start background tasks", error=str(e))
            self.is_running = False
            raise BackgroundTaskError(f"Failed to start background tasks: {str(e)}")
    
    async def stop_periodic_cleanup(self) -> None:
        """
        Stop all periodic background tasks gracefully
        
        Validates: Requirements 12.5
        """
        if not self.is_running:
            logger.info("Background tasks are not running")
            return
        
        try:
            logger.info("Stopping periodic background tasks")
            self.is_running = False
            
            # Cancel cleanup task
            if self.cleanup_task and not self.cleanup_task.done():
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    logger.debug("Cleanup task cancelled successfully")
            
            # Cancel monitoring task
            if self.monitoring_task and not self.monitoring_task.done():
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    logger.debug("Monitoring task cancelled successfully")
            
            logger.info("Background tasks stopped successfully")
            
        except Exception as e:
            logger.error("Error stopping background tasks", error=str(e))
            raise BackgroundTaskError(f"Error stopping background tasks: {str(e)}")
    
    async def cleanup_expired_access(self) -> CleanupResult:
        """
        Clean up expired sticker access and other expired features
        
        Returns:
            CleanupResult with cleanup statistics
            
        Validates: Requirements 12.2, 12.3, 12.4, 12.5
        """
        try:
            logger.info("Starting cleanup of expired access")
            
            errors = []
            cleaned_users = 0
            cleaned_files = 0
            
            # Clean up expired sticker access (Requirement 12.2)
            try:
                sticker_cleanup_count = await self.sticker_manager.cleanup_expired_stickers()
                cleaned_users += sticker_cleanup_count
                
                logger.info("Sticker access cleanup completed", 
                           cleaned_users=sticker_cleanup_count)
                
            except Exception as e:
                error_msg = f"Error cleaning up sticker access: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
            
            # Clean up expired VIP access
            try:
                vip_cleanup_count = await self._cleanup_expired_vip_access()
                cleaned_users += vip_cleanup_count
                
                logger.info("VIP access cleanup completed", 
                           cleaned_users=vip_cleanup_count)
                
            except Exception as e:
                error_msg = f"Error cleaning up VIP access: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
            
            # Clean up old parsing transactions (older than 90 days)
            try:
                transaction_cleanup_count = await self._cleanup_old_transactions()
                cleaned_files += transaction_cleanup_count
                
                logger.info("Old transactions cleanup completed", 
                           cleaned_transactions=transaction_cleanup_count)
                
            except Exception as e:
                error_msg = f"Error cleaning up old transactions: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
            
            # Create completion message
            completion_message = f"Cleanup completed: {cleaned_users} users, {cleaned_files} files"
            if errors:
                completion_message += f" with {len(errors)} errors"
            
            result = CleanupResult(
                cleaned_users=cleaned_users,
                cleaned_files=cleaned_files,
                errors=errors,
                completion_message=completion_message
            )
            
            logger.info("Cleanup operation completed", 
                       cleaned_users=cleaned_users,
                       cleaned_files=cleaned_files,
                       error_count=len(errors))
            
            return result
            
        except Exception as e:
            logger.error("Critical error during cleanup operation", error=str(e))
            return CleanupResult(
                cleaned_users=0,
                cleaned_files=0,
                errors=[f"Critical cleanup error: {str(e)}"],
                completion_message="Cleanup failed due to critical error"
            )
    
    async def monitor_parsing_health(self) -> HealthStatus:
        """
        Monitor the health of the parsing system and overall bot status
        
        Returns:
            HealthStatus with system health information
            
        Validates: Requirements 12.4
        """
        try:
            logger.debug("Monitoring parsing system health")
            
            errors = []
            is_healthy = True
            parsing_active = False
            background_tasks_running = self.is_running
            database_connected = False
            
            # Check database connectivity
            try:
                # Simple query to test database connection
                user_count = self.db.query(User).count()
                database_connected = True
                logger.debug("Database connectivity check passed", user_count=user_count)
                
            except Exception as e:
                database_connected = False
                error_msg = f"Database connectivity error: {str(e)}"
                errors.append(error_msg)
                is_healthy = False
                logger.error(error_msg)
            
            # Check parsing system activity (last 10 minutes)
            try:
                ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
                recent_transactions = self.db.query(ParsedTransaction).filter(
                    ParsedTransaction.parsed_at >= ten_minutes_ago
                ).count()
                
                # Consider parsing active if there were transactions in the last 10 minutes
                # or if there are active parsing rules
                active_rules = self.db.query(ParsingRule).filter(
                    ParsingRule.is_active == True
                ).count()
                
                parsing_active = recent_transactions > 0 or active_rules > 0
                
                logger.debug("Parsing system health check completed", 
                           recent_transactions=recent_transactions,
                           active_rules=active_rules,
                           parsing_active=parsing_active)
                
            except Exception as e:
                error_msg = f"Parsing system health check error: {str(e)}"
                errors.append(error_msg)
                is_healthy = False
                logger.error(error_msg)
            
            # Check for system errors in the last hour
            try:
                # This is a placeholder for more sophisticated error monitoring
                # In a real implementation, you might check error logs or metrics
                pass
                
            except Exception as e:
                error_msg = f"System error monitoring failed: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
            
            # Overall health assessment
            if not database_connected or not background_tasks_running:
                is_healthy = False
            
            health_status = HealthStatus(
                is_healthy=is_healthy,
                parsing_active=parsing_active,
                background_tasks_running=background_tasks_running,
                database_connected=database_connected,
                last_check=datetime.utcnow(),
                errors=errors
            )
            
            if is_healthy:
                logger.debug("System health check passed")
            else:
                logger.warning("System health check failed", 
                              error_count=len(errors),
                              errors=errors)
            
            return health_status
            
        except Exception as e:
            logger.error("Critical error during health monitoring", error=str(e))
            return HealthStatus(
                is_healthy=False,
                parsing_active=False,
                background_tasks_running=False,
                database_connected=False,
                last_check=datetime.utcnow(),
                errors=[f"Critical monitoring error: {str(e)}"]
            )
    
    async def _periodic_cleanup_loop(self) -> None:
        """
        Internal method for running periodic cleanup tasks
        
        Validates: Requirements 12.1, 12.5
        """
        logger.info("Starting periodic cleanup loop", 
                   interval_seconds=self.cleanup_interval_seconds)
        
        while self.is_running:
            try:
                # Perform cleanup
                cleanup_result = await self.cleanup_expired_access()
                
                # Log cleanup results (Requirement 12.4)
                logger.info("Periodic cleanup completed", 
                           cleaned_users=cleanup_result.cleaned_users,
                           cleaned_files=cleanup_result.cleaned_files,
                           error_count=len(cleanup_result.errors))
                
                if cleanup_result.errors:
                    logger.warning("Cleanup completed with errors", 
                                  errors=cleanup_result.errors)
                
            except Exception as e:
                # Handle errors gracefully and continue operation (Requirement 12.5)
                logger.error("Error in periodic cleanup loop", error=str(e))
            
            # Wait for next cleanup cycle
            try:
                await asyncio.sleep(self.cleanup_interval_seconds)
            except asyncio.CancelledError:
                logger.info("Periodic cleanup loop cancelled")
                break
        
        logger.info("Periodic cleanup loop stopped")
    
    async def _periodic_monitoring_loop(self) -> None:
        """
        Internal method for running periodic health monitoring
        
        Validates: Requirements 12.4, 12.5
        """
        logger.info("Starting periodic monitoring loop", 
                   interval_seconds=self.monitoring_interval_seconds)
        
        while self.is_running:
            try:
                # Perform health monitoring
                health_status = await self.monitor_parsing_health()
                
                # Log health status (Requirement 12.4)
                if health_status.is_healthy:
                    logger.debug("System health monitoring passed")
                else:
                    logger.warning("System health issues detected", 
                                  errors=health_status.errors)
                
            except Exception as e:
                # Handle errors gracefully and continue operation (Requirement 12.5)
                logger.error("Error in periodic monitoring loop", error=str(e))
            
            # Wait for next monitoring cycle
            try:
                await asyncio.sleep(self.monitoring_interval_seconds)
            except asyncio.CancelledError:
                logger.info("Periodic monitoring loop cancelled")
                break
        
        logger.info("Periodic monitoring loop stopped")
    
    async def _cleanup_expired_vip_access(self) -> int:
        """
        Clean up expired VIP access for users
        
        Returns:
            Number of users whose VIP access was cleaned up
        """
        try:
            current_time = datetime.utcnow()
            
            # Find users with expired VIP access
            expired_vip_users = self.db.query(User).filter(
                User.is_vip == True,
                User.vip_until <= current_time
            ).all()
            
            cleanup_count = 0
            
            for user in expired_vip_users:
                try:
                    logger.info("Cleaning up expired VIP access", 
                               user_id=user.telegram_id,
                               username=user.username,
                               expired_at=user.vip_until)
                    
                    user.is_vip = False
                    user.vip_until = None
                    cleanup_count += 1
                    
                except Exception as user_error:
                    logger.error("Error cleaning up individual VIP user", 
                                error=str(user_error),
                                user_id=user.telegram_id)
                    continue
            
            # Commit changes
            if cleanup_count > 0:
                self.db.commit()
                logger.info(f"Cleaned up expired VIP access for {cleanup_count} users")
            
            return cleanup_count
            
        except Exception as e:
            logger.error("Error during VIP access cleanup", error=str(e))
            self.db.rollback()
            return 0
    
    async def _cleanup_old_transactions(self, days_old: int = 90) -> int:
        """
        Clean up old parsing transactions to prevent database bloat
        
        Args:
            days_old: Remove transactions older than this many days
            
        Returns:
            Number of transactions cleaned up
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # Count old transactions before deletion
            old_transactions = self.db.query(ParsedTransaction).filter(
                ParsedTransaction.parsed_at < cutoff_date
            )
            
            transaction_count = old_transactions.count()
            
            if transaction_count > 0:
                # Delete old transactions
                old_transactions.delete()
                self.db.commit()
                
                logger.info(f"Cleaned up {transaction_count} old transactions", 
                           cutoff_date=cutoff_date,
                           days_old=days_old)
            else:
                logger.debug("No old transactions found to clean up")
            
            return transaction_count
            
        except Exception as e:
            logger.error("Error during transaction cleanup", error=str(e))
            self.db.rollback()
            return 0
    
    def get_task_status(self) -> Dict[str, Any]:
        """
        Get current status of background tasks
        
        Returns:
            Dictionary with task status information
        """
        return {
            'is_running': self.is_running,
            'cleanup_interval_seconds': self.cleanup_interval_seconds,
            'monitoring_interval_seconds': self.monitoring_interval_seconds,
            'cleanup_task_running': self.cleanup_task is not None and not self.cleanup_task.done(),
            'monitoring_task_running': self.monitoring_task is not None and not self.monitoring_task.done(),
            'last_status_check': datetime.utcnow().isoformat()
        }