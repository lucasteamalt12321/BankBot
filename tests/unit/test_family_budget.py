import hashlib
import hmac
from unittest.mock import patch

import pytest
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database.database as dbmod
import bot.web.family_budget as m
from database.database import (
    Base,
    BudgetTransaction,
    Debt,
    Family,
    FamilyMember,
    Payment,
    TransactionDetail,
)

BUDGET_TABLES = [
    Family.__table__,
    FamilyMember.__table__,
    BudgetTransaction.__table__,
    TransactionDetail.__table__,
    Debt.__table__,
    Payment.__table__,
]


@pytest.fixture
def db_env():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=BUDGET_TABLES)
    Session = sessionmaker(bind=engine)
    app = Flask(__name__)
    app.add_url_rule("/api/budget/family/status", view_func=m.api_family_status, methods=["GET"])
    app.add_url_rule("/api/budget/family/create", view_func=m.api_family_create, methods=["POST"])
    app.add_url_rule("/api/budget/family/join", view_func=m.api_family_join, methods=["POST"])
    app.add_url_rule("/api/budget/transactions", view_func=m.api_transactions_list, methods=["GET"])
    app.add_url_rule("/api/budget/transactions", view_func=m.api_transaction_create, methods=["POST"])
    app.add_url_rule("/api/budget/debts", view_func=m.api_debts_list, methods=["GET"])
    app.add_url_rule("/api/budget/debts/pay", view_func=m.api_debt_pay, methods=["POST"])
    app.add_url_rule("/api/budget/balance", view_func=m.api_balance, methods=["GET"])

    def _get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    with patch.object(dbmod, "get_db", _get_db):
        yield app, Session


def _signed_headers(uid: str | int, secret: str = "test-secret") -> dict:
    sig = hmac.new(secret.encode(), str(uid).encode(), hashlib.sha256).hexdigest()
    return {"X-User-Id": str(uid), "X-Budget-Sig": sig}


# ─── _get_user_id auth ──────────────────────────────────────────────────


def test_get_user_id_rejects_unauthenticated(db_env):
    app, _ = db_env
    with app.test_request_context("/"):
        assert m._get_user_id() == ""


def test_get_user_id_rejects_unsigned_user_id(db_env, monkeypatch):
    monkeypatch.setenv("BUDGET_API_SECRET", "test-secret")
    app, _ = db_env
    with app.test_request_context("/", headers={"X-User-Id": "123"}):
        assert m._get_user_id() == ""


def test_get_user_id_accepts_valid_signature(db_env, monkeypatch):
    monkeypatch.setenv("BUDGET_API_SECRET", "test-secret")
    app, _ = db_env
    with app.test_request_context("/", headers=_signed_headers(123)):
        assert m._get_user_id() == "123"


def test_get_user_id_rejects_forged_signature(db_env, monkeypatch):
    monkeypatch.setenv("BUDGET_API_SECRET", "test-secret")
    app, _ = db_env
    headers = _signed_headers(123, secret="other-secret")
    with app.test_request_context("/", headers=headers):
        assert m._get_user_id() == ""


def test_get_user_id_query_params(db_env, monkeypatch):
    monkeypatch.setenv("BUDGET_API_SECRET", "test-secret")
    app, _ = db_env
    sig = hmac.new(b"test-secret", b"123", hashlib.sha256).hexdigest()
    with app.test_request_context(f"/?user_id=123&sig={sig}"):
        assert m._get_user_id() == "123"


def test_budget_verify_empty_secret(db_env, monkeypatch):
    monkeypatch.delenv("BUDGET_API_SECRET", raising=False)
    app, _ = db_env
    with app.test_request_context("/", headers=_signed_headers(1, secret="x")):
        assert m._get_user_id() == ""


# ─── api_transaction_create validation ──────────────────────────────────


def test_transaction_create_validates_amount_type(db_env, monkeypatch):
    monkeypatch.setenv("BUDGET_API_SECRET", "test-secret")
    app, _ = db_env
    client = app.test_client()
    resp = client.post(
        "/api/budget/transactions",
        json={"family_id": 1, "amount": "abc", "for_whom_ids": ["1"]},
        headers=_signed_headers(1),
    )
    assert resp.status_code == 400
    assert "amount" in resp.get_json()["error"]


def test_transaction_create_rejects_nonmember_payer(db_env, monkeypatch):
    monkeypatch.setenv("BUDGET_API_SECRET", "test-secret")
    app, Session = db_env
    with Session() as s:
        fam = Family(name="Тест", admin_id="1", invite_code="123456")
        s.add(fam)
        s.flush()
        s.add(FamilyMember(family_id=fam.id, user_id="1", display_name="Аня"))
        s.commit()
        fam_id = fam.id

    client = app.test_client()
    resp = client.post(
        "/api/budget/transactions",
        json={"family_id": fam_id, "payer_id": "999", "amount": 100, "for_whom_ids": ["1"]},
        headers=_signed_headers(1),
    )
    assert resp.status_code == 403


