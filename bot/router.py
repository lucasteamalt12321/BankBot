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


def setup_routers(application, admin_commands=None, user_commands=None,
                  shop_commands=None, game_commands=None, system_commands=None):
    """
    Регистрирует обработчики команд в PTB Application (совместимость с python-telegram-bot).

    Args:
        application: PTB Application instance
        admin_commands: Экземпляр AdminCommands
        user_commands: Экземпляр UserCommands
        shop_commands: Экземпляр ShopCommands
        game_commands: Экземпляр GameCommands
        system_commands: Экземпляр SystemCommands
    """
    from telegram.ext import CommandHandler

    modules = [
        ("system", system_commands),
        ("user", user_commands),
        ("shop", shop_commands),
        ("game", game_commands),
        ("admin", admin_commands),
    ]

    for _name, module in modules:
        if module is None:
            continue
        for attr_name in dir(module):
            if attr_name.endswith("_command") and callable(getattr(module, attr_name)):
                cmd = attr_name.replace("_command", "")
                handler = CommandHandler(cmd, getattr(module, attr_name))
                application.add_handler(handler)
