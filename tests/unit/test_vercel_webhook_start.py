from unittest.mock import Mock, patch

from api.index import WEBHOOK_SECRET, app


def test_vercel_webhook_replies_to_start() -> None:
    update_payload = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "text": "/start",
            "chat": {"id": 12345, "type": "private"},
        },
    }

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None

    with patch("api.index.requests.post", return_value=mock_response) as mock_post:
        response = app.test_client().post(
            f"/telegram/webhook/{WEBHOOK_SECRET}",
            json=update_payload,
        )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}
    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert payload["chat_id"] == 12345
    assert "BankBot работает на Vercel" in payload["text"]


def test_normalize_start_with_bot_mention() -> None:
    update_payload = {
        "update_id": 2,
        "message": {
            "message_id": 11,
            "text": "/start@lt_lo_game_bot",
            "chat": {"id": 12345, "type": "group"},
        },
    }

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None

    with patch("api.index.requests.post", return_value=mock_response) as mock_post:
        response = app.test_client().post(
            f"/telegram/webhook/{WEBHOOK_SECRET}",
            json=update_payload,
        )

    assert response.status_code == 200
    mock_post.assert_called_once()
