"""
Integration tests for Message Monitoring Middleware with MessageParser
Tests the complete integration between middleware and message parsing functionality
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes
import sys
import os
from decimal import Decimal
from datetime import datetime

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.message_monitoring_middleware import MessageMonitoringMiddleware
from core.message_parser import MessageParser
from core.advanced_models import ParsedTransaction, ParsingRule as AdvancedParsingRule
from database.database import get_db, create_tables, ParsingRule, User as DBUser, ParsedTransaction as DBParsedTransaction


class TestMessageMonitoringIntegration:
    """Integration test cases for middleware and parser"""
    
    @pytest.fixture
    def middleware(self):
        """Create middleware instance"""
        return MessageMonitoringMiddleware()
    
    @pytest.fixture
    def sample_shmalala_message(self):
        """Sample Shmalala fishing message"""
        return """🎣 [Рыбалка] 🎣

Рыбак: TestUser
На крючке: Карп (2.5 кг)
Погода: Солнечно
Место: Озеро
Энергии осталось: 85 ⚡️
Удочка: Золотая (ещё 45 мин.)

Монеты: +150 (1500)💰
Опыт: +25 (250 / 500)🔋"""
    
    @pytest.fixture
    def sample_gdcards_message(self):
        """Sample GDcards message"""
        return """🃏 НОВАЯ КАРТА 🃏

Игрок: TestUser
─────────────────
Карта: "Огненный дракон"
─────────────────
Редкость: Эпическая (🟣 3.2%)
Коллекция: 45/100 карт
Лимит карт сегодня: 3 из 5

