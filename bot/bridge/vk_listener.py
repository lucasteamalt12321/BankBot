"""VK listener for Bridge module — polls VK Long Poll and forwards to Telegram."""

import asyncio
import threading
from typing import Optional

import structlog
import vk_api
from vk_api.longpoll import VkEventType, VkLongPoll

from bot.bridge.loop_guard import has_bot_mark

logger = structlog.get_logger()


class VKListenerThread(threading.Thread):
    """Thread that polls VK Long Poll API and forwards messages to Telegram.

    Runs as a daemon thread. Forwards messages from VK to TG via
    asyncio.run_coroutine_threadsafe to safely interact with the aiogram event loop.

    Args:
        vk_token: VK API token for authentication.
        tg_chat_id: Telegram chat ID to forward messages to.
        bot: aiogram Bot instance.
        loop: asyncio event loop running in the main thread.
    """

    def __init__(
        self,
        vk_token: str,
        tg_chat_id: int,
        bot,  # aiogram.Bot
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Initialize VKListenerThread.

        Args:
            vk_token: VK API token for authentication.
            tg_chat_id: Telegram chat ID to forward messages to.
            bot: aiogram Bot instance.
            loop: asyncio event loop running in the main thread.
        """
        super().__init__(name="vk-listener", daemon=True)
        self._vk_token = vk_token
        self._tg_chat_id = tg_chat_id
        self._bot = bot
        self._loop = loop
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Signal the thread to stop on next Long Poll iteration."""
        self._stop_event.set()

    def run(self) -> None:
        """Main loop: poll VK Long Poll and forward messages to Telegram."""
        try:
            session = vk_api.VkApi(token=self._vk_token)
            longpoll = VkLongPoll(session)
            logger.info("VK Long Poll listener started")

            for event in longpoll.listen():
                if self._stop_event.is_set():
                    break

                if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                    self._handle_event(event, session)
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error("VK listener error", error=str(e))
        finally:
            logger.info("VK Long Poll listener stopped")

    def _handle_event(self, event, session: vk_api.VkApi) -> None:
        """Process a VK message event and forward to Telegram.

        Skips messages containing [BOT] mark to prevent forwarding loops.
        Forwards text and supported media attachments.

        Args:
            event: VK Long Poll event with message data.
            session: Authenticated VkApi session (reused to avoid re-auth).
        """
        text = getattr(event, "text", "") or ""

        if has_bot_mark(text):
            logger.debug("Skipping VK message with [BOT] mark")
            return

        sender_name = self._get_sender_name(event, session)
        forwarded_text = f"[VK] {sender_name}: {text}" if text else f"[VK] {sender_name}:"

        asyncio.run_coroutine_threadsafe(
            self._bot.send_message(
                chat_id=self._tg_chat_id,
                text=forwarded_text,
            ),
            self._loop,
        )
        logger.info(
            "Message forwarded to TG",
            platform="tg",
            sender=sender_name,
            text_preview=text[:50],
        )

        # Пересылка медиавложений (Б-6)
        attachments = getattr(event, "attachments", {})
        if attachments:
            self._handle_attachments(event, attachments, sender_name)

    def _handle_attachments(self, event, attachments: dict, sender_name: str) -> None:
        """Forward VK media attachments to Telegram.

        Supports photos, videos, and documents with exponential backoff retries.

        Args:
            event: VK Long Poll event.
            attachments: Dict of attachment type → attachment data from the event.
            sender_name: Display name of the VK sender.
        """
        import time

        for attach_type, attach_data in attachments.items():
            url: Optional[str] = None
            send_coro = None

            if attach_type.startswith("attach") and isinstance(attach_data, str):
                # Вложения в формате "photo{owner_id}_{id}" и т.п. — пропускаем без URL
                continue

            try:
                if attach_type == "photo":
                    sizes = attach_data.get("sizes", [])
                    if sizes:
                        url = sizes[-1].get("url")
                    if url:
                        send_coro = self._bot.send_photo(
                            chat_id=self._tg_chat_id,
                            photo=url,
                            caption=f"[VK] {sender_name}",
                        )
                elif attach_type == "video":
                    owner_id = attach_data.get("owner_id", "")
                    video_id = attach_data.get("id", "")
                    url = f"https://vk.com/video{owner_id}_{video_id}"
                    send_coro = self._bot.send_message(
                        chat_id=self._tg_chat_id,
                        text=f"[VK] {sender_name}: {url}",
                    )
                elif attach_type == "doc":
                    url = attach_data.get("url")
                    if url:
                        send_coro = self._bot.send_document(
                            chat_id=self._tg_chat_id,
                            document=url,
                            caption=f"[VK] {sender_name}",
                        )

                if send_coro is None:
                    continue

                # Повторные попытки: 1s → 2s → 4s, максимум 3 попытки
                for attempt in range(3):
                    try:
                        asyncio.run_coroutine_threadsafe(send_coro, self._loop)
                        logger.info(
                            "Media forwarded to TG",
                            attach_type=attach_type,
                            sender=sender_name,
                        )
                        break
                    except Exception as e:
                        delay = 2**attempt
                        logger.warning(
                            "Media forward failed, retrying",
                            attempt=attempt + 1,
                            delay=delay,
                            error=str(e),
                        )
                        time.sleep(delay)

            except Exception as e:
                logger.error(
                    "Failed to process attachment",
                    attach_type=attach_type,
                    error=str(e),
                )

    def _get_sender_name(self, event, session: vk_api.VkApi) -> str:
        """Extract sender display name from VK event.

        Args:
            event: VK Long Poll event.
            session: Authenticated VkApi session.

        Returns:
            Sender display name or 'VK User' as fallback.
        """
        try:
            vk = session.get_api()
            user_id = event.user_id
            users = vk.users.get(user_ids=user_id, fields="first_name,last_name")
            if users:
                u = users[0]
                name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
                return name or "VK User"
        except Exception:
            pass
        return "VK User"
