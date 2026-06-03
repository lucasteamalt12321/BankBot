from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.chess.lichess_api import LichessUser, parse_lichess_user
from bot.commands.chess_commands_ptb import _format_link_success, chess_link_command


def test_parse_lichess_user_normalizes_payload() -> None:
    user = parse_lichess_user({"username": "DrNykterstein", "title": "GM", "online": True})

    assert user == LichessUser(username="DrNykterstein", title="GM", online=True)


def test_parse_lichess_user_rejects_invalid_payload() -> None:
    assert parse_lichess_user({"disabled": True}) is None


def test_format_link_success_contains_username() -> None:
    text = _format_link_success(LichessUser(username="DrNykterstein", title="GM", online=True))

    assert "Lichess аккаунт привязан" in text
    assert "GM DrNykterstein" in text
    assert "онлайн" in text


@pytest.mark.asyncio
async def test_chess_link_usage_without_subcommand() -> None:
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message, effective_user=SimpleNamespace(id=123))
    context = SimpleNamespace(args=[])

    await chess_link_command(update, context)

    message.reply_text.assert_awaited_once()
    assert "Использование" in message.reply_text.await_args.args[0]
