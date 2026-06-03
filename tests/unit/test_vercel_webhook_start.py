from unittest.mock import Mock, patch

from api.index import CHAT_RESPONSE_MODES, WEBHOOK_SECRET, app


def test_vercel_webhook_replies_to_start() -> None:
    update_payload = {
        "update_id": 1,
            "message": {
                "message_id": 10,
                "text": "/start",
                "chat": {"id": 12345, "type": "private"},
                "from": {"id": 2091908459, "first_name": "LucasTeam"},
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
    assert "[BANK] LucasTeam BankBot" in payload["text"]
    assert "Привет, LucasTeam!" in payload["text"]
    assert "ID: 2091908459" in payload["text"]
    assert "/long_all — полный режим для всех" in payload["text"]


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


def test_vercel_webhook_long_mode_changes_start_text() -> None:
    CHAT_RESPONSE_MODES.clear()
    client = app.test_client()

    long_update = {
        "update_id": 3,
        "message": {
            "message_id": 12,
            "text": "/long",
            "chat": {"id": 222, "type": "private"},
            "from": {"id": 2091908459, "first_name": "LucasTeam"},
        },
    }
    start_update = {
        "update_id": 4,
        "message": {
            "message_id": 13,
            "text": "/start",
            "chat": {"id": 222, "type": "private"},
            "from": {"id": 2091908459, "first_name": "LucasTeam"},
        },
    }

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None

    with patch("api.index.requests.post", return_value=mock_response) as mock_post:
        client.post(f"/telegram/webhook/{WEBHOOK_SECRET}", json=long_update)
        response = client.post(f"/telegram/webhook/{WEBHOOK_SECRET}", json=start_update)

    assert response.status_code == 200
    assert mock_post.call_count == 2
    start_payload = mock_post.call_args.kwargs["json"]
    assert "Добро пожаловать в Мета-Игровую Платформу LucasTeam" in start_payload["text"]
    assert "[COMMANDS] Основные команды:" in start_payload["text"]
