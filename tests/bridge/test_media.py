"""Tests for bridge_bot.media module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bridge_bot.media import (
    _retry,
    upload_doc_to_vk,
    upload_photo_to_vk,
    upload_video_to_vk,
    MAX_RETRIES,
)


class TestRetry:
    """Tests for _retry helper function."""

    def test_retry_success_first_attempt(self):
        """Test successful call on first attempt."""
        func = MagicMock(return_value="success")
        result = _retry(func, "arg1", kwarg1="value")
        assert result == "success"
        func.assert_called_once_with("arg1", kwarg1="value")

    def test_retry_success_after_failures(self):
        """Test successful call after failures."""
        func = MagicMock(side_effect=[Exception("Fail 1"), Exception("Fail 2"), "success"])

        with patch("bridge_bot.media.time.sleep"):
            result = _retry(func)
            assert result == "success"
            assert func.call_count == 3

    def test_retry_max_attempts_exceeded(self):
        """Test exception after max retries."""
        func = MagicMock(side_effect=Exception("Always fails"))

        with patch("bridge_bot.media.time.sleep"):
            with pytest.raises(Exception) as exc_info:
                _retry(func)
            assert str(exc_info.value) == "Always fails"
            assert func.call_count == MAX_RETRIES

    def test_retry_sleep_delays(self):
        """Test exponential backoff delays."""
        func = MagicMock(side_effect=[Exception("Fail"), "success"])

        with patch("bridge_bot.media.time.sleep") as mock_sleep:
            _retry(func)
            assert mock_sleep.call_count == 1
            assert mock_sleep.call_args[0][0] == 2**0


class TestUploadPhoto:
    """Tests for upload_photo_to_vk function."""

    @patch("bridge_bot.media._retry")
    @patch("bridge_bot.media.requests.post")
    def test_upload_photo_success(self, mock_post, mock_retry):
        """Test successful photo upload."""

        mock_vk_session = MagicMock()
        mock_vk = MagicMock()
        mock_vk.photos.getMessagesUploadServer.return_value = {
            "upload_url": "http://upload.server/upload"
        }
        mock_vk.photos.saveMessagesPhoto.return_value = [
            {"owner_id": -123, "id": 456}
        ]
        mock_vk_session.get_api.return_value = mock_vk

        mock_retry.side_effect = lambda f: f()

        file_bytes = b"fake image data"
        result = upload_photo_to_vk(file_bytes, mock_vk_session, -2000000000)

        assert result == "photo-123_456"

    @patch("bridge_bot.media._retry")
    @patch("bridge_bot.media.requests.post")
    @patch("bridge_bot.media.Path.unlink")
    def test_upload_photo_cleans_temp_file(self, mock_unlink, mock_post, mock_retry):
        """Test that temp file is deleted after upload."""

        mock_vk_session = MagicMock()
        mock_vk = MagicMock()
        mock_vk.photos.getMessagesUploadServer.return_value = {
            "upload_url": "http://upload.server/upload"
        }
        mock_vk.photos.saveMessagesPhoto.return_value = [
            {"owner_id": -123, "id": 456}
        ]
        mock_vk_session.get_api.return_value = mock_vk

        mock_post.return_value = MagicMock(json=lambda: {"photo": "x", "server": 1, "hash": "h"})

        mock_retry.side_effect = lambda f: f()

        file_bytes = b"fake image data"
        upload_photo_to_vk(file_bytes, mock_vk_session, -2000000000)

        mock_unlink.assert_called_once()


class TestUploadVideo:
    """Tests for upload_video_to_vk function."""

    @patch("bridge_bot.media._retry")
    @patch("bridge_bot.media.requests.post")
    def test_upload_video_success(self, mock_post, mock_retry):
        """Test successful video upload."""

        mock_vk_session = MagicMock()
        mock_vk = MagicMock()
        mock_vk.video.save.return_value = {
            "upload_url": "http://upload.server/upload",
            "owner_id": -123,
            "video_id": 789,
        }
        mock_vk_session.get_api.return_value = mock_vk

        mock_post.return_value = MagicMock()
        mock_retry.side_effect = lambda f: f()

        file_bytes = b"fake video data"
        result = upload_video_to_vk(file_bytes, "test.mp4", mock_vk_session)

        assert result == "video-123_789"


class TestUploadDoc:
    """Tests for upload_doc_to_vk function."""

    @patch("bridge_bot.media._retry")
    @patch("bridge_bot.media.requests.post")
    def test_upload_doc_success(self, mock_post, mock_retry):
        """Test successful document upload."""

        mock_vk_session = MagicMock()
        mock_vk = MagicMock()
        mock_vk.docs.getMessagesUploadServer.return_value = {
            "upload_url": "http://upload.server/upload"
        }
        mock_vk.docs.save.return_value = {
            "doc": {"owner_id": -123, "id": 999}
        }
        mock_vk_session.get_api.return_value = mock_vk

        mock_retry.side_effect = lambda f: f()
        mock_post.return_value = MagicMock(json=lambda: {"file": "saved_file"})

        file_bytes = b"fake document data"
        result = upload_doc_to_vk(file_bytes, "document.pdf", mock_vk_session, -2000000000)

        assert result == "doc-123_999"