def test_transaction_create_rejects_nonmember_for_whom(db_env, monkeypatch):
    monkeypatch.setenv("BUDGET_API_SECRET", "test-secret")
    app, Session = db_env
    with Session() as s:
        fam = Family(name="Тест", admin_id="1", invite_code="123456")
        s.add(fam)
        s.flush()
        s.add(FamilyMember(family_id=fam.id, user_id="1", display_name="Аня"))
        s.commit()
        fam_id = fam.id

    client = app.test_client()
    resp = client.post(
        "/api/budget/transactions",
        json={"family_id": fam_id, "payer_id": "1", "amount": 100, "for_whom_ids": ["1", "777"]},
        headers=_signed_headers(1),
    )
    assert resp.status_code == 403


def test_transaction_create_valid_flow(db_env, monkeypatch):
    monkeypatch.setenv("BUDGET_API_SECRET", "test-secret")
    app, Session = db_env
    with Session() as s:
        fam = Family(name="Тест", admin_id="1", invite_code="123456")
        s.add(fam)
        s.flush()
        s.add(FamilyMember(family_id=fam.id, user_id="1", display_name="Аня"))
        s.add(FamilyMember(family_id=fam.id, user_id="2", display_name="Лука"))
        s.commit()
        fam_id = fam.id

    client = app.test_client()
    resp = client.post(
        "/api/budget/transactions",
        json={"family_id": fam_id, "payer_id": "1", "amount": 100, "for_whom_ids": ["1", "2"]},
        headers=_signed_headers(1),
    )
    assert resp.status_code == 201


# ─── api_debt_pay validation ────────────────────────────────────────────


def test_debt_pay_rejects_nonmember(db_env, monkeypatch):
    monkeypatch.setenv("BUDGET_API_SECRET", "test-secret")
    app, Session = db_env
    with Session() as s:
        fam = Family(name="Тест", admin_id="1", invite_code="123456")
        s.add(fam)
        s.flush()
        s.add(FamilyMember(family_id=fam.id, user_id="1", display_name="Аня"))
        s.commit()
        fam_id = fam.id

    client = app.test_client()
    resp = client.post(
        "/api/budget/debts/pay",
        json={"family_id": fam_id, "debtor_id": "1", "creditor_id": "5", "amount": 100},
        headers=_signed_headers(1),
    )
    assert resp.status_code == 403


def test_debt_pay_rejects_paying_others_debt(db_env, monkeypatch):
    monkeypatch.setenv("BUDGET_API_SECRET", "test-secret")
    app, Session = db_env
    with Session() as s:
        fam = Family(name="Тест", admin_id="1", invite_code="123456")
        s.add(fam)
        s.flush()
        s.add(FamilyMember(family_id=fam.id, user_id="1", display_name="Аня"))
        s.add(FamilyMember(family_id=fam.id, user_id="2", display_name="Лука"))
        s.add(FamilyMember(family_id=fam.id, user_id="3", display_name="Мама"))
        s.add(Debt(family_id=fam.id, debtor_id="2", creditor_id="1", amount_left=50))
        s.commit()
        fam_id = fam.id

    client = app.test_client()
    # member "3" tries to settle member "2" debt -> 403 (not your debt)
    resp = client.post(
        "/api/budget/debts/pay",
        json={"family_id": fam_id, "debtor_id": "2", "creditor_id": "1", "amount": 50},
        headers=_signed_headers(3),
    )
    assert resp.status_code == 403
    assert "свои" in resp.get_json()["error"]


def test_debt_pay_own_debt_succeeds(db_env, monkeypatch):
    monkeypatch.setenv("BUDGET_API_SECRET", "test-secret")
    app, Session = db_env
    with Session() as s:
        fam = Family(name="Тест", admin_id="1", invite_code="123456")
        s.add(fam)
        s.flush()
        s.add(FamilyMember(family_id=fam.id, user_id="1", display_name="Аня"))
        s.add(FamilyMember(family_id=fam.id, user_id="2", display_name="Лука"))
        s.add(Debt(family_id=fam.id, debtor_id="2", creditor_id="1", amount_left=50))
        s.commit()
        fam_id = fam.id

    client = app.test_client()
    resp = client.post(
        "/api/budget/debts/pay",
        json={"family_id": fam_id, "debtor_id": "2", "creditor_id": "1", "amount": 50},
        headers=_signed_headers(2),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "paid"
    assert all(d["amount_left"] == 0 for d in body["debts"])