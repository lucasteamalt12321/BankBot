"""Обработчики входящих сообщений из Telegram-канала."""

import structlog
from aiogram import Router
from aiogram.filters import Filter
from aiogram.types import Message

from bridge_bot.config import BRIDGE_TG_CHAT_ID, VK_PEER_ID, VK_TOKEN
from bridge_bot.loop_guard import has_bot_mark
from bridge_bot.queue import MessageQueue, OutboundMessage
from bridge_bot.vk_publisher import send_text

logger = structlog.get_logger()

router = Router(name="bridge-tg-forwarder")

_message_queue: MessageQueue | None = None


def get_message_queue() -> MessageQueue:
    """Get or create the global message queue.

    Returns:
        Singleton MessageQueue instance configured to send to VK.
    """
    global _message_queue
    if _message_queue is None:

        def _send(msg: OutboundMessage) -> None:
            send_text(
                text=msg.text,
                peer_id=VK_PEER_ID,
                sender_name=msg.sender_name,
                vk_token=VK_TOKEN,
            )

        _message_queue = MessageQueue(send_func=_send)
    return _message_queue


class BridgeChatFilter(Filter):
    """Filter: only messages from the configured Bridge TG chat."""

    async def __call__(self, message: Message) -> bool:
        """Check if message originates from the configured Bridge chat.

        Args:
            message: Incoming Telegram message.

        Returns:
            True if message is from BRIDGE_TG_CHAT_ID, False otherwise.
        """
        return message.chat.id == BRIDGE_TG_CHAT_ID


@router.message(BridgeChatFilter())
async def forward_to_vk(message: Message) -> None:
    """Forward Telegram message to VK via MessageQueue.

    Skips messages containing [BOT] mark to prevent forwarding loops.

    Args:
        message: Incoming Telegram message.
    """
    text = message.text or message.caption or ""

    if has_bot_mark(text):
        logger.debug("Skipping message with [BOT] mark", chat_id=message.chat.id)
        return

    sender_name = message.from_user.full_name if message.from_user else "Unknown"

    outbound = OutboundMessage(
        text=text,
        platform="vk",
        sender_name=sender_name,
    )
    get_message_queue().put(outbound)
    logger.info(
        "Message queued for VK",
        sender=sender_name,
        chat_id=message.chat.id,
        text_preview=text[:50],
    )
