# social_system.py
from sqlalchemy.orm import Session
from database.database import Friendship, Gift, Clan, ClanMember, User, UserNotification
from typing import List, Dict, Optional
from datetime import datetime
import structlog

logger = structlog.get_logger()


class SocialSystem:
    """Система социальных функций"""

    def __init__(self, db: Session):
        self.db = db

    # ===== Система друзей =====
    def send_friend_request(self, user_id: int, friend_identifier: str) -> Dict:
        """Отправка запроса на добавление в друзья"""
        from utils.core.user_manager import UserManager
        user_manager = UserManager(self.db)

        # Ищем друга
        friend = user_manager.identify_user(friend_identifier)
        if not friend:
            return {"success": False, "reason": "Пользователь не найден"}

        if user_id == friend.id:
            return {"success": False, "reason": "Нельзя добавить самого себя в друзья"}

        # Проверяем существующие запросы
        existing = self.db.query(Friendship).filter(
            ((Friendship.user_id == user_id) & (Friendship.friend_id == friend.id)) |
            ((Friendship.user_id == friend.id) & (Friendship.friend_id == user_id))
        ).first()

        if existing:
            status = existing.status
            if status == 'pending':
                return {"success": False, "reason": "Запрос уже отправлен"}
            elif status == 'accepted':
                return {"success": False, "reason": "Уже друзья"}
            elif status == 'blocked':
                return {"success": False, "reason": "Пользователь заблокировал вас"}

        # Создаем запрос
        friendship = Friendship(
            user_id=user_id,
            friend_id=friend.id,
            status='pending'
        )

        self.db.add(friendship)

        # Отправляем уведомление
        self._send_notification(
            friend.id,
            "👋 Новый запрос в друзья",
            f"{self._get_user_name(user_id)} хочет добавить вас в друзья",
            {'type': 'friend_request', 'from_user_id': user_id}
        )

        self.db.commit()

        return {"success": True, "friend_id": friend.id}

    def accept_friend_request(self, user_id: int, friend_id: int) -> Dict:
        """Принятие запроса в друзья"""
        friendship = self.db.query(Friendship).filter(
            Friendship.user_id == friend_id,
            Friendship.friend_id == user_id,
            Friendship.status == 'pending'
        ).first()

        if not friendship:
            return {"success": False, "reason": "Запрос не найден"}

        friendship.status = 'accepted'
        friendship.updated_at = datetime.utcnow()

        # Проверяем достижение "Социализатор"
        self._check_socializer_achievement(user_id)
        self._check_socializer_achievement(friend_id)

        # Отправляем уведомление
        self._send_notification(
            friend_id,
            "✅ Запрос в друзья принят",
            f"{self._get_user_name(user_id)} принял ваш запрос в друзья",
            {'type': 'friend_request_accepted', 'user_id': user_id}
        )

        self.db.commit()

        return {"success": True, "friend_id": friend_id}

    def get_friends(self, user_id: int) -> List[Dict]:
        """Получение списка друзей"""
        friendships = self.db.query(Friendship).filter(
            ((Friendship.user_id == user_id) | (Friendship.friend_id == user_id)) &
            (Friendship.status == 'accepted')
        ).all()

        friends = []
        for f in friendships:
            if f.user_id == user_id:
                friend_id = f.friend_id
            else:
                friend_id = f.user_id

            friend = self.db.query(User).filter(User.id == friend_id).first()
            if friend:
                friends.append({
                    'id': friend.id,
                    'username': friend.username,
                    'first_name': friend.first_name,
                    'last_name': friend.last_name,
                    'balance': friend.balance,
                    'friends_since': f.created_at
                })

        return friends

    def get_friend_requests(self, user_id: int) -> List[Dict]:
        """Получение входящих запросов в друзья"""
        requests = self.db.query(Friendship).filter(
            Friendship.friend_id == user_id,
            Friendship.status == 'pending'
        ).all()

        result = []
        for req in requests:
            user = self.db.query(User).filter(User.id == req.user_id).first()
            if user:
                result.append({
                    'id': req.id,
                    'user_id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'sent_at': req.created_at
                })

        return result

    # ===== Система подарков =====
    def send_gift(self, sender_id: int, receiver_identifier: str,
                  gift_type: str, gift_value: int, message: str = None) -> Dict:
        """Отправка подарка"""
        from utils.core.user_manager import UserManager
        user_manager = UserManager(self.db)

        # Ищем получателя
        receiver = user_manager.identify_user(receiver_identifier)
        if not receiver:
            return {"success": False, "reason": "Пользователь не найден"}

        if sender_id == receiver.id:
            return {"success": False, "reason": "Нельзя отправить подарок самому себе"}

        sender = self.db.query(User).filter(User.id == sender_id).first()

        if gift_type == 'coins':
            if sender.balance < gift_value:
                return {"success": False, "reason": "Недостаточно средств"}

            if gift_value <= 0:
                return {"success": False, "reason": "Сумма должна быть положительной"}

            # Списываем у отправителя
            sender.balance -= gift_value

            # Создаем подарок
            gift = Gift(
                sender_id=sender_id,
                receiver_id=receiver.id,
                amount=gift_value,
                message=message
            )

            self.db.add(gift)
            self.db.commit()

            # Начисляем получателю
            receiver.balance += gift_value

            # Проверяем достижение "Щедрый"
            self._check_generous_achievement(sender_id)

            # Отправляем уведомление
            self._send_notification(
                receiver.id,
                "🎁 Вы получили подарок!",
                f"{self._get_user_name(sender_id)} отправил вам {gift_value} монет\n"
                f"Сообщение: {message or 'Без сообщения'}",
                {'type': 'gift_received', 'gift_id': gift.id, 'amount': gift_value}
            )

            self.db.commit()

            return {
                "success": True,
                "gift_id": gift.id,
                "receiver_id": receiver.id,
                "amount": gift_value
            }

        return {"success": False, "reason": "Неизвестный тип подарка"}

    def get_gifts(self, user_id: int, gift_type: str = 'received',
                  limit: int = 20) -> List[Dict]:
        """Получение списка подарков"""
        if gift_type == 'received':
            gifts = self.db.query(Gift).filter(
                Gift.receiver_id == user_id
            ).order_by(Gift.created_at.desc()).limit(limit).all()
        else:  # sent
            gifts = self.db.query(Gift).filter(
                Gift.sender_id == user_id
            ).order_by(Gift.created_at.desc()).limit(limit).all()

        result = []
        for gift in gifts:
            sender = self.db.query(User).filter(User.id == gift.sender_id).first()
            receiver = self.db.query(User).filter(User.id == gift.receiver_id).first()

            result.append({
                'id': gift.id,
                'sender': {
                    'id': sender.id,
                    'username': sender.username,
                    'first_name': sender.first_name
                } if sender else None,
                'receiver': {
                    'id': receiver.id,
                    'username': receiver.username,
                    'first_name': receiver.first_name
                } if receiver else None,
                'amount': gift.amount,
                'message': gift.message,
                'status': gift.status,
                'created_at': gift.created_at,
                'opened_at': gift.opened_at
            })

        return result

    # ===== Система кланов =====
    def create_clan(self, owner_id: int, name: str, description: str = None) -> Dict:
        """Создание клана"""
        # Проверяем существование клана с таким именем
        existing = self.db.query(Clan).filter(
            Clan.name.ilike(name)
        ).first()

        if existing:
            return {"success": False, "reason": "Клан с таким именем уже существует"}

        # Проверяем, не состоит ли пользователь уже в клане
        existing_membership = self.db.query(ClanMember).filter(
            ClanMember.user_id == owner_id
        ).first()

        if existing_membership:
            return {"success": False, "reason": "Вы уже состоите в клане"}

        # Создаем клан
        clan = Clan(
            name=name,
            description=description,
            owner_id=owner_id
        )

        self.db.add(clan)
        self.db.flush()  # Получаем ID клана

        # Добавляем владельца в клан
        member = ClanMember(
            clan_id=clan.id,
            user_id=owner_id,
            role='owner'
        )

        self.db.add(member)
        self.db.commit()

        return {
            "success": True,
            "clan_id": clan.id,
            "clan_name": clan.name
        }

    def join_clan(self, user_id: int, clan_name: str) -> Dict:
        """Вступление в клан"""
        clan = self.db.query(Clan).filter(
            Clan.name.ilike(clan_name),
            Clan.is_active
        ).first()

        if not clan:
            return {"success": False, "reason": "Клан не найден"}

        # Проверяем, не состоит ли пользователь уже в клане
        existing = self.db.query(ClanMember).filter(
            ClanMember.user_id == user_id
        ).first()

        if existing:
            return {"success": False, "reason": "Вы уже состоите в клане"}

        # Проверяем лимит участников
        member_count = self.db.query(ClanMember).filter(
            ClanMember.clan_id == clan.id
        ).count()

        if member_count >= 50:  # Максимум 50 участников
            return {"success": False, "reason": "В клане достигнут лимит участников"}

        # Добавляем в клан
        member = ClanMember(
            clan_id=clan.id,
            user_id=user_id,
            role='member'
        )

        self.db.add(member)

        # Отправляем уведомление владельцу клана
        self._send_notification(
            clan.owner_id,
            "👥 Новый участник в клане",
            f"{self._get_user_name(user_id)} вступил в ваш клан '{clan.name}'",
            {'type': 'clan_join', 'clan_id': clan.id, 'user_id': user_id}
        )

        self.db.commit()

        return {
            "success": True,
            "clan_id": clan.id,
            "clan_name": clan.name
        }

    def get_clan_info(self, clan_id: int) -> Optional[Dict]:
        """Получение информации о клане"""
        clan = self.db.query(Clan).filter(Clan.id == clan_id).first()
        if not clan:
            return None

        members = self.db.query(ClanMember).filter(
            ClanMember.clan_id == clan_id
        ).all()

        owner = self.db.query(User).filter(User.id == clan.owner_id).first()

        member_list = []
        total_balance = 0

        for member in members:
            user = self.db.query(User).filter(User.id == member.user_id).first()
            if user:
                total_balance += user.balance
                member_list.append({
                    'id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'role': member.role,
                    'balance': user.balance,
                    'joined_at': member.joined_at
                })

        return {
            'id': clan.id,
            'name': clan.name,
            'description': clan.description,
            'owner': {
                'id': owner.id,
                'username': owner.username,
                'first_name': owner.first_name
            } if owner else None,
            'members': member_list,
            'member_count': len(member_list),
            'total_balance': total_balance,
            'created_at': clan.created_at
        }

    def get_user_clan(self, user_id: int) -> Optional[Dict]:
        """Получение клана пользователя"""
        membership = self.db.query(ClanMember).filter(
            ClanMember.user_id == user_id
        ).first()

        if not membership:
            return None

        return self.get_clan_info(membership.clan_id)

    def leave_clan(self, user_id: int) -> Dict:
        """Выход из клана"""
        membership = self.db.query(ClanMember).filter(
            ClanMember.user_id == user_id
        ).first()

        if not membership:
            return {"success": False, "reason": "Вы не состоите в клане"}

        clan = self.db.query(Clan).filter(Clan.id == membership.clan_id).first()

        # Если владелец пытается выйти
        if membership.role == 'owner':
            # Проверяем, есть ли другие участники
            other_members = self.db.query(ClanMember).filter(
                ClanMember.clan_id == clan.id,
                ClanMember.user_id != user_id
            ).first()

            if other_members:
                return {"success": False, "reason": "Владелец не может покинуть клан пока в нем есть участники"}
            else:
                # Удаляем клан
                self.db.delete(clan)

        self.db.delete(membership)
        self.db.commit()

        return {"success": True, "clan_name": clan.name if clan else None}

    # ===== Вспомогательные методы =====
    def _get_user_name(self, user_id: int) -> str:
        """Получение имени пользователя"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            if user.username:
                return f"@{user.username}"
            elif user.first_name:
                return user.first_name
        return f"Пользователь #{user_id}"

    def _send_notification(self, user_id: int, title: str, message: str, data: Dict = None):
        """Отправка уведомления"""
        notification = UserNotification(
            user_id=user_id,
            notification_type='social',
            title=title,
            message=message,
            data=data or {},
            expires_at=datetime.utcnow().replace(hour=23, minute=59, second=59)
        )

        self.db.add(notification)

    def _check_socializer_achievement(self, user_id: int):
        """Проверка достижения 'Социализатор' (5 друзей)"""
        friends_count = len(self.get_friends(user_id))

        if friends_count >= 5:
            # Здесь должна быть логика проверки и выдачи достижения
            # Пока просто логируем
            logger.info(f"User {user_id} has {friends_count} friends (achievement condition met)")

    def _check_generous_achievement(self, user_id: int):
        """Проверка достижения 'Щедрый' (отправить подарок)"""
        gifts_sent = self.db.query(Gift).filter(
            Gift.sender_id == user_id
        ).count()

        if gifts_sent >= 1:
            logger.info(f"User {user_id} sent a gift (achievement condition met)")

    def get_social_stats(self, user_id: int) -> Dict:
        """Получение социальной статистики пользователя"""
        friends_count = len(self.get_friends(user_id))
        friend_requests_count = len(self.get_friend_requests(user_id))

        gifts_sent = self.db.query(Gift).filter(
            Gift.sender_id == user_id
        ).count()

        gifts_received = self.db.query(Gift).filter(
            Gift.receiver_id == user_id
        ).count()

        clan_info = self.get_user_clan(user_id)

        return {
            'friends_count': friends_count,
            'friend_requests_count': friend_requests_count,
            'gifts_sent': gifts_sent,
            'gifts_received': gifts_received,
            'in_clan': clan_info is not None,
            'clan_name': clan_info['name'] if clan_info else None,
            'clan_role': next((m['role'] for m in clan_info['members'] if m['id'] == user_id),
                              None) if clan_info else None
        }
