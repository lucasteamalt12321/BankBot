"""Family Budget API — backend logic for the Family Budget web app."""

from __future__ import annotations

import json
import random
import string
from datetime import datetime

from flask import Response, jsonify, request


def _generate_invite_code() -> str:
    """Generate a unique 6-character invite code."""
    return ''.join(random.choices(string.digits, k=6))


def _get_user_id() -> str:
    """Extract user_id from request args (Telegram user_id passed as query param)."""
    uid = request.args.get("user_id", "")
    if not uid:
        uid = request.headers.get("X-User-Id", "")
    return uid


def api_family_status():
    """GET /api/budget/family/status — returns family info for the current user."""
    from database.database import Family, FamilyMember, get_db

    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "user_id required"}), 401

    db = next(get_db())
    try:
        member = db.query(FamilyMember).filter(FamilyMember.user_id == user_id).first()
        if not member:
            return jsonify({"family": None})

        family = db.query(Family).filter(Family.id == member.family_id).first()
        if not family:
            return jsonify({"family": None})

        members = (
            db.query(FamilyMember)
            .filter(FamilyMember.family_id == family.id)
            .all()
        )
        return jsonify({
            "family": {
                "id": family.id,
                "name": family.name,
                "admin_id": family.admin_id,
                "invite_code": family.invite_code,
                "created_at": family.created_at.isoformat() if family.created_at else None,
                "members": [
                    {
                        "user_id": m.user_id,
                        "display_name": m.display_name,
                        "joined_at": m.joined_at.isoformat() if m.joined_at else None,
                    }
                    for m in members
                ],
            }
        })
    finally:
        db.close()


def api_family_create():
    """POST /api/budget/family/create — create a new family."""
    from database.database import Family, FamilyMember, get_db

    data = request.get_json(silent=True) or {}
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "user_id required"}), 401

    name = data.get("name", "").strip()
    display_name = data.get("display_name", "").strip() or user_id
    if not name:
        return jsonify({"error": "family name required"}), 400

    db = next(get_db())
    try:
        existing = db.query(FamilyMember).filter(FamilyMember.user_id == user_id).first()
        if existing:
            return jsonify({"error": "already in a family"}), 400

        invite_code = _generate_invite_code()
        while db.query(Family).filter(Family.invite_code == invite_code).first():
            invite_code = _generate_invite_code()

        family = Family(name=name, admin_id=user_id, invite_code=invite_code)
        db.add(family)
        db.flush()

        member = FamilyMember(family_id=family.id, user_id=user_id, display_name=display_name)
        db.add(member)
        db.commit()

        return jsonify({
            "family": {
                "id": family.id,
                "name": family.name,
                "admin_id": family.admin_id,
                "invite_code": family.invite_code,
                "members": [{"user_id": member.user_id, "display_name": member.display_name}],
            }
        }), 201
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def api_family_join():
    """POST /api/budget/family/join — join a family by invite code."""
    from database.database import Family, FamilyMember, get_db

    data = request.get_json(silent=True) or {}
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "user_id required"}), 401

    code = data.get("code", "").strip()
    display_name = data.get("display_name", "").strip() or user_id
    if not code:
        return jsonify({"error": "invite code required"}), 400

    db = next(get_db())
    try:
        existing = db.query(FamilyMember).filter(FamilyMember.user_id == user_id).first()
        if existing:
            return jsonify({"error": "already in a family"}), 400

        family = db.query(Family).filter(Family.invite_code == code).first()
        if not family:
            return jsonify({"error": "invalid invite code"}), 404

        member = FamilyMember(family_id=family.id, user_id=user_id, display_name=display_name)
        db.add(member)
        db.commit()

        return jsonify({
            "family": {
                "id": family.id,
                "name": family.name,
                "admin_id": family.admin_id,
                "invite_code": family.invite_code,
            }
        }), 200
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def api_transactions_list():
    """GET /api/budget/transactions — list family transactions."""
    from database.database import BudgetTransaction, FamilyMember, get_db

    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "user_id required"}), 401

    family_id = request.args.get("family_id", type=int)
    if not family_id:
        return jsonify({"error": "family_id required"}), 400

    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 200))
    except ValueError:
        limit = 50

    db = next(get_db())
    try:
        member = (
            db.query(FamilyMember)
            .filter(FamilyMember.user_id == user_id, FamilyMember.family_id == family_id)
            .first()
        )
        if not member:
            return jsonify({"error": "not a member of this family"}), 403

        txns = (
            db.query(BudgetTransaction)
            .filter(BudgetTransaction.family_id == family_id)
            .order_by(BudgetTransaction.created_at.desc())
            .limit(limit)
            .all()
        )

        result = []
        for t in txns:
            details = [
                {"for_whom_id": d.for_whom_id, "share": d.share}
                for d in t.details
            ]
            result.append({
                "id": t.id,
                "payer_id": t.payer_id,
                "amount": t.amount,
                "category": t.category,
                "description": t.description,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "details": details,
            })

        return jsonify({"transactions": result})
    finally:
        db.close()


