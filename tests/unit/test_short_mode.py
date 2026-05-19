from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.commands.game_commands_ptb import games_command
from bot.short_mode import (
    is_short_mode,
    long_all_command,
    long_command,
    short_all_command,
    short_command,
)


async def test_short_command_enables_concise_mode() -> None:
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(user_data={}, bot_data={})

    await short_command(update, context)

    assert is_short_mode(context) is True
    message.reply_text.assert_awaited_once()
    assert "Краткий режим включён для вас" in message.reply_text.await_args.args[0]


async def test_long_command_disables_concise_mode() -> None:
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(user_data={"short_mode_enabled": True}, bot_data={})

    await long_command(update, context)

    assert is_short_mode(context) is False
    message.reply_text.assert_awaited_once()


async def test_short_all_lists_main_menus() -> None:
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(user_data={}, bot_data={})

    await short_all_command(update, context)

    assert is_short_mode(context) is True
    assert context.bot_data["global_short_mode_enabled"] is True
    text = message.reply_text.await_args.args[0]
    assert "/balance" in text
    assert "/shop" in text
    assert "/long_all" in text


async def test_long_all_disables_global_short_mode() -> None:
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(user_data={}, bot_data={"global_short_mode_enabled": True})

    await long_all_command(update, context)

    assert is_short_mode(context) is False
    assert context.bot_data["global_short_mode_enabled"] is False
    message.reply_text.assert_awaited_once()


def test_global_short_mode_applies_without_personal_flag() -> None:
    context = SimpleNamespace(user_data={}, bot_data={"global_short_mode_enabled": True})

    assert is_short_mode(context) is True


def test_short_mode_is_default_without_flags() -> None:
    context = SimpleNamespace(user_data={}, bot_data={})

    assert is_short_mode(context) is True


def test_personal_long_overrides_default_and_global_short() -> None:
    context = SimpleNamespace(
        user_data={"short_mode_enabled": False},
        bot_data={"global_short_mode_enabled": True},
    )

    assert is_short_mode(context) is False


async def test_games_command_uses_short_mode() -> None:
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(user_data={"short_mode_enabled": True}, bot_data={})

    await games_command(update, context)

    text = message.reply_text.await_args.args[0]
    assert "Мини-игры:" in text
    assert "/play cities" in text
    assert "Классическая игра" not in text
