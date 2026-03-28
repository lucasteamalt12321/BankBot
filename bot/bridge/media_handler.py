"""Media handler for Bridge module — uploads TG media to VK."""

import tempfile
import time
from pathlib import Path
from typing import Optional

import requests
import structlog
import vk_api

logger = structlog.get_logger()

MAX_RETRIES = 3


def _retry(func, *args, **kwargs):
    """Execute func with exponential backoff retries (1s → 2s → 4s).

    Args:
        func: Callable to execute.
        *args: Positional arguments for func.
        **kwargs: Keyword arguments for func.

    Returns:
        Return value of func on success.

    Raises:
        Exception: Re-raises the last exception after MAX_RETRIES attempts.
    """
    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise
            delay = 2**attempt
            logger.warning(
                "Retrying after error",
                attempt=attempt + 1,
                delay=delay,
                error=str(e),
            )
            time.sleep(delay)


def upload_photo_to_vk(
    file_bytes: bytes,
    vk_session: vk_api.VkApi,
    peer_id: int,
) -> str:
    """Upload photo bytes to VK and return attachment string.

    Downloads photo to a temporary file, uploads via VK Photos API,
    then removes the temporary file.

    Args:
        file_bytes: Raw photo bytes.
        vk_session: Authenticated VkApi session.
        peer_id: VK peer_id for the target chat.

    Returns:
        VK attachment string like 'photo{owner_id}_{photo_id}'.

    Raises:
        Exception: On upload failure after MAX_RETRIES attempts.
    """
    vk = vk_session.get_api()

    def _upload() -> str:
        upload_server = vk.photos.getMessagesUploadServer(peer_id=peer_id)
        upload_url = upload_server["upload_url"]

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                response = requests.post(upload_url, files={"photo": f}, timeout=30).json()
            saved = vk.photos.saveMessagesPhoto(
                photo=response["photo"],
                server=response["server"],
                hash=response["hash"],
            )
            photo = saved[0]
            attachment = f"photo{photo['owner_id']}_{photo['id']}"
            logger.info("Photo uploaded to VK", attachment=attachment)
            return attachment
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    return _retry(_upload)


def upload_video_to_vk(
    file_bytes: bytes,
    filename: str,
    vk_session: vk_api.VkApi,
) -> str:
    """Upload video bytes to VK and return attachment string.

    Downloads video to a temporary file, uploads via VK Video API,
    then removes the temporary file.

    Args:
        file_bytes: Raw video bytes.
        filename: Original filename with extension (used to determine suffix).
        vk_session: Authenticated VkApi session.

    Returns:
        VK attachment string like 'video{owner_id}_{video_id}'.

    Raises:
        Exception: On upload failure after MAX_RETRIES attempts.
    """
    vk = vk_session.get_api()

    def _upload() -> str:
        upload_info = vk.video.save(name=filename, is_private=1)
        upload_url = upload_info["upload_url"]
        owner_id = upload_info["owner_id"]
        video_id = upload_info["video_id"]

        suffix = Path(filename).suffix or ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                requests.post(upload_url, files={"video_file": (filename, f)}, timeout=120)
            attachment = f"video{owner_id}_{video_id}"
            logger.info("Video uploaded to VK", attachment=attachment)
            return attachment
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    return _retry(_upload)


def upload_doc_to_vk(
    file_bytes: bytes,
    filename: str,
    vk_session: vk_api.VkApi,
    peer_id: int,
) -> str:
    """Upload document bytes to VK and return attachment string.

    Downloads document to a temporary file, uploads via VK Docs API,
    then removes the temporary file.

    Args:
        file_bytes: Raw document bytes.
        filename: Original filename with extension.
        vk_session: Authenticated VkApi session.
        peer_id: VK peer_id for the target chat.

    Returns:
        VK attachment string like 'doc{owner_id}_{doc_id}'.

    Raises:
        Exception: On upload failure after MAX_RETRIES attempts.
    """
    vk = vk_session.get_api()

    def _upload() -> str:
        upload_server = vk.docs.getMessagesUploadServer(peer_id=peer_id, type="doc")
        upload_url = upload_server["upload_url"]

        suffix = Path(filename).suffix or ".bin"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                response = requests.post(
                    upload_url,
                    files={"file": (filename, f)},
                    timeout=60,
                ).json()
            saved = vk.docs.save(file=response["file"], title=filename)
            doc = saved["doc"]
            attachment = f"doc{doc['owner_id']}_{doc['id']}"
            logger.info("Document uploaded to VK", attachment=attachment, filename=filename)
            return attachment
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    return _retry(_upload)


async def download_tg_file(bot, file_id: str) -> Optional[bytes]:
    """Download a file from Telegram by file_id.

    Args:
        bot: aiogram Bot instance.
        file_id: Telegram file identifier.

    Returns:
        Raw file bytes, or None if download failed.
    """
    try:
        tg_file = await bot.get_file(file_id)
        file_bytes = await bot.download_file(tg_file.file_path)
        return file_bytes.read() if hasattr(file_bytes, "read") else bytes(file_bytes)
    except Exception as e:
        logger.error("Failed to download TG file", file_id=file_id, error=str(e))
        return None