def api_transaction_create():
    """POST /api/budget/transactions — add a new expense and create debts."""
    from database.database import BudgetTransaction, Debt, FamilyMember, TransactionDetail, get_db

    data = request.get_json(silent=True) or {}
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "user_id required"}), 401

    family_id = data.get("family_id")
    payer_id = data.get("payer_id", user_id)
    amount = data.get("amount", type=int)
    category = data.get("category", "Другое")
    description = data.get("description", "")
    for_whom_ids = data.get("for_whom_ids", [])

    if not family_id:
        return jsonify({"error": "family_id required"}), 400
    if not amount or amount <= 0:
        return jsonify({"error": "amount must be positive"}), 400
    if not for_whom_ids:
        return jsonify({"error": "for_whom_ids required"}), 400

    db = next(get_db())
    try:
        member = (
            db.query(FamilyMember)
            .filter(FamilyMember.user_id == user_id, FamilyMember.family_id == family_id)
            .first()
        )
        if not member:
            return jsonify({"error": "not a member"}), 403

        txn = BudgetTransaction(
            family_id=family_id,
            payer_id=payer_id,
            amount=amount,
            category=category,
            description=description,
        )
        db.add(txn)
        db.flush()

        share = amount // len(for_whom_ids)
        remainder = amount % len(for_whom_ids)

        for i, fw_id in enumerate(for_whom_ids):
            actual_share = share + (1 if i < remainder else 0)
            detail = TransactionDetail(
                transaction_id=txn.id,
                for_whom_id=fw_id,
                share=actual_share,
            )
            db.add(detail)

            if fw_id != payer_id:
                debt = Debt(
                    family_id=family_id,
                    debtor_id=fw_id,
                    creditor_id=payer_id,
                    amount_left=actual_share,
                )
                db.add(debt)

        db.commit()
        return jsonify({"id": txn.id, "status": "created"}), 201
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def api_transaction_delete(transaction_id: int):
    """DELETE /api/budget/transactions/<id> — delete a transaction and reverse debts."""
    from database.database import BudgetTransaction, Debt, Family, FamilyMember, get_db

    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "user_id required"}), 401

    db = next(get_db())
    try:
        txn = db.query(BudgetTransaction).filter(BudgetTransaction.id == transaction_id).first()
        if not txn:
            return jsonify({"error": "transaction not found"}), 404

        member = db.query(FamilyMember).filter(
            FamilyMember.user_id == user_id, FamilyMember.family_id == txn.family_id
        ).first()
        if not member:
            return jsonify({"error": "not a member"}), 403

        if user_id != txn.payer_id:
            fam = db.query(Family).filter(Family.id == txn.family_id).first()
            if not fam or fam.admin_id != user_id:
                return jsonify({"error": "only author or admin can delete"}), 403

        # Reverse debts created by this transaction
        for detail in txn.details:
            if detail.for_whom_id != txn.payer_id:
                existing_debts = (
                    db.query(Debt)
                    .filter(
                        Debt.family_id == txn.family_id,
                        Debt.debtor_id == detail.for_whom_id,
                        Debt.creditor_id == txn.payer_id,
                        Debt.amount_left > 0,
                    )
                    .order_by(Debt.created_at.desc())
                    .all()
                )
                for d in existing_debts:
                    if d.amount_left >= detail.share:
                        d.amount_left -= detail.share
                        detail.share = 0
                        break
                    else:
                        detail.share -= d.amount_left
                        d.amount_left = 0

                # Remove zeroed debts
                db.query(Debt).filter(Debt.amount_left <= 0).delete()

        db.delete(txn)
        db.commit()
        return jsonify({"status": "deleted"})
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def api_debts_list():
    """GET /api/budget/debts — list active debts for a family."""
    from database.database import Debt, FamilyMember, get_db

    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "user_id required"}), 401

    family_id = request.args.get("family_id", type=int)
    if not family_id:
        return jsonify({"error": "family_id required"}), 400

    db = next(get_db())
    try:
        member = (
            db.query(FamilyMember)
            .filter(FamilyMember.user_id == user_id, FamilyMember.family_id == family_id)
            .first()
        )
        if not member:
            return jsonify({"error": "not a member"}), 403

        debts = (
            db.query(Debt)
            .filter(Debt.family_id == family_id, Debt.amount_left > 0)
            .order_by(Debt.created_at.asc())
            .all()
        )

        return jsonify({
            "debts": [
                {
                    "id": d.id,
                    "debtor_id": d.debtor_id,
                    "creditor_id": d.creditor_id,
                    "amount_left": d.amount_left,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in debts
            ]
        })
    finally:
        db.close()


def api_debt_pay():
    """POST /api/budget/debts/pay — cascade debt repayment."""
    from database.database import Debt, FamilyMember, Payment, get_db

    data = request.get_json(silent=True) or {}
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "user_id required"}), 401

    family_id = data.get("family_id")
    debtor_id = data.get("debtor_id")
    creditor_id = data.get("creditor_id")
    amount = data.get("amount", type=int)

    if not all([family_id, debtor_id, creditor_id, amount]):
        return jsonify({"error": "family_id, debtor_id, creditor_id, amount required"}), 400
    if amount <= 0:
        return jsonify({"error": "amount must be positive"}), 400

    db = next(get_db())
    try:
        member = (
            db.query(FamilyMember)
            .filter(FamilyMember.user_id == user_id, FamilyMember.family_id == family_id)
            .first()
        )
        if not member:
            return jsonify({"error": "not a member"}), 403

        remaining = amount

        # Step 1: find all active debts debtor -> creditor, oldest first
        debts = (
            db.query(Debt)
            .filter(
                Debt.family_id == family_id,
                Debt.debtor_id == debtor_id,
                Debt.creditor_id == creditor_id,
                Debt.amount_left > 0,
            )
            .order_by(Debt.created_at.asc())
            .all()
        )

        for debt in debts:
            if remaining <= 0:
                break
            if debt.amount_left >= remaining:
                debt.amount_left -= remaining
                remaining = 0
            else:
                remaining -= debt.amount_left
                debt.amount_left = 0

        # Remove zeroed debts
        db.query(Debt).filter(Debt.amount_left <= 0).delete()

        # Step 2: if overpayment remains after clearing all debts to this creditor
        if remaining > 0:
            # Check if debtor has other active debts to other creditors
            other_debts = (
                db.query(Debt)
                .filter(
                    Debt.family_id == family_id,
                    Debt.debtor_id == debtor_id,
                    Debt.creditor_id != creditor_id,
                    Debt.amount_left > 0,
                )
                .order_by(Debt.created_at.asc())
                .all()
            )

            for debt in other_debts:
                if remaining <= 0:
                    break
                if debt.amount_left >= remaining:
                    debt.amount_left -= remaining
                    remaining = 0
                else:
                    remaining -= debt.amount_left
                    debt.amount_left = 0

            # Remove zeroed debts
            db.query(Debt).filter(Debt.amount_left <= 0).delete()

        # Step 3: if still remaining — creditor now owes debtor (role swap)
        if remaining > 0:
            existing_reverse = (
                db.query(Debt)
                .filter(
                    Debt.family_id == family_id,
                    Debt.debtor_id == creditor_id,
                    Debt.creditor_id == debtor_id,
                    Debt.amount_left > 0,
                )
                .first()
            )
            if existing_reverse:
                existing_reverse.amount_left += remaining
            else:
                rev_debt = Debt(
                    family_id=family_id,
                    debtor_id=creditor_id,
                    creditor_id=debtor_id,
                    amount_left=remaining,
                )
                db.add(rev_debt)
            remaining = 0

        # Record payment
        pay = Payment(
            family_id=family_id,
            debtor_id=debtor_id,
            creditor_id=creditor_id,
            amount=amount,
        )
        db.add(pay)
        db.commit()

        # Return updated debt list
        updated_debts = (
            db.query(Debt)
            .filter(Debt.family_id == family_id, Debt.amount_left > 0)
            .order_by(Debt.created_at.asc())
            .all()
        )

        return jsonify({
            "status": "paid",
            "debts": [
                {
                    "id": d.id,
                    "debtor_id": d.debtor_id,
                    "creditor_id": d.creditor_id,
                    "amount_left": d.amount_left,
                }
                for d in updated_debts
            ]
        })
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def api_balance():
    """GET /api/budget/balance — net balance for each member."""
    from database.database import Debt, FamilyMember, get_db

    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "user_id required"}), 401

    family_id = request.args.get("family_id", type=int)
    if not family_id:
        return jsonify({"error": "family_id required"}), 400

    db = next(get_db())
    try:
        member = (
            db.query(FamilyMember)
            .filter(FamilyMember.user_id == user_id, FamilyMember.family_id == family_id)
            .first()
        )
        if not member:
            return jsonify({"error": "not a member"}), 403

        members = (
            db.query(FamilyMember)
            .filter(FamilyMember.family_id == family_id)
            .all()
        )
        member_ids = [m.user_id for m in members]

        # Calculate net balance: what others owe you - what you owe others
        balances = {uid: 0 for uid in member_ids}

        debts = (
            db.query(Debt)
            .filter(Debt.family_id == family_id, Debt.amount_left > 0)
            .all()
        )
        for d in debts:
            if d.debtor_id in balances:
                balances[d.debtor_id] -= d.amount_left
            if d.creditor_id in balances:
                balances[d.creditor_id] += d.amount_left

        return jsonify({
            "balances": [
                {"user_id": uid, "net": balances.get(uid, 0)}
                for uid in member_ids
            ]
        })
    finally:
        db.close()


