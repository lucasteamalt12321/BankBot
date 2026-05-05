"""Unit tests for BalanceService."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.services.balance_service import BalanceService
from core.repositories.user_repository import UserRepository
from database.database import Base, User


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def user_repository(in_memory_db):
    return UserRepository(in_memory_db)


@pytest.fixture
def balance_service(in_memory_db):
    return BalanceService(in_memory_db)


@pytest.fixture
def test_user(in_memory_db):
    user = User(id=1, telegram_id=123456, username="testuser", balance=100)
    in_memory_db.add(user)
    in_memory_db.commit()
    return user


class TestBalanceServiceInitialization:
    def test_init_creates_service(self, in_memory_db):
        service = BalanceService(in_memory_db)
        assert service is not None
        assert service._balance_repo is not None
        assert service._tx_repo is not None


class TestBalanceServiceAccrual:
    def test_accrue_adds_balance(self, balance_service, test_user, in_memory_db):
        result = balance_service.accrue(test_user.id, 50, "Test accrual")
        assert result is not None
        assert result.balance == 150

    def test_accrue_negative_amount_raises(self, balance_service, test_user):
        with pytest.raises(ValueError, match="positive"):
            balance_service.accrue(test_user.id, -10, "Test")

    def test_accrue_zero_raises(self, balance_service, test_user):
        with pytest.raises(ValueError, match="positive"):
            balance_service.accrue(test_user.id, 0, "Test")

    def test_accrue_user_not_found_returns_none(self, balance_service):
        result = balance_service.accrue(99999, 50, "Test")
        assert result is None


class TestBalanceServiceDeduction:
    def test_deduct_subtracts_balance(self, balance_service, test_user, in_memory_db):
        result = balance_service.deduct(test_user.id, 30, "Test deduction")
        assert result is not None
        assert result.balance == 70

    def test_deduct_negative_amount_raises(self, balance_service, test_user):
        with pytest.raises(ValueError, match="positive"):
            balance_service.deduct(test_user.id, -10, "Test")

    def test_deduct_insufficient_balance_raises(self, balance_service, test_user):
        with pytest.raises(ValueError, match="Insufficient balance"):
            balance_service.deduct(test_user.id, 200, "Test")

    def test_deduct_exact_balance_works(self, balance_service, test_user, in_memory_db):
        result = balance_service.deduct(test_user.id, 100, "Empty account")
        assert result is not None
        assert result.balance == 0

    def test_deduct_user_not_found_returns_none(self, balance_service):
        result = balance_service.deduct(99999, 50, "Test")
        assert result is None


class TestBalanceServiceGetBalance:
    def test_get_balance_returns_balance(self, balance_service, test_user):
        result = balance_service.get_balance(test_user.id)
        assert result == 100

    def test_get_balance_user_not_found(self, balance_service):
        result = balance_service.get_balance(99999)
        assert result is None
