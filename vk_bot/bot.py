"""Инициализация VK Long Poll сессии."""

from __future__ import annotations

import structlog
import vk_api
from vk_api.longpoll import VkLongPoll

from vk_bot.config import VK_TOKEN

logger = structlog.get_logger()


def create_vk_session() -> vk_api.VkApi:
    """Создать аутентифицированную VK API сессию.

    Returns:
        Аутентифицированный VkApi объект.
    """
    return vk_api.VkApi(token=VK_TOKEN)


def create_longpoll(session: vk_api.VkApi) -> VkLongPoll:
    """Создать VK Long Poll объект.

    Args:
        session: Аутентифицированная VK API сессия.

    Returns:
        VkLongPoll объект для получения событий.
    """
    return VkLongPoll(session)