Очки: +75"""
    
    @pytest.fixture
    def mock_update_shmalala(self, sample_shmalala_message):
        """Create mock update with Shmalala message"""
        update = Mock(spec=Update)
        
        # Mock message
        message = Mock(spec=Message)
        message.text = sample_shmalala_message
        message.message_id = 123
        message.reply_text = AsyncMock()
        
        # Mock user (external bot)
        user = Mock(spec=User)
        user.id = 98765  # Different from target user
        user.is_bot = True
        user.username = "shmalala_bot"
        
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
    def mock_update_gdcards(self, sample_gdcards_message):
        """Create mock update with GDcards message"""
        update = Mock(spec=Update)
        
        # Mock message
        message = Mock(spec=Message)
        message.text = sample_gdcards_message
        message.message_id = 124
        message.reply_text = AsyncMock()
        
        # Mock user (external bot)
        user = Mock(spec=User)
        user.id = 98766  # Different from target user
        user.is_bot = True
        user.username = "gdcards_bot"
        
        # Mock chat
        chat = Mock(spec=Chat)
        chat.id = -67891
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
        """Create mock context"""
        return Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session"""
        db = Mock()
        
        # Mock parsing rules
        shmalala_rule = Mock()
        shmalala_rule.id = 1
        shmalala_rule.bot_name = "Shmalala"
        shmalala_rule.pattern = r'Монеты:\s*\+(\d+)'
        shmalala_rule.multiplier = Decimal('1.0')
        shmalala_rule.currency_type = "coins"
        shmalala_rule.is_active = True
        
        gdcards_rule = Mock()
        gdcards_rule.id = 2
        gdcards_rule.bot_name = "GDcards"
        gdcards_rule.pattern = r'Очки:\s*\+(\d+)'
        gdcards_rule.multiplier = Decimal('1.0')
        gdcards_rule.currency_type = "points"
        gdcards_rule.is_active = True
        
        db.query.return_value.filter.return_value.all.return_value = [shmalala_rule, gdcards_rule]
        
        # Mock user query
        mock_user = Mock()
        mock_user.balance = 1000
        mock_user.last_activity = datetime.utcnow()
        db.query.return_value.filter.return_value.first.return_value = mock_user
        
        # Mock transaction creation
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        
        return db
    
    @pytest.mark.asyncio
    @patch('core.message_monitoring_middleware.get_db')
    async def test_shmalala_message_integration(self, mock_get_db, middleware, mock_update_shmalala, 
                                              mock_context, mock_db_session):
        """Test complete integration with Shmalala message"""
        mock_get_db.return_value = iter([mock_db_session])
        
        # Process the message
        result = await middleware.process_message(mock_update_shmalala, mock_context)
        
        # Verify result
        assert result is not None
        assert isinstance(result, ParsedTransaction)
        assert result.source_bot == "Shmalala"
        assert result.original_amount == Decimal('150')
        assert result.converted_amount == Decimal('150')
        assert result.currency_type == "coins"
        
        # Verify notification was sent
        mock_update_shmalala.message.reply_text.assert_called_once()
        notification_text = mock_update_shmalala.message.reply_text.call_args[0][0]
        assert "💫 Обнаружена игровая активность!" in notification_text
        assert "Shmalala" in notification_text
        assert "150" in notification_text
    
    @pytest.mark.asyncio
    @patch('core.message_monitoring_middleware.get_db')
    async def test_gdcards_message_integration(self, mock_get_db, middleware, mock_update_gdcards, 
                                             mock_context, mock_db_session):
        """Test complete integration with GDcards message"""
        mock_get_db.return_value = iter([mock_db_session])
        
        # Process the message
        result = await middleware.process_message(mock_update_gdcards, mock_context)
        
        # Verify result
        assert result is not None
        assert isinstance(result, ParsedTransaction)
        assert result.source_bot == "GDcards"
        assert result.original_amount == Decimal('75')
        assert result.converted_amount == Decimal('75')
        assert result.currency_type == "points"
        
        # Verify notification was sent
        mock_update_gdcards.message.reply_text.assert_called_once()
        notification_text = mock_update_gdcards.message.reply_text.call_args[0][0]
        assert "💫 Обнаружена игровая активность!" in notification_text
        assert "GDcards" in notification_text
        assert "75" in notification_text
    
    @pytest.mark.asyncio
    @patch('core.message_monitoring_middleware.get_db')
    async def test_non_game_message_ignored(self, mock_get_db, middleware, mock_context, mock_db_session):
        """Test that non-game messages are ignored"""
        mock_get_db.return_value = iter([mock_db_session])
        
        # Create update with regular message
        update = Mock(spec=Update)
        message = Mock(spec=Message)
        message.text = "Hello, this is a regular message"
        message.message_id = 125
        
        user = Mock(spec=User)
        user.id = 12345
        user.is_bot = False
        user.username = "regular_user"
        
        chat = Mock(spec=Chat)
        chat.id = -67892
        chat.type = "supergroup"
        
        update.message = message
        update.effective_user = user
        update.effective_chat = chat
        message.from_user = user
        message.chat = chat
        
        # Process the message
        result = await middleware.process_message(update, mock_context)
        
        # Verify no processing occurred
        assert result is None
    
    @pytest.mark.asyncio
    @patch('core.message_monitoring_middleware.get_db')
    async def test_duplicate_message_handling(self, mock_get_db, middleware, mock_update_shmalala, 
                                            mock_context, mock_db_session):
        """Test that duplicate messages are handled correctly"""
        mock_get_db.return_value = iter([mock_db_session])
        
        # Process the same message twice
        result1 = await middleware.process_message(mock_update_shmalala, mock_context)
        result2 = await middleware.process_message(mock_update_shmalala, mock_context)
        
        # First processing should succeed
        assert result1 is not None
        
        # Second processing should be skipped (duplicate)
        assert result2 is None
    
    @pytest.mark.asyncio
    @patch('core.message_monitoring_middleware.get_db')
    async def test_parsing_error_handling(self, mock_get_db, middleware, mock_update_shmalala, 
                                        mock_context):
        """Test error handling during parsing"""
        # Mock database session that raises an exception
        mock_db_session = Mock()
        mock_db_session.query.side_effect = Exception("Database error")
        mock_get_db.return_value = iter([mock_db_session])
        
        # Process the message
        result = await middleware.process_message(mock_update_shmalala, mock_context)
        
        # Should handle error gracefully
        assert result is None
    
    @pytest.mark.asyncio
    async def test_middleware_disabled_integration(self, middleware, mock_update_shmalala, mock_context):
        """Test that disabled middleware doesn't process messages"""
        middleware.disable()
        
        result = await middleware.process_message(mock_update_shmalala, mock_context)
        
        assert result is None
    
    def test_bot_identification_integration(self, middleware):
        """Test bot identification with various message types"""
        # Test Shmalala bot identification
        message = Mock()
        message.from_user = Mock()
        message.from_user.is_bot = True
        message.from_user.username = "shmalala_bot"
        message.text = "🎣 [Рыбалка] 🎣"
        
        assert middleware._is_external_game_bot(message) is True
        
        # Test GDcards bot identification
        message.from_user.username = "gdcards_bot"
        message.text = "🃏 НОВАЯ КАРТА 🃏"
        
        assert middleware._is_external_game_bot(message) is True
        
        # Test unknown bot
        message.from_user.username = "unknown_bot"
        message.text = "Regular message"
        
        assert middleware._is_external_game_bot(message) is False
    
    def test_message_processing_criteria_integration(self, middleware):
        """Test message processing criteria with realistic messages"""
        message = Mock()
        
        # Test Shmalala patterns
        shmalala_patterns = [
            "Монеты: +150",
            "🎣 [Рыбалка] 🎣 Рыбак: TestUser",
            "Игрок: TestUser угадал(а) слово!",
            "Победил(а) TestUser и забрал(а) 100 💰 монетки"
        ]
        
        for pattern in shmalala_patterns:
            message.text = pattern
            assert middleware._should_process_message(message) is True, f"Pattern '{pattern}' should be processed"
        
        # Test GDcards patterns
        gdcards_patterns = [
            "Очки: +75",
            "🃏 НОВАЯ КАРТА 🃏",
            "Игрок: TestUser",
            "Карта: \"Огненный дракон\"",
            "Редкость: Эпическая"
        ]
        
        for pattern in gdcards_patterns:
            message.text = pattern
            assert middleware._should_process_message(message) is True, f"Pattern '{pattern}' should be processed"
        
        # Test non-game patterns
        non_game_patterns = [
            "Hello world",
            "How are you?",
            "Regular chat message",
            "No game content here"
        ]
        
        for pattern in non_game_patterns:
            message.text = pattern
            assert middleware._should_process_message(message) is False, f"Pattern '{pattern}' should not be processed"


if __name__ == "__main__":
    pytest.main([__file__])