# bot/handlers/parsing_handler.py
"""
Unified parsing handler that integrates the new message parsing system.
This handler bridges the Telegram bot with the advanced parsing infrastructure.

Supports three target bots:
- gusya_cards (Гуся Cards): coins
- gdcards (GDcards): orbs  <- PRIORITY
- shmalala (Shmalala): money

Trigger: user replies to target bot message with 'парсинг'
"""

import structlog
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import text
from telegram.error import NetworkError, TimedOut

from src.classifier import MessageClassifier
from src.parsers import (
    ProfileParser, AccrualParser, FishingParser, KarmaParser,
    MafiaGameEndParser, MafiaProfileParser, BunkerGameEndParser, BunkerProfileParser,
    ParserError
)
from core.parsers.unified import UnifiedParser
from core.parsers.base import AccrualResult, ProfileResult, GameEndResult
from src.message_processor import MessageProcessor
from src.balance_manager import BalanceManager
from src.repository import SQLiteRepository
from src.coefficient_provider import CoefficientProvider
from src.idempotency import IdempotencyChecker
from src.audit_logger import AuditLogger

logger = structlog.get_logger()

PARSING_REPLY_TIMEOUTS = {
    "connect_timeout": 15,
    "read_timeout": 25,
    "write_timeout": 25,
    "pool_timeout": 15,
}


async def _reply_text_with_retry(update, context, text: str, *, max_retries: int = 3):
    """Send parsing replies with retries.

    HF Spaces sometimes gets a transient Telegram timeout exactly when sending
    replies to supergroups. For group chats we avoid Telegram reply threading
    and send a plain chat message first; this is more reliable on HF.
    """
    message = getattr(update, "message", None)
    chat = getattr(update, "effective_chat", None)
    last_error = None
    chat_type = getattr(chat, "type", "") if chat is not None else ""

    if chat is not None and chat_type in {"group", "supergroup"}:
        for attempt in range(1, max_retries + 1):
            try:
                sent = await context.bot.send_message(
                    chat_id=chat.id,
                    text=text,
                    **PARSING_REPLY_TIMEOUTS,
                )
                logger.info("Parsing response sent via direct send_message", chat_id=chat.id)
                return sent
            except (TimedOut, NetworkError) as exc:
                last_error = exc
                logger.warning(
                    "Parsing direct send_message timeout, retrying",
                    attempt=attempt,
                    max_retries=max_retries,
                    error_type=type(exc).__name__,
                    error_msg=str(exc),
                )
                await asyncio.sleep(min(attempt, 2))

    for attempt in range(1, max_retries + 1):
        try:
            if message is not None:
                sent = await message.reply_text(text, **PARSING_REPLY_TIMEOUTS)
                logger.info("Parsing response sent via reply_text")
                return sent
        except (TimedOut, NetworkError) as exc:
            last_error = exc
            logger.warning(
                "Parsing reply_text timeout, retrying",
                attempt=attempt,
                max_retries=max_retries,
                error_type=type(exc).__name__,
                error_msg=str(exc),
            )
            await asyncio.sleep(min(attempt, 3))

    if chat is not None and chat_type not in {"group", "supergroup"}:
        for attempt in range(1, max_retries + 1):
            try:
                sent = await context.bot.send_message(
                    chat_id=chat.id,
                    text=text,
                    **PARSING_REPLY_TIMEOUTS,
                )
                logger.info("Parsing response sent via fallback send_message", chat_id=chat.id)
                return sent
            except (TimedOut, NetworkError) as exc:
                last_error = exc
                logger.warning(
                    "Parsing send_message fallback timeout, retrying",
                    attempt=attempt,
                    max_retries=max_retries,
                    error_type=type(exc).__name__,
                    error_msg=str(exc),
                )
                await asyncio.sleep(min(attempt, 3))

    logger.error(
        "Parsing reply delivery failed after retries",
        error_type=type(last_error).__name__ if last_error else None,
        error_msg=str(last_error) if last_error else None,
    )
    return None


