"""Shop service for business logic related to shop operations."""

from datetime import datetime
from typing import Optional, List
from database.database import ShopCategory, ShopItem, UserPurchase
from src.repository.user_repository import UserRepository


class ShopService:
    """
    Сервис для управления магазином.
    
    Содержит бизнес-логику связанную с товарами и покупками.
    """

    def __init__(self, user_repo: UserRepository):
        """
        Инициализация сервиса магазина.

        Args:
            user_repo: Репозиторий для работы с пользователями
        """
        self.user_repo = user_repo

    def get_all_categories(self, only_active: bool = True) -> List[ShopCategory]:
        """
        Получить все категории товаров.

        Args:
            only_active: Только активные категории

        Returns:
            Список категорий
        """
        query = self.user_repo.session.query(ShopCategory)
        if only_active:
            query = query.filter(ShopCategory.is_active)
        return query.order_by(ShopCategory.sort_order).all()

    def get_category_by_id(self, category_id: int) -> Optional[ShopCategory]:
        """
        Получить категорию по ID.

        Args:
            category_id: ID категории

        Returns:
            ShopCategory или None если не найдена
        """
        return self.user_repo.session.query(ShopCategory).filter_by(
            id=category_id
        ).first()

    def get_all_items(
        self,
        only_active: bool = True,
        category_id: int = None
    ) -> List[ShopItem]:
        """
        Получить все товары.

        Args:
            only_active: Только активные товары
            category_id: Фильтр по категории (опционально)

        Returns:
            Список товаров
        """
        query = self.user_repo.session.query(ShopItem)
        if only_active:
            query = query.filter(ShopItem.is_active)
        if category_id:
            query = query.filter(ShopItem.category_id == category_id)
        return query.order_by(ShopItem.name).all()

    def get_item_by_id(self, item_id: int) -> Optional[ShopItem]:
        """
        Получить товар по ID.

        Args:
            item_id: ID товара

        Returns:
            ShopItem или None если не найден
        """
        return self.user_repo.session.query(ShopItem).filter_by(
            id=item_id
        ).first()

    def get_items_by_category(
        self,
        category_id: int,
        only_active: bool = True
    ) -> List[ShopItem]:
        """
        Получить товары по категории.

        Args:
            category_id: ID категории
            only_active: Только активные товары

        Returns:
            Список товаров
        """
        query = self.user_repo.session.query(ShopItem).filter_by(
            category_id=category_id
        )
        if only_active:
            query = query.filter(ShopItem.is_active)
        return query.order_by(ShopItem.name).all()

    def purchase_item(
        self,
        user_id: int,
        item_id: int,
        price_paid: int = None
    ) -> Optional[UserPurchase]:
        """
        Покупка товара пользователем.

        Args:
            user_id: ID пользователя
            item_id: ID товара
            price_paid: Цена покупки (если None, используется цена товара)

        Returns:
            Созданная UserPurchase или None если покупка не удалась

        Raises:
            ValueError: Если пользователь или товар не найден, или недостаточно средств
        """
        user = self.user_repo.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        item = self.user_repo.session.query(ShopItem).filter_by(id=item_id).first()
        if not item:
            raise ValueError(f"Item {item_id} not found")

        if not item.is_active:
            raise ValueError(f"Item {item_id} is not active")

        # Проверяем лимит покупок
        if item.purchase_limit > 0:
            current_purchases = self.user_repo.session.query(UserPurchase).filter_by(
                user_id=user_id,
                item_id=item_id,
                is_active=True
            ).count()
            if current_purchases >= item.purchase_limit:
                raise ValueError(
                    f"Purchase limit reached for item {item_id}. "
                    f"Maximum: {item.purchase_limit}"
                )

        # Проверяем cooldown
        if item.cooldown_hours > 0:
            from datetime import timedelta
            cooldown_until = datetime.utcnow() - timedelta(hours=item.cooldown_hours)
            recent_purchase = self.user_repo.session.query(UserPurchase).filter_by(
                user_id=user_id,
                item_id=item_id
            ).filter(UserPurchase.purchased_at > cooldown_until).first()
            if recent_purchase:
                raise ValueError(
                    f"Item {item_id} is on cooldown. "
                    f"Try again in {item.cooldown_hours} hours"
                )

        # Проверяем баланс
        price = price_paid if price_paid is not None else item.price
        if user.balance < price:
            raise ValueError(
                f"Insufficient balance. User has {user.balance}, "
                f"item costs {price}"
            )

        # Создаем запись покупки
        user_purchase = UserPurchase(
            user_id=user_id,
            item_id=item_id,
            purchase_price=price,
            purchased_at=datetime.utcnow(),
            is_active=True
        )
        self.user_repo.session.add(user_purchase)

        # Обновляем баланс пользователя
        user.balance -= price
        user.total_purchases += 1

        # Фиксируем изменения
        self.user_repo.session.commit()
        self.user_repo.session.refresh(user_purchase)
        self.user_repo.session.refresh(user)

        return user_purchase

    def get_user_purchases(
        self,
        user_id: int,
        only_active: bool = True,
        limit: int = 50,
        offset: int = 0
    ) -> List[UserPurchase]:
        """
        Получить историю покупок пользователя.

        Args:
            user_id: ID пользователя
            only_active: Только активные покупки
            limit: Максимальное количество записей
            offset: Смещение для пагинации

        Returns:
            Список покупок
        """
        query = self.user_repo.session.query(UserPurchase).filter_by(
            user_id=user_id
        )
        if only_active:
            query = query.filter(UserPurchase.is_active)
        return query.order_by(UserPurchase.purchased_at.desc()).offset(offset).limit(limit).all()

    def get_user_total_purchases(self, user_id: int) -> int:
        """
        Получить общее количество покупок пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Количество покупок
        """
        return self.user_repo.session.query(UserPurchase).filter_by(
            user_id=user_id
        ).count()

    def activate_item(self, user_id: int, item_id: int) -> Optional[UserPurchase]:
        """
        Активировать купленный товар для пользователя.

        Args:
            user_id: ID пользователя
            item_id: ID товара

        Returns:
            Обновленная UserPurchase или None если не найдена
        """
        user_purchase = self.user_repo.session.query(UserPurchase).filter_by(
            user_id=user_id,
            item_id=item_id
        ).first()
        if user_purchase:
            if not user_purchase.is_active:
                user_purchase.is_active = True
                self.user_repo.session.commit()
                self.user_repo.session.refresh(user_purchase)
            return user_purchase
        return None

    def deactivate_item(self, user_id: int, item_id: int) -> Optional[UserPurchase]:
        """
        Деактивировать купленный товар для пользователя.

        Args:
            user_id: ID пользователя
            item_id: ID товара

        Returns:
            Обновленная UserPurchase или None если не найдена
        """
        user_purchase = self.user_repo.session.query(UserPurchase).filter_by(
            user_id=user_id,
            item_id=item_id
        ).first()
        if user_purchase:
            if user_purchase.is_active:
                user_purchase.is_active = False
                self.user_repo.session.commit()
                self.user_repo.session.refresh(user_purchase)
            return user_purchase
        return None
