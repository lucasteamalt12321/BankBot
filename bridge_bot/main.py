"""BridgeBot — точка входа.

Запускает aiogram-бота для пересылки сообщений TG ↔ VK.
"""

import asyncio
import signal

import structlog

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bridge_bot.config import (
    BRIDGE_ENABLED,
    BRIDGE_TG_CHAT_ID,
    VK_TOKEN,
    VK_PEER_ID,
    BRIDGE_ADMIN_CHAT_ID,
)
from bridge_bot.handlers import router as bridge_router
from common.config import bot_settings
from core.middleware import ErrorHandlingMiddleware

from bridge_bot.vk_listener import VKListenerThread

logger = structlog.get_logger()


async def main() -> None:
    """Запустить BridgeBot с поддержкой graceful shutdown."""
    bot = Bot(
        token=bot_settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    admin_chat_id = BRIDGE_ADMIN_CHAT_ID or (
        bot_settings.ADMIN_TELEGRAM_ID if bot_settings.ADMIN_TELEGRAM_ID else None
    )
    dp.message.middleware(ErrorHandlingMiddleware(admin_chat_id=admin_chat_id))
    dp.callback_query.middleware(ErrorHandlingMiddleware(admin_chat_id=admin_chat_id))
    logger.info("ErrorHandlingMiddleware registered", admin_chat_id=admin_chat_id)

    vk_thread: VKListenerThread | None = None

    if BRIDGE_ENABLED:
        dp.include_router(bridge_router)
        loop = asyncio.get_event_loop()
        vk_thread = VKListenerThread(
            vk_token=VK_TOKEN,
            tg_chat_id=BRIDGE_TG_CHAT_ID,
            bot=bot,
            loop=loop,
        )
        vk_thread.start()
        logger.info("Bridge started", tg_chat_id=BRIDGE_TG_CHAT_ID, vk_peer_id=VK_PEER_ID)
    else:
        logger.info("Bridge disabled (BRIDGE_ENABLED=false)")

    shutdown_event = asyncio.Event()

    def _handle_signal(sig: signal.Signals) -> None:
        logger.info("Shutdown signal received", signal=sig.name)
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_signal, sig)
        except NotImplementedError:
            signal.signal(sig, lambda s, f: _handle_signal(signal.Signals(s)))

    try:
        polling_task = asyncio.create_task(dp.start_polling(bot))
        shutdown_task = asyncio.create_task(shutdown_event.wait())
        done, pending = await asyncio.wait(
            {polling_task, shutdown_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    finally:
        closed: list[str] = []
        if vk_thread is not None:
            vk_thread.stop()
            vk_thread.join(timeout=5)
            closed.append("VKListenerThread")
        try:
            from database.connection import close_pool
            await close_pool()
            closed.append("DatabaseConnectionPool")
        except Exception:
            pass
        await bot.session.close()
        closed.append("BotSession")
        logger.info("Shutdown complete", resources=closed)


if __name__ == "__main__":
    asyncio.run(main())
