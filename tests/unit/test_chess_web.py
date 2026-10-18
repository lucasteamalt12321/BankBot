"""Unit tests for the chess web endpoints (CH-TEST).

Covers the previously untested web surface of the Chess Module:

* ``POST /api/chess/puzzle`` — 1 puzzle/24h cooldown;
* ``POST /api/chess/puzzle/check`` — +5 coins and history log only for the
  logged-in owner of a fresh pending puzzle;
* ``GET /api/chess/stats`` — link state, coin balance and recent history.

Anonymous gating of these endpoints is covered separately in
``tests/unit/test_freemium_gates.py``.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

USER = {"id": 42, "login": "tester"}


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE chess_accounts (
                user_id INTEGER PRIMARY KEY,
                lichess_username TEXT NOT NULL,
                linked_at TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE user_coins (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 0,
                last_puzzle_at TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE chess_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                lichess_username TEXT,
                puzzle_id TEXT,
                puzzle_rating INTEGER,
                puzzle_themes TEXT
            )
        """))
    return engine


def _uid() -> int:
    from api.index import _web_user_id

    return _web_user_id("u42")


def _auth_patches(engine, user=USER):
    return (
        patch("api.index.get_db_engine", return_value=engine),
        patch("api.index._get_session_user", return_value=user),
        patch("api.index._auth_token_from_request", return_value="tok"),
    )


def _pending(uid, solution=("e2e4", "e7e5"), age_seconds=0.0, logged_uid=None, web=True):
    return {
        "puzzle_id": "abc123",
        "solution": list(solution),
        "rating": 1500,
        "themes": "middlegame",
        "username": "tester",
        "initial_ply": 0,
        "web": web,
        "logged_uid": uid if logged_uid is None else logged_uid,
        "created_at": time.time() - age_seconds,
    }


# --- /api/chess/puzzle/check: rewards -------------------------------------


def test_puzzle_check_correct_move_awards_five_coins_and_logs():
    from api.index import app

    engine = _make_engine()
    uid = _uid()
    db, sess, tok = _auth_patches(engine)

    with patch.dict("api.index._PENDING_PUZZLES", {uid: _pending(uid)}, clear=True), \
            db, sess, tok, \
            patch("api.index.update_user_coins") as coins, \
            patch("api.index.log_chess_game") as log:
        response = app.test_client().post("/api/chess/puzzle/check", json={"move": "E2E4"})

    assert response.status_code == 200
    assert response.get_json()["correct"] is True

    coins.assert_called_once()
    assert coins.call_args.args[0] == uid
    assert coins.call_args.args[1] == 5

    log.assert_called_once()
    assert log.call_args.args[2] == "abc123"


def test_puzzle_check_wrong_move_awards_nothing():
    from api.index import app

    engine = _make_engine()
    uid = _uid()
    db, sess, tok = _auth_patches(engine)

    with patch.dict("api.index._PENDING_PUZZLES", {uid: _pending(uid)}, clear=True), \
            db, sess, tok, \
            patch("api.index.update_user_coins") as coins, \
            patch("api.index.log_chess_game") as log:
        response = app.test_client().post("/api/chess/puzzle/check", json={"move": "a1a2"})

    assert response.status_code == 200
    assert response.get_json()["correct"] is False
    coins.assert_not_called()
    log.assert_not_called()


def test_puzzle_check_solution_not_leaked_on_wrong_move():
    from api.index import app

    engine = _make_engine()
    uid = _uid()
    db, sess, tok = _auth_patches(engine)

    with patch.dict("api.index._PENDING_PUZZLES", {uid: _pending(uid)}, clear=True), \
            db, sess, tok:
        response = app.test_client().post("/api/chess/puzzle/check", json={"move": "a1a2"})

    assert response.get_json() == {"correct": False, "move": None}


def test_puzzle_check_does_not_pay_a_non_owner():
    """Freemium: the anonymous/other visitor sees the answer, but no coins move."""
    from api.index import app

    engine = _make_engine()
    uid = _uid()
    db, sess, tok = _auth_patches(engine)

    with patch.dict("api.index._PENDING_PUZZLES", {uid: _pending(uid, logged_uid=uid + 1)}, clear=True), \
            db, sess, tok, \
            patch("api.index.update_user_coins") as coins, \
            patch("api.index.log_chess_game") as log:
        response = app.test_client().post("/api/chess/puzzle/check", json={"move": "e2e4"})

    assert response.get_json()["correct"] is True
    coins.assert_not_called()
    log.assert_not_called()


