"""Unit tests for ParsingService.

Priority: GDcards (orbs)
Also covers: Gusya Cards (coins), Shmalala (money)
"""

import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bank_bot.services.parsing_service import ParsingService, PARSING_PATTERNS
from database.database import Base, User, UserResource, ConversionRate


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
def sample_user(db_session):
    """Create a test user."""
    user = User(
        telegram_id=123456,
        username="testuser",
        first_name="Test",
        balance=100,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_conversion_rates(db_session):
    """Create default conversion rates for all bots."""
    rates = [
        ConversionRate(bot_name="gusya_cards", resource_type="coins", k=Decimal("1.0")),
        ConversionRate(bot_name="gdcards", resource_type="orbs", k=Decimal("2.0")),
        ConversionRate(bot_name="shmalala", resource_type="money", k=Decimal("1.5")),
    ]
    for rate in rates:
        db_session.add(rate)
    db_session.commit()
    return rates


class TestParsingServiceGDcards:
    """GDcards parsing tests — PRIORITY."""

    def test_detect_bot_gdcards_orbs(self, db_session):
        """Detect GDcards from orbs message."""
        service = ParsingService(db_session)
        text = "🃏 НОВАЯ КАРТА 🃏\n...\n🤩 Орбы: +10"
        assert service.detect_bot(text) == "gdcards"

    def test_detect_bot_gdcards_without_emoji(self, db_session):
        """Detect GDcards without emoji."""
        service = ParsingService(db_session)
        text = "Орбы: +25"
        assert service.detect_bot(text) == "gdcards"

    def test_extract_amount_gdcards(self, db_session):
        """Extract orb amount from GDcards message."""
        service = ParsingService(db_session)
        text = "🤩 Орбы: +10"
        assert service.extract_amount(text, "gdcards") == 10

    def test_extract_amount_gdcarts_large(self, db_session):
        """Extract large orb amount."""
        service = ParsingService(db_session)
        text = "🤩 Орбы: +999"
        assert service.extract_amount(text, "gdcards") == 999

    def test_parse_and_accrue_gdcards(self, db_session, sample_user, sample_conversion_rates):
        """Full flow: parse GDcards message and accrue points."""
        service = ParsingService(db_session)
        text = "🃏 НОВАЯ КАРТА 🃏\n...\n🤩 Орбы: +10"

        success, message, details = service.parse_and_accrue(sample_user.id, text)

        assert success is True
        assert "Зачислено 20 очков" in message  # 10 * 2.0 = 20
        assert "по курсу 2.0 за орб" in message
        assert "Ваш баланс: 120 очков" in message  # 100 + 20 = 120

        # Check internal n tracking
        assert details["b"] == 10
        assert details["k"] == Decimal("2.0")
        assert details["points"] == 20
        assert details["n_old"] == 0
        assert details["n_new"] == 10
        assert details["balance_old"] == 100
        assert details["balance_new"] == 120

    def test_parse_and_accrue_gdcards_multiple(self, db_session, sample_user, sample_conversion_rates):
        """Multiple parsing accumulates n correctly."""
        service = ParsingService(db_session)
        text1 = "🤩 Орбы: +5"
        text2 = "🤩 Орбы: +15"

        success1, _, details1 = service.parse_and_accrue(sample_user.id, text1)
        assert success1 is True
        assert details1["n_new"] == 5
        assert details1["balance_new"] == 110  # 100 + 5*2 = 110

        success2, _, details2 = service.parse_and_accrue(sample_user.id, text2)
        assert success2 is True
        assert details2["n_new"] == 20  # 5 + 15
        assert details2["balance_new"] == 140  # 110 + 15*2 = 140

    def test_gdcarts_not_detected_as_other_bot(self, db_session):
        """GDcards message should not be detected as Shmalala."""
        service = ParsingService(db_session)
        text = "🤩 Орбы: +10"
        assert service.detect_bot(text) == "gdcards"
        assert service.detect_bot(text) != "shmalala"


class TestParsingServiceGusyaCards:
    """Gusya Cards parsing tests."""

    def test_detect_bot_gusya(self, db_session):
        """Detect Gusya Cards from coins message."""
        service = ParsingService(db_session)
        text = "💰 Монеты • +8 [16]"
        assert service.detect_bot(text) == "gusya_cards"

    def test_extract_amount_gusya(self, db_session):
        """Extract coin amount from Gusya message."""
        service = ParsingService(db_session)
        text = "💰 Монеты • +8 [16]"
        assert service.extract_amount(text, "gusya_cards") == 8

    def test_parse_and_accrue_gusya(self, db_session, sample_user, sample_conversion_rates):
        """Full flow: parse Gusya message and accrue points."""
        service = ParsingService(db_session)
        text = "🪄 Вы нашли карточку\n💎 Редкость • Редкая\n✨ Очки • +3,000\n💰 Монеты • +8 [16]"

        success, message, details = service.parse_and_accrue(sample_user.id, text)

        assert success is True
        assert "Зачислено 8 очков" in message  # 8 * 1.0 = 8
        assert "по курсу 1.0 за монету" in message
        assert details["b"] == 8
        assert details["points"] == 8
        assert details["balance_new"] == 108  # 100 + 8


class TestParsingServiceShmalala:
    """Shmalala parsing tests."""

    def test_detect_bot_shmalala(self, db_session):
        """Detect Shmalala from money message."""
        service = ParsingService(db_session)
        text = "Монеты: +14 (3947)💰"
        assert service.detect_bot(text) == "shmalala"

    def test_extract_amount_shmalala(self, db_session):
        """Extract money amount from Shmalala message."""
        service = ParsingService(db_session)
        text = "Монеты: +14 (3947)💰"
        assert service.extract_amount(text, "shmalala") == 14

    def test_parse_and_accrue_shmalala(self, db_session, sample_user, sample_conversion_rates):
        """Full flow: parse Shmalala message and accrue points."""
        service = ParsingService(db_session)
        text = "🎣 [Рыбалка] 🎣\n...\nМонеты: +14 (3947)💰"

        success, message, details = service.parse_and_accrue(sample_user.id, text)

        assert success is True
        assert "Зачислено 21 очков" in message  # 14 * 1.5 = 21
        assert "по курсу 1.5 за монету" in message
        assert details["b"] == 14
        assert details["points"] == 21
        assert details["balance_new"] == 121  # 100 + 21


class TestParsingServiceErrors:
    """Error handling tests."""

    def test_unrecognized_message(self, db_session, sample_user):
        """Return error for unrecognized message."""
        service = ParsingService(db_session)
        text = "Это обычное сообщение без игровых данных"

        success, message, details = service.parse_and_accrue(sample_user.id, text)

        assert success is False
        assert "Не удалось распознать данные" in message
        assert details == {}

    def test_negative_amount(self, db_session, sample_user):
        """Handle negative amount gracefully."""
        service = ParsingService(db_session)
        # Simulate negative by crafting text that won't match positive pattern
        text = "🤩 Орбы: -10"

        success, message, details = service.parse_and_accrue(sample_user.id, text)

        assert success is False
        assert "Не удалось распознать данные" in message

    def test_user_not_found(self, db_session, sample_conversion_rates):
        """Handle non-existent user."""
        service = ParsingService(db_session)
        text = "🤩 Орбы: +10"

        success, message, details = service.parse_and_accrue(99999, text)

        assert success is False
        assert "Ошибка при обработке данных" in message

    def test_default_conversion_rate_when_missing(self, db_session, sample_user):
        """Use default k=1.0 when conversion rate not in DB."""
        service = ParsingService(db_session)
        text = "🤩 Орбы: +10"

        success, message, details = service.parse_and_accrue(sample_user.id, text)

        assert success is True
        assert details["k"] == Decimal("1.0")
        assert details["points"] == 10  # 10 * 1.0 = 10


class TestParsingServicePatterns:
    """Regex pattern validation tests."""

    def test_gusya_pattern_matches(self):
        """Gusya regex matches expected format."""
        pattern = PARSING_PATTERNS["gusya_cards"]["patterns"][0]
        match = pattern.search("💰 Монеты • +8 [16]")
        assert match is not None
        assert match.group(1) == "8"

    def test_gdcards_pattern_matches(self):
        """GDcards regex matches expected format."""
        pattern = PARSING_PATTERNS["gdcards"]["patterns"][0]
        match = pattern.search("🤩 Орбы: +10")
        assert match is not None
        assert match.group(1) == "10"

    def test_shmalala_pattern_matches(self):
        """Shmalala regex matches expected format."""
        pattern = PARSING_PATTERNS["shmalala"]["patterns"][0]
        match = pattern.search("Монеты: +14 (3947)💰")
        assert match is not None
        assert match.group(1) == "14"
