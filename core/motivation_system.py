# motivation_system.py
import os
import sys

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database.database import User, Transaction
from typing import Dict, Optional
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()


class MotivationSystem:
    """Система мотивации и ежедневных бонусов"""

    def __init__(self, db: Session):
        self.db = db

        # Конфигурация ежедневных бонусов
        self.DAILY_BONUS_CONFIG = {
            'base_amount': 10,
            'streak_multipliers': {
                1: 1.0,  # 10 монет
                3: 1.5,  # 15 монет
                7: 2.0,  # 20 монет
                14: 2.5,  # 25 монет
                30: 3.0,  # 30 монет
                90: 4.0,  # 40 монет
                365: 5.0  # 50 монет
            },
            'activity_bonuses': {
                'mini_game_played': 5,
                'shop_purchase': 10,
                'dnd_session': 25,
                'invite_friend': 50
            }
        }

    def claim_daily_bonus(self, user_id: int) -> Dict:
        """Выдача ежедневного бонуса"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "reason": "Пользователь не найден"}

        # Проверяем, получал ли уже бонус сегодня
        today = datetime.utcnow().date()
        last_bonus_date = self.get_last_bonus_date(user_id)

        if last_bonus_date == today:
            return {"success": False, "reason": "Бонус уже получен сегодня"}

        # Рассчитываем стрик и награду
        streak = self.calculate_streak(user_id)
        bonus_amount = self.calculate_bonus_amount(streak)

        # Начисляем бонус
        user.balance += bonus_amount

        # Создаем транзакцию
        transaction = Transaction(
            user_id=user_id,
            amount=bonus_amount,
            transaction_type='daily_bonus',
            source_game='system',
            description=f"Ежедневный бонус (стрик: {streak} дней)",
            meta_data={
                'streak': streak,
                'bonus_type': 'daily',
                'multiplier': self.DAILY_BONUS_CONFIG['streak_multipliers'].get(streak, 1.0)
            }
        )

        self.db.add(transaction)
        self.db.commit()

        # Обновляем последнюю активность
        user.last_activity = datetime.utcnow()
        self.db.commit()

        logger.info(
            "Daily bonus claimed",
            user_id=user_id,
            streak=streak,
            amount=bonus_amount
        )

        return {
            "success": True,
            "streak": streak,
            "amount": bonus_amount,
            "next_streak": streak + 1,
            "next_multiplier": self.DAILY_BONUS_CONFIG['streak_multipliers'].get(streak + 1, 1.0)
        }

    def get_last_bonus_date(self, user_id: int) -> Optional[datetime.date]:
        """Получение даты последнего бонуса"""
        last_bonus = self.db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == 'daily_bonus'
        ).order_by(Transaction.created_at.desc()).first()

        return last_bonus.created_at.date() if last_bonus else None

    def calculate_streak(self, user_id: int) -> int:
        """Расчет текущего стрика ежедневных бонусов"""
        streak = 0
        current_date = datetime.utcnow().date()

        # Получаем все бонусы за последние 30 дней
        start_date = current_date - timedelta(days=30)
        bonuses = self.db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == 'daily_bonus',
            Transaction.created_at >= start_date
        ).order_by(Transaction.created_at.desc()).all()

        if not bonuses:
            return 0

        # Проверяем последовательность дней
        expected_date = current_date
        for bonus in bonuses:
            bonus_date = bonus.created_at.date()

            if bonus_date == expected_date:
                streak += 1
                expected_date -= timedelta(days=1)
            else:
                break

        return streak

    def calculate_bonus_amount(self, streak: int) -> int:
        """Расчет суммы бонуса на основе стрика"""
        base_amount = self.DAILY_BONUS_CONFIG['base_amount']
        multiplier = self.DAILY_BONUS_CONFIG['streak_multipliers'].get(streak, 1.0)

        return int(base_amount * multiplier)

    def award_activity_bonus(self, user_id: int, activity_type: str) -> Dict:
        """Начисление бонуса за активность"""
        if activity_type not in self.DAILY_BONUS_CONFIG['activity_bonuses']:
            return {"success": False, "reason": "Неизвестный тип активности"}

        bonus_amount = self.DAILY_BONUS_CONFIG['activity_bonuses'][activity_type]
        user = self.db.query(User).filter(User.id == user_id).first()

        if not user:
            return {"success": False, "reason": "Пользователь не найден"}

        user.balance += bonus_amount

        activity_names = {
            'mini_game_played': 'игра в мини-игры',
            'shop_purchase': 'покупка в магазине',
            'dnd_session': 'участие в D&D сессии',
            'invite_friend': 'приглашение друга'
        }

        transaction = Transaction(
            user_id=user_id,
            amount=bonus_amount,
            transaction_type='activity_bonus',
            source_game='system',
            description=f"Бонус за {activity_names.get(activity_type, activity_type)}",
            meta_data={'activity_type': activity_type}
        )

        self.db.add(transaction)
        self.db.commit()

        return {
            "success": True,
            "activity_type": activity_type,
            "amount": bonus_amount,
            "new_balance": user.balance
        }

    def get_weekly_challenges(self, user_id: int) -> Dict:
        """Получение еженедельных заданий"""
        # Здесь можно реализовать сложную логику заданий
        # Пока возвращаем заглушку
        current_week = datetime.utcnow().isocalendar()[1]

        challenges = {
            'week': current_week,
            'challenges': [
                {
                    'id': 1,
                    'name': 'Игровой марафон',
                    'description': 'Сыграйте в 5 разных мини-игр',
                    'progress': 0,
                    'target': 5,
                    'reward': 100,
                    'type': 'mini_games'
                },
                {
                    'id': 2,
                    'name': 'Мастер покупок',
                    'description': 'Совершите 3 покупки в магазине',
                    'progress': 0,
                    'target': 3,
                    'reward': 150,
                    'type': 'shop'
                },
                {
                    'id': 3,
                    'name': 'Ролевик',
                    'description': 'Участвуйте в 2 D&D сессиях',
                    'progress': 0,
                    'target': 2,
                    'reward': 200,
                    'type': 'dnd'
                }
            ]
        }

        return challenges

    def get_user_motivation_stats(self, user_id: int) -> Dict:
        """Получение статистики мотивации пользователя"""
        streak = self.calculate_streak(user_id)
        last_bonus_date = self.get_last_bonus_date(user_id)
        today = datetime.utcnow().date()

        can_claim_today = last_bonus_date != today
        next_bonus_amount = self.calculate_bonus_amount(streak + 1) if can_claim_today else self.calculate_bonus_amount(
            streak)

        return {
            'current_streak': streak,
            'can_claim_today': can_claim_today,
            'last_bonus_date': last_bonus_date,
            'next_bonus_amount': next_bonus_amount,
            'next_multiplier': self.DAILY_BONUS_CONFIG['streak_multipliers'].get(streak + 1, 1.0)
        }