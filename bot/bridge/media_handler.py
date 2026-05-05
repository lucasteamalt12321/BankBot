"""Shim: re-export из bridge_bot/media.py."""

from bridge_bot.media import (
    upload_photo_to_vk,
    upload_video_to_vk,
    upload_doc_to_vk,
    download_tg_file,
)

__all__ = ["upload_photo_to_vk", "upload_video_to_vk", "upload_doc_to_vk", "download_tg_file"]
