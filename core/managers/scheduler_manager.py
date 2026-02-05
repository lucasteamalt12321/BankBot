"""
SchedulerManager for the Telegram Bot Shop System
Manages APScheduler with SQLite persistence for delayed tasks
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import asdict
import json
import pytz

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.executors.pool import ThreadPoolExecutor
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    BackgroundScheduler = None
    SQLAlchemyJobStore = None
    ThreadPoolExecutor = None

from .shop_models import ScheduledTask, ShopError


logger = logging.getLogger(__name__)


class SchedulerError(ShopError):
    """Exception raised for scheduler-related errors"""
    pass


class SchedulerManager:
    """
    Manages APScheduler with SQLite persistence for delayed tasks
    Handles task scheduling, restoration, and cleanup
    """
    
    def __init__(self, db_url: str, scheduler_db_url: Optional[str] = None):
        """
        Initialize the SchedulerManager
        
        Args:
            db_url: Main database URL for storing task metadata
            scheduler_db_url: Separate database URL for APScheduler jobstore
        """
        if not APSCHEDULER_AVAILABLE:
            raise SchedulerError("APScheduler is not installed. Please install it with: pip install APScheduler")
        
        self.db_url = db_url
        self.scheduler_db_url = scheduler_db_url or db_url
        self.scheduler = None
        self._is_started = False
        
        # Configure timezone to UTC for consistency
        self.timezone = pytz.UTC
        
        self._setup_scheduler()
    
    def _setup_scheduler(self):
        """Configure APScheduler with SQLite persistence"""
        try:
            # Configure jobstore for persistence
            jobstores = {
                'default': SQLAlchemyJobStore(url=self.scheduler_db_url)
            }
            
            # Configure executors
            executors = {
                'default': ThreadPoolExecutor(20)
            }
            
            # Job defaults
            job_defaults = {
                'coalesce': False,
                'max_instances': 3,
                'misfire_grace_time': 30
            }
            
            # Create scheduler
            self.scheduler = BackgroundScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone=self.timezone
            )
            
            # Add event listeners
            self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
            self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
            
            logger.info("APScheduler configured with SQLite persistence")
            
        except Exception as e:
            logger.error(f"Failed to setup scheduler: {e}")
            raise SchedulerError(f"Failed to setup scheduler: {e}")
    
    def start(self):
        """Start the scheduler"""
        if not self._is_started and self.scheduler:
            try:
                self.scheduler.start()
                self._is_started = True
                logger.info("APScheduler started successfully")
            except Exception as e:
                logger.error(f"Failed to start scheduler: {e}")
                raise SchedulerError(f"Failed to start scheduler: {e}")
    
    def shutdown(self, wait: bool = True):
        """Shutdown the scheduler"""
        if self._is_started and self.scheduler:
            try:
                self.scheduler.shutdown(wait=wait)
                self._is_started = False
                logger.info("APScheduler shutdown successfully")
            except Exception as e:
                logger.error(f"Failed to shutdown scheduler: {e}")
    
    def schedule_message_deletion(self, user_id: int, chat_id: int, message_id: int, 
                                delay_hours: int = 24, task_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Schedule a message for deletion after specified delay
        
        Args:
            user_id: ID of the user who triggered the task
            chat_id: Chat ID where the message is located
            message_id: ID of the message to delete
            delay_hours: Hours to wait before deletion (default: 24)
            task_data: Additional data for the task
            
        Returns:
            Job ID for the scheduled task
        """
        if not self._is_started:
            raise SchedulerError("Scheduler is not started")
        
        # Calculate execution time
        execute_at = datetime.now(self.timezone) + timedelta(hours=delay_hours)
        
        # Create job ID
        job_id = f"delete_message_{user_id}_{message_id}_{int(execute_at.timestamp())}"
        
        try:
            # Store task metadata in database
            self._store_scheduled_task(
                user_id=user_id,
                chat_id=chat_id,
                message_id=message_id,
                task_type="message_deletion",
                execute_at=execute_at,
                task_data=task_data,
                job_id=job_id
            )
            
            # Schedule the job
            self.scheduler.add_job(
                func=self._execute_message_deletion,
                trigger='date',
                run_date=execute_at,
                args=[user_id, chat_id, message_id, task_data],
                id=job_id,
                replace_existing=True
            )
            
            logger.info(f"Scheduled message deletion: job_id={job_id}, execute_at={execute_at}")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to schedule message deletion: {e}")
            raise SchedulerError(f"Failed to schedule message deletion: {e}")
    
    def schedule_custom_task(self, user_id: int, chat_id: int, task_type: str,
                           execute_at: datetime, task_data: Optional[Dict[str, Any]] = None,
                           callback_func=None) -> str:
        """
        Schedule a custom task
        
        Args:
            user_id: ID of the user who triggered the task
            chat_id: Chat ID associated with the task
            task_type: Type of task to execute
            execute_at: When to execute the task
            task_data: Additional data for the task
            callback_func: Function to call when task executes
            
        Returns:
            Job ID for the scheduled task
        """
        if not self._is_started:
            raise SchedulerError("Scheduler is not started")
        
        # Ensure execute_at is timezone-aware
        if execute_at.tzinfo is None:
            execute_at = self.timezone.localize(execute_at)
        
        # Create job ID
        job_id = f"{task_type}_{user_id}_{int(execute_at.timestamp())}"
        
        try:
            # Store task metadata in database
            self._store_scheduled_task(
                user_id=user_id,
                chat_id=chat_id,
                task_type=task_type,
                execute_at=execute_at,
                task_data=task_data,
                job_id=job_id
            )
            
            # Use provided callback or default handler
            func = callback_func or self._execute_custom_task
            args = [user_id, chat_id, task_type, task_data] if not callback_func else [task_data]
            
            # Schedule the job
            self.scheduler.add_job(
                func=func,
                trigger='date',
                run_date=execute_at,
                args=args,
                id=job_id,
                replace_existing=True
            )
            
            logger.info(f"Scheduled custom task: job_id={job_id}, task_type={task_type}, execute_at={execute_at}")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to schedule custom task: {e}")
            raise SchedulerError(f"Failed to schedule custom task: {e}")
    
    def cancel_task(self, job_id: str) -> bool:
        """
        Cancel a scheduled task
        
        Args:
            job_id: ID of the job to cancel
            
        Returns:
            True if task was cancelled, False if not found
        """
        try:
            self.scheduler.remove_job(job_id)
            self._mark_task_completed(job_id)
            logger.info(f"Cancelled scheduled task: {job_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to cancel task {job_id}: {e}")
            return False
    
    def restore_scheduled_tasks(self):
        """
        Restore scheduled tasks from database on startup
        This method should be called after bot restart to restore pending tasks
        """
        if not self._is_started:
            self.start()
        
        try:
            # Get pending tasks from database
            pending_tasks = self._get_pending_tasks()
            
            restored_count = 0
            for task in pending_tasks:
                try:
                    # Check if task is still in the future
                    now = datetime.now(self.timezone)
                    if task.execute_at <= now:
                        # Task is overdue, mark as completed and skip
                        self._mark_task_completed_by_id(task.id)
                        logger.warning(f"Skipping overdue task: {task.id}")
                        continue
                    
                    # Restore the task based on its type
                    if task.task_type == "message_deletion":
                        job_id = f"delete_message_{task.user_id}_{task.message_id}_{int(task.execute_at.timestamp())}"
                        self.scheduler.add_job(
                            func=self._execute_message_deletion,
                            trigger='date',
                            run_date=task.execute_at,
                            args=[task.user_id, task.chat_id, task.message_id, task.task_data],
                            id=job_id,
                            replace_existing=True
                        )
                        restored_count += 1
                    else:
                        # Generic task restoration
                        job_id = f"{task.task_type}_{task.user_id}_{int(task.execute_at.timestamp())}"
                        self.scheduler.add_job(
                            func=self._execute_custom_task,
                            trigger='date',
                            run_date=task.execute_at,
                            args=[task.user_id, task.chat_id, task.task_type, task.task_data],
                            id=job_id,
                            replace_existing=True
                        )
                        restored_count += 1
                        
                except Exception as e:
                    logger.error(f"Failed to restore task {task.id}: {e}")
            
            logger.info(f"Restored {restored_count} scheduled tasks from database")
            
        except Exception as e:
            logger.error(f"Failed to restore scheduled tasks: {e}")
            raise SchedulerError(f"Failed to restore scheduled tasks: {e}")
    
    def get_pending_tasks_count(self) -> int:
        """Get count of pending tasks"""
        try:
            tasks = self._get_pending_tasks()
            return len(tasks)
        except Exception as e:
            logger.error(f"Failed to get pending tasks count: {e}")
            return 0
    
    def cleanup_completed_tasks(self, older_than_days: int = 7):
        """
        Clean up completed tasks older than specified days
        
        Args:
            older_than_days: Remove completed tasks older than this many days
        """
        try:
            cutoff_date = datetime.now(self.timezone) - timedelta(days=older_than_days)
            
            with sqlite3.connect(self.db_url.replace('sqlite:///', '')) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM scheduled_tasks 
                    WHERE is_completed = TRUE 
                    AND created_at < ?
                """, (cutoff_date,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
            logger.info(f"Cleaned up {deleted_count} completed tasks older than {older_than_days} days")
            
        except Exception as e:
            logger.error(f"Failed to cleanup completed tasks: {e}")
    
    def _store_scheduled_task(self, user_id: int, chat_id: int, task_type: str,
                            execute_at: datetime, task_data: Optional[Dict[str, Any]] = None,
                            message_id: Optional[int] = None, job_id: Optional[str] = None):
        """Store scheduled task metadata in database"""
        try:
            with sqlite3.connect(self.db_url.replace('sqlite:///', '')) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO scheduled_tasks 
                    (user_id, chat_id, message_id, task_type, execute_at, task_data, is_completed, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, FALSE, ?)
                """, (
                    user_id, chat_id, message_id, task_type, execute_at,
                    json.dumps(task_data) if task_data else None,
                    datetime.now(self.timezone)
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to store scheduled task: {e}")
            raise
    
    def _get_pending_tasks(self) -> List[ScheduledTask]:
        """Get all pending tasks from database"""
        try:
            with sqlite3.connect(self.db_url.replace('sqlite:///', '')) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, user_id, chat_id, message_id, task_type, execute_at, task_data, created_at
                    FROM scheduled_tasks 
                    WHERE is_completed = FALSE
                    ORDER BY execute_at ASC
                """)
                
                tasks = []
                for row in cursor.fetchall():
                    task_data = json.loads(row[6]) if row[6] else None
                    execute_at = datetime.fromisoformat(row[5])
                    if execute_at.tzinfo is None:
                        execute_at = self.timezone.localize(execute_at)
                    
                    created_at = datetime.fromisoformat(row[7]) if row[7] else None
                    if created_at and created_at.tzinfo is None:
                        created_at = self.timezone.localize(created_at)
                    
                    task = ScheduledTask(
                        id=row[0],
                        user_id=row[1],
                        chat_id=row[2],
                        message_id=row[3],
                        task_type=row[4],
                        execute_at=execute_at,
                        task_data=task_data,
                        is_completed=False,
                        created_at=created_at
                    )
                    tasks.append(task)
                
                return tasks
                
        except Exception as e:
            logger.error(f"Failed to get pending tasks: {e}")
            return []
    
    def _mark_task_completed(self, job_id: str):
        """Mark a task as completed by job_id"""
        # This is a simplified approach - in a real implementation,
        # you might want to store job_id in the database for easier lookup
        pass
    
    def _mark_task_completed_by_id(self, task_id: int):
        """Mark a task as completed by database ID"""
        try:
            with sqlite3.connect(self.db_url.replace('sqlite:///', '')) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE scheduled_tasks 
                    SET is_completed = TRUE 
                    WHERE id = ?
                """, (task_id,))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to mark task {task_id} as completed: {e}")
    
    def _execute_message_deletion(self, user_id: int, chat_id: int, message_id: int, 
                                task_data: Optional[Dict[str, Any]] = None):
        """
        Execute message deletion task
        This is a placeholder - actual implementation should integrate with bot
        """
        logger.info(f"Executing message deletion: user_id={user_id}, chat_id={chat_id}, message_id={message_id}")
        
        # Mark task as completed in database
        try:
            with sqlite3.connect(self.db_url.replace('sqlite:///', '')) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE scheduled_tasks 
                    SET is_completed = TRUE 
                    WHERE user_id = ? AND message_id = ? AND task_type = 'message_deletion' AND is_completed = FALSE
                """, (user_id, message_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to mark message deletion task as completed: {e}")
        
        # TODO: Integrate with actual bot to delete message and send expiration notice
        # This would typically call bot.delete_message(chat_id, message_id)
        # and bot.send_message(chat_id, "Время действия стикеров истекло!")
    
    def _execute_custom_task(self, user_id: int, chat_id: int, task_type: str, 
                           task_data: Optional[Dict[str, Any]] = None):
        """
        Execute custom task
        This is a placeholder for custom task execution
        """
        logger.info(f"Executing custom task: user_id={user_id}, chat_id={chat_id}, task_type={task_type}")
        
        # Mark task as completed in database
        try:
            with sqlite3.connect(self.db_url.replace('sqlite:///', '')) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE scheduled_tasks 
                    SET is_completed = TRUE 
                    WHERE user_id = ? AND task_type = ? AND is_completed = FALSE
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (user_id, task_type))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to mark custom task as completed: {e}")
    
    def _job_executed(self, event):
        """Handle job execution events"""
        logger.info(f"Job executed successfully: {event.job_id}")
    
    def _job_error(self, event):
        """Handle job error events"""
        logger.error(f"Job failed: {event.job_id}, exception: {event.exception}")