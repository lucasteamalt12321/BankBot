"""Parsing service for extracting resources from game bot messages.

Supports three target bots:
- gusya_cards (Гуся Cards): coins
- gdcards (GDcards): orbs  <- PRIORITY
- shmalala (Shmalala): money

Logic:
  b = extracted amount from message
  k = conversion coefficient from DB
  points = b * k
  n = n + b (internal accumulated value)
  balance = balance + points
"""

import re
import structlog
from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from bank_bot.repositories.balance_repository import BalanceRepository
from bank_bot.repositories.transaction_repository import TransactionRepository
from database.database import UserResource, ConversionRate

logger = structlog.get_logger()

# Regex patterns for each bot
PARSING_PATTERNS = {
    "gusya_cards": {
        "resource_type": "coins",
        "emoji": "💰",
        "patterns": [
            re.compile(r"💰\s*Монеты\s*•\s*\+(\d+)\s*\["),
            re.compile(r"Монеты\s*•\s*\+(\d+)"),
        ],
    },
    "gdcards": {
        "resource_type": "orbs",
        "emoji": "🤩",
        "patterns": [
            re.compile(r"🤩\s*Орбы:\s*\+(\d+)"),
            re.compile(r"Орбы:\s*\+(\d+)"),
        ],
    },
    "shmalala": {
        "resource_type": "money",
        "emoji": "🎣",
        "patterns": [
            re.compile(r"Монеты:\s*\+(\d+)\s*\("),
            re.compile(r"Монеты:\s*\+(\d+)"),
        ],
    },
}

BOT_DISPLAY_NAMES = {
    "gusya_cards": "Гуся Cards",
    "gdcards": "GDcards",
    "shmalala": "Shmalala",
}

RESOURCE_DISPLAY_NAMES = {
    "coins": "монету",
    "orbs": "орб",
    "money": "монету",
}


