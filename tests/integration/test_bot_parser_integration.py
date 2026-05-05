"""
Integration tests for bot parser integration
Tests that the bot correctly processes game messages using the integrated parser
"""

import pytest
import sys
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from telegram import Update, Message, User as TelegramUser, Chat
from telegram.ext import ContextTypes


class TestBotParserIntegration:
    """Test suite for bot parser integration"""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session"""
        session = MagicMock()
        session.query = MagicMock()
        session.add = MagicMock()
        session.commit = MagicMock()
        session.refresh = MagicMock()
        session.close = MagicMock()
        return session

    @pytest.fixture
    def mock_user(self):
        """Create a mock Telegram user"""
        user = Mock(spec=TelegramUser)
        user.id = 123456
        user.username = "test_user"
        user.first_name = "Test"
        user.is_bot = False
        return user

    @pytest.fixture
    def mock_chat(self):
        """Create a mock chat"""
        chat = Mock(spec=Chat)
        chat.id = 789012
        chat.type = "group"
        return chat

    @pytest.fixture
    def mock_message(self, mock_user, mock_chat):
        """Create a mock message"""
        message = Mock(spec=Message)
        message.text = ""
        message.from_user = mock_user
        message.chat = mock_chat
        message.reply_text = AsyncMock()
        return message

    @pytest.fixture
    def mock_update(self, mock_message, mock_user, mock_chat):
        """Create a mock update"""
        update = Mock(spec=Update)
        update.message = mock_message
        update.effective_user = mock_user
        update.effective_chat = mock_chat
        return update

    @pytest.fixture
    def mock_context(self):
        """Create a mock context"""
        return Mock(spec=ContextTypes.DEFAULT_TYPE)

    @pytest.mark.asyncio
    async def test_parse_fishing_message(self, mock_update, mock_context, mock_db_session):
        """Test parsing fishing message"""
        from bot.bot import TelegramBot

        # Setup fishing message
        fishing_message = """🎣 [Рыбалка] 🎣
Рыбак: @fisher_user
Улов: Золотая рыбка
Монеты: +250 (1500)💰
Опыт: +10"""

        # Setup reply to bot message
        mock_bot_user = Mock()
        mock_bot_user.is_bot = True
        mock_bot_user.first_name = "Shmalala Bot"
        mock_bot_user.username = "shmalala_bot"

        mock_reply_message = Mock()
        mock_reply_message.from_user = mock_bot_user
        mock_reply_message.text = fishing_message
        mock_reply_message.caption = None

        mock_update.message.reply_to_message = mock_reply_message
        mock_update.message.text = "парсинг"

        # Mock database
        with patch('bot.bot.get_db') as mock_get_db:
            mock_get_db.return_value = iter([mock_db_session])

            # Mock User model
            from database.database import User
            mock_user_obj = Mock(spec=User)
            mock_user_obj.id = 1
            mock_user_obj.username = "fisher_user"
            mock_user_obj.balance = 1000
            mock_user_obj.telegram_id = mock_update.effective_user.id

            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user_obj

            # Create bot and process manual parsing
            bot = TelegramBot()
            await bot.handle_manual_parsing(mock_update, mock_context)

            # Verify user balance was updated
            assert mock_user_obj.balance == 1250

            # Verify notification was sent
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "fisher_user" in call_args
            assert "250" in call_args
            assert "🎣" in call_args

    @pytest.mark.asyncio
    async def test_parse_card_message(self, mock_update, mock_context, mock_db_session):
        """Test parsing card message via manual parsing"""
        from bot.bot import TelegramBot

        # Setup card message
        card_message = """🃏 НОВАЯ КАРТА 🃏
Игрок: @card_player
Карта: Легендарная
Очки: +150
Редкость: Epic"""

        # Setup reply to bot message
        mock_bot_user = Mock()
        mock_bot_user.is_bot = True
        mock_bot_user.first_name = "GDCards Bot"
        mock_bot_user.username = "gdcards_bot"

        mock_reply_message = Mock()
        mock_reply_message.from_user = mock_bot_user
        mock_reply_message.text = card_message
        mock_reply_message.caption = None

        mock_update.message.reply_to_message = mock_reply_message
        mock_update.message.text = "парсинг"

        # Mock database
        with patch('bot.bot.get_db') as mock_get_db:
            mock_get_db.return_value = iter([mock_db_session])

            # Mock User model
            from database.database import User
            mock_user_obj = Mock(spec=User)
            mock_user_obj.id = 2
            mock_user_obj.username = "card_player"
            mock_user_obj.balance = 500
            mock_user_obj.telegram_id = mock_update.effective_user.id

            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user_obj

            # Create bot and process manual parsing
            bot = TelegramBot()
            await bot.handle_manual_parsing(mock_update, mock_context)

            # Verify user balance was updated
            assert mock_user_obj.balance == 650

            # Verify notification was sent
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "card_player" in call_args
            assert "150" in call_args
            assert "🃏" in call_args

    @pytest.mark.asyncio
    async def test_create_new_user_from_manual_parsing(self, mock_update, mock_context, mock_db_session):
        """Test creating new user from manual parsing"""
        from bot.bot import TelegramBot

        # Setup message
        fishing_message = """🎣 [Рыбалка] 🎣
