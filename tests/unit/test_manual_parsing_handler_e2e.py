"""E2E tests for ParsingHandler.handle_manual_parsing against a real SQLite database.

Covers both parsing stacks end-to-end with real PTB handler objects:
- target-bot path (ParsingService + conversion_rates) for GD Cards accrual
- legacy fallback path (UnifiedParser + direct users/transactions update) for True Mafia
- idempotency (processed_messages) via real SQLiteRepository
- duplicate / unrecognized / non-reply flows
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from telegram import Message, Update, User as TelegramUser, Chat
from telegram.ext import ContextTypes

import database.database as db_module
from database.database import Base

from bot.handlers.parsing_handler import ParsingHandler


@pytest.fixture
def real_db(tmp_path):
    """Real SQLite file DB shared by raw SQLiteRepository and SQLAlchemy."""
    db_path = str(tmp_path / "parsing_e2e.db")
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    yield {"path": db_path, "engine": engine, "Session": Session}
    engine.dispose()


@pytest.fixture
def patched_db(real_db, monkeypatch):
    """Point both DB entry points at the real SQLite file."""
    Session = real_db["Session"]
    monkeypatch.setattr(db_module, "engine", real_db["engine"])
    monkeypatch.setattr(db_module, "SessionLocal", Session)
    monkeypatch.setattr("utils.admin.admin_system.SessionLocal", Session)
    return real_db


@pytest.fixture
def handler(patched_db):
    """Real ParsingHandler wired to the real SQLite file DB."""
    return ParsingHandler(
        db_path=patched_db["path"], coefficients_path="config/coefficients.json"
    )


def build_update(message_text: str, *, user_id: int = 555777, chat_type: str = "private"):
    """Build a PTB-style update mocking a user reply to a game bot message."""
    reply_date = datetime(2026, 8, 3, 12, 0, 0)
    reply_from = Mock(spec=TelegramUser)
    reply_from.id = 111
    reply_from.username = "game_bot"
    reply_from.first_name = "GameBot"
    reply_from.is_bot = True

    reply = Mock(spec=Message)
    reply.text = message_text
    reply.caption = None
    reply.date = reply_date
    reply.from_user = reply_from

    user = Mock(spec=TelegramUser)
    user.id = user_id
    user.username = "test_player"
    user.first_name = "Test"

    chat = Mock(spec=Chat)
    chat.id = 789012
    chat.type = chat_type

    message = Mock(spec=Message)
    message.reply_to_message = reply
    message.reply_text = AsyncMock()
    message.text = "парсинг"
    message.from_user = user
    message.chat = chat

    update = Mock(spec=Update)
    update.message = message
    update.effective_user = user
    update.effective_chat = chat

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = Mock()
    return update, context, reply_date


def balance_of(db, telegram_id: int):
    row = db.execute(
        text("SELECT balance FROM users WHERE telegram_id = :tid"),
        {"tid": telegram_id},
    ).mappings().first()
    return None if row is None else float(row["balance"])


def count_transactions(db, telegram_id: int):
    return db.execute(
        text(
            "SELECT COUNT(*) FROM transactions t "
            "JOIN users u ON u.id = t.user_id WHERE u.telegram_id = :tid"
        ),
        {"tid": telegram_id},
    ).scalar()


class TestHandleManualParsingE2E:
    async def test_target_bot_gdcards_accrual(self, handler, patched_db):
        """GD Cards accrual via ParsingService with canonical rate (2.5)."""
        text_ = "🃏 НОВАЯ КАРТА 🃏\nПоздравляем!\n🤩 Орбы: +10"
        update, context, _ = build_update(text_)

        await handler.handle_manual_parsing(update, context)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Зачислено 25 очков" in reply_text
        assert "(по курсу 2.5 за орб" in reply_text

        Session = patched_db["Session"]
        db = Session()
        try:
            assert balance_of(db, 555777) == 25.0
            assert count_transactions(db, 555777) == 1
        finally:
            db.close()

    async def test_legacy_truemafia_profile(self, handler, patched_db):
        """True Mafia profile via legacy UnifiedParser path (15:1)."""
        text_ = "👤 Олег\n💵 Деньги: 3000\n"
        update, context, _ = build_update(text_)

        await handler.handle_manual_parsing(update, context)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "✅ True Mafia — сообщение обработано!" in reply_text
        assert "курс 15:1" in reply_text

        Session = patched_db["Session"]
        db = Session()
        try:
            assert balance_of(db, 555777) == pytest.approx(200.0)
            assert count_transactions(db, 555777) == 1
        finally:
            db.close()

    async def test_idempotency_blocks_duplicate(self, handler, patched_db):
        """Same message + date parsed twice -> second blocked, no double accrual."""
        text_ = "🃏 НОВАЯ КАРТА 🃏\n🤩 Орбы: +10"
        update, context, _ = build_update(text_)

        await handler.handle_manual_parsing(update, context)
        await handler.handle_manual_parsing(update, context)

        Session = patched_db["Session"]
        db = Session()
        try:
            assert balance_of(db, 555777) == 25.0
            assert count_transactions(db, 555777) == 1
        finally:
            db.close()

        replies = update.message.reply_text.call_args_list
        assert len(replies) == 2
        assert "уже было обработано" in replies[1][0][0]

    async def test_unrecognized_message(self, handler, patched_db):
        """Non-game reply -> not recognized, no balance change."""
        text_ = "какой-то обычный текст без игровых паттернов"
        update, context, _ = build_update(text_)

        await handler.handle_manual_parsing(update, context)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Сообщение не распознано" in reply_text

        Session = patched_db["Session"]
        db = Session()
        try:
            assert balance_of(db, 555777) is None
        finally:
            db.close()

    async def test_no_reply_message(self, handler, patched_db):
        """No reply_to_message -> guidance message, no balance change."""
        update, context, _ = build_update("🤩 Орбы: +10")
        update.message.reply_to_message = None

        await handler.handle_manual_parsing(update, context)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "парсинг работает только по реальному reply" in reply_text

        Session = patched_db["Session"]
        db = Session()
        try:
            assert balance_of(db, 555777) is None
        finally:
            db.close()