class ParsingService:
    """Service for parsing game messages and updating balances.

    Priority: GDcards (orbs)
    """

    def __init__(self, session: Session) -> None:
        """Initialize with SQLAlchemy session.

        Args:
            session: Active SQLAlchemy session.
        """
        self._session = session
        self._balance_repo = BalanceRepository(session)
        self._tx_repo = TransactionRepository(session)

    def detect_bot(self, text: str) -> Optional[str]:
        """Detect which bot the message is from.

        Args:
            text: Message text to analyze.

        Returns:
            Bot identifier (gusya_cards, gdcards, shmalala) or None.
        """
        text_lower = text.lower()

        # GDcards priority detection
        if "орбы" in text_lower or "🤩" in text:
            # Verify with pattern
            for pattern in PARSING_PATTERNS["gdcards"]["patterns"]:
                if pattern.search(text):
                    return "gdcards"

        # Gusya Cards
        if "монеты" in text_lower and ("💰" in text or "гус" in text_lower):
            for pattern in PARSING_PATTERNS["gusya_cards"]["patterns"]:
                if pattern.search(text):
                    return "gusya_cards"

        # Shmalala
        if "монеты:" in text_lower and "💰" in text:
            for pattern in PARSING_PATTERNS["shmalala"]["patterns"]:
                if pattern.search(text):
                    return "shmalala"

        # Fallback: try all patterns
        for bot_name, config in PARSING_PATTERNS.items():
            for pattern in config["patterns"]:
                if pattern.search(text):
                    return bot_name

        return None

    def extract_amount(self, text: str, bot_name: str) -> Optional[int]:
        """Extract resource amount b from message text.

        Args:
            text: Message text.
            bot_name: Bot identifier.

        Returns:
            Extracted amount b or None if not found.
        """
        config = PARSING_PATTERNS.get(bot_name)
        if not config:
            return None

        for pattern in config["patterns"]:
            match = pattern.search(text)
            if match:
                try:
                    amount = int(match.group(1))
                    if amount < 0:
                        logger.warning(
                            "Negative amount extracted",
                            bot=bot_name,
                            amount=amount,
                            text_preview=text[:100],
                        )
                        return None
                    return amount
                except (ValueError, IndexError):
                    continue

        return None

    def get_or_create_user_resource(
        self, user_id: int, bot_name: str, resource_type: str
    ) -> UserResource:
        """Get existing UserResource or create new one with n=0.

        Args:
            user_id: User primary key.
            bot_name: Bot name.
            resource_type: Resource type.

        Returns:
            UserResource instance.
        """
        resource = (
            self._session.query(UserResource)
            .filter(
                UserResource.user_id == user_id,
                UserResource.bot_name == bot_name,
                UserResource.resource_type == resource_type,
            )
            .first()
        )

        if resource is None:
            resource = UserResource(
                user_id=user_id,
                bot_name=bot_name,
                resource_type=resource_type,
                n=0,
            )
            self._session.add(resource)
            self._session.flush()
            logger.info(
                "Created new user resource",
                user_id=user_id,
                bot_name=bot_name,
                resource_type=resource_type,
            )

        return resource

    def get_conversion_rate(self, bot_name: str, resource_type: str) -> Decimal:
        """Get conversion coefficient k from DB.

        Args:
            bot_name: Bot name.
            resource_type: Resource type.

        Returns:
            Conversion coefficient k (default 1.0 if not found).
        """
        rate = (
            self._session.query(ConversionRate)
            .filter(
                ConversionRate.bot_name == bot_name,
                ConversionRate.resource_type == resource_type,
                ConversionRate.is_active == True,  # noqa: E712
            )
            .first()
        )

        if rate is None:
            logger.warning(
                "Conversion rate not found, using default 1.0",
                bot_name=bot_name,
                resource_type=resource_type,
            )
            return Decimal("1.0")

        return Decimal(str(rate.k))

    def parse_and_accrue(
        self, user_id: int, text: str
    ) -> Tuple[bool, str, dict]:
        """Parse message and accrue points to user balance.

        Args:
            user_id: User primary key.
            text: Message text from target bot.

        Returns:
            Tuple of (success: bool, message: str, details: dict).
            details contains: bot_name, resource_type, b, k, points, n_old, n_new,
                             balance_old, balance_new
        """
        # Step 1: Detect bot
        bot_name = self.detect_bot(text)
        if bot_name is None:
            logger.info(
                "Bot not detected in message",
                user_id=user_id,
                text_preview=text[:200],
            )
            return False, "Не удалось распознать данные в сообщении", {}

        config = PARSING_PATTERNS[bot_name]
        resource_type = config["resource_type"]

        # Step 2: Extract amount b
        b = self.extract_amount(text, bot_name)
        if b is None:
            logger.warning(
                "Could not extract amount",
                user_id=user_id,
                bot_name=bot_name,
                text_preview=text[:200],
            )
            return False, "Не удалось распознать данные в сообщении", {}

        # Step 3: Get conversion rate k
        k = self.get_conversion_rate(bot_name, resource_type)

        # Step 4: Calculate points
        points = int(b * k)
        if points <= 0:
            logger.error(
                "Invalid points calculated",
                user_id=user_id,
                bot_name=bot_name,
                b=b,
                k=k,
                points=points,
            )
            return False, "Ошибка при обработке данных", {}

        # Step 5: Get or create user resource (n tracking)
        user_resource = self.get_or_create_user_resource(
            user_id, bot_name, resource_type
        )
        n_old = user_resource.n
        n_new = n_old + b
        user_resource.n = n_new

        # Step 6: Update user balance
        user = self._balance_repo.add_balance(user_id, points)
        if user is None:
            logger.error(
                "User not found for balance update",
                user_id=user_id,
            )
            return False, "Ошибка при обработке данных", {}

        balance_new = user.balance
        balance_old = balance_new - points

        # Step 7: Log transaction
        bot_display = BOT_DISPLAY_NAMES.get(bot_name, bot_name)
        resource_display = RESOURCE_DISPLAY_NAMES.get(resource_type, resource_type)
        self._tx_repo.log_transaction(
            user_id=user_id,
            amount=points,
            transaction_type="parsing_accrual",
            description=f"Парсинг {bot_display}: +{b} {resource_type} (курс {k})",
            source_game=bot_name,
        )

        logger.info(
            "Parsing accrual completed",
            user_id=user_id,
            bot_name=bot_name,
            b=b,
            k=float(k),
            points=points,
            n_old=n_old,
            n_new=n_new,
            balance_old=balance_old,
            balance_new=balance_new,
        )

        # Step 8: Build response message
        # Format k: show at least one decimal place for whole numbers
        k_str = str(k).rstrip("0").rstrip(".") if "." in str(k) else str(k)
        k_display = k_str if "." in k_str else f"{k_str}.0"
        response = (
            f"Зачислено {points} очков "
            f"(по курсу {k_display} за {resource_display}). "
            f"Ваш баланс: {balance_new} очков"
        )

        details = {
            "bot_name": bot_name,
            "resource_type": resource_type,
            "b": b,
            "k": k,
            "points": points,
            "n_old": n_old,
            "n_new": n_new,
            "balance_old": balance_old,
            "balance_new": balance_new,
        }

        return True, response, details
