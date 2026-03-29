"""VK Bot — точка входа.

Запускает VK Long Poll для приёма сообщений и публикации в VK-канал.
В текущей архитектуре VK Long Poll встроен в BridgeBot (VKListenerThread).
Этот модуль предоставляет независимую точку входа для запуска VK Bot отдельно.
"""

from __future__ import annotations

import signal
import threading

import structlog

from vk_bot.bot import create_vk_session, create_longpoll
from vk_bot.config import VK_TOKEN, VK_PEER_ID
from bridge_bot.loop_guard import has_bot_mark

logger = structlog.get_logger()

_stop_event = threading.Event()


def _handle_signal(signum: int, frame) -> None:  # noqa: ANN001
    logger.info("VK Bot shutdown signal received", signal=signum)
    _stop_event.set()


def run() -> None:
    """Запустить VK Long Poll цикл."""
    if not VK_TOKEN:
        logger.error("VK_TOKEN не задан, VK Bot не запущен")
        return

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    session = create_vk_session()
    longpoll = create_longpoll(session)
    vk = session.get_api()  # noqa: F841

    logger.info("VK Bot started", peer_id=VK_PEER_ID)

    try:
        from vk_api.longpoll import VkEventType
        for event in longpoll.listen():
            if _stop_event.is_set():
                break
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                text = event.text or ""
                if has_bot_mark(text):
                    logger.debug("Skipping [BOT] message", text=text[:50])
                    continue
                logger.info("VK message received", text=text[:80])
    except Exception as e:
        logger.error("VK Long Poll error", error=str(e))
    finally:
        logger.info("VK Bot stopped")


if __name__ == "__main__":
    run()
