"""Tests for vk_bot.main module."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestPublishToChannel:
    """Tests for _publish_to_channel function."""

    def test_publish_text_message_success(self):
        """Test successful text message publishing."""
        from vk_bot.main import _publish_to_channel

        mock_vk = MagicMock()
        mock_vk.messages.send.return_value = 12345

        result = _publish_to_channel(mock_vk, -2000000000, "Test message")

        assert result is True
        mock_vk.messages.send.assert_called_once_with(
            peer_id=-2000000000,
            message="Test message",
            random_id=0,
        )

    def test_publish_message_with_attachments(self):
        """Test message publishing with attachments."""
        from vk_bot.main import _publish_to_channel

        mock_vk = MagicMock()
        mock_vk.messages.send.return_value = 12345

        attachments = ["photo123_456", "video123_789"]
        result = _publish_to_channel(mock_vk, -2000000000, "Test", attachments)

        assert result is True
        mock_vk.messages.send.assert_called_once_with(
            peer_id=-2000000000,
            message="Test",
            random_id=0,
            attachment=attachments,
        )

    def test_publish_failure(self):
        """Test handling of publish failure."""
        from vk_bot.main import _publish_to_channel

        mock_vk = MagicMock()
        mock_vk.messages.send.side_effect = Exception("API Error")

        result = _publish_to_channel(mock_vk, -2000000000, "Test")

        assert result is False


class TestGetMessageAttachments:
    """Tests for _get_message_attachments function."""

    def test_get_photo_attachment(self):
        """Test extracting photo attachment."""
        from vk_bot.main import _get_message_attachments

        mock_vk = MagicMock()
        mock_vk.messages.getById.return_value = {
            "items": [
                {
                    "id": 1,
                    "attachments": [
                        {
                            "type": "photo",
                            "photo": {
                                "owner_id": -123456,
                                "id": 789,
                                "access_key": "abc123",
                            },
                        }
                    ],
                }
            ]
        }

        result = _get_message_attachments(mock_vk, 1, -2000000000)

        assert result == ["photo-123456_789_abc123"]

    def test_get_video_attachment(self):
        """Test extracting video attachment."""
        from vk_bot.main import _get_message_attachments

        mock_vk = MagicMock()
        mock_vk.messages.getById.return_value = {
            "items": [
                {
                    "id": 2,
                    "attachments": [
                        {
                            "type": "video",
                            "video": {
                                "owner_id": -123456,
                                "id": 456,
                            },
                        }
                    ],
                }
            ]
        }

        result = _get_message_attachments(mock_vk, 2, -2000000000)

        assert result == ["video-123456_456"]

    def test_no_attachments(self):
        """Test message without attachments."""
        from vk_bot.main import _get_message_attachments

        mock_vk = MagicMock()
        mock_vk.messages.getById.return_value = {
            "items": [{"id": 3, "attachments": []}]
        }

        result = _get_message_attachments(mock_vk, 3, -2000000000)

        assert result is None

    def test_api_error(self):
        """Test handling API error when getting attachments."""
        from vk_bot.main import _get_message_attachments

        mock_vk = MagicMock()
        mock_vk.messages.getById.side_effect = Exception("API Error")

        result = _get_message_attachments(mock_vk, 1, -2000000000)

        assert result is None

    def test_empty_response(self):
        """Test empty API response."""
        from vk_bot.main import _get_message_attachments

        mock_vk = MagicMock()
        mock_vk.messages.getById.return_value = {}

        result = _get_message_attachments(mock_vk, 1, -2000000000)

        assert result is None


class TestBotMark:
    """Tests for [BOT] mark filtering."""

    def test_has_bot_mark_true(self):
        """Test detection of [BOT] mark."""
        from bridge_bot.loop_guard import has_bot_mark

        assert has_bot_mark("Hello [BOT]") is True
        assert has_bot_mark("[BOT] Hello") is True
        assert has_bot_mark("Hello [BOT] World") is True

    def test_has_bot_mark_false(self):
        """Test absence of [BOT] mark."""
        from bridge_bot.loop_guard import has_bot_mark

        assert has_bot_mark("Hello World") is False
        assert has_bot_mark("BOT in text") is False
        assert has_bot_mark("") is False
