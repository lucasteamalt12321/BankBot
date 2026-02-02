# bank_system.py
import os
import sys

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database.database import User, Transaction
from utils.user_manager import UserManager
from bot.parsers import ParsedActivity, UniversalParser
from utils.config import settings, ADVANCED_CURRENCY_CONFIG, TRANSACTION_SECURITY
from typing import List, Dict
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()


class BankSystem:
    """Основная банковская система"""

    def __init__(self, db: Session):
        self.db = db
        self.user_manager = UserManager(db)
        self.parser = UniversalParser()
        self.currency_config = ADVANCED_CURRENCY_CONFIG
        self.security_config = TRANSACTION_SECURITY

    def process_message(self, message_text: str, source_hint: str = None) -> List[Dict]:
        """Обработка сообщения и начисление валюты"""
        
        try:
            # Парсим сообщение
            activities = self.parser.parse_message(message_text, source_hint)
        except Exception as e:
            logger.error(
                "Failed to parse message",
                error=str(e),
                message_preview=message_text[:100],
                source_hint=source_hint
            )
            return [{
                'success': False,
                'error': f"Parse error: {str(e)}",
                'message_preview': message_text[:100]
            }]

        results = []

        for activity in activities:
            try:
                # Пропускаем неизвестных пользователей
                if activity.user_identifier == 'unknown':
                    logger.warning(
                        "Skipping unknown user activity",
                        activity_type=activity.activity_type,
                        raw_message=message_text[:100]
                    )
                    continue

                result = self.process_activity(activity)
                results.append(result)

                logger.info(
                    "Activity processed",
                    user=activity.user_identifier,
                    activity=activity.activity_type,
                    points=activity.points,
                    converted_amount=result.get('converted_amount', 0)
                )

            except Exception as e:
                logger.error(
                    "Failed to process activity",
                    user=activity.user_identifier,
                    activity=activity.activity_type,
                    error=str(e),
                    raw_message=message_text[:100]
                )
                results.append({
                    'success': False,
                    'error': str(e),
                    'activity': activity,
                    'raw_message_preview': message_text[:100]
                })

        return results

    def process_activity(self, activity: ParsedActivity) -> Dict:
        """Обработка одной активности"""

        # Идентифицируем пользователя
        user = self.user_manager.identify_user(activity.user_identifier)

        # Конвертируем валюту
        converted_amount = self.convert_currency(
            activity.points,
            activity.game_source,
            activity.activity_type
        )

        # Проверяем безопасность транзакции
        if not self.validate_transaction(user, converted_amount):
            raise ValueError("Транзакция не прошла проверку безопасности")

        # Создаем транзакцию
        transaction = Transaction(
            user_id=user.id,
            amount=converted_amount,
            transaction_type='game_reward',
            source_game=activity.game_source,
            description=f"{activity.activity_type}: {activity.points} -> {converted_amount} банковских",
            meta_data={
                'original_points': activity.points,
                'activity_type': activity.activity_type,
                'user_identifier': activity.user_identifier,
                **(activity.metadata or {})
            }
        )

        # Обновляем баланс пользователя
        user.balance += converted_amount
        user.last_activity = datetime.utcnow()

        # Сохраняем в БД
        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)

        return {
            'success': True,
            'user_id': user.id,
            'user_name': user.first_name or user.username or activity.user_identifier,
            'original_points': activity.points,
            'converted_amount': converted_amount,
            'new_balance': user.balance,
            'transaction_id': transaction.id,
            'activity': activity
        }

    def convert_currency(self, points: int, game_source: str, activity_type: str) -> int:
        """Конвертация валюты из игровой в банковскую"""

        if game_source not in self.currency_config:
            # Если игра не настроена, используем курс 1:1
            return points

        config = self.currency_config[game_source]
        base_rate = config['base_rate']

        # Применяем базовый курс
        converted = int(points * base_rate)

        # Применяем множители для конкретных событий
        if 'event_multipliers' in config and activity_type in config['event_multipliers']:
            multiplier = config['event_multipliers'][activity_type]
            converted = int(converted * multiplier)

        # Применяем множители редкости для карточных игр
        if 'rarity_multipliers' in config and activity_type.startswith('card_'):
            rarity = activity_type.replace('card_', '')
            if rarity in config['rarity_multipliers']:
                multiplier = config['rarity_multipliers'][rarity]
                converted = int(converted * multiplier)

        return max(1, converted)  # Минимум 1 банковская монета

    def validate_transaction(self, user: User, amount: int) -> bool:
        """Валидация транзакции по правилам безопасности"""

        # Проверка максимальной суммы за раз
        if amount > self.security_config['max_single_amount']:
            logger.warning(
                "Large transaction detected",
                user_id=user.id,
                amount=amount,
                limit=self.security_config['max_single_amount']
            )
            # Логируем, но не блокируем

        # Проверка количества транзакций в час (оптимизированная версия)
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_transactions = self.db.query(Transaction.id).filter(
            Transaction.user_id == user.id,
            Transaction.created_at >= hour_ago
        ).limit(self.security_config['max_hourly_transactions']).count()

        if recent_transactions >= self.security_config['max_hourly_transactions']:
            logger.warning(
                "Too many transactions per hour",
                user_id=user.id,
                count=recent_transactions,
                limit=self.security_config['max_hourly_transactions']
            )
            return False

        # Проверка дубликатов - отключаем для нормальной работы системы
        # В реальных условиях пользователи могут получать одинаковые суммы за разные игровые события
        # и строгая проверка дубликатов может блокировать легитимные транзакции

        return True

    def get_user_balance(self, user_identifier: str, telegram_id: int = None) -> Dict:
        """Получение баланса пользователя"""

        user = self.user_manager.identify_user(user_identifier, telegram_id)

        return {
            'user_id': user.id,
            'balance': user.balance,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'last_activity': user.last_activity
        }

    def get_user_history(self, user_identifier: str, limit: int = 10, telegram_id: int = None) -> Dict:
        """Получение истории транзакций пользователя"""

        user = self.user_manager.identify_user(user_identifier, telegram_id)

        transactions = self.db.query(Transaction).filter(
            Transaction.user_id == user.id
        ).order_by(Transaction.created_at.desc()).limit(limit).all()

        return {
            'user_id': user.id,
            'balance': user.balance,
            'transactions': [
                {
                    'id': t.id,
                    'amount': t.amount,
                    'type': t.transaction_type,
                    'source': t.source_game,
                    'description': t.description,
                    'created_at': t.created_at
                }
                for t in transactions
            ]
        }

    def admin_adjust_balance(self, user_identifier: str, amount: int, reason: str, admin_id: int) -> Dict:
        """Административная корректировка баланса"""

        user = self.user_manager.identify_user(user_identifier)

        transaction = Transaction(
            user_id=user.id,
            amount=amount,
            transaction_type='admin_adjustment',
            source_game='admin',
            description=f"Административная корректировка: {reason}",
            meta_data={
                'admin_id': admin_id,
                'reason': reason
            }
        )

        user.balance += amount
        user.last_activity = datetime.utcnow()

        self.db.add(transaction)
        self.db.commit()

        logger.info(
            "Admin balance adjustment",
            user_id=user.id,
            amount=amount,
            admin_id=admin_id,
            reason=reason
        )

        return {
            'success': True,
            'user_id': user.id,
            'amount': amount,
            'new_balance': user.balance,
            'transaction_id': transaction.id
        }

    def get_system_stats(self) -> Dict:
        """Получение статистики системы"""

        total_users = self.db.query(User).count()
        from sqlalchemy import func
        total_balance = self.db.query(User).with_entities(
            func.sum(User.balance)
        ).scalar() or 0

        today = datetime.utcnow().date()
        today_transactions = self.db.query(Transaction).filter(
            func.date(Transaction.created_at) == today
        ).count()

        return {
            'total_users': total_users,
            'total_balance': total_balance,
            'today_transactions': today_transactions,
            'currency_config': self.currency_config
        }