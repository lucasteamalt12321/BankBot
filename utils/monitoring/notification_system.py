"""Notification system with DB storage and realtime delivery transports."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from html import escape
from typing import Any

import aiohttp
import structlog
from sqlalchemy.orm import Session

from database.database import User, UserNotification
from src.config import settings

logger = structlog.get_logger()


class NotificationSystem:
    """Система уведомлений с поддержкой Telegram и ntfy (системные поп-апы)"""

    def __init__(self, db: Session, bot=None):
        self.db = db
        self.bot = bot
        self.ntfy_url = settings.NTFY_BASE_URL.rstrip("/")

    async def send_notification(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> UserNotification:
        """Отправка уведомления пользователю, в Telegram и ntfy"""

        notification = UserNotification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            data=data or {},
            is_read=False,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )

        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)

        logger.info(
            "Notification saved to DB",
            user_id=user_id,
            notification_type=notification_type,
            notification_id=notification.id
        )

        # 1. Отправка в Telegram
        user = self.db.query(User).filter(User.id == user_id).first()
        await self.send_realtime_notification(
            title=title,
            message=message,
            notification_type=notification_type,
            user=user,
        )

        return notification

    async def send_realtime_notification(
        self,
        title: str,
        message: str,
        notification_type: str,
        user: User | None = None,
    ) -> None:
        """Deliver notification through enabled realtime transports."""

        await self._send_to_telegram(user, title, message)
        logger.info(
            "Watch notification mode is temporarily disabled",
            notification_type=notification_type,
        )

    async def _send_to_telegram(
        self,
        user: User | None,
        title: str,
        message: str,
    ) -> None:
        """Вспомогательный метод для отправки уведомления в Telegram."""
        if not self.bot or not user or not user.telegram_id:
            return

        try:
            formatted_text = f"<b>{escape(title)}</b>\n\n{escape(message)}"
            await self.bot.send_message(
                chat_id=user.telegram_id,
                text=formatted_text,
                parse_mode="HTML",
            )
            logger.info("Notification sent to Telegram", user_id=user.telegram_id)
        except Exception as e:
            logger.error("Failed to send Telegram notification", error=str(e))

    async def _send_to_ntfy(self, title: str, message: str, ntype: str):
        """Вспомогательный метод для отправки в ntfy.sh"""
        if not settings.NTFY_ENABLED or not settings.NTFY_TOPIC:
            return

        try:
            topic = settings.NTFY_TOPIC
            
            # Настройка кнопок
            actions = [
                {
                    "action": "view",
                    "label": "Открыть Telegram",
                    "url": "tg://resolve?domain=lt_lo_game_bot",
                    "clear": True
                }
            ]
            
            headers = {
                "Title": title,
                "Priority": "high",
                "Tags": settings.NTFY_TAGS,
                "Actions": json.dumps(actions),
            }

            timeout = aiohttp.ClientTimeout(total=settings.NTFY_TIMEOUT_SECONDS)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.ntfy_url}/{topic}",
                    data=message.encode("utf-8"),
                    headers=headers,
                    proxy=settings.PROXY_URL,
                ) as response:
                    if response.status == 200:
                        logger.info("Notification sent to ntfy", topic=topic)
                    else:
                        logger.warning("Failed to send to ntfy", status=response.status)
        except Exception as e:
            logger.error("Error sending to ntfy", error=str(e))

    async def _send_to_adb(self, title: str, message: str, ntype: str) -> None:
        """Вспомогательный метод для отправки уведомления через adb shell."""
        if not settings.ADB_NOTIFICATIONS_ENABLED:
            return

        adb_path = settings.ADB_PATH.strip()
        serial = settings.ADB_DEVICE_SERIAL.strip()

        command = [adb_path]
        if serial:
            command.extend(["-s", serial])
        command.extend(
            [
                "shell",
                "cmd",
                "notification",
                "post",
                "-S",
                "bigtext",
                "BankBot",
                ntype,
                f"{title}\n{message}",
            ]
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            if process.returncode == 0:
                logger.info("Notification sent to ADB", type=ntype)
            else:
                logger.warning(
                    "Failed to send to ADB",
                    returncode=process.returncode,
                    stderr=stderr.decode("utf-8", errors="ignore"),
                    stdout=stdout.decode("utf-8", errors="ignore"),
                )
        except FileNotFoundError:
            logger.error("ADB executable not found", adb_path=adb_path)
        except Exception as e:
            logger.error("Error sending to ADB", error=str(e))

    async def send_transaction_notification(self, user_id: int, amount: int,
                                      transaction_type: str, description: str):
        """Уведомление о транзакции"""

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return

        title = "💰 Новая транзакция"

        if amount > 0:
            message = f"Вам начислено {amount} банковских монет"
            if description:
                message += f"\nПричина: {description}"
        else:
            message = f"Списано {abs(amount)} банковских монет"
            if description:
                message += f"\nПричина: {description}"

        message += f"\n\n💳 Новый баланс: {user.balance} монет"

        return await self.send_notification(
            user_id=user_id,
            notification_type='transaction',
            title=title,
            message=message,
            data={
                'amount': amount,
                'transaction_type': transaction_type,
                'new_balance': user.balance
            }
        )

    async def send_achievement_notification(self, user_id: int, achievement: dict[str, Any]):
        """Уведомление о получении достижения"""

        title = "🏆 Новое достижение!"

        tier_icons = {
            'bronze': '🥉',
            'silver': '🥈',
            'gold': '🥇'
        }

        icon = tier_icons.get(achievement.get('tier'), '🏅')

        message = f"{icon} {achievement.get('name', 'Достижение')}\n\n"
        message += f"{achievement.get('description', '')}\n\n"
        message += f"💎 Награда: {achievement.get('points', 0)} очков достижений"

        return await self.send_notification(
            user_id=user_id,
            notification_type='achievement',
            title=title,
            message=message,
            data={
                'achievement_id': achievement.get('id'),
                'achievement_code': achievement.get('code'),
                'points': achievement.get('points', 0),
                'tier': achievement.get('tier')
            }
        )

    async def send_purchase_notification(self, user_id: int, item_name: str,
                                   price: int, new_balance: int):
        """Уведомление о покупке"""

        title = "🛍️ Покупка совершена"
        message = f"Вы приобрели: {item_name}\n"
        message += f"💸 Стоимость: {price} монет\n"
        message += f"💳 Новый баланс: {new_balance} монет"

        return await self.send_notification(
            user_id=user_id,
            notification_type='purchase',
            title=title,
            message=message,
            data={
                'item_name': item_name,
                'price': price,
                'new_balance': new_balance
            }
        )

    async def send_game_notification(self, user_id: int, game_type: str,
                               result: str, reward: int = 0):
        """Уведомление о результате игры"""

        game_names = {
            'cities': '🏙️ Города',
            'killer_words': '🔪 Слова, которые могут убить',
            'gd_levels': '🎵 Уровни GD',
            'dnd': '🎲 D&D'
        }

        title = f"{game_names.get(game_type, '🎮 Игра')} завершена"

        if reward > 0:
            message = f"🎉 {result}!\n\n"
            message += f"💰 Вы получили {reward} банковских монет"
        else:
            message = f"📊 Результат: {result}"

        return await self.send_notification(
            user_id=user_id,
            notification_type='game',
            title=title,
            message=message,
            data={
                'game_type': game_type,
                'result': result,
                'reward': reward
            }
        )

    async def send_system_notification(self, user_id: int, title: str, message: str):
        """Системное уведомление"""

        return await self.send_notification(
            user_id=user_id,
            notification_type='system',
            title=title,
            message=message
        )

    def get_user_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Получение уведомлений пользователя"""

        query = self.db.query(UserNotification).filter(
            UserNotification.user_id == user_id
        )

        if unread_only:
            query = query.filter(not UserNotification.is_read)

        notifications = query.order_by(
            UserNotification.created_at.desc()
        ).limit(limit).all()

        result = []
        for notification in notifications:
            result.append({
                'id': notification.id,
                'type': notification.notification_type,
                'title': notification.title,
                'message': notification.message,
                'is_read': notification.is_read,
                'created_at': notification.created_at,
                'expires_at': notification.expires_at,
                'data': notification.data
            })

        return result

    def mark_as_read(self, notification_id: int, user_id: int = None) -> bool:
        """Пометить уведомление как прочитанное"""

        query = self.db.query(UserNotification).filter(
            UserNotification.id == notification_id
        )

        if user_id:
            query = query.filter(UserNotification.user_id == user_id)

        notification = query.first()

        if not notification:
            return False

        notification.is_read = True
        notification.read_at = datetime.utcnow()

        self.db.commit()

        logger.info(
            "Notification marked as read",
            notification_id=notification_id,
            user_id=notification.user_id
        )

        return True

    def mark_all_as_read(self, user_id: int) -> int:
        """Пометить все уведомления пользователя как прочитанные"""

        updated = self.db.query(UserNotification).filter(
            UserNotification.user_id == user_id,
            not UserNotification.is_read
        ).update({
            'is_read': True,
            'read_at': datetime.utcnow()
        })

        self.db.commit()

        logger.info(
            "All notifications marked as read",
            user_id=user_id,
            count=updated
        )

        return updated

    def get_unread_count(self, user_id: int) -> int:
        """Получение количества непрочитанных уведомлений"""

        return self.db.query(UserNotification).filter(
            UserNotification.user_id == user_id,
            not UserNotification.is_read
        ).count()

    def cleanup_expired(self) -> int:
        """Очистка просроченных уведомлений"""

        expired = self.db.query(UserNotification).filter(
            UserNotification.expires_at < datetime.utcnow()
        ).all()

        count = len(expired)

        for notification in expired:
            self.db.delete(notification)

        if count > 0:
            self.db.commit()
            logger.info(f"Cleaned up {count} expired notifications")

        return count