class ParsingHandler:
    """
    Unified handler for parsing game messages and updating balances.
    Integrates the new message parsing system with the Telegram bot.
    
    Priority: GDcards (orbs)
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

    async def handle_target_bot_parsing(self, update, context, message_text: str, user) -> bool:
        """
        Handle parsing for target bots (gusya_cards, gdcards, shmalala, shmalala_karma).
        Uses new ParsingService with coefficient-based conversion.
        Supports both accrual messages (+X) and profile messages (current balance).
        
        Args:
            update: Telegram update
            context: Callback context
            message_text: Text of the replied message
            user: Telegram user
            
        Returns:
            True if handled by this method, False to fall back to legacy parsing
        """
        from bank_bot.services.parsing_service import ParsingService
        from database.database import SessionLocal

        db = SessionLocal()
        try:
            parsing_service = ParsingService(db)
            
            # Check if this is an accrual message (+X format)
            bot_name = parsing_service.detect_bot(message_text)
            is_profile = False
            
            # If not accrual, check if it's a profile message
            if bot_name is None:
                bot_name = parsing_service.detect_profile_bot(message_text)
                is_profile = True
            
            if bot_name is None:
                return False

            # Get user ID from database
            from utils.admin.admin_system import AdminSystem
            admin_system = AdminSystem(self.repository.db_path)
            admin_system.register_user(user.id, user.username, user.first_name)
            user_data = admin_system.get_user_by_id(user.id)
            
            if not user_data:
                await _reply_text_with_retry(update, context, "❌ Пользователь не найден в системе.")
                return True

            user_id = user_data.get("id")
            if not user_id:
                await _reply_text_with_retry(update, context, "❌ Ошибка идентификации пользователя.")
                return True

            # Route to appropriate parsing method
            if is_profile:
                success, response, details = parsing_service.parse_profile_and_accrue(
                    user_id=user_id,
                    text=message_text
                )
            else:
                success, response, details = parsing_service.parse_and_accrue(
                    user_id=user_id,
                    text=message_text
                )

            if success:
                db.commit()
                logger.info(
                    "Target bot parsing success",
                    user_id=user.id,
                    bot_name=details.get("bot_name"),
                    points=details.get("points"),
                    is_profile=is_profile,
                )
                await _reply_text_with_retry(update, context, response)
            else:
                db.rollback()
                logger.warning(
                    "Target bot parsing failed",
                    user_id=user.id,
                    response=response,
                )
                await _reply_text_with_retry(update, context, f"❌ {response}")

            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Target bot parsing error: {e}", exc_info=True)
            await _reply_text_with_retry(update, context, "❌ Ошибка при обработке данных")
            return True
        finally:
            db.close()

    async def handle_manual_parsing(self, update, context):
        """
        Handle manual parsing triggered by 'парсинг' command.
        Uses new ParsingService for target bots (GDcards priority),
        falls back to UnifiedParser for legacy games.
        """
        from utils.admin.admin_system import AdminSystem

        replied_message = update.message.reply_to_message
        message_text = ""
        message_date = datetime.now()
        if replied_message:
            message_text = replied_message.text or replied_message.caption or ""
            message_date = replied_message.date or datetime.now()

        if not message_text:
            await _reply_text_with_retry(
                update,
                context,
                "❌ Я не вижу сообщение, на которое вы ответили.\n\n"
                "Для защиты от накрутки парсинг работает только по реальному reply "
                "на сообщение игрового бота, которое Telegram передал нашему боту.\n"
                "Попробуйте ответить именно на сообщение GDcards/Shmalala или добавьте "
                "бота в группу администратором/отключите Privacy Mode через BotFather.",
            )
            return

        user = update.effective_user
        message_id = self.idempotency_checker.generate_message_id(
            message_text, message_date
        )

        # Idempotency check
        if self.idempotency_checker.is_processed(message_id):
            await _reply_text_with_retry(
                update,
                context,
                "⚠️ Это сообщение уже было обработано ранее.\n"
                "Монеты начислены, повторный парсинг невозможен."
            )
            logger.info(f"Duplicate parsing blocked for user {user.id}")
            return

        logger.info(f"Manual parsing by user {user.id}: {message_text[:120]}")

        # Try new target bot parsing first (GDcards priority)
        handled = await self.handle_target_bot_parsing(update, context, message_text, user)
        if handled:
            self.idempotency_checker.mark_processed(message_id)
            return

        # Fall back to legacy UnifiedParser for other games
        parser = UnifiedParser()
        result = parser.parse(message_text)

        if not result:
            await update.message.reply_text(
                "❌ Сообщение не распознано как игровое.\n"
                "Поддерживаемые игры: 🃏 GD Cards, 🎣 Shmalala, 🎮 True Mafia, 🏚️ Bunker RP"
            )
            logger.info(f"Message not recognized for user {user.id}")
            return

        # Determine bank coins based on game and result type
        bank_coins = 0.0
        details = []
        game_emoji = {"GD Cards": "🃏", "Shmalala": "🎣", "True Mafia": "🎮", "Bunker RP": "🏚️"}.get(result.game, "🎲")

        if isinstance(result, AccrualResult):
            if result.game == "GD Cards":
                bank_coins = float(result.amount) / 2
                details.append(f"{game_emoji} Начисление: +{result.amount} очков")
                details.append(f"🏦 Конвертация: +{bank_coins:.1f} монет (курс 2:1)")
            elif result.game == "Shmalala":
                bank_coins = float(result.amount)
                details.append(f"{game_emoji} Начисление: +{result.amount}")
                details.append(f"🏦 Конвертация: +{bank_coins:.1f} монет (курс 1:1)")

        elif isinstance(result, ProfileResult):
            if result.game == "GD Cards":
                bank_coins = float(result.balance) / 2
                details.append(f"{game_emoji} Профиль, баланс: {result.balance}")
                details.append(f"🏦 Конвертация: +{bank_coins:.1f} монет (курс 2:1)")
            elif result.game == "True Mafia":
                bank_coins = float(result.balance) / 15
                details.append(f"{game_emoji} Профиль, деньги: {result.balance}")
                details.append(f"🏦 Конвертация: +{bank_coins:.1f} монет (курс 15:1)")
            elif result.game == "Bunker RP":
                bank_coins = float(result.balance) / 20
                details.append(f"{game_emoji} Профиль, деньги: {result.balance}")
                details.append(f"🏦 Конвертация: +{bank_coins:.1f} монет (курс 20:1)")

        elif isinstance(result, GameEndResult):
            if result.game == "True Mafia":
                bank_coins = 1.0
                details.append(f"{game_emoji} Победители: {', '.join(result.winners[:5])}")
                details.append(f"🏦 Начислено: +{bank_coins:.0f} монета (курс 15:1)")
            elif result.game == "Bunker RP":
                bank_coins = 1.0
                details.append(f"{game_emoji} Выжившие: {', '.join(result.winners[:5])}")
                details.append(f"🏦 Начислено: +{bank_coins:.0f} монета (курс 20:1)")

        # Apply balance update
        if bank_coins > 0:
            try:
                admin_system = AdminSystem(self.repository.db_path)
                admin_system.register_user(user.id, user.username, user.first_name)
                user_data = admin_system.get_user_by_id(user.id)

                if user_data:
                    current_balance = float(user_data.get("balance", 0))
                    new_balance = current_balance + bank_coins

                    from database.database import SessionLocal
                    db = SessionLocal()
                    try:
                        db.execute(
                            text("UPDATE users SET balance = :balance WHERE telegram_id = :tid"),
                            {"balance": new_balance, "tid": user.id},
                        )
                        user_row = db.execute(
                            text("SELECT id FROM users WHERE telegram_id = :tid"),
                            {"tid": user.id},
                        ).mappings().first()
                        if user_row:
                            db.execute(
                                text(
                                    "INSERT INTO transactions (user_id, amount, transaction_type, description, created_at) "
                                    "VALUES (:uid, :amount, 'accrual', :desc, :created)"
                                ),
                                {
                                    "uid": user_row["id"],
                                    "amount": bank_coins,
                                    "desc": f"{result.game}: {result.__class__.__name__}",
                                    "created": datetime.now(),
                                },
                            )
                        db.commit()
                    finally:
                        db.close()

                    details.append(f"\n💰 Баланс: {current_balance:.1f} → {new_balance:.1f}")
                    logger.info(f"Balance updated for user {user.id}: +{bank_coins}")
            except Exception as e:
                logger.error(f"Balance update failed: {e}", exc_info=True)
                details.append(f"\n⚠️ Начисление не выполнено: {e}")

        # Mark as processed
        self.idempotency_checker.mark_processed(message_id)

        # Build response
        response = f"✅ {result.game} — сообщение обработано!\n\n"
        response += "\n".join(details)
        response += "\n\n💡 /balance — проверить баланс"

        await update.message.reply_text(response)
        logger.info(f"Parsing complete for user {user.id}: {result.game}")
