"""Command router for Telegram bot."""

from aiogram import Router

from bot.commands import (
    admin_router,
    user_router,
    shop_router,
    game_router,
    system_router,
)


def create_router() -> Router:
    """
    Создает и настраивает роутер для всех команд.
    
    Returns:
        Router с зарегистрированными обработчиками команд
    """
    router = Router()
    
    # Регистрируем роутеры команд
    router.include_router(system_router)
    router.include_router(user_router)
    router.include_router(shop_router)
    router.include_router(game_router)
    router.include_router(admin_router)
    
    return router


# Глобальный экземпляр роутера
bot_router = create_router()
