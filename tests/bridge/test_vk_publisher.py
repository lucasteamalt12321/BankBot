"""Tests for bridge_bot.vk_publisher module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bridge_bot.queue import RateLimitError


class TestVkPublisher:
    """Tests for VK publisher functions."""

    @patch("bridge_bot.vk_publisher._create_vk_session")
    @patch("bridge_bot.vk_publisher.add_bot_mark")
    def test_send_text_success(self, mock_add_mark, mock_create_session):
        """Test successful text message send."""
        from bridge_bot.vk_publisher import send_text

        mock_vk = MagicMock()
        mock_vk.messages.send.return_value = 12345
        mock_session = MagicMock()
        mock_session.get_api.return_value = mock_vk
        mock_create_session.return_value = mock_session

        mock_add_mark.return_value = "[TG] Test: Hello [BOT]"

        result = send_text(
            text="Hello",
            peer_id=-2000000000,
            sender_name="Test",
            vk_token="test_token",
        )

        assert result == 12345
        mock_vk.messages.send.assert_called_once()
        call_kwargs = mock_vk.messages.send.call_args.kwargs
        assert call_kwargs["peer_id"] == -2000000000
        assert "[BOT]" in call_kwargs["message"]

    @patch("bridge_bot.vk_publisher._create_vk_session")
    def test_send_text_prefixes_message(self, mock_create_session):
        """Test that message is prefixed with sender name."""
        from bridge_bot.vk_publisher import send_text

        mock_vk = MagicMock()
        mock_vk.messages.send.return_value = 1
        mock_session = MagicMock()
        mock_session.get_api.return_value = mock_vk
        mock_create_session.return_value = mock_session

        send_text(
            text="Hello",
            peer_id=-2000000000,
            sender_name="John Doe",
            vk_token="test_token",
        )

        call_kwargs = mock_vk.messages.send.call_args.kwargs
        assert "[TG] John Doe:" in call_kwargs["message"]

    @patch("bridge_bot.vk_publisher._create_vk_session")
    @patch("bridge_bot.vk_publisher.add_bot_mark")
    def test_send_text_rate_limit(self, mock_add_mark, mock_create_session):
        """Test RateLimitError on VK API error code 9."""
        from bridge_bot.vk_publisher import send_text

        import vk_api

        mock_vk = MagicMock()
        mock_vk.messages.send.side_effect = vk_api.ApiError(
            vk=mock_vk,
            method="messages.send",
            values={"peer_id": -2000000000},
            raw={"error_code": 9},
            error={"error_code": 9, "error_msg": "Flood control"},
        )
        mock_session = MagicMock()
        mock_session.get_api.return_value = mock_vk
        mock_create_session.return_value = mock_session

        mock_add_mark.return_value = "Test [BOT]"

        with pytest.raises(RateLimitError):
            send_text(
                text="Hello",
                peer_id=-2000000000,
                sender_name="Test",
                vk_token="test_token",
            )

    @patch("bridge_bot.vk_publisher._create_vk_session")
    @patch("bridge_bot.vk_publisher.add_bot_mark")
    def test_send_text_other_api_error(self, mock_add_mark, mock_create_session):
        """Test re-raise of non-rate-limit API errors."""
        from bridge_bot.vk_publisher import send_text

        import vk_api

        mock_vk = MagicMock()
        mock_vk.messages.send.side_effect = vk_api.ApiError(
            vk=mock_vk,
            method="messages.send",
            values={"peer_id": -2000000000},
            raw={"error_code": 10},
            error={"error_code": 10, "error_msg": "Internal server error"},
        )
        mock_session = MagicMock()
        mock_session.get_api.return_value = mock_vk
        mock_create_session.return_value = mock_session

        mock_add_mark.return_value = "Test [BOT]"

        with pytest.raises(vk_api.ApiError):
            send_text(
                text="Hello",
                peer_id=-2000000000,
                sender_name="Test",
                vk_token="test_token",
            )

    def test_create_vk_session(self):
        """Test VK session creation."""
        from bridge_bot.vk_publisher import _create_vk_session

        session = _create_vk_session("test_token")
        assert session is not None
