# achievements.py
from sqlalchemy.orm import Session
from database.database import UserAchievement, Achievement
from typing import List, Dict
from datetime import datetime
import structlog

logger = structlog.get_logger()


class AchievementSystem:
    """Система достижений"""

    def __init__(self, db: Session):
        self.db = db
        self.initialize_achievements()

    def initialize_achievements(self):
        """Инициализация стандартных достижений"""

        achievements_data = [
            # Банковские достижения
            {
                'code': 'first_deposit',
                'name': 'Первый взнос',
                'description': 'Получить первую награду в банк-аггрегаторе',
                'category': 'bank',
                'tier': 'bronze',
                'points': 10
            },
            {
                'code': 'balance_1000',
                'name': 'Тысячник',
                'description': 'Накопить 1000 банковских монет',
                'category': 'bank',
                'tier': 'silver',
                'points': 25
            },
            {
                'code': 'balance_10000',
                'name': 'Десятитысячник',
                'description': 'Накопить 10000 банковских монет',
                'category': 'bank',
                'tier': 'gold',
                'points': 100
            },
            {
                'code': 'shopper',
                'name': 'Покупатель',
                'description': 'Совершить первую покупку в магазине',
                'category': 'shop',
                'tier': 'bronze',
                'points': 15
            },
            {
                'code': 'collector',
                'name': 'Коллекционер',
                'description': 'Купить 10 разных товаров',
                'category': 'shop',
                'tier': 'silver',
                'points': 50
            },

            # Игровые достижения
            {
                'code': 'shmalala_master',
                'name': 'Мастер Шмалалы',
                'description': 'Получить 1000 монет в Shmalala',
                'category': 'games',
                'tier': 'silver',
                'points': 30
            },
            {
                'code': 'gd_cards_expert',
                'name': 'Эксперт GD Cards',
                'description': 'Получить 500 очков в GD Cards',
                'category': 'games',
                'tier': 'silver',
                'points': 25
            },
            {
                'code': 'mafia_winner',
                'name': 'Победитель мафии',
                'description': 'Выиграть 10 игр в True Mafia',
                'category': 'games',
                'tier': 'gold',
                'points': 75
            },
            {
                'code': 'bunker_survivor',
                'name': 'Выживший в бункере',
                'description': 'Выжить в 5 играх Bunker RP',
                'category': 'games',
                'tier': 'silver',
                'points': 40
            },

            # Социальные достижения
            {
                'code': 'socializer',
                'name': 'Социализатор',
                'description': 'Иметь 5 друзей в системе',
                'category': 'social',
                'tier': 'bronze',
                'points': 20
            },
            {
                'code': 'generous',
                'name': 'Щедрый',
                'description': 'Отправить подарок другу',
                'category': 'social',
                'tier': 'bronze',
                'points': 15
            },

            # D&D достижения
            {
                'code': 'dnd_master',
                'name': 'Мастер D&D',
                'description': 'Провести 5 сессий D&D',
                'category': 'dnd',
                'tier': 'gold',
                'points': 100
            },
            {
                'code': 'dnd_player',
                'name': 'Игрок D&D',
                'description': 'Участвовать в 3 сессиях D&D',
                'category': 'dnd',
                'tier': 'silver',
                'points': 30
            },

            # Системные достижения
            {
                'code': 'daily_streak_7',
                'name': 'Неделя активности',
                'description': 'Зайти в систему 7 дней подряд',
                'category': 'system',
                'tier': 'silver',
                'points': 25
            },
            {
                'code': 'daily_streak_30',
                'name': 'Месяц активности',
                'description': 'Зайти в систему 30 дней подряд',
                'category': 'system',
                'tier': 'gold',
                'points': 150
            },
            {
                'code': 'inviter',
                'name': 'Пригласитель',
                'description': 'Пригласить 3 друзей в систему',
                'category': 'system',
                'tier': 'silver',
                'points': 50
            }
        ]

        for ach_data in achievements_data:
            existing = self.db.query(Achievement).filter(
                Achievement.code == ach_data['code']
            ).first()

            if not existing:
                achievement = Achievement(**ach_data)
                self.db.add(achievement)

        self.db.commit()

    def check_achievements(self, user_id: int, event_type: str, event_data: Dict = None):
        """Проверка достижений по событию"""

        achievements_to_check = []

        # Определяем какие достижения проверять по типу события
        if event_type == 'transaction':
            achievements_to_check = [
                'first_deposit', 'balance_1000', 'balance_10000'
            ]
        elif event_type == 'purchase':
            achievements_to_check = ['shopper', 'collector']
        elif event_type == 'game_activity':
            if event_data and event_data.get('game') == 'shmalala':
                achievements_to_check = ['shmalala_master']
            elif event_data and event_data.get('game') == 'gdcards':
                achievements_to_check = ['gd_cards_expert']
            elif event_data and event_data.get('game') == 'true_mafia':
                achievements_to_check = ['mafia_winner']
            elif event_data and event_data.get('game') == 'bunkerrp':
                achievements_to_check = ['bunker_survivor']
        elif event_type == 'dnd_session':
            achievements_to_check = ['dnd_master', 'dnd_player']
        elif event_type == 'social_action':
            achievements_to_check = ['socializer', 'generous']
        elif event_type == 'daily_login':
            achievements_to_check = ['daily_streak_7', 'daily_streak_30']

        unlocked = []

        for achievement_code in achievements_to_check:
            achievement = self.db.query(Achievement).filter(
                Achievement.code == achievement_code
            ).first()

            if not achievement:
                continue

            # Проверяем, не получено ли уже достижение
            existing = self.db.query(UserAchievement).filter(
                UserAchievement.user_id == user_id,
                UserAchievement.achievement_id == achievement.id
            ).first()

            if existing:
                continue

            # Проверяем условия достижения
            if self.check_achievement_conditions(user_id, achievement_code, event_data):
                user_achievement = UserAchievement(
                    user_id=user_id,
                    achievement_id=achievement.id,
                    unlocked_at=datetime.utcnow(),
                    progress=100
                )

                self.db.add(user_achievement)
                unlocked.append(achievement)

                logger.info(
                    "Achievement unlocked",
                    user_id=user_id,
                    achievement_code=achievement_code,
                    achievement_name=achievement.name
                )

        if unlocked:
            self.db.commit()

        return unlocked

    def check_achievement_conditions(self, user_id: int, achievement_code: str, event_data: Dict = None) -> bool:
        """Проверка условий для получения достижения"""

        from database.database import User, Transaction, UserPurchase

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        if achievement_code == 'first_deposit':
            # Проверяем, есть ли транзакции у пользователя
            transactions = self.db.query(Transaction).filter(
                Transaction.user_id == user_id
            ).count()
            return transactions > 0

        elif achievement_code == 'balance_1000':
            return user.balance >= 1000

        elif achievement_code == 'balance_10000':
            return user.balance >= 10000

        elif achievement_code == 'shopper':
            purchases = self.db.query(UserPurchase).filter(
                UserPurchase.user_id == user_id
            ).count()
            return purchases > 0

        elif achievement_code == 'collector':
            # Для упрощения - считаем покупки
            purchases = self.db.query(UserPurchase).filter(
                UserPurchase.user_id == user_id
            ).count()
            return purchases >= 10

        elif achievement_code == 'shmalala_master':
            # В реальной реализации здесь была бы логика подсчета
            # Для демонстрации используем баланс
            return user.balance >= 1000

        # Остальные достижения проверяются аналогично

        return False

    def get_user_achievements(self, user_id: int) -> Dict:
        """Получение достижений пользователя"""

        user_achievements = self.db.query(UserAchievement).filter(
            UserAchievement.user_id == user_id
        ).join(Achievement).all()

        achievements_by_category = {
            'bank': [],
            'shop': [],
            'games': [],
            'social': [],
            'dnd': [],
            'system': []
        }

        total_points = 0

        for ua in user_achievements:
            achievement_data = {
                'id': ua.achievement.id,
                'code': ua.achievement.code,
                'name': ua.achievement.name,
                'description': ua.achievement.description,
                'category': ua.achievement.category,
                'tier': ua.achievement.tier,
                'points': ua.achievement.points,
                'unlocked_at': ua.unlocked_at,
                'progress': ua.progress
            }

            achievements_by_category[ua.achievement.category].append(achievement_data)
            total_points += ua.achievement.points

        # Сортируем по уровню (золото, серебро, бронза)
        tier_order = {'gold': 1, 'silver': 2, 'bronze': 3}
        for category in achievements_by_category:
            achievements_by_category[category].sort(
                key=lambda x: (tier_order.get(x['tier'], 4), x['name'])
            )

        return {
            'total_achievements': len(user_achievements),
            'total_points': total_points,
            'by_category': achievements_by_category,
            'unlocked': [
                {
                    'name': ua.achievement.name,
                    'description': ua.achievement.description,
                    'unlocked_at': ua.unlocked_at.strftime('%d.%m.%Y'),
                    'tier': ua.achievement.tier,
                    'points': ua.achievement.points
                }
                for ua in user_achievements
            ]
        }

    def get_available_achievements(self, user_id: int) -> Dict:
        """Получение доступных для получения достижений"""

        unlocked_achievements = self.db.query(UserAchievement).filter(
            UserAchievement.user_id == user_id
        ).all()

        unlocked_ids = [ua.achievement_id for ua in unlocked_achievements]

        all_achievements = self.db.query(Achievement).all()

        available = []

        for achievement in all_achievements:
            if achievement.id not in unlocked_ids:
                # Проверяем прогресс
                progress = self.calculate_progress(user_id, achievement.code)

                available.append({
                    'id': achievement.id,
                    'code': achievement.code,
                    'name': achievement.name,
                    'description': achievement.description,
                    'category': achievement.category,
                    'tier': achievement.tier,
                    'points': achievement.points,
                    'progress': progress,
                    'progress_percentage': min(100, int(progress))
                })

        # Сортируем по прогрессу (от большего к меньшему)
        available.sort(key=lambda x: x['progress_percentage'], reverse=True)

        return {
            'available': available,
            'total_available': len(available)
        }

    def calculate_progress(self, user_id: int, achievement_code: str) -> int:
        """Расчет прогресса достижения"""

        from database.database import User, Transaction, UserPurchase

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return 0

        if achievement_code == 'balance_1000':
            return min(100, int(user.balance / 1000 * 100))

        elif achievement_code == 'balance_10000':
            return min(100, int(user.balance / 10000 * 100))

        elif achievement_code == 'collector':
            purchases = self.db.query(UserPurchase).filter(
                UserPurchase.user_id == user_id
            ).count()
            return min(100, int(purchases / 10 * 100))

        # Остальные достижения рассчитываются аналогично

        return 0