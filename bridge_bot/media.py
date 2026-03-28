"""Работа с медиафайлами (скачивание из TG, загрузка в VK)."""

# Re-export из bot/bridge/media_handler.py
from bot.bridge.media_handler import (
    upload_photo_to_vk,
    upload_video_to_vk,
    upload_doc_to_vk,
    download_tg_file,
)

__all__ = ["upload_photo_to_vk", "upload_video_to_vk", "upload_doc_to_vk", "download_tg_file"]
