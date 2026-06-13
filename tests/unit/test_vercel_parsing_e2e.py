"""E2E tests for Vercel parsing: all 6 bots + bank operations."""

from unittest.mock import Mock, patch

from api.index import CHAT_RESPONSE_MODES, WEBHOOK_SECRET, app, parse_bot_message, BOT_CONVERSION_RATES

# ── Real message examples from chat export ──────────────────────

GDCARDS_CARD = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: Romankhrus
Карта: Elki Team
Категория: Команды
───────────────
Описание: Команда экспоузеров...
───────────────
🟣 Редкость: Эпическая (1/63) • 17.0%
⭐️ Очки: +3
🤩 Орбы: +10
🃏 Коллекция: 6/252 карт
───────────────"""

GDCARDS_CHEST = "🎁 Romankhrus открыл сундук и получил 96 орб"

GUSYA_CARDS = "💰 Монеты • +8 [16]"

SHMALALA_FISHING = """🎣 [Рыбалка] 🎣
Рыбак: LucasTeam Luke
Опыт: +4 (405 / 782)🔋
На крючке: 🐉 Судак (2.23 кг)
Монеты: +14 (3947)💰"""

SHMALALA_KARMA = "Лайк! Вы повысили рейтинг пользователя LucasTeam Luke.\nТеперь его рейтинг: 13 ❤️"

CHAOMETER_PROFILE = """🍵Профиль
👤 LucasTeam

