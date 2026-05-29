"""Unit tests for GD Module commands."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes, ConversationHandler

from bot.commands.gd_commands_ptb import (
    submit_command_start,
    submit_select_level,
    submit_upload_media,
    submit_confirm,
    submit_cancel,
    get_gd_handlers,
    SUBMIT_SELECT_LEVEL,
    SUBMIT_UPLOAD_MEDIA,
    SUBMIT_CONFIRM,
)


@pytest.fixture
def mock_update():
    """Create a mock Update object."""
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.from_user = MagicMock(spec=User)
    update.message.from_user.id = 12345
    update.message.from_user.username = "testuser"
    update.message.from_user.full_name = "Test User"
    update.message.text = None
    update.message.video = None
    update.message.photo = None
    update.message.document = None
    return update


@pytest.fixture
def mock_context():
    """Create a mock ContextTypes.DEFAULT_TYPE object."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    return context


class TestSubmitCommandStart:
    """Tests for submit_command_start handler."""

    @pytest.mark.asyncio
    async def test_submit_command_start_sends_message(self, mock_update, mock_context):
        """Test that /submit command starts the conversation."""
        mock_update.message.reply_text = AsyncMock()

        result = await submit_command_start(mock_update, mock_context)

        assert result == SUBMIT_SELECT_LEVEL
        mock_update.message.reply_text.assert_called_once()
        assert "Geometry Dash" in mock_update.message.reply_text.call_args[0][0]
        assert "Введите название уровня" in mock_update.message.reply_text.call_args[0][0]


class TestSubmitSelectLevel:
    """Tests for submit_select_level handler."""

    @pytest.mark.asyncio
    async def test_submit_select_level_stores_level(self, mock_update, mock_context):
        """Test that level name is stored in user_data."""
        mock_update.message.text = "Cubes"
        mock_update.message.reply_text = AsyncMock()

        result = await submit_select_level(mock_update, mock_context)

        assert result == SUBMIT_UPLOAD_MEDIA
        assert mock_context.user_data["submit_level"] == "Cubes"
        mock_update.message.reply_text.assert_called_once()
        assert "Cubes" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_submit_select_level_strips_whitespace(self, mock_update, mock_context):
        """Test that level name is stripped of whitespace."""
        mock_update.message.text = "  Tartarus  "
        mock_update.message.reply_text = AsyncMock()

        await submit_select_level(mock_update, mock_context)

        assert mock_context.user_data["submit_level"] == "Tartarus"


class TestSubmitUploadMedia:
    """Tests for submit_upload_media handler."""

    @pytest.mark.asyncio
    async def test_submit_upload_media_stores_video(self, mock_update, mock_context):
        """Test that video is stored in user_data."""
        mock_video = MagicMock()
        mock_video.file_id = "video_file_id_123"
        mock_video.file_size = 1024 * 1024
        mock_update.message.video = mock_video
        mock_update.message.document = None
        mock_update.message.photo = None
        mock_update.message.reply_video = AsyncMock()
        mock_update.message.reply_text = AsyncMock()

        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {"submit_level": "Cubes"}

        result = await submit_upload_media(mock_update, context)

        assert result == SUBMIT_CONFIRM
        assert context.user_data["submit_media"]["file_id"] == "video_file_id_123"
        assert context.user_data["submit_media"]["type"] == "video"
        mock_update.message.reply_video.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_upload_media_stores_photo(self, mock_update, mock_context):
        """Test that photo is stored in user_data."""
        mock_photo = [MagicMock()]
        mock_photo[0].file_id = "photo_file_id_456"
        mock_photo[0].file_size = 512 * 512
        mock_update.message.video = None
        mock_update.message.document = None
        mock_update.message.photo = mock_photo
        mock_update.message.reply_photo = AsyncMock()

        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {"submit_level": "Cubes"}

        result = await submit_upload_media(mock_update, context)

        assert result == SUBMIT_CONFIRM
        assert context.user_data["submit_media"]["type"] == "photo"

    @pytest.mark.asyncio
    async def test_submit_upload_media_rejects_invalid_media(self, mock_update, mock_context):
        """Test that non-media messages are rejected."""
        mock_update.message.video = None
        mock_update.message.document = None
        mock_update.message.photo = None
        mock_update.message.reply_text = AsyncMock()

        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {"submit_level": "Cubes"}

        result = await submit_upload_media(mock_update, context)

        assert result == SUBMIT_UPLOAD_MEDIA
        mock_update.message.reply_text.assert_called_once()
        assert "Пожалуйста, отправьте видео или фото" in mock_update.message.reply_text.call_args[0][0]


class TestSubmitConfirm:
    """Tests for submit_confirm handler."""

    @pytest.mark.asyncio
    async def test_submit_confirm_cancels(self, mock_update, mock_context):
        """Test that cancel button ends conversation."""
        mock_update.message.text = "❌ Отменить"
        mock_update.message.reply_text = AsyncMock()

        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {"submit_level": "Cubes", "submit_media": {"file_id": "test"}}

        result = await submit_confirm(mock_update, context)

        assert result == ConversationHandler.END
        mock_update.message.reply_text.assert_called_once()
        assert "Отправка отменена" in mock_update.message.reply_text.call_args[0][0]
        assert not context.user_data

    @pytest.mark.asyncio
    async def test_submit_confirm_invalid_response(self, mock_update, mock_context):
        """Test that invalid response asks for confirmation."""
        mock_update.message.text = "Maybe"
        mock_update.message.reply_text = AsyncMock()

        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {"submit_level": "Cubes", "submit_media": {"file_id": "test"}}

        result = await submit_confirm(mock_update, context)

        assert result == SUBMIT_CONFIRM
        mock_update.message.reply_text.assert_called_once()
        assert "Пожалуйста, выберите" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    @patch("bot.commands.gd_commands_ptb.get_db_session")
    async def test_submit_confirm_saves_submission(self, mock_get_db_session, mock_update, mock_context):
        """Test that confirmed submission is saved to database."""
        mock_update.message.text = "✅ Подтвердить"
        mock_update.message.reply_text = AsyncMock()

        mock_session = MagicMock()
        mock_get_db_session.return_value.__enter__.return_value = mock_session

        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {
            "submit_level": "Cubes",
            "submit_media": {"file_id": "test_media", "type": "video", "file_size": 1024}
        }

        result = await submit_confirm(mock_update, context)

        assert result == ConversationHandler.END
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_update.message.reply_text.assert_called_once()
        assert "Заявка отправлена" in mock_update.message.reply_text.call_args[0][0]


class TestSubmitCancel:
    """Tests for submit_cancel handler."""

    @pytest.mark.asyncio
    async def test_submit_cancel(self, mock_update, mock_context):
        """Test that cancel command ends conversation."""
        mock_update.message.reply_text = AsyncMock()

        result = await submit_cancel(mock_update, mock_context)

        assert result == ConversationHandler.END
        mock_update.message.reply_text.assert_called_once()
        assert "Отправка отменена" in mock_update.message.reply_text.call_args[0][0]
        assert not mock_context.user_data


class TestGetGdHandlers:
    """Tests for get_gd_handlers function."""

    def test_get_gd_handlers_returns_list(self):
        """Test that get_gd_handlers returns a list."""
        handlers = get_gd_handlers()

        assert isinstance(handlers, list)
        assert len(handlers) == 1
        assert handlers[0].entry_points[0].callback.__name__ == "submit_command_start"
