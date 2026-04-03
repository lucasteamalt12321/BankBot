# bot/handlers/parsing_handler.py
"""
Unified parsing handler that integrates the new message parsing system.
This handler bridges the Telegram bot with the advanced parsing infrastructure.
"""

import structlog
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from src.classifier import MessageClassifier
from src.parsers import (
    ProfileParser, AccrualParser, FishingParser, KarmaParser,
    MafiaGameEndParser, MafiaProfileParser, BunkerGameEndParser, BunkerProfileParser,
    ParserError
)
from src.message_processor import MessageProcessor
from src.balance_manager import BalanceManager
from src.repository import SQLiteRepository
from src.coefficient_provider import CoefficientProvider
from src.idempotency import IdempotencyChecker
from src.audit_logger import AuditLogger

logger = structlog.get_logger()


class ParsingHandler:
    """
    Unified handler for parsing game messages and updating balances.
    Integrates the new message parsing system with the Telegram bot.
    """
    
    def __init__(self, db_path: str = "data/bot.db", coefficients_path: str = "config/coefficients.json"):
        """
        Initialize the parsing handler with all required components.
        
        Args:
            db_path: Path to SQLite database
            coefficients_path: Path to coefficients JSON file
        """
        # Initialize components
        self.classifier = MessageClassifier()
        self.profile_parser = ProfileParser()
        self.accrual_parser = AccrualParser()
        self.fishing_parser = FishingParser()
        self.karma_parser = KarmaParser()
        self.mafia_game_end_parser = MafiaGameEndParser()
        self.mafia_profile_parser = MafiaProfileParser()
        self.bunker_game_end_parser = BunkerGameEndParser()
        self.bunker_profile_parser = BunkerProfileParser()
        
        # Initialize database repository
        self.repository = SQLiteRepository(db_path)
        
        # Initialize coefficient provider
        try:
            self.coefficient_provider = CoefficientProvider.from_config(coefficients_path)
        except FileNotFoundError:
            # Fallback to default coefficients
            logger.warning(f"Coefficients file not found at {coefficients_path}, using defaults")
            self.coefficient_provider = CoefficientProvider({
                "GD Cards": 1,
                "Shmalala": 1,
                "Shmalala Karma": 1,
                "True Mafia": 15,
                "Bunker RP": 20
            })
        
        # Initialize audit logger
        audit_log = logging.getLogger("audit")
        self.audit_logger = AuditLogger(audit_log)
        
        # Initialize balance manager
        self.balance_manager = BalanceManager(
            repository=self.repository,
            coefficient_provider=self.coefficient_provider,
            logger=self.audit_logger
        )
        
        # Initialize idempotency checker
        self.idempotency_checker = IdempotencyChecker(self.repository)
        
        # Initialize message processor
        self.message_processor = MessageProcessor(
            classifier=self.classifier,
            profile_parser=self.profile_parser,
            accrual_parser=self.accrual_parser,
            fishing_parser=self.fishing_parser,
            karma_parser=self.karma_parser,
            mafia_game_end_parser=self.mafia_game_end_parser,
            mafia_profile_parser=self.mafia_profile_parser,
            bunker_game_end_parser=self.bunker_game_end_parser,
            bunker_profile_parser=self.bunker_profile_parser,
            balance_manager=self.balance_manager,
            idempotency_checker=self.idempotency_checker,
            logger=self.audit_logger
        )
        
        logger.info("ParsingHandler initialized with new message parsing system")
    
    def parse_message(self, text: str, timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Parse a game message and update balances.
        
        Args:
            text: Raw message text
            timestamp: Message timestamp (defaults to now)
            
        Returns:
            Dictionary with parsing results:
            {
                'success': bool,
                'message_type': str,
                'player_name': str (if applicable),
                'amount': Decimal (if applicable),
                'error': str (if failed)
            }
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        try:
            # Process the message
            self.message_processor.process_message(text, timestamp)
            
            # Classify to get message type for response
            message_type = self.classifier.classify(text)
            
            return {
                'success': True,
                'message_type': message_type.name,
                'error': None
            }
            
        except ParserError as e:
            logger.warning(f"Parsing failed: {e}", message_preview=text[:100])
            return {
                'success': False,
                'message_type': 'UNKNOWN',
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error during parsing: {e}", exc_info=True)
            return {
                'success': False,
                'message_type': 'ERROR',
                'error': f"Internal error: {str(e)}"
            }
    
    def is_game_message(self, text: str) -> bool:
        """
        Check if a message is from a supported game.
        
        Args:
            text: Message text
            
        Returns:
            True if message is from a supported game
        """
        from src.classifier import MessageType
        message_type = self.classifier.classify(text)
        return message_type != MessageType.UNKNOWN
    
    async def handle_manual_parsing(self, update, context):
        """
        Handle manual parsing triggered by 'парсинг' command.
        
        Args:
            update: Telegram update object
            context: Telegram context object
        """
        from utils.admin.admin_system import AdminSystem
        
        # Get the message being replied to
        replied_message = update.message.reply_to_message
        if not replied_message or not replied_message.text:
            await update.message.reply_text("❌ Ответьте на сообщение игры словом 'парсинг'")
            return
        
        message_text = replied_message.text
        user = update.effective_user
        
        logger.info(f"Manual parsing requested by user {user.id} for message: {message_text[:100]}")
        
        # Parse the message using old system (it works correctly)
        result = self.parse_message(message_text)
        
        if result['success']:
            # Get detailed parsing information
            message_type = result['message_type']
            
            # Try to extract parsed data and update balance in admin system
            try:
                # Re-parse to get detailed info
                from src.classifier import MessageType
                msg_type_enum = self.classifier.classify(message_text)
                
                details = []
                bank_coins = 0
                
                if msg_type_enum == MessageType.SHMALALA_FISHING:
                    parsed = self.fishing_parser.parse(message_text)
                    bank_coins = float(parsed.coins)
                    details.append(f"🎣 Игрок: {parsed.player_name}")
                    details.append(f"💰 Монеты: +{parsed.coins}")
                    details.append(f"🏦 Начислено: +{bank_coins} банковских монет")
                    
                elif msg_type_enum == MessageType.SHMALALA_KARMA:
                    parsed = self.karma_parser.parse(message_text)
                    bank_coins = float(parsed.karma)
                    details.append(f"❤️ Игрок: {parsed.player_name}")
                    details.append(f"⭐ Карма: +{parsed.karma}")
                    details.append(f"🏦 Начислено: +{bank_coins} банковских монет")
                    
                elif msg_type_enum == MessageType.GDCARDS_ACCRUAL:
                    parsed = self.accrual_parser.parse(message_text)
                    bank_coins = float(parsed.points) / 2  # Курс 2:1
                    details.append(f"🃏 Игрок: {parsed.player_name}")
                    details.append(f"🎴 Очки: +{parsed.points}")
                    details.append(f"🏦 Начислено: +{bank_coins} банковских монет (курс 2:1)")
                    
                elif msg_type_enum == MessageType.GDCARDS_PROFILE:
                    parsed = self.profile_parser.parse(message_text)
                    bank_coins = float(parsed.orbs) / 2  # Курс 2:1
                    details.append(f"🃏 Игрок: {parsed.player_name}")
                    details.append(f"💎 Орбы: {parsed.orbs}")
                    details.append(f"🏦 Начислено: +{bank_coins} банковских монет (курс 2:1)")
                    
                elif msg_type_enum == MessageType.TRUEMAFIA_GAME_END:
                    parsed = self.mafia_game_end_parser.parse(message_text)
                    bank_coins = 1  # Курс 15:1, но начисляем 1 монету
                    details.append(f"🎮 Победители: {', '.join(parsed.winners)}")
                    details.append("🏦 Каждому начислено: +1 банковская монета (курс 15:1)")
                    
                elif msg_type_enum == MessageType.TRUEMAFIA_PROFILE:
                    parsed = self.mafia_profile_parser.parse(message_text)
                    bank_coins = float(parsed.money) / 15  # Курс 15:1
                    details.append(f"🎮 Игрок: {parsed.player_name}")
                    details.append(f"💵 Деньги: {parsed.money}")
                    details.append(f"🏦 Начислено: +{bank_coins} банковских монет (курс 15:1)")
                    
                elif msg_type_enum == MessageType.BUNKERRP_GAME_END:
                    parsed = self.bunker_game_end_parser.parse(message_text)
                    bank_coins = 1  # Курс 20:1, но начисляем 1 монету
                    details.append(f"🏚️ Выжившие: {', '.join(parsed.winners)}")
                    details.append("🏦 Каждому начислено: +1 банковская монета (курс 20:1)")
                    
                elif msg_type_enum == MessageType.BUNKERRP_PROFILE:
                    parsed = self.bunker_profile_parser.parse(message_text)
                    bank_coins = float(parsed.money) / 20  # Курс 20:1
                    details.append(f"🏚️ Игрок: {parsed.player_name}")
                    details.append(f"💵 Деньги: {parsed.money}")
                    details.append(f"🏦 Начислено: +{bank_coins} банковских монет (курс 20:1)")
                
                # Update balance in admin system (main database)
                if bank_coins > 0:
                    admin_system = AdminSystem(self.repository.db_path)
                    
                    # Ensure user is registered
                    admin_system.register_user(user.id, user.username, user.first_name)
                    
                    # Get current balance
                    user_data = admin_system.get_user_by_id(user.id)
                    if user_data:
                        current_balance = user_data['balance']
                        new_balance = current_balance + bank_coins
                        
                        # Update balance
                        conn = admin_system.get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE users SET balance = ? WHERE telegram_id = ?",
                            (new_balance, user.id)
                        )
                        conn.commit()
                        
                        # Add transaction record
                        cursor.execute(
                            "SELECT id FROM users WHERE telegram_id = ?",
                            (user.id,)
                        )
                        user_row = cursor.fetchone()
                        if user_row:
                            from datetime import datetime
                            cursor.execute(
                                """INSERT INTO transactions 
                                   (user_id, amount, transaction_type, description, created_at)
                                   VALUES (?, ?, ?, ?, ?)""",
                                (user_row['id'], bank_coins, 'accrual', 
                                 f"Парсинг: {message_type}", datetime.now())
                            )
                            conn.commit()
                        
                        conn.close()
                        
                        details.append(f"\n💰 Новый баланс: {new_balance} очков")
                        logger.info(f"Balance updated for user {user.id}: {current_balance} -> {new_balance}")
                
                # Build response with details
                response = "✅ Сообщение успешно обработано!\n\n"
                response += f"📊 Тип: {message_type}\n\n"
                if details:
                    response += "📝 Детали:\n" + "\n".join(details)
                else:
                    response += "💡 Используйте /balance для проверки баланса"
                
                await update.message.reply_text(response)
                logger.info(f"Manual parsing successful for user {user.id}")
                
            except Exception as e:
                # Fallback to simple response if detailed parsing fails
                logger.error(f"Could not get detailed parsing info: {e}", exc_info=True)
                await update.message.reply_text(
                    f"✅ Сообщение обработано, но возникла ошибка при начислении\n"
                    f"📊 Тип: {message_type}\n\n"
                    f"❌ Ошибка: {str(e)}"
                )
        else:
            await update.message.reply_text(
                f"❌ Не удалось обработать сообщение\n"
                f"Ошибка: {result.get('error', 'Неизвестная ошибка')}"
            )
            logger.warning(f"Manual parsing failed for user {user.id}: {result.get('error')}")
