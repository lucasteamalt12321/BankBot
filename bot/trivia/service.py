# service.py
"""Trivia service for managing game progress and awarding coins."""

import structlog
from datetime import datetime
from sqlalchemy.orm import Session
from database.database import User, Transaction

logger = structlog.get_logger()


class TriviaService:
    """Service to handle core database updates for the Trivia game."""

    def __init__(self, db: Session):
        """Initialize with active database session."""
        self.db = db

    def process_correct_answer(
        self,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        coins: int,
        question_text: str,
    ) -> int:
        """Award coins to the winner and record the transaction.

        Args:
            telegram_user_id: Telegram ID of the user.
            username: Telegram username.
            first_name: User first name.
            last_name: User last name.
            coins: Coins to award.
            question_text: Question text for the transaction description.

        Returns:
            The user's new balance.
        """
        user = self.db.query(User).filter(User.telegram_id == telegram_user_id).first()
        
        if user is None:
            user = User(
                telegram_id=telegram_user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                balance=coins,
                total_earned=coins,
                last_activity=datetime.utcnow(),
            )
            self.db.add(user)
            self.db.flush()
            logger.info("Auto-registered trivia winner", telegram_id=telegram_user_id, user_id=user.id)
        else:
            user.balance += coins
            user.total_earned += coins
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            user.last_activity = datetime.utcnow()

        # Log transaction
        tx = Transaction(
            user_id=user.id,
            amount=coins,
            transaction_type="trivia_win",
            source_game="trivia",
            description=f"Брейн-Ринг: правильный ответ на вопрос «{question_text[:60]}...»",
            meta_data={"question": question_text, "prize": coins},
        )
        self.db.add(tx)
        self.db.commit()

        logger.info(
            "Trivia win recorded successfully",
            telegram_id=telegram_user_id,
            user_id=user.id,
            prize=coins,
            new_balance=user.balance,
        )
        return int(user.balance)
