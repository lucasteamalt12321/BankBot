"""Unit tests for the Trivia Game (Брейн-Ринг по Канону Олеговируса)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bot.trivia.questions import generate_trivia_question
from bot.trivia.service import TriviaService
from database.database import Base, User, Transaction


@pytest.fixture
def db_session():
    """Create in-memory SQLite session for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_user(db_session):
    """Create a sample user in DB."""
    user = User(
        telegram_id=999111,
        username="trivia_master",
        first_name="Trivia",
        last_name="Hero",
        balance=50,
    )
    db_session.add(user)
    db_session.commit()
    return user


class TestTriviaQuestions:
    """Test trivia question pool validation and dynamic generation."""

    def test_question_generator(self):
        """Verify the dynamic generator produces correct structure and distractors."""
        for _ in range(50):  # Run multiple times to verify randomness and correctness
            q = generate_trivia_question()
            assert "id" in q
            assert "text" in q
            assert "options" in q
            assert "correct_index" in q
            assert "explanation" in q
            assert len(q["options"]) == 4
            assert q["correct_text"] in q["options"]
            assert q["options"][q["correct_index"]] == q["correct_text"]


class TestTriviaService:
    """Test TriviaService functionality."""

    def test_award_coins_to_existing_user(self, db_session, test_user):
        """Verify that TriviaService correctly awards coins to an existing user."""
        service = TriviaService(db_session)
        new_balance = service.process_correct_answer(
            telegram_user_id=test_user.telegram_id,
            username="new_nick",
            first_name="Trivia",
            last_name="Hero",
            coins=25,
            question_text="Что такое СГД?",
        )

        assert new_balance == 75
        
        # Verify user update in DB
        db_user = db_session.query(User).filter(User.telegram_id == test_user.telegram_id).first()
        assert db_user.balance == 75
        assert db_user.total_earned == 25
        assert db_user.username == "new_nick"

        # Verify transaction log
        tx = db_session.query(Transaction).filter(Transaction.user_id == db_user.id).first()
        assert tx is not None
        assert tx.amount == 25
        assert tx.transaction_type == "trivia_win"
        assert tx.source_game == "trivia"

    def test_award_coins_to_new_user(self, db_session):
        """Verify that TriviaService automatically registers a new user if not present."""
        service = TriviaService(db_session)
        new_balance = service.process_correct_answer(
            telegram_user_id=888222,
            username="new_player",
            first_name="Alex",
            last_name="Smith",
            coins=25,
            question_text="Что означает eight-nine?",
        )

        assert new_balance == 25

        db_user = db_session.query(User).filter(User.telegram_id == 888222).first()
        assert db_user is not None
        assert db_user.balance == 25
        assert db_user.total_earned == 25
        assert db_user.username == "new_player"

        tx = db_session.query(Transaction).filter(Transaction.user_id == db_user.id).first()
        assert tx is not None
        assert tx.amount == 25
        assert tx.transaction_type == "trivia_win"
