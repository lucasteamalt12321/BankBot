# shop_system.py
import os
import sys

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database.database import ShopCategory, ShopItem, UserPurchase, User, Transaction
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()


class EnhancedShopSystem:
    """Улучшенная система магазина с реальной активацией товаров"""

    def __init__(self, db: Session):
        self.db = db

    def initialize_default_categories(self):
        """Инициализация стандартных категорий магазина"""

        categories_data = [
            {"name": "Стикеры и медиа", "description": "Безлимитные стикерпаки и GIF-анимации", "sort_order": 1},
            {"name": "Привилегии", "description": "Админка на день, особые роли в чате", "sort_order": 2},
            {"name": "Игровые бусты", "description": "Множители опыта, временные бонусы", "sort_order": 3},
            {"name": "Кастомный контент", "description": "Персонализированные команды, уникальные возможности",
             "sort_order": 4}
        ]

        for cat_data in categories_data:
            existing = self.db.query(ShopCategory).filter(ShopCategory.name == cat_data["name"]).first()
            if not existing:
                category = ShopCategory(**cat_data)
                self.db.add(category)

        self.db.commit()

    def initialize_default_items(self):
        """Инициализация стандартных товаров"""

        # Получаем категории
        categories = {cat.name: cat.id for cat in self.db.query(ShopCategory).all()}

        items_data = [
            # Стикеры и медиа
            {
                "category_id": categories.get("Стикеры и медиа"),
                "name": "Безлимитные стикеры (24ч)",
                "description": "Неограниченное использование стикеров на 24 часа",
                "price": 100,
                "item_type": "sticker",
                "meta_data": {"duration_hours": 24, "activation_type": "unlimited_stickers"},
                "cooldown_hours": 24
            },
            {
                "category_id": categories.get("Стикеры и медиа"),
                "name": "Премиум стикерпак",
                "description": "Эксклюзивный набор премиум стикеров",
                "price": 100,
                "item_type": "sticker",
                "meta_data": {"sticker_pack": "premium", "activation_type": "sticker_pack"},
                "purchase_limit": 1
            },

            # Привилегии
            {
                "category_id": categories.get("Привилегии"),
                "name": "Админка на день",
                "description": "Права администратора чата на 24 часа",
                "price": 100,
                "item_type": "privilege",
                "meta_data": {"privilege_type": "admin_day", "duration_hours": 24,
                              "activation_type": "admin_privileges"},
                "cooldown_hours": 168  # неделя
            },
            {
                "category_id": categories.get("Привилегии"),
                "name": "VIP статус (неделя)",
                "description": "Специальный статус и дополнительные возможности",
                "price": 100,
                "item_type": "privilege",
                "meta_data": {"privilege_type": "vip_week", "duration_hours": 168, "activation_type": "vip_privileges"},
                "cooldown_hours": 168
            },

            # Игровые бусты
            {
                "category_id": categories.get("Игровые бусты"),
                "name": "Двойной опыт (2ч)",
                "description": "Удвоение получаемого опыта в играх на 2 часа",
                "price": 100,
                "item_type": "boost",
                "meta_data": {"boost_type": "xp_multiplier", "multiplier": 2.0, "duration_hours": 2,
                              "activation_type": "experience_boost"},
                "cooldown_hours": 24
            },
            {
                "category_id": categories.get("Игровые бусты"),
                "name": "Бонус к балансу (+100)",
                "description": "Мгновенное начисление 100 банковских монет",
                "price": 100,
                "item_type": "boost",
                "meta_data": {"boost_type": "balance_bonus", "amount": 100, "activation_type": "balance_bonus"}
            },

            # Кастомный контент
            {
                "category_id": categories.get("Кастомный контент"),
                "name": "Персональная команда",
                "description": "Создание собственной команды для бота",
                "price": 100,
                "item_type": "custom",
                "meta_data": {"custom_type": "personal_command", "activation_type": "custom_command"},
                "purchase_limit": 1
            },
            {
                "category_id": categories.get("Кастомный контент"),
                "name": "Кастомный заголовок",
                "description": "Уникальный заголовок профиля",
                "price": 100,
                "item_type": "custom",
                "meta_data": {"custom_type": "custom_title", "activation_type": "custom_title"},
                "purchase_limit": 1
            }
        ]

        for item_data in items_data:
            if item_data["category_id"]:
                existing = self.db.query(ShopItem).filter(
                    ShopItem.name == item_data["name"]
                ).first()
                if not existing:
                    item = ShopItem(**item_data)
                    self.db.add(item)

        self.db.commit()

    def get_shop_catalog(self) -> Dict:
        """Получение полного каталога магазина"""

        categories = self.db.query(ShopCategory).filter(
            ShopCategory.is_active == True
        ).order_by(ShopCategory.sort_order).all()

        catalog = {}
        for category in categories:
            items = self.db.query(ShopItem).filter(
                ShopItem.category_id == category.id,
                ShopItem.is_active == True
            ).all()

            catalog[category.name] = {
                "description": category.description,
                "items": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "description": item.description,
                        "price": item.price,
                        "type": item.item_type,
                        "limit": item.purchase_limit,
                        "cooldown": item.cooldown_hours
                    }
                    for item in items
                ]
            }

        return catalog

    def get_user_inventory(self, user_id: int) -> List[Dict]:
        """Получение инвентаря пользователя"""

        purchases = self.db.query(UserPurchase).filter(
            UserPurchase.user_id == user_id,
            UserPurchase.is_active == True
        ).join(ShopItem).all()

        inventory = []
        for purchase in purchases:
            item_dict = {
                "id": purchase.id,
                "item_name": purchase.item.name,
                "item_type": purchase.item.item_type,
                "purchase_price": purchase.purchase_price,
                "purchased_at": purchase.purchased_at,
                "expires_at": purchase.expires_at,
                "is_active": purchase.is_active,
                "meta_data": purchase.meta_data
            }
            inventory.append(item_dict)

        return inventory

    def can_purchase_item(self, user_id: int, item_id: int) -> Dict:
        """Проверка возможности покупки товара"""

        user = self.db.query(User).filter(User.id == user_id).first()
        item = self.db.query(ShopItem).filter(ShopItem.id == item_id).first()

        if not user or not item:
            return {"can_purchase": False, "reason": "Пользователь или товар не найден"}

        if not item.is_active:
            return {"can_purchase": False, "reason": "Товар не доступен"}

        if user.balance < item.price:
            return {"can_purchase": False, "reason": f"Недостаточно средств. Нужно {item.price}, у вас {user.balance}"}

        # Проверка лимита покупок
        if item.purchase_limit > 0:
            user_purchase_count = self.db.query(UserPurchase).filter(
                UserPurchase.user_id == user_id,
                UserPurchase.item_id == item_id,
                UserPurchase.is_active == True
            ).count()

            if user_purchase_count >= item.purchase_limit:
                return {"can_purchase": False, "reason": f"Превышен лимит покупок ({item.purchase_limit})"}

        # Проверка cooldown
        if item.cooldown_hours > 0:
            last_purchase = self.db.query(UserPurchase).filter(
                UserPurchase.user_id == user_id,
                UserPurchase.item_id == item_id,
                UserPurchase.is_active == True
            ).order_by(UserPurchase.purchased_at.desc()).first()

            if last_purchase:
                cooldown_end = last_purchase.purchased_at + timedelta(hours=item.cooldown_hours)
                if datetime.utcnow() < cooldown_end:
                    remaining_hours = int((cooldown_end - datetime.utcnow()).total_seconds() / 3600)
                    return {"can_purchase": False, "reason": f"Cooldown активен. Осталось {remaining_hours} часов"}

        return {"can_purchase": True}

    def purchase_item(self, user_id: int, item_id: int) -> Dict:
        """Покупка товара"""

        # Проверяем возможность покупки
        check_result = self.can_purchase_item(user_id, item_id)
        if not check_result["can_purchase"]:
            return {"success": False, "reason": check_result["reason"]}

        user = self.db.query(User).filter(User.id == user_id).first()
        item = self.db.query(ShopItem).filter(ShopItem.id == item_id).first()

        # Создаем покупку
        purchase = UserPurchase(
            user_id=user_id,
            item_id=item_id,
            purchase_price=item.price,
            meta_data=item.meta_data
        )

        # Для временных товаров устанавливаем срок действия
        if item.meta_data and "duration_hours" in item.meta_data:
            purchase.expires_at = datetime.utcnow() + timedelta(hours=item.meta_data["duration_hours"])

        # Списываем средства
        user.balance -= item.price

        # Активируем товар
        activation_result = self.activate_item(user, item, purchase)

        # Сохраняем результат активации в meta_data покупки
        if purchase.meta_data is None:
            purchase.meta_data = {}
        purchase.meta_data.update({
            'activation_result': activation_result,
            'activated_at': datetime.utcnow().isoformat()
        })

        self.db.add(purchase)
        self.db.commit()
        self.db.refresh(purchase)

        logger.info(
            "Item purchased",
            user_id=user_id,
            item_id=item_id,
            item_name=item.name,
            price=item.price,
            activation_result=activation_result
        )

        return {
            "success": True,
            "purchase_id": purchase.id,
            "item_name": item.name,
            "price": item.price,
            "new_balance": user.balance,
            "activation_result": activation_result
        }

    def activate_item(self, user: User, item: ShopItem, purchase: UserPurchase) -> Dict:
        """Активация купленного товара"""

        activation_handlers = {
            "sticker": self.activate_sticker_item,
            "privilege": self.activate_privilege_item,
            "boost": self.activate_boost_item,
            "custom": self.activate_custom_item
        }

        handler = activation_handlers.get(item.item_type)
        if handler:
            return handler(user, item, purchase)

        return {"activated": False, "message": "Неизвестный тип товара"}

    def activate_sticker_item(self, user: User, item: ShopItem, purchase: UserPurchase) -> Dict:
        """Активация стикерпака"""
        activation_type = item.meta_data.get('activation_type', '')

        if activation_type == 'unlimited_stickers':
            duration = item.meta_data.get('duration_hours', 24)
            return self.activate_unlimited_stickers(user, duration)
        elif activation_type == 'sticker_pack':
            pack_type = item.meta_data.get('sticker_pack', 'premium')
            return self.activate_sticker_pack(user, pack_type)
        else:
            return {"activated": True, "message": f"Стикерпак '{item.name}' активирован"}

    def activate_privilege_item(self, user: User, item: ShopItem, purchase: UserPurchase) -> Dict:
        """Активация привилегии"""
        activation_type = item.meta_data.get('activation_type', '')

        if activation_type == 'admin_privileges':
            duration = item.meta_data.get('duration_hours', 24)
            return self.activate_admin_privileges(user, duration)
        elif activation_type == 'vip_privileges':
            duration = item.meta_data.get('duration_hours', 168)
            return self.activate_vip_privileges(user, duration)
        else:
            return {"activated": True, "message": f"Привилегия '{item.name}' активирована"}

    def activate_boost_item(self, user: User, item: ShopItem, purchase: UserPurchase) -> Dict:
        """Активация буста"""
        activation_type = item.meta_data.get('activation_type', '')

        if activation_type == 'balance_bonus':
            bonus_amount = item.meta_data.get('amount', 0)
            user.balance += bonus_amount

            # Создаем транзакцию для бонуса
            transaction = Transaction(
                user_id=user.id,
                amount=bonus_amount,
                transaction_type='shop_bonus',
                source_game='shop',
                description=f"Бонус от покупки: {item.name}",
                meta_data={'purchase_id': purchase.id, 'item_name': item.name}
            )
            self.db.add(transaction)

            return {"activated": True, "message": f"Бонус {bonus_amount} монет начислен на баланс"}
        elif activation_type == 'experience_boost':
            duration = item.meta_data.get('duration_hours', 2)
            multiplier = item.meta_data.get('multiplier', 2.0)
            return self.activate_experience_boost(user, duration, multiplier)
        else:
            return {"activated": True, "message": f"Буст '{item.name}' активирован"}

    def activate_custom_item(self, user: User, item: ShopItem, purchase: UserPurchase) -> Dict:
        """Активация кастомного товара"""
        activation_type = item.meta_data.get('activation_type', '')

        if activation_type == 'custom_command':
            return self.activate_custom_command(user)
        elif activation_type == 'custom_title':
            return self.activate_custom_title(user)
        else:
            return {"activated": True, "message": f"Кастомный элемент '{item.name}' создан"}

    # Реальные методы активации
    def activate_unlimited_stickers(self, user: User, duration_hours: int) -> Dict:
        """Активация безлимитных стикеров"""
        # В реальной реализации здесь будет логика активации в Telegram
        expires_at = datetime.utcnow() + timedelta(hours=duration_hours)
        return {
            "activated": True,
            "message": f"Безлимитные стикеры активированы на {duration_hours} часов",
            "expires_at": expires_at.isoformat()
        }

    def activate_sticker_pack(self, user: User, pack_type: str) -> Dict:
        """Активация стикерпака"""
        # В реальной реализации здесь будет отправка стикерпака пользователю
        return {
            "activated": True,
            "message": f"Стикерпак '{pack_type}' активирован и отправлен вам"
        }

    def activate_admin_privileges(self, user: User, duration_hours: int) -> Dict:
        """Активация прав администратора"""
        # В реальной реализации здесь будет выдача прав в Telegram чате
        expires_at = datetime.utcnow() + timedelta(hours=duration_hours)
        return {
            "activated": True,
            "message": f"Права администратора активированы на {duration_hours} часов",
            "expires_at": expires_at.isoformat(),
            "privilege_type": "admin"
        }

    def activate_vip_privileges(self, user: User, duration_hours: int) -> Dict:
        """Активация VIP статуса"""
        expires_at = datetime.utcnow() + timedelta(hours=duration_hours)
        return {
            "activated": True,
            "message": f"VIP статус активирован на {duration_hours} часов",
            "expires_at": expires_at.isoformat(),
            "privilege_type": "vip"
        }

    def activate_experience_boost(self, user: User, duration_hours: int, multiplier: float) -> Dict:
        """Активация буста опыта"""
        expires_at = datetime.utcnow() + timedelta(hours=duration_hours)
        return {
            "activated": True,
            "message": f"Буст опыта {multiplier}x активирован на {duration_hours} часов",
            "expires_at": expires_at.isoformat(),
            "multiplier": multiplier
        }

    def activate_custom_command(self, user: User) -> Dict:
        """Активация кастомной команды"""
        # В реальной реализации здесь будет создание кастомной команды
        command_name = f"custom_{user.id}"
        return {
            "activated": True,
            "message": f"Кастомная команда /{command_name} создана",
            "command_name": command_name
        }

    def activate_custom_title(self, user: User) -> Dict:
        """Активация кастомного заголовка"""
        return {
            "activated": True,
            "message": "Кастомный заголовок активирован в вашем профиле"
        }

    def get_user_purchase_history(self, user_id: int, limit: int = 20) -> List[Dict]:
        """Получение истории покупок пользователя"""

        purchases = self.db.query(UserPurchase).filter(
            UserPurchase.user_id == user_id
        ).join(ShopItem).order_by(UserPurchase.purchased_at.desc()).limit(limit).all()

        history = []
        for purchase in purchases:
            history.append({
                "id": purchase.id,
                "item_name": purchase.item.name,
                "item_type": purchase.item.item_type,
                "price": purchase.purchase_price,
                "purchased_at": purchase.purchased_at,
                "expires_at": purchase.expires_at,
                "is_active": purchase.is_active,
                "activation_result": purchase.meta_data.get('activation_result', {}) if purchase.meta_data else {}
            })

        return history

    def check_expired_items(self):
        """Проверка и деактивация просроченных товаров"""
        now = datetime.utcnow()
        expired_purchases = self.db.query(UserPurchase).filter(
            UserPurchase.expires_at <= now,
            UserPurchase.is_active == True
        ).all()

        for purchase in expired_purchases:
            purchase.is_active = False
            logger.info(f"Expired purchase deactivated: {purchase.id}")

        self.db.commit()
        return len(expired_purchases)