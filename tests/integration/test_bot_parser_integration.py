"""
Integration tests for bot parser integration
Tests that the bot correctly processes game messages using the integrated parser
"""

import pytest
import sys
import os
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
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
        update.effective_message = mock_message
        update.effective_user = mock_user
        update.effective_chat = mock_chat
        return update

    @pytest.fixture
    def mock_context(self):
        """Create a mock context"""
        return Mock(spec=ContextTypes.DEFAULT_TYPE)

    @pytest.fixture
    def isolated_parsing_env(self):
        """Isolated DB environment so parsing integration tests don't touch the real DB.

        Reconfigures the global SQLAlchemy engine/session (used by AdminSystem and
        ParsingService) to a temporary SQLite file and yields
        ``(engine, Session, repo_path)`` where ``repo_path`` is the SQLite file used by
        the legacy SQLiteRepository.
        """
        import database.database as _dbmod
        import utils.admin.admin_system as _admsys
        from database.database import Base, User as _User

        # Use a SINGLE temporary database file for both the SQLAlchemy session
        # (used for seeding and assertions) and the legacy SQLiteRepository /
        # AdminSystem used by the handler. Using two separate files caused the
        # handler to read a stale balance (0) from its own DB and overwrite the
        # seeded balance, producing incorrect results.
        sql_fd, sql_path = tempfile.mkstemp(suffix=".db")
        os.close(sql_fd)
        repo_path = sql_path

        engine = create_engine(f"sqlite:///{sql_path}")
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        orig_engine = _dbmod.engine
        orig_session = _dbmod.SessionLocal
        orig_adm_session = _admsys.SessionLocal

        _dbmod.engine = engine
        _dbmod.SessionLocal = Session
        _admsys.SessionLocal = Session

        try:
            yield engine, Session, repo_path
        finally:
            _dbmod.engine = orig_engine
            _dbmod.SessionLocal = orig_session
            _admsys.SessionLocal = orig_adm_session
            try:
                os.unlink(sql_path)
            except OSError:
                pass

    @pytest.mark.asyncio
    async def test_parse_fishing_message(self, mock_update, mock_context, isolated_parsing_env):
        """Test parsing fishing message accrues points to the user balance."""
        from bot.handlers.parsing_handler import ParsingHandler
        from database.database import User as _User

        engine, Session, repo_path = isolated_parsing_env

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
        mock_update.effective_chat.type = "private"

        # Seed the user with an initial balance
        user_id = mock_update.effective_user.id
        s = Session()
        s.add(_User(telegram_id=user_id, username="fisher_user", balance=1000, is_admin=False))
        s.commit()
        s.close()

        handler = ParsingHandler(db_path=repo_path)
        await handler.handle_manual_parsing(mock_update, mock_context)

        # Verify user balance was updated by +250 coins converted at the
        # canonical Shmalala rate (2.5) -> +625 accrued to balance (1000 -> 1625).
        s = Session()
        user = s.query(_User).filter_by(telegram_id=user_id).first()
        assert user is not None
        assert user.balance == 1625
        s.close()

        # Verify notification was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "625" in call_args
        assert "1625" in call_args

    @pytest.mark.asyncio
    async def test_parse_card_message(self, mock_update, mock_context, isolated_parsing_env):
        """Test parsing card message accrues points to the user balance."""
        from bot.handlers.parsing_handler import ParsingHandler
        from database.database import User as _User

        engine, Session, repo_path = isolated_parsing_env

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
        mock_update.effective_chat.type = "private"

        # Seed the user with an initial balance
        user_id = mock_update.effective_user.id
        s = Session()
        s.add(_User(telegram_id=user_id, username="card_player", balance=500, is_admin=False))
        s.commit()
        s.close()

        handler = ParsingHandler(db_path=repo_path)
        await handler.handle_manual_parsing(mock_update, mock_context)

        # Verify user balance was updated by +150 points converted at the
        # canonical GD Cards rate (2.5) -> +375 accrued to balance (500 -> 875).
        s = Session()
        user = s.query(_User).filter_by(telegram_id=user_id).first()
        assert user is not None
        assert user.balance == 875
        s.close()

        # Verify notification was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "150" in call_args
        assert "875" in call_args

    @pytest.mark.asyncio
    async def test_create_new_user_from_manual_parsing(self, mock_update, mock_context, isolated_parsing_env):
        """Test creating a new user from manual parsing when none exists yet."""
        from bot.handlers.parsing_handler import ParsingHandler
        from database.database import User as _User

        engine, Session, repo_path = isolated_parsing_env

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
        mock_update.effective_chat.type = "private"

        user_id = mock_update.effective_user.id

        handler = ParsingHandler(db_path=repo_path)
        await handler.handle_manual_parsing(mock_update, mock_context)

        # Verify a new user was created and credited with +100 coins converted
        # at the canonical Shmalala rate (2.5) -> +250 accrued to balance.
        s = Session()
        user = s.query(_User).filter_by(telegram_id=user_id).first()
        assert user is not None
        assert user.balance == 250
        s.close()

        # Verify notification was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "250" in call_args

    @pytest.mark.asyncio
    async def test_reject_non_bot_reply(self, mock_update, mock_context, isolated_parsing_env):
        """Test that manual parsing of a non-game reply reports it as unrecognized."""
        from bot.handlers.parsing_handler import ParsingHandler

        _, _, repo_path = isolated_parsing_env

        # Setup reply to a regular (non-bot) message that is not a game message
        mock_user = Mock()
        mock_user.is_bot = False
        mock_user.first_name = "Regular User"

        mock_reply_message = Mock()
        mock_reply_message.from_user = mock_user
        mock_reply_message.text = "Some message"
        mock_reply_message.caption = None

        mock_update.message.reply_to_message = mock_reply_message
        mock_update.message.text = "парсинг"
        mock_update.effective_chat.type = "private"

        handler = ParsingHandler(db_path=repo_path)
        await handler.handle_manual_parsing(mock_update, mock_context)

        # Verify an error message was sent (message not recognized as a game)
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "не распознано" in call_args

    @pytest.mark.asyncio
    async def test_parse_all_messages_ignores_non_reply_messages(self, mock_update, mock_context):
        """Test that parse_all_messages ignores non-reply messages (only reply-based parsing enabled)"""
        from bot.bot import TelegramBot

        # Setup fishing message
        mock_update.message.text = """🎣 [Рыбалка] 🎣
Рыбак: @test_fisher
Монеты: +50 (500)💰"""

        mock_update.effective_chat.type = "group"
        mock_update.message.reply_to_message = None  # Not a reply

        bot = TelegramBot()
        await bot.parse_all_messages(mock_update, mock_context)

        # Verify no processing happened (non-reply messages ignored)
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

        class _FakeSettings:
            BOT_TOKEN = "123456:TEST"
            BOT_USERNAME = ""
            PROXY_URL = ""
            TELEGRAM_BASE_URL = ""
            ADMIN_TELEGRAM_ID = 0

        with patch("bot.bot.settings", _FakeSettings()):
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
