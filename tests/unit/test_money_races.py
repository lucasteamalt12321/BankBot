"""BUG-05: регрессионные тесты на гонки за деньги.

Раньше баланс менялся через read-modify-write под ``with_for_update()``,
который на SQLite является no-op, поэтому параллельные начисления/списания
затирали друг друга. Теперь все изменения баланса — атомарные SQL-операции.
"""

import asyncio
import threading
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from bank_bot.repositories.balance_repository import BalanceRepository
from bank_bot.services.balance_service import BalanceService
from core.managers.shop_manager import ShopManager
from database.database import Base, ShopItem, User


def _engine(tmp_path, name):
    return create_engine(
        f"sqlite:///{tmp_path / name}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )


def test_concurrent_accruals_do_not_lose_money(tmp_path):
    """Два потока начисляют по 10 монет 25 раз — должно получиться 500."""
    engine = _engine(tmp_path, "races.db")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, telegram_id, username, balance) "
                "VALUES (1, 1, 'u', 0)"
            )
        )

    errors: list = []

    def worker():
        session = sessionmaker(bind=engine)()
        try:
            repo = BalanceRepository(session)
            for _ in range(25):
                repo.add_balance(1, 10)
                session.commit()
        except Exception as exc:  # pragma: no cover - диагностика потока
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    with engine.connect() as conn:
        balance = conn.execute(text("SELECT balance FROM users WHERE id = 1")).scalar()
    assert balance == 500


@pytest.fixture
def db(tmp_path):
    engine = _engine(tmp_path, "money.db")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=1, telegram_id=1, username="u", balance=100))
    session.add(
        ShopItem(
            id=1,
            name="sticker",
            price=60,
            item_type="sticker",
            is_active=True,
            meta_data={"duration_hours": 24},
        )
    )
    session.commit()
    yield session
    session.close()


def test_deduct_cannot_overdraw(db):
    """Условный UPDATE не даёт уйти в минус и не меняет баланс при отказе."""
    service = BalanceService(db)
    service.deduct(1, 80, "first")
    db.commit()

    with pytest.raises(ValueError, match="Insufficient balance"):
        service.deduct(1, 80, "second")

    assert db.execute(text("SELECT balance FROM users WHERE id = 1")).scalar() == 20


def test_shop_purchase_deducts_atomically(db):
    manager = ShopManager(db)
    result = asyncio.run(manager.process_purchase(1, 1))

    assert result.success is True
    assert result.new_balance == Decimal("40")
    assert db.execute(text("SELECT balance FROM users WHERE id = 1")).scalar() == 40
    assert db.execute(text("SELECT total_purchases FROM users WHERE id = 1")).scalar() == 1

    user = db.query(User).filter(User.id == 1).first()
    assert user.sticker_unlimited is True


def test_shop_purchase_insufficient_keeps_balance(db):
    """Неудачная покупка не должна списывать деньги."""
    db.add(User(id=2, telegram_id=2, username="poor", balance=10))
    db.commit()

    manager = ShopManager(db)
    result = asyncio.run(manager.process_purchase(2, 1))

    assert result.success is False
    assert result.error_code == "INSUFFICIENT_BALANCE"
    assert db.execute(text("SELECT balance FROM users WHERE id = 2")).scalar() == 10
    assert Decimal(str(result.new_balance or 0)) >= 0
