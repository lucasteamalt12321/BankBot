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
        mock_update.message.text = """🎣 [Рыбалка] 🎣
Рыбак: @fisher_user
Улов: Золотая рыбка
Монеты: +250 (1500)💰
Опыт: +10"""
        
        # Mock database
        with patch('bot.bot.get_db') as mock_get_db:
            mock_get_db.return_value = iter([mock_db_session])
            
            # Mock User model
            from database.database import User
            mock_user_obj = Mock(spec=User)
            mock_user_obj.id = 1
            mock_user_obj.username = "fisher_user"
            mock_user_obj.balance = 1000
            
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user_obj
            
            # Create bot and process message
            bot = TelegramBot()
            await bot.process_game_message(mock_update, mock_context)
            
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
        """Test parsing card message"""
        from bot.bot import TelegramBot
        
        # Setup card message
        mock_update.message.text = """🃏 НОВАЯ КАРТА 🃏
Игрок: @card_player
Карта: Легендарная
Очки: +150
Редкость: Epic"""
        
        # Mock database
        with patch('bot.bot.get_db') as mock_get_db:
            mock_get_db.return_value = iter([mock_db_session])
            
            # Mock User model
            from database.database import User
            mock_user_obj = Mock(spec=User)
            mock_user_obj.id = 2
            mock_user_obj.username = "card_player"
            mock_user_obj.balance = 500
            
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user_obj
            
            # Create bot and process message
            bot = TelegramBot()
            await bot.process_game_message(mock_update, mock_context)
            
            # Verify user balance was updated
            assert mock_user_obj.balance == 650
            
            # Verify notification was sent
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "card_player" in call_args
            assert "150" in call_args
            assert "🃏" in call_args
    
    @pytest.mark.asyncio
    async def test_create_new_user_from_game_message(self, mock_update, mock_context, mock_db_session):
        """Test creating new user from game message"""
        from bot.bot import TelegramBot
        
        # Setup message
        mock_update.message.text = """🎣 [Рыбалка] 🎣
Рыбак: @new_fisher
Монеты: +100 (100)💰"""
        
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
                return user
            
            with patch('database.database.User', side_effect=create_user):
                # Create bot and process message
                bot = TelegramBot()
                await bot.process_game_message(mock_update, mock_context)
                
                # Verify user was created
                mock_db_session.add.assert_called_once()
                mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_ignore_non_game_message(self, mock_update, mock_context, mock_db_session):
        """Test that non-game messages are ignored"""
        from bot.bot import TelegramBot
        
        # Setup non-game message
        mock_update.message.text = "Hello, this is just a regular message"
        
        # Mock database
        with patch('bot.bot.get_db') as mock_get_db:
            mock_get_db.return_value = iter([mock_db_session])
            
            # Create bot and process message
            bot = TelegramBot()
            await bot.process_game_message(mock_update, mock_context)
            
            # Verify no database operations were performed
            mock_db_session.add.assert_not_called()
            mock_db_session.commit.assert_not_called()
            
            # Verify no notification was sent
            mock_update.message.reply_text.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_parse_all_messages_detects_game_message(self, mock_update, mock_context):
        """Test that parse_all_messages correctly detects game messages"""
        from bot.bot import TelegramBot
        
        # Setup fishing message
        mock_update.message.text = """🎣 [Рыбалка] 🎣
Рыбак: @test_fisher
Монеты: +50 (500)💰"""
        
        mock_update.effective_chat.type = "group"
        
        # Mock process_game_message
        with patch.object(TelegramBot, 'process_game_message', new_callable=AsyncMock) as mock_process:
            bot = TelegramBot()
            await bot.parse_all_messages(mock_update, mock_context)
            
            # Verify process_game_message was called
            mock_process.assert_called_once_with(mock_update, mock_context)
    
    @pytest.mark.asyncio
    async def test_parse_all_messages_shows_help_for_non_game(self, mock_update, mock_context):
        """Test that parse_all_messages shows help for non-game messages in private chat"""
        from bot.bot import TelegramBot
        
        # Setup non-game message in private chat
        mock_update.message.text = "Hello bot"
        mock_update.effective_chat.type = "private"
        
        bot = TelegramBot()
        await bot.parse_all_messages(mock_update, mock_context)
        
        # Verify help message was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "банк-аггрегатор" in call_args
        assert "/start" in call_args


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
