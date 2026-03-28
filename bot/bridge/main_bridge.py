"""Bridge bot entry point — aiogram bot with Bridge module integration.

Точка входа для запуска aiogram-бота с Bridge-модулем (TG ↔ VK).
Основной bot/main.py использует python-telegram-bot для банковского функционала.
"""

import asyncio
import signal
import structlog

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.bridge.config import (
    BRIDGE_ENABLED,
    BRIDGE_TG_CHAT_ID,
    VK_TOKEN,
    VK_PEER_ID,
)
from bot.bridge.telegram_forwarder import router as bridge_router
from bot.bridge.vk_listener import VKListenerThread
from config.settings import bot_settings

logger = structlog.get_logger()


async def main() -> None:
    """Start aiogram bot with Bridge module.

    Запускает aiogram Dispatcher, при BRIDGE_ENABLED=true поднимает
    VKListenerThread. Реализует Graceful Shutdown: при SIGTERM/SIGINT
    останавливает VK-поток, закрывает сессию бота и соединения с БД.
    """
    bot = Bot(
        token=bot_settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

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
        logger.info("Bridge module started", tg_chat_id=BRIDGE_TG_CHAT_ID, vk_peer_id=VK_PEER_ID)
    else:
        logger.info("Bridge module disabled (BRIDGE_ENABLED=false)")

    # Graceful shutdown handler
    shutdown_event = asyncio.Event()

    def _handle_signal(sig: signal.Signals) -> None:
        logger.info("Shutdown signal received", signal=sig.name)
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_signal, sig)
        except NotImplementedError:
            # Windows не поддерживает add_signal_handler — используем signal.signal
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
        closed_resources: list[str] = []

        if vk_thread is not None:
            logger.info("Stopping VK listener thread...")
            vk_thread.stop()
            vk_thread.join(timeout=5)
            closed_resources.append("VKListenerThread")
            logger.info("VK listener thread stopped")

        # Закрываем Connection Pool / соединения с БД если они были открыты
        try:
            from database.connection import close_pool
            await close_pool()
            closed_resources.append("DatabaseConnectionPool")
        except (ImportError, Exception) as exc:
            logger.debug("DB pool close skipped", reason=str(exc))

        await bot.session.close()
        closed_resources.append("BotSession")

        logger.info(
            "Shutdown complete. Closed resources",
            resources=closed_resources,
        )


if __name__ == "__main__":
    asyncio.run(main())
