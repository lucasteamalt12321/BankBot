"""VK Bot — точка входа.

Запускает VK Long Poll для приёма сообщений и публикации в VK-канал.
В текущей архитектуре VK Long Poll встроен в BridgeBot (VKListenerThread).
Этот модуль предоставляет независимую точку входа для запуска VK Bot отдельно.
"""

from __future__ import annotations

import signal
import threading
from typing import Optional

import structlog

from vk_bot.bot import create_vk_session, create_longpoll
from vk_bot.config import VK_TOKEN, VK_PEER_ID
from bridge_bot.loop_guard import has_bot_mark

logger = structlog.get_logger()

_stop_event = threading.Event()


def _handle_signal(signum: int, frame) -> None:  # noqa: ANN001
    logger.info("VK Bot shutdown signal received", signal=signum)
    _stop_event.set()


def _publish_to_channel(vk, peer_id: int, message: str, attachments: Optional[list] = None) -> bool:
    """Публиковать сообщение в VK-канал.

    Args:
        vk: VK API объект.
        peer_id: ID канала/чата для публикации.
        message: Текст сообщения.
        attachments: Список вложений (опционально).

    Returns:
        True если успешно, False иначе.
    """
    try:
        params = {
            "peer_id": peer_id,
            "message": message,
            "random_id": 0,
        }
        if attachments:
            params["attachment"] = attachments

        result = vk.messages.send(**params)
        logger.info("Message published to VK channel", peer_id=peer_id, message_id=result)
        return True
    except Exception as e:
        logger.error("Failed to publish to VK channel", error=str(e), peer_id=peer_id)
        return False


def _get_message_attachments(vk, message_id: int, peer_id: int) -> Optional[list]:
    """Получить вложения сообщения.

    Args:
        vk: VK API объект.
        message_id: ID сообщения.
        peer_id: ID чата/канала.

    Returns:
        Список строк вложений или None.
    """
    try:
        msgs = vk.messages.getById(message_ids=[message_id], peer_id=peer_id)
        if msgs and msgs.get("items"):
            msg = msgs["items"][0]
            attachments = msg.get("attachments", [])
            if attachments:
                attachment_strings = []
                for att in attachments:
                    att_type = att.get("type")
                    att_obj = att.get(att_type, {})
                    owner_id = att_obj.get("owner_id")
                    item_id = att_obj.get("id")
                    access_key = att_obj.get("access_key", "")
                    if owner_id and item_id:
                        attach_str = f"{att_type}{owner_id}_{item_id}"
                        if access_key:
                            attach_str += f"_{access_key}"
                        attachment_strings.append(attach_str)
                return attachment_strings if attachment_strings else None
    except Exception as e:
        logger.warning("Failed to get attachments", error=str(e))
    return None


def run() -> None:
    """Запустить VK Long Poll цикл."""
    if not VK_TOKEN:
        logger.error("VK_TOKEN не задан, VK Bot не запущен")
        return

    if not VK_PEER_ID:
        logger.error("VK_PEER_ID не задан, VK Bot не может публиковать в канал")
        return

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    session = create_vk_session()
    longpoll = create_longpoll(session)
    vk = session.get_api()

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

                logger.info("VK message received", text=text[:80], msg_id=event.message_id)

                attachments = _get_message_attachments(vk, event.message_id, event.peer_id)
                _publish_to_channel(vk, VK_PEER_ID, text, attachments)

    except Exception as e:
        logger.error("VK Long Poll error", error=str(e))
    finally:
        logger.info("VK Bot stopped")


if __name__ == "__main__":
    run()