🌤 Сегодня: 4.3 л.
🤯 Всего: 34.9 л.
👽 Осталось попыток: 0"""

BUNKERRP_WIN = """Прошли в бункер:
1. LucasTeam Luke
2. Nikitos
3. Roman
Не прошли в бункер:
4. Sasha"""

MARKDOWN_LINK = '<a href="" onclick="return ShowMentionName()">LucasTeam</a>, <em>ты выпил(а) 1.7 л. чая. Выпито всего - 6.7 л.</em>'

# ── Parser unit tests ───────────────────────────────────────────


def test_parse_gdcards_card():
    result = parse_bot_message(GDCARDS_CARD)
    assert result is not None
    assert result["game"] == "GDcards"
    assert result["orbs"] == 10
    assert result["player"] == "Romankhrus"
    assert result["card"] == "Elki Team"
    assert result["rate"] == BOT_CONVERSION_RATES["gdcards"]
    assert result["coins"] == int(10 * result["rate"])


def test_parse_gdcards_chest():
    result = parse_bot_message(GDCARDS_CHEST)
    assert result is not None
    assert result["game"] == "GDcards"
    assert result["orbs"] == 96
    assert result["player"] == "Romankhrus"
    assert result["card"] == "Сундук"


def test_parse_gusya_cards():
    result = parse_bot_message(GUSYA_CARDS)
    assert result is not None
    assert result["game"] == "Гуся Cards"
    assert result["amount"] == 8
    assert result["rate"] == BOT_CONVERSION_RATES["gusya_cards"]
    assert result["coins"] == int(8 * result["rate"])


def test_parse_shmalala_fishing():
    result = parse_bot_message(SHMALALA_FISHING)
    assert result is not None
    assert result["game"] == "Shmalala"
    assert result["type"] == "fishing"
    assert result["amount"] == 14
    assert result["rate"] == BOT_CONVERSION_RATES["shmalala"]
    assert result["coins"] == int(14 * result["rate"])


def test_parse_shmalala_karma():
    result = parse_bot_message(SHMALALA_KARMA)
    assert result is not None
    assert result["game"] == "Shmalala"
    assert result["type"] == "karma"
    assert result["amount"] == 13
    assert result["rate"] == BOT_CONVERSION_RATES["shmalala_karma"]
    assert result["coins"] == int(13 * result["rate"])


def test_parse_chaometer():
    result = parse_bot_message(CHAOMETER_PROFILE)
    assert result is not None
    assert result["game"] == "Чайометр"
    assert result["player"] == "LucasTeam"
    assert result["amount"] == 4.3
    assert result["total"] == 34.9
    assert result["rate"] == BOT_CONVERSION_RATES["chaometer"]
    assert result["coins"] == int(4.3 * result["rate"])


def test_parse_bunkerrp():
    result = parse_bot_message(BUNKERRP_WIN)
    assert result is not None
    assert result["game"] == "BunkerRP"
    assert result["player"] == "LucasTeam Luke"
    assert result["winners"] == ["LucasTeam Luke", "Nikitos", "Roman"]
    assert result["rate"] == BOT_CONVERSION_RATES["bunkerrp"]
    assert result["coins"] == int(result["rate"])


def test_parse_markdown_tea_action_not_profile():
    """Action response (not profile) should not match chaometer parser."""
    result = parse_bot_message(MARKDOWN_LINK)
    assert result is None


def test_parse_empty():
    assert parse_bot_message("") is None
    assert parse_bot_message(None) is None


def test_parse_gibberish():
    assert parse_bot_message("asdfghjkl") is None
    assert parse_bot_message("какой-то случайный текст") is None


def test_parse_negative_coins_not_returned():
    result = parse_bot_message("🎣 [Рыбалка]\nМонеты: +0")
    if result:
        assert result["coins"] >= 0


def _build_parsing_update(replied_text: str) -> dict:
    """Build a Telegram update dict simulating a reply with 'парсинг'."""
    return {
        "update_id": 100,
        "message": {
            "message_id": 50,
            "text": "парсинг",
            "chat": {"id": 12345, "type": "group"},
            "from": {"id": 2091908459, "first_name": "TestUser"},
            "reply_to_message": {
                "message_id": 49,
                "text": replied_text,
                "chat": {"id": 12345, "type": "group"},
                "from": {"id": 111111, "first_name": "BotUser"},
            },
        },
    }


def _mock_db_for_add_balance(mock_db):
    """Setup get_db_engine mock so all DB functions succeed."""
    mock_conn = Mock()
    mock_conn.commit.return_value = None
    mock_mappings = Mock()
    mock_mappings.all.return_value = []
    mock_mappings.first.return_value = {"id": 1}
    mock_result = Mock()
    mock_result.mappings.return_value = mock_mappings
    mock_conn.execute.return_value = mock_result
    mock_context = Mock()
    mock_context.__enter__ = Mock(return_value=mock_conn)
    mock_context.__exit__ = Mock(return_value=None)
    mock_db.return_value.connect.return_value = mock_context


@patch("api.index.get_db_engine")
@patch("api.index.send_telegram_message")
def test_webhook_parsing_gdcards(mock_send, mock_db):
    _mock_db_for_add_balance(mock_db)
    payload = _build_parsing_update(GDCARDS_CARD)
    response = app.test_client().post(f"/telegram/webhook/{WEBHOOK_SECRET}", json=payload)
    assert response.status_code == 200
    assert response.get_json() == {"ok": True}
    mock_send.assert_called_once()
    text = mock_send.call_args[0][1]
    assert "Начислено" in text
    assert "GDcards" in text


@patch("api.index.get_db_engine")
@patch("api.index.send_telegram_message")
def test_webhook_parsing_gusya(mock_send, mock_db):
    _mock_db_for_add_balance(mock_db)
    payload = _build_parsing_update(GUSYA_CARDS)
    response = app.test_client().post(f"/telegram/webhook/{WEBHOOK_SECRET}", json=payload)
    assert response.status_code == 200
    mock_send.assert_called_once()
    text = mock_send.call_args[0][1]
    assert "Начислено" in text


@patch("api.index.get_db_engine")
@patch("api.index.send_telegram_message")
def test_webhook_parsing_shmalala(mock_send, mock_db):
    _mock_db_for_add_balance(mock_db)
    payload = _build_parsing_update(SHMALALA_FISHING)
    response = app.test_client().post(f"/telegram/webhook/{WEBHOOK_SECRET}", json=payload)
    assert response.status_code == 200
    mock_send.assert_called_once()
    text = mock_send.call_args[0][1]
    assert "Начислено" in text


@patch("api.index.get_db_engine")
@patch("api.index.send_telegram_message")
def test_webhook_parsing_chaometer(mock_send, mock_db):
    _mock_db_for_add_balance(mock_db)
    payload = _build_parsing_update(CHAOMETER_PROFILE)
    response = app.test_client().post(f"/telegram/webhook/{WEBHOOK_SECRET}", json=payload)
    assert response.status_code == 200
    mock_send.assert_called_once()
    text = mock_send.call_args[0][1]
    assert "Начислено" in text
    assert "Чайометр" in text


@patch("api.index.get_db_engine")
@patch("api.index.send_telegram_message")
def test_webhook_parsing_bunkerrp(mock_send, mock_db):
    _mock_db_for_add_balance(mock_db)
    payload = _build_parsing_update(BUNKERRP_WIN)
    response = app.test_client().post(f"/telegram/webhook/{WEBHOOK_SECRET}", json=payload)
    assert response.status_code == 200
    mock_send.assert_called_once()
    text = mock_send.call_args[0][1]
    assert "Начислено" in text
    assert "BunkerRP" in text


@patch("api.index.get_db_engine")
@patch("api.index.send_telegram_message")
def test_webhook_parsing_failure_message(mock_send, mock_db):
    mock_db.return_value.connect.return_value.__enter__.return_value.execute.return_value.mappings.return_value.first.return_value = None
    payload = _build_parsing_update("какой-то левый текст")
    response = app.test_client().post(f"/telegram/webhook/{WEBHOOK_SECRET}", json=payload)
    assert response.status_code == 200
    mock_send.assert_called_once()
    text = mock_send.call_args[0][1]
    assert "Не удалось распарсить" in text


@patch("api.index.get_db_engine")
@patch("api.index.send_telegram_message")
def test_webhook_parsing_no_reply_ignored(mock_send, mock_db):
    """Message with 'парсинг' but not a reply should be ignored."""
    payload = {
        "update_id": 101,
        "message": {
            "message_id": 51,
            "text": "парсинг",
            "chat": {"id": 12345, "type": "group"},
            "from": {"id": 2091908459, "first_name": "TestUser"},
        },
    }
    response = app.test_client().post(f"/telegram/webhook/{WEBHOOK_SECRET}", json=payload)
    assert response.status_code == 200
    mock_send.assert_not_called()


@patch("api.index.get_db_engine")
@patch("api.index.send_telegram_message")
def test_webhook_parsing_priority_gdcards_over_shmalala(mock_send, mock_db):
    """GDcards has priority over Shmalala if text matches both."""
    _mock_db_for_add_balance(mock_db)
    mixed = "🃏 НОВАЯ КАРТА\n🤩 Орбы: +5\nМонеты: +100"
    payload = _build_parsing_update(mixed)
    response = app.test_client().post(f"/telegram/webhook/{WEBHOOK_SECRET}", json=payload)
    assert response.status_code == 200
    mock_send.assert_called_once()
    text = mock_send.call_args[0][1]
    assert "GDcards" in text
