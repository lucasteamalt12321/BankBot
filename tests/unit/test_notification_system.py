from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from bot.commands.notification_commands_ptb import (
    notify_status_command,
    notifications_clear_command,
    notifications_command,
    test_adb_command,
)
from utils.monitoring.notification_system import NotificationSystem


@pytest.mark.asyncio
async def test_send_realtime_notification_uses_telegram_ntfy_and_adb() -> None:
    notification_system = NotificationSystem(db=Mock(), bot=AsyncMock())
    user = SimpleNamespace(telegram_id=123456)

    with (
        patch.object(notification_system, "_send_to_telegram", new=AsyncMock()) as send_tg,
        patch.object(notification_system, "_send_to_ntfy", new=AsyncMock()) as send_ntfy,
        patch.object(notification_system, "_send_to_adb", new=AsyncMock()) as send_adb,
    ):
        await notification_system.send_realtime_notification(
            title="Test",
            message="Body",
            notification_type="system",
            user=user,
        )

    send_tg.assert_awaited_once_with(user, "Test", "Body")
    send_ntfy.assert_awaited_once_with("Test", "Body", "system")
    send_adb.assert_awaited_once_with("Test", "Body", "system")


@pytest.mark.asyncio
async def test_send_to_adb_skips_when_disabled() -> None:
    notification_system = NotificationSystem(db=Mock())

    with patch("utils.monitoring.notification_system.settings") as mocked_settings:
        mocked_settings.ADB_NOTIFICATIONS_ENABLED = False
        await notification_system._send_to_adb("Title", "Body", "system")


@pytest.mark.asyncio
async def test_send_to_adb_builds_command_with_serial() -> None:
    notification_system = NotificationSystem(db=Mock())
    process = AsyncMock()
    process.communicate.return_value = (b"ok", b"")
    process.returncode = 0

    with (
        patch("utils.monitoring.notification_system.settings") as mocked_settings,
        patch(
            "utils.monitoring.notification_system.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ) as create_proc,
    ):
        mocked_settings.ADB_NOTIFICATIONS_ENABLED = True
        mocked_settings.ADB_PATH = "adb"
        mocked_settings.ADB_DEVICE_SERIAL = "emulator-5554"

        await notification_system._send_to_adb("Title", "Body", "system")

    create_proc.assert_awaited_once()
    args = create_proc.await_args.args
    assert args[:3] == ("adb", "-s", "emulator-5554")
    assert "notification" in args
    assert "Title\nBody" in args


@pytest.mark.asyncio
async def test_notifications_command_uses_internal_user_id() -> None:
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=777),
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    context = SimpleNamespace()
    mock_db = Mock()
    mock_query = Mock()
    mock_db.query.return_value = mock_query
    mock_query.filter_by.return_value.first.return_value = SimpleNamespace(id=42)

    with patch("bot.commands.notification_commands_ptb.get_db", return_value=iter([mock_db])):
        with patch.object(NotificationSystem, "get_user_notifications", return_value=[] ) as get_notifications:
            with patch.object(NotificationSystem, "get_unread_count", return_value=0) as get_count:
                await notifications_command(update, context)

    get_notifications.assert_called_once_with(42, limit=20)
    get_count.assert_called_once_with(42)
    update.message.reply_text.assert_awaited_once()
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_notifications_clear_command_uses_internal_user_id() -> None:
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=888),
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    context = SimpleNamespace()
    mock_db = Mock()
    mock_query = Mock()
    mock_db.query.return_value = mock_query
    mock_query.filter_by.return_value.first.return_value = SimpleNamespace(id=99)

    with patch("bot.commands.notification_commands_ptb.get_db", return_value=iter([mock_db])):
        with patch.object(NotificationSystem, "mark_all_as_read", return_value=3) as clear_all:
            await notifications_clear_command(update, context)

    clear_all.assert_called_once_with(99)
    update.message.reply_text.assert_awaited_once()
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_notifications_command_requires_registration() -> None:
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=999),
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    context = SimpleNamespace()
    mock_db = Mock()
    mock_query = Mock()
    mock_db.query.return_value = mock_query
    mock_query.filter_by.return_value.first.return_value = None

    with patch("bot.commands.notification_commands_ptb.get_db", return_value=iter([mock_db])):
        await notifications_command(update, context)

    update.message.reply_text.assert_awaited_once_with("Сначала зарегистрируйтесь через /start")
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_notify_status_command_shows_transport_flags() -> None:
    update = SimpleNamespace(message=SimpleNamespace(reply_text=AsyncMock()))
    context = SimpleNamespace()

    with patch("bot.commands.notification_commands_ptb.settings") as mocked_settings:
        mocked_settings.BOT_TOKEN = "token"
        mocked_settings.NTFY_ENABLED = True
        mocked_settings.NTFY_TOPIC = "topic-name"
        mocked_settings.NTFY_BASE_URL = "https://ntfy.example.com"
        mocked_settings.PROXY_URL = "http://127.0.0.1:1080"
        mocked_settings.ADB_NOTIFICATIONS_ENABLED = False
        mocked_settings.ADB_PATH = "adb"
        mocked_settings.ADB_DEVICE_SERIAL = ""

        await notify_status_command(update, context)

    update.message.reply_text.assert_awaited_once()
    reply_text = update.message.reply_text.await_args.args[0]
    assert "Telegram realtime: <b>on</b>" in reply_text
    assert "ntfy topic: <code>topic-name</code>" in reply_text
    assert "adb: <b>off</b>" in reply_text


@pytest.mark.asyncio
async def test_test_adb_command_reports_disabled_transport() -> None:
    update = SimpleNamespace(message=SimpleNamespace(reply_text=AsyncMock()))
    context = SimpleNamespace()
    mock_db = Mock()

    with (
        patch("bot.commands.notification_commands_ptb.get_db", return_value=iter([mock_db])),
        patch("bot.commands.notification_commands_ptb.settings") as mocked_settings,
    ):
        mocked_settings.ADB_NOTIFICATIONS_ENABLED = False
        await test_adb_command(update, context)

    update.message.reply_text.assert_awaited_once_with(
        "ADB-уведомления отключены. Установите ADB_NOTIFICATIONS_ENABLED=true и попробуйте снова."
    )
    mock_db.close.assert_called_once()