Рыбак: @new_fisher
Монеты: +100 (100)💰"""

        # Setup reply to bot message
        mock_bot_user = Mock()
        mock_bot_user.is_bot = True
        mock_bot_user.first_name = "Shmalala Bot"
        mock_bot_user.username = "shmalala_bot"

        mock_reply_message = Mock()
        mock_reply_message.from_user = mock_bot_user
        mock_reply_message.text = fishing_message
        mock_reply_message.caption = None

        mock_update.message.reply_to_message = mock_reply_message
        mock_update.message.text = "парсинг"

        # Mock database - user doesn't exist
        with patch('bot.bot.get_db') as mock_get_db:
            mock_get_db.return_value = iter([mock_db_session])

            # User doesn't exist initially
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            # Mock User model for creation
            from database.database import User

            def create_user(*args, **kwargs):
                user = Mock(spec=User)
                user.id = 3
                user.username = "new_fisher"
                user.balance = 100
                user.telegram_id = mock_update.effective_user.id
                return user

            with patch('database.database.User', side_effect=create_user):
                # Create bot and process manual parsing
                bot = TelegramBot()
                await bot.handle_manual_parsing(mock_update, mock_context)

                # Verify user was created
                mock_db_session.add.assert_called()
                mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_reject_non_bot_reply(self, mock_update, mock_context, mock_db_session):
        """Test that manual parsing rejects non-bot replies"""
        from bot.bot import TelegramBot

        # Setup reply to regular user message (not bot)
        mock_user = Mock()
        mock_user.is_bot = False
        mock_user.first_name = "Regular User"

        mock_reply_message = Mock()
        mock_reply_message.from_user = mock_user
        mock_reply_message.text = "Some message"

        mock_update.message.reply_to_message = mock_reply_message
        mock_update.message.text = "парсинг"

        # Create bot and process manual parsing
        bot = TelegramBot()
        await bot.handle_manual_parsing(mock_update, mock_context)

        # Verify error message was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "игрового бота" in call_args

    @pytest.mark.asyncio
    async def test_parse_all_messages_ignores_automatic_parsing(self, mock_update, mock_context):
        """Test that parse_all_messages ignores automatic parsing (only manual parsing enabled)"""
        from bot.bot import TelegramBot

        # Setup fishing message
        mock_update.message.text = """🎣 [Рыбалка] 🎣
Рыбак: @test_fisher
Монеты: +50 (500)💰"""

        mock_update.effective_chat.type = "group"
        mock_update.message.reply_to_message = None  # Not a reply

        bot = TelegramBot()
        await bot.parse_all_messages(mock_update, mock_context)

        # Verify no processing happened (automatic parsing disabled)
        mock_update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_parse_all_messages_shows_help_for_non_game(self, mock_update, mock_context):
        """Test that parse_all_messages shows help for non-game messages in private chat"""
        from bot.bot import TelegramBot

        # Setup non-game message in private chat
        mock_update.message.text = "Hello bot"
        mock_update.effective_chat.type = "private"
        mock_update.message.reply_to_message = None

        bot = TelegramBot()
        await bot.parse_all_messages(mock_update, mock_context)

        # Verify help message was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "банк-аггрегатор" in call_args
        assert "/start" in call_args
        assert "парсинг" in call_args  # Should mention manual parsing


class TestParserDetection:
    """Test parser detection in various scenarios"""

    def test_detect_fishing_message(self):
        """Test detection of fishing messages"""
        from core.parsers.simple_parser import parse_game_message

        message = """🎣 [Рыбалка] 🎣
Рыбак: @user
Монеты: +100 (1000)💰"""

        result = parse_game_message(message)
        assert result is not None
        assert result['type'] == 'fishing'

    def test_detect_card_message(self):
        """Test detection of card messages"""
        from core.parsers.simple_parser import parse_game_message

        message = """🃏 НОВАЯ КАРТА 🃏
Игрок: @user
Очки: +200"""

        result = parse_game_message(message)
        assert result is not None
        assert result['type'] == 'card'

    def test_no_detection_for_regular_message(self):
        """Test that regular messages are not detected as game messages"""
        from core.parsers.simple_parser import parse_game_message

        message = "This is just a regular chat message"

        result = parse_game_message(message)
        assert result is None


class TestCommandNormalization:
    """Test command normalization for bot mentions."""

    def test_normalize_bot_command_strips_bot_mention(self):
        """Command with @botname should match the base command."""
        from bot.bot import _normalize_bot_command

        assert _normalize_bot_command("/start@lt_lo_game_bot") == "/start"
        assert _normalize_bot_command("/start@lt_lo_game_bot payload") == "/start"

    def test_extract_bot_mentioned_command_matches_configured_username(self):
        """Only commands addressed to this bot should be extracted."""
        from bot.bot import _extract_bot_mentioned_command

        assert (
            _extract_bot_mentioned_command("/start@lt_lo_game_bot", "lt_lo_game_bot")
            == "/start"
        )
        assert (
            _extract_bot_mentioned_command("/start@other_bot", "lt_lo_game_bot") == ""
        )

    @pytest.mark.asyncio
    async def test_handle_mentioned_start_uses_runtime_bot_username_when_config_empty(self):
        """Mentioned /start should work even if BOT_USERNAME is not set in env."""
        from bot.bot import TelegramBot

        with patch("bot.bot.settings") as mock_settings:
            mock_settings.BOT_TOKEN = "123456:TEST"
            mock_settings.BOT_USERNAME = ""

            bot = TelegramBot()
            bot.welcome_command = AsyncMock()

            update = Mock()
            update.effective_message = Mock(text="/start@lt_lo_game_bot")

            context = Mock()
            context.bot = Mock(username="lt_lo_game_bot")

            await bot.handle_mentioned_commands(update, context)

            bot.welcome_command.assert_awaited_once_with(update, context)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