FAMILY_BUDGET_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Семейный бюджет</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; background: #f2f2f7; padding: 16px; min-height: 100vh; }
        .container { max-width: 600px; margin: 0 auto; }
        .card { background: white; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
        h1 { font-size: 24px; text-align: center; color: #1c1c1e; margin-bottom: 8px; }
        h2 { font-size: 18px; color: #1c1c1e; margin-bottom: 12px; }
        .subtitle { text-align: center; color: #8e8e93; font-size: 14px; margin-bottom: 20px; }
        .btn { display: inline-flex; align-items: center; justify-content: center; width: 100%; padding: 14px; font-size: 16px; font-weight: 600; border: none; border-radius: 10px; cursor: pointer; transition: all 0.2s; margin-bottom: 8px; }
        .btn:active { opacity: 0.7; }
        .btn-primary { background: #007aff; color: white; }
        .btn-secondary { background: #e5e5ea; color: #1c1c1e; }
        .btn-danger { background: #ff3b30; color: white; }
        .btn-success { background: #34c759; color: white; }
        .btn-small { padding: 10px 16px; width: auto; font-size: 14px; display: inline-block; }
        .input { width: 100%; padding: 12px; font-size: 16px; border: 2px solid #e5e5ea; border-radius: 10px; margin-bottom: 12px; outline: none; transition: border-color 0.2s; }
        .input:focus { border-color: #007aff; }
        .select { width: 100%; padding: 12px; font-size: 16px; border: 2px solid #e5e5ea; border-radius: 10px; margin-bottom: 12px; background: white; }
        .label { font-size: 14px; font-weight: 600; color: #3a3a3c; margin-bottom: 6px; display: block; }
        .row { display: flex; gap: 12px; align-items: center; padding: 12px 0; border-bottom: 1px solid #e5e5ea; }
        .row:last-child { border-bottom: none; }
        .debt-info { flex: 1; }
        .debt-text { font-size: 16px; color: #1c1c1e; }
        .debt-amount { font-size: 14px; color: #8e8e93; }
        .positive { color: #34c759; }
        .negative { color: #ff3b30; }
        .fab { position: fixed; bottom: 24px; right: 24px; width: 56px; height: 56px; border-radius: 28px; background: #007aff; color: white; font-size: 28px; border: none; cursor: pointer; box-shadow: 0 4px 12px rgba(0,122,255,0.4); display: flex; align-items: center; justify-content: center; }
        .fab:active { opacity: 0.7; }
        .screen { display: none; }
        .screen.active { display: block; }
        .hidden { display: none !important; }
        .toast { position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%); background: #1c1c1e; color: white; padding: 12px 24px; border-radius: 8px; font-size: 14px; z-index: 100; animation: fadeIn 0.3s; }
        @keyframes fadeIn { from { opacity: 0; transform: translateX(-50%) translateY(20px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }
        .balance-bar { display: flex; justify-content: space-around; margin: 16px 0; flex-wrap: wrap; gap: 8px; }
        .balance-item { text-align: center; flex: 1; min-width: 80px; padding: 8px; background: #f8f8fa; border-radius: 8px; }
        .balance-item .name { font-size: 12px; color: #8e8e93; }
        .balance-item .amount { font-size: 18px; font-weight: 700; }
        .chip { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 500; background: #e5e5ea; margin: 2px; }
        .chip-active { background: #007aff; color: white; }
        .header-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
        .header-bar h1 { margin: 0; }
        .back-btn { font-size: 28px; background: none; border: none; cursor: pointer; padding: 4px; }
        .filter-row { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
        .filter-row .chip { cursor: pointer; }
        @media print { .fab, .btn, .back-btn, .filter-row { display: none !important; } }
    </style>
</head>
<body>
    <div class="container">
        <div id="screen-auth" class="screen active">
            <div class="card">
                <h1>💰 Семейный бюджет</h1>
                <p class="subtitle">Учёт семейных трат и долгов</p>
                <button class="btn btn-primary" onclick="showCreateFamily()">👨‍👩‍👧‍👦 Создать семью</button>
                <button class="btn btn-secondary" onclick="showJoinFamily()">🔑 Присоединиться по коду</button>
            </div>
        </div>

        <div id="screen-create-family" class="screen">
            <div class="card">
                <div class="header-bar">
                    <button class="back-btn" onclick="showAuth()">←</button>
                    <h1>Создать семью</h1>
                </div>
                <label class="label">Название семьи</label>
                <input class="input" id="family-name" placeholder="Например, Семья Петровых">
                <label class="label">Ваше имя</label>
                <input class="input" id="create-display-name" placeholder="Например, Папа">
                <button class="btn btn-primary" onclick="createFamily()">Создать</button>
            </div>
        </div>

        <div id="screen-join-family" class="screen">
            <div class="card">
                <div class="header-bar">
                    <button class="back-btn" onclick="showAuth()">←</button>
                    <h1>Присоединиться</h1>
                </div>
                <label class="label">Код приглашения</label>
                <input class="input" id="invite-code" placeholder="6 цифр" maxlength="6" inputmode="numeric">
                <label class="label">Ваше имя</label>
                <input class="input" id="join-display-name" placeholder="Например, Мама">
                <button class="btn btn-primary" onclick="joinFamily()">Присоединиться</button>
            </div>
        </div>

        <div id="screen-dashboard" class="screen">
            <div class="card">
                <div class="header-bar">
                    <h1 id="dash-family-name">🏠 Семья</h1>
                    <div style="flex:1;"></div>
                    <button class="btn btn-small btn-secondary" onclick="logout()">Выйти</button>
                </div>
                <p class="subtitle" id="dash-invite-code">Код: </p>
                <div id="balance-bar" class="balance-bar"></div>
            </div>

            <div class="card">
                <h2>📋 Долги</h2>
                <div id="debt-list"></div>
                <div id="debt-empty" class="hidden" style="text-align:center;padding:20px;color:#8e8e93;">Нет активных долгов ✨</div>
            </div>

            <div class="card">
                <h2>👥 Участники</h2>
                <div id="member-list"></div>
            </div>

            <button class="fab" onclick="showAddExpense()">+</button>
        </div>

        <div id="screen-add-expense" class="screen">
            <div class="card">
                <div class="header-bar">
                    <button class="back-btn" onclick="showDashboard()">←</button>
                    <h1>➕ Новая трата</h1>
                </div>
                <label class="label">Кто заплатил</label>
                <select class="select" id="expense-payer"></select>
                <label class="label">За кого (можно выбрать несколько)</label>
                <div id="expense-for-whom"></div>
                <label class="label">Сумма (₽)</label>
                <input class="input" id="expense-amount" type="number" min="1" placeholder="250">
                <label class="label">Категория</label>
                <select class="select" id="expense-category">
                    <option>Еда</option><option>Транспорт</option><option>Хозяйство</option><option>Развлечения</option><option>Другое</option>
                </select>
                <label class="label">Описание (необязательно)</label>
                <input class="input" id="expense-description" placeholder="Что купили?">
                <button class="btn btn-success" onclick="createExpense()">💾 Сохранить</button>
            </div>
        </div>

        <div id="screen-pay-debt" class="screen">
            <div class="card">
                <div class="header-bar">
                    <button class="back-btn" onclick="showDashboard()">←</button>
                    <h1>💳 Погасить долг</h1>
                </div>
                <label class="label">Кто отдаёт</label>
                <div id="pay-debtor-display" style="font-size:18px;font-weight:600;margin-bottom:12px;"></div>
                <label class="label">Кому</label>
                <div id="pay-creditor-display" style="font-size:18px;font-weight:600;margin-bottom:12px;"></div>
                <label class="label">Сумма (₽)</label>
                <input class="input" id="pay-amount" type="number" min="1" placeholder="Сумма погашения">
                <button class="btn btn-success" onclick="payDebt()">💸 Погасить</button>
            </div>
        </div>

        <div id="screen-history" class="screen">
            <div class="card">
                <div class="header-bar">
                    <button class="back-btn" onclick="showDashboard()">←</button>
                    <h1>📜 История</h1>
                </div>
                <div id="history-list"></div>
            </div>
        </div>
    </div>

    <script>
        const BASE = '/api/budget';
        let USER_ID = new URLSearchParams(window.location.search).get('user_id') || '';
        let STATE = { family: null, debts: [], members: [] };

        async function api(method, path, body) {
            const opts = { method, headers: { 'Content-Type': 'application/json', 'X-User-Id': USER_ID } };
            if (body) opts.body = JSON.stringify(body);
            const res = await fetch(BASE + path, opts);
            return res.json();
        }

        async function get(path) { return api('GET', path); }
        async function post(path, data) { return api('POST', path, data); }
        async function del(path) { return api('DELETE', path); }

        function showToast(msg) {
            const t = document.createElement('div');
            t.className = 'toast';
            t.textContent = msg;
            document.body.appendChild(t);
            setTimeout(() => t.remove(), 2500);
        }

        function showScreen(id) {
            document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
            document.getElementById(id).classList.add('active');
        }

        function showAuth() { showScreen('screen-auth'); }
        function showCreateFamily() { showScreen('screen-create-family'); }
        function showJoinFamily() { showScreen('screen-join-family'); }

        function logout() {
            USER_ID = '';
            STATE = { family: null, debts: [], members: [] };
            showAuth();
        }

        async function createFamily() {
            const name = document.getElementById('family-name').value.trim();
            const displayName = document.getElementById('create-display-name').value.trim() || 'Участник';
            if (!name) { showToast('Введите название семьи'); return; }
            const res = await post('/family/create', { name, display_name: displayName });
            if (res.error) { showToast(res.error); return; }
            STATE.family = res.family;
            showToast('Семья создана! Код: ' + res.family.invite_code);
            await loadDashboard();
        }

        async function joinFamily() {
            const code = document.getElementById('invite-code').value.trim();
            const displayName = document.getElementById('join-display-name').value.trim() || 'Участник';
            if (!code) { showToast('Введите код приглашения'); return; }
            const res = await post('/family/join', { code, display_name: displayName });
            if (res.error) { showToast(res.error); return; }
            STATE.family = res.family;
            showToast('Вы присоединились к семье!');
            await loadDashboard();
        }

          async function loadDashboard() {
              if (!USER_ID) { showToast('Необходима авторизация'); showAuth(); return; }
              let status;
              try {
                  status = await get('/family/status?user_id=' + USER_ID);
              } catch(e) {
                  console.error('Failed to load family status', e);
                  showAuth();
                  return;
              }
              if (!status.family) { showAuth(); return; }
            STATE.family = status.family;

            document.getElementById('dash-family-name').textContent = '🏠 ' + status.family.name;
            document.getElementById('dash-invite-code').textContent = 'Код приглашения: ' + status.family.invite_code;

            STATE.members = status.family.members || [];
            renderMembers();

            const debtsRes = await get('/debts?family_id=' + status.family.id + '&user_id=' + USER_ID);
            STATE.debts = debtsRes.debts || [];
            renderDebts();

            const balanceRes = await get('/balance?family_id=' + status.family.id + '&user_id=' + USER_ID);
            renderBalances(balanceRes.balances || []);

            showScreen('screen-dashboard');
        }

        function renderMembers() {
            const el = document.getElementById('member-list');
            el.innerHTML = STATE.members.map(m =>
                '<div class="row"><span class="debt-text">' + esc(m.display_name) + '</span></div>'
            ).join('');
        }

        function renderDebts() {
            const el = document.getElementById('debt-list');
            const empty = document.getElementById('debt-empty');
            if (!STATE.debts.length) {
                el.innerHTML = '';
                empty.classList.remove('hidden');
                return;
            }
            empty.classList.add('hidden');
            el.innerHTML = STATE.debts.map(d => {
                const debtorName = getUserName(d.debtor_id);
                const creditorName = getUserName(d.creditor_id);
                return '<div class="row">' +
                    '<div class="debt-info"><div class="debt-text">' + esc(debtorName) + ' → ' + esc(creditorName) + '</div>' +
                    '<div class="debt-amount">' + d.amount_left + ' ₽</div></div>' +
                    '<button class="btn btn-small btn-primary" onclick="showPayDebt(\'' + esc(d.debtor_id) + '\',\'' + esc(d.creditor_id) + '\',' + d.amount_left + ')">Погасить</button>' +
                    '</div>';
            }).join('');
        }

        function renderBalances(balances) {
            const el = document.getElementById('balance-bar');
            el.innerHTML = balances.map(b => {
                const name = getUserName(b.user_id);
                const cls = b.net >= 0 ? 'positive' : 'negative';
                const sign = b.net >= 0 ? '+' : '';
                return '<div class="balance-item"><div class="name">' + esc(name) + '</div>' +
                    '<div class="amount ' + cls + '">' + sign + b.net + '</div></div>';
            }).join('');
        }

        function getUserName(userId) {
            const m = STATE.members.find(m => m.user_id === userId);
            return m ? m.display_name : userId;
        }

        function esc(s) {
            const d = document.createElement('div');
            d.textContent = s;
            return d.innerHTML;
        }

        async function showAddExpense() {
            const payerEl = document.getElementById('expense-payer');
            const forWhomEl = document.getElementById('expense-for-whom');
            payerEl.innerHTML = STATE.members.map(m =>
                '<option value="' + esc(m.user_id) + '">' + esc(m.display_name) + '</option>'
            ).join('');
            forWhomEl.innerHTML = STATE.members.map(m =>
                '<label style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">' +
                '<input type="checkbox" value="' + esc(m.user_id) + '">' + esc(m.display_name) + '</label>'
            ).join('');
            document.getElementById('expense-amount').value = '';
            document.getElementById('expense-description').value = '';
            showScreen('screen-add-expense');
        }

        async function createExpense() {
            const payerId = document.getElementById('expense-payer').value;
            const checkboxes = document.querySelectorAll('#expense-for-whom input[type=checkbox]:checked');
            const forWhomIds = Array.from(checkboxes).map(c => c.value);
            const amount = parseInt(document.getElementById('expense-amount').value);
            const category = document.getElementById('expense-category').value;
            const description = document.getElementById('expense-description').value.trim();

            if (!forWhomIds.length) { showToast('Выберите, за кого заплатили'); return; }
            if (!amount || amount <= 0) { showToast('Введите корректную сумму'); return; }

            const res = await post('/transactions', {
                family_id: STATE.family.id,
                payer_id: payerId,
                amount,
                category,
                description,
                for_whom_ids: forWhomIds
            });
            if (res.error) { showToast(res.error); return; }
            showToast('Трата добавлена!');
            await loadDashboard();
        }

        let _payData = null;

        function showPayDebt(debtorId, creditorId, amountLeft) {
            _payData = { debtor_id: debtorId, creditor_id: creditorId };
            document.getElementById('pay-debtor-display').textContent = '👤 ' + getUserName(debtorId);
            document.getElementById('pay-creditor-display').textContent = '👤 ' + getUserName(creditorId);
            document.getElementById('pay-amount').value = amountLeft;
            document.getElementById('pay-amount').max = amountLeft;
            showScreen('screen-pay-debt');
        }

        async function payDebt() {
            const amount = parseInt(document.getElementById('pay-amount').value);
            if (!amount || amount <= 0) { showToast('Введите корректную сумму'); return; }
            const res = await post('/debts/pay', {
                family_id: STATE.family.id,
                debtor_id: _payData.debtor_id,
                creditor_id: _payData.creditor_id,
                amount
            });
            if (res.error) { showToast(res.error); return; }
            showToast('Долг погашен!');
            await loadDashboard();
        }

        // Init
        if (USER_ID) {
            loadDashboard();
        }
    </script>
</body>
</html>"""


def family_budget_page():
    """GET /family_budget — serve the SPA."""
    return Response(FAMILY_BUDGET_HTML, mimetype="text/html")
