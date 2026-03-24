"""
Dependency Injection middleware for aiogram.

Provides services to command handlers through middleware.
"""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.orm import Session

from database.database import get_db
from src.repository.user_repository import UserRepository
from core.services.user_service import UserService
from core.services.admin_service import AdminService
from core.services.admin_stats_service import AdminStatsService
from core.services.broadcast_service import BroadcastService
from core.services.shop_service import ShopService
from core.services.transaction_service import TransactionService


class DependencyInjectionMiddleware(BaseMiddleware):
    """
    Middleware для инъекции зависимостей в обработчики команд.
    
    Создает экземпляры сервисов и репозиториев для каждого запроса
    и добавляет их в data для использования в обработчиках.
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Инъекция зависимостей в обработчик.
        
        Args:
            handler: Следующий обработчик в цепочке
            event: Telegram событие
            data: Данные для передачи в обработчик
            
        Returns:
            Результат выполнения обработчика
        """
        # Получаем сессию БД
        db: Session = next(get_db())
        
        try:
            # Создаем репозитории
            user_repo = UserRepository(db)
            
            # Создаем сервисы
            user_service = UserService(user_repo)
            admin_service = AdminService(user_repo)
            admin_stats_service = AdminStatsService(db)
            shop_service = ShopService(user_repo)
            transaction_service = TransactionService(user_repo)
            
            # Broadcast service требует bot instance
            bot = data.get("bot")
            broadcast_service = BroadcastService(db, bot) if bot else None
            
            # Добавляем зависимости в data
            data["db"] = db
            data["user_repo"] = user_repo
            data["user_service"] = user_service
            data["admin_service"] = admin_service
            data["admin_stats_service"] = admin_stats_service
            data["broadcast_service"] = broadcast_service
            data["shop_service"] = shop_service
            data["transaction_service"] = transaction_service
            
            # Вызываем следующий обработчик
            return await handler(event, data)
            
        finally:
            # Закрываем сессию БД
            db.close()
