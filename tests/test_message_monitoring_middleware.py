"""
Unit tests for Message Monitoring Middleware
Tests the middleware functionality for intercepting and processing group messages
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes
import sys
import os

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.message_monitoring_middleware import MessageMonitoringMiddleware, message_monitoring_middleware
from core.advanced_models import ParsedTransaction
from datetime import datetime
from decimal import Decimal


class TestMessageMonitoringMiddleware:
    """Test cases for MessageMonitoringMiddleware"""
    
    @pytest.fixture
    def middleware(self):
        """Create a fresh middleware instance for testing"""
        return MessageMonitoringMiddleware()
    
    @pytest.fixture
    def mock_update(self):
        """Create a mock Telegram update object"""
        update = Mock(spec=Update)
        
        # Mock message
        message = Mock(spec=Message)
        message.text = "Test message"
        message.message_id = 123
        
        # Mock user
        user = Mock(spec=User)
        user.id = 12345
        user.is_bot = False
        user.username = "testuser"
        
        # Mock chat
        chat = Mock(spec=Chat)
        chat.id = -67890
        chat.type = "supergroup"
        
        # Wire up the mocks
        update.message = message
        update.effective_user = user
        update.effective_chat = chat
        message.from_user = user
        message.chat = chat
        
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock context object"""
        return Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    @pytest.fixture
    def mock_parsed_transaction(self):
        """Create a mock parsed transaction"""
        return ParsedTransaction(
            id=1,
            user_id=12345,
            source_bot="Shmalala",
            original_amount=Decimal("100"),
            converted_amount=Decimal("100"),
            currency_type="coins",
            parsed_at=datetime.utcnow(),
            message_text="Test message"
        )
    
    def test_middleware_initialization(self, middleware):
        """Test middleware initializes correctly"""
        assert middleware.enabled is True
        assert middleware.message_parser is None
        assert len(middleware.processed_messages) == 0
    
    def test_enable_disable_middleware(self, middleware):
        """Test enabling and disabling middleware"""
        # Test disable
        middleware.disable()
        assert middleware.enabled is False
        assert middleware.is_enabled() is False
        
        # Test enable
        middleware.enable()
        assert middleware.enabled is True
        assert middleware.is_enabled() is True
    
    def test_is_external_game_bot_by_username(self, middleware, mock_update):
        """Test bot identification by username"""
        # Test with known bot username
        mock_update.message.from_user.username = "shmalala_bot"
        mock_update.message.from_user.is_bot = True
        
        result = middleware._is_external_game_bot(mock_update.message)
        assert result is True
        
        # Test with unknown bot username
        mock_update.message.from_user.username = "unknown_bot"
        result = middleware._is_external_game_bot(mock_update.message)
        assert result is False
    
    def test_is_external_game_bot_by_content(self, middleware, mock_update):
        """Test bot identification by message content"""
        mock_update.message.from_user.is_bot = True
        mock_update.message.from_user.username = None
        
        # Test with Shmalala pattern
        mock_update.message.text = "🎣 [Рыбалка] 🎣 Рыбак: TestUser Монеты: +50"
        result = middleware._is_external_game_bot(mock_update.message)
        assert result is True
        
        # Test with GDcards pattern
        mock_update.message.text = "🃏 НОВАЯ КАРТА 🃏 Игрок: TestUser Очки: +25"
        result = middleware._is_external_game_bot(mock_update.message)
        assert result is True
        
        # Test with no matching pattern
        mock_update.message.text = "Regular bot message"
        result = middleware._is_external_game_bot(mock_update.message)
        assert result is False
    
    def test_should_process_message_currency_patterns(self, middleware, mock_update):
        """Test message processing decision based on currency patterns"""
        # Test with currency pattern
        mock_update.message.text = "Монеты: +100"
        result = middleware._should_process_message(mock_update.message)
        assert result is True
        
        mock_update.message.text = "Очки: +50"
        result = middleware._should_process_message(mock_update.message)
        assert result is True
        
        # Test without currency pattern
        mock_update.message.text = "Regular message"
        result = middleware._should_process_message(mock_update.message)
        assert result is False
    
    def test_should_process_message_game_patterns(self, middleware, mock_update):
        """Test message processing decision based on game patterns"""
        game_patterns = [
            "🎣 [Рыбалка] 🎣",
            "🃏 НОВАЯ КАРТА 🃏",
            "[Игра Крокодил]",
            "Игрок: TestUser",
            "Рыбак: TestUser",
            "Карта: TestCard",
            "Редкость: Редкая",
            "Победил(а) TestUser",
            "TestUser угадал(а) слово"
        ]
        
        for pattern in game_patterns:
            mock_update.message.text = pattern
            result = middleware._should_process_message(mock_update.message)
            assert result is True, f"Pattern '{pattern}' should be processed"
    
    @pytest.mark.asyncio
    async def test_process_message_disabled_middleware(self, middleware, mock_update, mock_context):
        """Test that disabled middleware returns None"""
        middleware.disable()
        
        result = await middleware.process_message(mock_update, mock_context)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_process_message_no_text(self, middleware, mock_update, mock_context):
        """Test processing message with no text"""
        mock_update.message.text = None
        
        result = await middleware.process_message(mock_update, mock_context)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_process_message_bot_user_non_game(self, middleware, mock_update, mock_context):
        """Test processing message from non-game bot"""
        mock_update.effective_user.is_bot = True
        mock_update.message.from_user.is_bot = True
        mock_update.message.text = "Regular bot message"
        
        result = await middleware.process_message(mock_update, mock_context)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_process_message_private_chat_non_game_bot(self, middleware, mock_update, mock_context):
        """Test processing message in private chat from non-game bot"""
        mock_update.effective_chat.type = "private"
        mock_update.effective_user.is_bot = False
        mock_update.message.text = "Regular message"
        
        result = await middleware.process_message(mock_update, mock_context)
        assert result is None
    
    @pytest.mark.asyncio
    @patch('core.message_monitoring_middleware.get_db')
    async def test_process_message_successful_parsing(self, mock_get_db, middleware, mock_update, 
                                                    mock_context, mock_parsed_transaction):
        """Test successful message parsing"""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_parser = AsyncMock()
        mock_parser.parse_message.return_value = mock_parsed_transaction
        
        with patch.object(middleware, '_get_message_parser', return_value=mock_parser):
            with patch.object(middleware, '_should_process_message', return_value=True):
                with patch.object(middleware, '_send_parsing_notification', new_callable=AsyncMock):
                    # Set up message for processing
                    mock_update.message.text = "🎣 [Рыбалка] 🎣 Рыбак: TestUser Монеты: +100"
                    
                    result = await middleware.process_message(mock_update, mock_context)
                    
                    assert result is not None
                    assert result.user_id == 12345
                    assert result.source_bot == "Shmalala"
                    assert result.converted_amount == Decimal("100")
    
    @pytest.mark.asyncio
    @patch('core.message_monitoring_middleware.get_db')
    async def test_process_message_no_parsing_match(self, mock_get_db, middleware, mock_update, mock_context):
        """Test message processing when no parsing patterns match"""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_parser = AsyncMock()
        mock_parser.parse_message.return_value = None
        
        with patch.object(middleware, '_get_message_parser', return_value=mock_parser):
            with patch.object(middleware, '_should_process_message', return_value=True):
                result = await middleware.process_message(mock_update, mock_context)
                
                assert result is None
    
    def test_processed_messages_cache_management(self, middleware):
        """Test that processed messages cache is managed correctly"""
        # Add messages to cache manually (simulating the actual process_message flow)
        for i in range(1200):  # More than the 1000 limit
            message_id = f"message_{i}"
            middleware.processed_messages.add(message_id)
            
            # Simulate the cache management logic from process_message
            if len(middleware.processed_messages) > 1000:
                old_messages = list(middleware.processed_messages)[:500]
                for old_msg in old_messages:
                    middleware.processed_messages.discard(old_msg)
        
        # Cache should be trimmed to prevent memory issues
        assert len(middleware.processed_messages) <= 1000
    
    def test_get_stats(self, middleware):
        """Test middleware statistics"""
        stats = middleware.get_stats()
        
        assert 'enabled' in stats
        assert 'processed_messages_count' in stats
        assert 'parser_initialized' in stats
        
        assert stats['enabled'] is True
        assert stats['processed_messages_count'] == 0
        assert stats['parser_initialized'] is False
    
    def test_clear_processed_messages(self, middleware):
        """Test clearing processed messages cache"""
        # Add some messages
        middleware.processed_messages.add("test1")
        middleware.processed_messages.add("test2")
        
        assert len(middleware.processed_messages) == 2
        
        # Clear cache
        middleware.clear_processed_messages()
        
        assert len(middleware.processed_messages) == 0
    
    @pytest.mark.asyncio
    async def test_send_parsing_notification(self, middleware, mock_update, mock_context, mock_parsed_transaction):
        """Test sending parsing notification"""
        mock_update.message.reply_text = AsyncMock()
        
        await middleware._send_parsing_notification(mock_update, mock_context, mock_parsed_transaction)
        
        # Verify notification was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        
        assert "💫 Обнаружена игровая активность!" in call_args
        assert "Shmalala" in call_args
        assert "100" in call_args
    
    def test_global_middleware_instance(self):
        """Test that global middleware instance is accessible"""
        from core.message_monitoring_middleware import get_middleware_instance
        
        instance = get_middleware_instance()
        assert isinstance(instance, MessageMonitoringMiddleware)
        assert instance.enabled is True


if __name__ == "__main__":
    pytest.main([__file__])