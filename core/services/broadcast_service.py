"""Broadcast service for business logic related to message broadcasting."""

import asyncio
import logging
from typing import List
from sqlalchemy.orm import Session
from telegram import Bot
from telegram.error import TelegramError, BadRequest, Forbidden

from database.database import User
from core.models.advanced_models import BroadcastResult, NotificationResult

logger = logging.getLogger(__name__)


class BroadcastService:
    """
    Сервис для рассылки сообщений пользователям.
    
    Содержит бизнес-логику связанную с массовой рассылкой сообщений.
    """

    def __init__(self, db: Session, bot: Bot):
        """
        Инициализация сервиса рассылки.

        Args:
            db: Database session
            bot: Telegram bot instance
        """
        self.db = db
        self.bot = bot
        self.batch_size = 50
        self.rate_limit_delay = 0.15
        self.max_retries = 3

    async def broadcast_to_all(self, message: str, sender_id: int) -> BroadcastResult:
        """
        Рассылка сообщения всем зарегистрированным пользователям.

        Args:
            message: Message text to broadcast
            sender_id: ID of the user sending the broadcast

        Returns:
            BroadcastResult: Results of the broadcast operation
        """
        import time
        start_time = time.time()

        try:
            logger.info(f"Starting broadcast to all users from sender {sender_id}")

            all_users = self.db.query(User).filter(User.telegram_id.isnot(None)).all()

            if not all_users:
                return BroadcastResult(
                    total_users=0,
                    successful_sends=0,
                    failed_sends=0,
                    errors=["No registered users found"],
                    completion_message="No users to broadcast to",
                    execution_time=time.time() - start_time
                )

            sender_user = self.db.query(User).filter(User.telegram_id == sender_id).first()
            sender_name = sender_user.first_name if sender_user and sender_user.first_name else f"User #{sender_id}"

            formatted_message = f"📢 <b>Объявление от {sender_name}:</b>\n\n{message}"

            result = await self._process_broadcast_batches(
                users=all_users,
                message=formatted_message,
                sender_id=sender_id
            )

            result.execution_time = time.time() - start_time

            logger.info(f"Broadcast completed: {result.successful_sends}/{result.total_users} successful")
            return result

        except Exception as e:
            logger.error(f"Error in broadcast_to_all: {e}")
            raise Exception(f"Failed to broadcast message: {str(e)}")

    async def notify_admins(self, notification: str, sender_id: int = None, purchase_info: dict = None) -> NotificationResult:
        """
        Отправка уведомления всем администраторам.

        Args:
            notification: Notification message
            sender_id: ID of the user who triggered the notification (optional)
            purchase_info: Dictionary with purchase details for admin item notifications

        Returns:
            NotificationResult: Results of the notification operation
        """
        try:
            logger.info(f"Sending admin notification from sender {sender_id}")

            admin_users = self.db.query(User).filter(
                User.is_admin,
                User.telegram_id.isnot(None)
            ).all()

            fallback_admin_ids = [2091908459]

            if not admin_users:
                admin_users = self.db.query(User).filter(
                    User.telegram_id.in_(fallback_admin_ids)
                ).all()

                if not admin_users:
                    logger.warning("No admin users found for notification")
                    return NotificationResult(
                        success=False,
                        message="No admin users found",
                        notified_admins=0,
                        failed_notifications=0
                    )

            formatted_notification = self._format_admin_notification(
                notification, sender_id, purchase_info
            )

            successful_sends = 0
            failed_sends = 0
            errors = []

            for admin_user in admin_users:
                try:
                    await self.bot.send_message(
                        chat_id=admin_user.telegram_id,
                        text=formatted_notification,
                        parse_mode='HTML'
                    )
                    successful_sends += 1
                    logger.debug(f"Notification sent to admin {admin_user.telegram_id}")

                    await asyncio.sleep(self.rate_limit_delay)

                except Exception as e:
                    failed_sends += 1
                    error_msg = f"Failed to notify admin {admin_user.telegram_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.warning(error_msg)

            success = successful_sends > 0
            message = f"Notified {successful_sends} administrators"
            if failed_sends > 0:
                message += f", {failed_sends} failed"

            logger.info(f"Admin notification completed: {successful_sends} successful, {failed_sends} failed")

            return NotificationResult(
                success=success,
                message=message,
                notified_admins=successful_sends,
                failed_notifications=failed_sends
            )

        except Exception as e:
            logger.error(f"Error in notify_admins: {e}")
            return NotificationResult(
                success=False,
                message=f"Failed to send admin notifications: {str(e)}",
                notified_admins=0,
                failed_notifications=0
            )

    def _format_admin_notification(self, notification: str, sender_id: int = None, purchase_info: dict = None) -> str:
        """
        Форматирование сообщения уведомления администратора.

        Args:
            notification: Base notification message
            sender_id: ID of the user who triggered the notification
            purchase_info: Dictionary with purchase details

        Returns:
            Formatted notification message
        """
        try:
            from datetime import datetime

            if purchase_info:
                header = "🛒 <b>Уведомление о покупке админ-товара</b>"
            else:
                header = "🔔 <b>Уведомление для администраторов</b>"

            sender_info = ""
            if sender_id:
                sender_user = self.db.query(User).filter(User.telegram_id == sender_id).first()
                if sender_user:
                    sender_info = f"👤 <b>Пользователь:</b> {sender_user.first_name or 'Unknown'}"
                    if sender_user.username:
                        sender_info += f" (@{sender_user.username})"
                    sender_info += f"\n🆔 <b>ID:</b> {sender_id}"
                    if sender_user.balance is not None:
                        sender_info += f"\n💰 <b>Баланс:</b> {sender_user.balance}"
                else:
                    sender_info = f"👤 <b>Пользователь ID:</b> {sender_id}"

            timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            time_info = f"⏰ <b>Время:</b> {timestamp}"

            purchase_details = ""
            if purchase_info:
                item_name = purchase_info.get('item_name', 'Unknown')
                item_price = purchase_info.get('item_price', 'Unknown')
                purchase_id = purchase_info.get('purchase_id', 'Unknown')

                purchase_details = "\n\n🛍️ <b>Детали покупки:</b>"
                purchase_details += f"\n📦 <b>Товар:</b> {item_name}"
                purchase_details += f"\n💵 <b>Цена:</b> {item_price}"
                purchase_details += f"\n🔢 <b>ID покупки:</b> {purchase_id}"

            parts = [header]
            if sender_info:
                parts.append(sender_info)
            parts.append(time_info)
            if purchase_details:
                parts.append(purchase_details)
            if notification and notification.strip():
                parts.append(f"\n📝 <b>Сообщение:</b>\n{notification}")

            return "\n\n".join(parts)

        except Exception as e:
            logger.error(f"Error formatting admin notification: {e}")
            return f"🔔 <b>Уведомление для администраторов</b>\n\n{notification}"

    async def _process_broadcast_batches(
        self, 
        users: List[User], 
        message: str, 
        sender_id: int
    ) -> BroadcastResult:
        """
        Обработка рассылки пакетами с асинхронной доставкой.

        Args:
            users: List of users to send message to
            message: Message to send
            sender_id: ID of sender

        Returns:
            BroadcastResult: Results of the broadcast operation
        """
        total_users = len(users)
        successful_sends = 0
        failed_sends = 0
        errors = []

        for i in range(0, total_users, self.batch_size):
            batch = users[i:i + self.batch_size]
            logger.debug(f"Processing batch {i//self.batch_size + 1}: {len(batch)} users")

            tasks = []
            for user in batch:
                if user.telegram_id:
                    task = self._send_message_with_retry(
                        user.telegram_id, 
                        message
                    )
                    tasks.append(task)

            if tasks:
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in batch_results:
                    if isinstance(result, Exception):
                        failed_sends += 1
                        errors.append(str(result))
                    elif result:
                        successful_sends += 1
                    else:
                        failed_sends += 1
                        errors.append("Unknown error in message sending")

            if i + self.batch_size < total_users:
                await asyncio.sleep(1.0)

        completion_message = f"Broadcast completed: {successful_sends} successful, {failed_sends} failed"

        return BroadcastResult(
            total_users=total_users,
            successful_sends=successful_sends,
            failed_sends=failed_sends,
            errors=errors[:10],
            completion_message=completion_message
        )

    async def _send_message_with_retry(
        self, 
        chat_id: int, 
        message: str
    ) -> bool:
        """
        Отправка сообщения с логикой повторных попыток.

        Args:
            chat_id: Telegram chat ID
            message: Message to send

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        for attempt in range(self.max_retries):
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='HTML'
                )

                await asyncio.sleep(self.rate_limit_delay)
                return True

            except Forbidden:
                logger.debug(f"User {chat_id} has blocked the bot")
                return False

            except BadRequest as e:
                logger.warning(f"Bad request for user {chat_id}: {e}")
                return False

            except TelegramError as e:
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Telegram error for user {chat_id}, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed to send message to user {chat_id} after {self.max_retries} attempts: {e}")
                    return False

            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Unexpected error for user {chat_id}, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Unexpected error sending to user {chat_id} after {self.max_retries} attempts: {e}")
                    return False

        return False
