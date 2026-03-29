"""Отправка сообщений в VK API."""

import random
from datetime import datetime, timezone
from typing import Optional

import structlog
import vk_api

from bridge_bot.loop_guard import add_bot_mark
from bridge_bot.queue import RateLimitError

logger = structlog.get_logger()


def _create_vk_session(token: str) -> vk_api.VkApi:
    """Create authenticated VK API session.

    Args:
        token: VK API token.

    Returns:
        Authenticated VkApi session.
    """
    return vk_api.VkApi(token=token)


def send_text(
    text: str,
    peer_id: int,
    sender_name: str,
    vk_token: str,
) -> int:
    """Send text message to VK chat.

    Prepends [TG] sender_name: prefix and adds [BOT] mark to prevent loops.

    Args:
        text: Original message text.
        peer_id: VK peer_id of the target chat.
        sender_name: Display name of the Telegram sender.
        vk_token: VK API token.

    Returns:
        VK message ID of the sent message.

    Raises:
        RateLimitError: If VK API returns error code 9 (too many requests).
        vk_api.exceptions.ApiError: On other VK API errors.
    """
    prefixed = f"[TG] {sender_name}: {text}"
    marked = add_bot_mark(prefixed)

    session = _create_vk_session(vk_token)
    vk = session.get_api()

    try:
        result: int = vk.messages.send(
            peer_id=peer_id,
            message=marked,
            random_id=random.randint(1, 2**31),
        )
        logger.info(
            "Message sent to VK",
            platform="vk",
            message_id=result,
            sender=sender_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        return result
    except vk_api.exceptions.ApiError as e:
        if e.code == 9:  # Too many requests
            retry_after: Optional[float] = None
            raise RateLimitError(retry_after=retry_after) from e
        raise