def test_puzzle_check_requires_login():
    from api.index import app

    engine = _make_engine()

    with patch.dict("api.index._PENDING_PUZZLES", {}, clear=True), \
            patch("api.index.get_db_engine", return_value=engine), \
            patch("api.index._get_session_user", return_value=None):
        response = app.test_client().post("/api/chess/puzzle/check", json={"move": "e2e4"})

    assert response.status_code == 401


def test_puzzle_check_without_pending_puzzle_is_400():
    from api.index import app

    engine = _make_engine()
    db, sess, tok = _auth_patches(engine)

    with patch.dict("api.index._PENDING_PUZZLES", {}, clear=True), db, sess, tok:
        response = app.test_client().post("/api/chess/puzzle/check", json={"move": "e2e4"})

    assert response.status_code == 400


def test_puzzle_check_expired_puzzle_is_400_and_no_reward():
    from api.index import app, _PENDING_PUZZLE_TTL

    engine = _make_engine()
    uid = _uid()
    db, sess, tok = _auth_patches(engine)
    expired = _pending(uid, age_seconds=_PENDING_PUZZLE_TTL + 60)

    with patch.dict("api.index._PENDING_PUZZLES", {uid: expired}, clear=True), \
            db, sess, tok, \
            patch("api.index.update_user_coins") as coins:
        response = app.test_client().post("/api/chess/puzzle/check", json={"move": "e2e4"})

    assert response.status_code == 400
    coins.assert_not_called()


# --- cooldown -------------------------------------------------------------


def test_puzzle_cooldown_remaining_hours_math():
    from api import index as index_api

    with patch.object(index_api, "get_user_coins",
                      return_value={"balance": 0, "last_puzzle_at": datetime.utcnow() - timedelta(hours=1)}):
        remaining = index_api._puzzle_cooldown_remaining_hours(1)
    assert remaining is not None
    assert 22.0 < remaining < 24.0

    with patch.object(index_api, "get_user_coins",
                      return_value={"balance": 0, "last_puzzle_at": datetime.utcnow() - timedelta(hours=25)}):
        assert index_api._puzzle_cooldown_remaining_hours(1) is None

    with patch.object(index_api, "get_user_coins", return_value=None):
        assert index_api._puzzle_cooldown_remaining_hours(1) is None


def test_puzzle_request_is_429_while_cooldown_active():
    from api.index import app

    engine = _make_engine()
    uid = _uid()
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO chess_accounts (user_id, lichess_username) VALUES (:u, 'tester')"),
            {"u": uid},
        )

    db, sess, tok = _auth_patches(engine)
    with db, sess, tok, patch("api.index._puzzle_cooldown_remaining_hours", return_value=12.0):
        response = app.test_client().post("/api/chess/puzzle", json={})

    assert response.status_code == 429
    body = response.get_json()
    assert body["cooldown"] is True
    assert body["cooldown_hours"] == 12.0


# --- /api/chess/stats -----------------------------------------------------


def test_chess_stats_returns_account_coins_and_history():
    from api.index import app

    engine = _make_engine()
    uid = _uid()
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO chess_accounts (user_id, lichess_username) VALUES (:u, 'tester')"),
            {"u": uid},
        )
        conn.execute(text("INSERT INTO user_coins (user_id, balance) VALUES (:u, 7)"), {"u": uid})
        conn.execute(text(
            "INSERT INTO chess_games (user_id, lichess_username, puzzle_id, puzzle_rating, puzzle_themes) "
            "VALUES (:u, 'tester', 'p1', 1500, 'fork')"
        ), {"u": uid})

    db, sess, tok = _auth_patches(engine)
    player = {"username": "tester", "online": True, "perfs": {}, "games": {"total": 10, "win": 4}}

    with db, sess, tok, patch("api.index.fetch_lichess_user", return_value=player):
        response = app.test_client().get("/api/chess/stats")

    assert response.status_code == 200
    data = response.get_json()
    assert data["linked"] is True
    assert data["coins"] == 7
    assert data["winrate"] == 40.0
    assert data["history"] == [{"puzzle_id": "p1", "rating": 1500}]


def test_chess_stats_for_unlinked_user_has_no_history():
    from api.index import app

    engine = _make_engine()
    db, sess, tok = _auth_patches(engine)

    with db, sess, tok:
        response = app.test_client().get("/api/chess/stats")

    assert response.status_code == 200
    data = response.get_json()
    assert data["linked"] is False
    assert data["coins"] == 0
    assert "history" not in data
