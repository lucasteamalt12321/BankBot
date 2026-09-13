"""Tests for the social module: public profiles, friends, weekly top."""

from datetime import datetime, timezone
from unittest.mock import patch
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

try:
    import bcrypt  # noqa: F401
except ImportError:  # Termux: bcrypt not available locally
    import sys
    import types

    _stub = types.ModuleType("bcrypt")
    _stub.hashpw = lambda pwd, salt: pwd
    _stub.gensalt = lambda rounds=12: b"$2b$12$stubstubstubstubstub"
    _stub.checkpw = lambda pwd, hashed: True
    sys.modules["bcrypt"] = _stub

from api.index import app


def _make_engine():
    """In-memory engine with sqlite-compatible schema for social tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _now_fn(dbapi_conn, _record):
        def now_impl():
            return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        dbapi_conn.create_function("NOW", 0, now_impl)

    ddl = """
    CREATE TABLE IF NOT EXISTS web_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login VARCHAR(64) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        display_name VARCHAR(100),
        gd_nickname VARCHAR(64),
        telegram_id BIGINT,
        lichess_nickname VARCHAR(64),
        email VARCHAR(255) UNIQUE,
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS web_sessions (
        token VARCHAR(64) PRIMARY KEY,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS user_coins (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        last_puzzle_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS friend_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user INTEGER NOT NULL,
        to_user INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS web_friends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        friend_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS web_activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        day TEXT NOT NULL,
        module TEXT NOT NULL,
        actions INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS web_streak (
        user_id INTEGER PRIMARY KEY,
        last_active_day TEXT NOT NULL,
        current_streak INTEGER NOT NULL DEFAULT 0,
        longest_streak INTEGER NOT NULL DEFAULT 0,
        total_active_days INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS web_achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        code TEXT NOT NULL,
        unlocked_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS rate_limits (
        key TEXT NOT NULL, ts DOUBLE PRECISION NOT NULL
    );
    CREATE UNIQUE INDEX IF NOT EXISTS uq_friend_requests_pair ON friend_requests(from_user, to_user);
    CREATE UNIQUE INDEX IF NOT EXISTS uq_web_friends_pair ON web_friends(user_id, friend_id);
    CREATE UNIQUE INDEX IF NOT EXISTS uq_web_achievements_user_code ON web_achievements(user_id, code);
    CREATE UNIQUE INDEX IF NOT EXISTS uq_web_activity_user_day_module ON web_activity_log(user_id, day, module);
    """
    with engine.begin() as conn:
        for stmt in ddl.split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
    return engine


def _auth_headers(token: str) -> dict:
    return {"X-Auth-Token": token}


def _register(client, login: str, email: str, display_name: str | None = None):
    payload = {"login": login, "password": "secret123", "email": email}
    if display_name:
        payload["display_name"] = display_name
    r = client.post("/api/auth/register", json=payload)
    assert r.status_code == 200, r.get_json()
    return r.get_json()["token"]


@patch("api.index.get_db_engine")
@patch("api.index._check_ai_rate", return_value=False)
@patch("api.index._check_db_rate", return_value=False)
def test_public_profile_and_search(_rate, _ai_rate, mock_engine):
    mock_engine.return_value = _make_engine()
    client = app.test_client()
    _register(client, "alice", "alice@test.local", "Алиса")
    bob_t = _register(client, "bobbob", "bob@test.local")
    _register(client, "carol", "carol@test.local")

    me = client.get("/api/auth/me", headers=_auth_headers(bob_t))
    assert me.status_code == 200
    bob_id = me.get_json()["id"]

    # Public profile, no auth
    p = client.get("/api/u/bobbob")
    assert p.status_code == 200
    prof = p.get_json()["profile"]
    assert prof["login"] == "bobbob"
    assert prof["is_self"] is False
    assert prof["relation"] == "none"
    for secret in ("email", "telegram_id", "password_hash"):
        assert secret not in prof and secret not in p.get_json()

    # Case-insensitive lookup
    assert client.get("/api/u/BOBBOB").status_code == 200

    # Not found
    assert client.get("/api/u/nobody") .status_code == 404

    # Own profile (relation self)
    own = client.get("/api/u/bobbob", headers=_auth_headers(bob_t))
    assert own.get_json()["profile"]["is_self"] is True

    # Search
    s = client.get("/api/users/search?q=bob")
    assert s.status_code == 200
    users = s.get_json()["users"]
    assert len(users) == 1
    assert users[0]["id"] == bob_id

    s_short = client.get("/api/users/search?q=a")
    assert s_short.status_code == 400

    # own id excluded from search
    s_own = client.get("/api/users/search?q=bob", headers=_auth_headers(bob_t))
    assert all(u["id"] != bob_id for u in s_own.get_json()["users"])


@patch("api.index.get_db_engine")
@patch("api.index._check_ai_rate", return_value=False)
@patch("api.index._check_db_rate", return_value=False)
def test_friend_full_flow(_rate, _ai_rate, mock_engine):
    mock_engine.return_value = _make_engine()
    client = app.test_client()
    alice_t = _register(client, "alice", "alice@test.local")
    bob_t = _register(client, "bobbob", "bob@test.local")
    carol_t = _register(client, "carol", "carol@test.local")

    alice_me = client.get("/api/auth/me", headers=_auth_headers(alice_t)).get_json()
    bob_me = client.get("/api/auth/me", headers=_auth_headers(bob_t)).get_json()
    carol_me = client.get("/api/auth/me", headers=_auth_headers(carol_t)).get_json()
    alice_id, bob_id, carol_id = alice_me["id"], bob_me["id"], carol_me["id"]

    # Self request rejected
    r = client.post("/api/friends/request", json={"friend_id": alice_id}, headers=_auth_headers(alice_t))
    assert r.status_code == 400

    # Invalid id
    r = client.post("/api/friends/request", json={"friend_id": 999999}, headers=_auth_headers(alice_t))
    assert r.status_code == 404

    # No auth
    r = client.get("/api/friends")
    assert r.status_code == 401
    r = client.post("/api/friends/request", json={"friend_id": bob_id})
    assert r.status_code == 401

    # alice -> bob
    assert client.post("/api/friends/request", json={"friend_id": bob_id}, headers=_auth_headers(alice_t)).status_code == 200
    # duplicate
    dup = client.post("/api/friends/request", json={"friend_id": bob_id}, headers=_auth_headers(alice_t))
    assert dup.status_code == 409
    # reverse pending also duplicate
    rev = client.post("/api/friends/request", json={"friend_id": alice_id}, headers=_auth_headers(bob_t))
    assert rev.status_code == 409

    # alice cannot accept her own outgoing request
    alice_in = client.get("/api/friends", headers=_auth_headers(alice_t)).get_json()
    assert not alice_in["incoming"]
    assert len(alice_in["outgoing"]) == 1
    assert alice_in["outgoing"][0]["login"] == "bobbob"

    bob_in = client.get("/api/friends", headers=_auth_headers(bob_t)).get_json()
    assert len(bob_in["incoming"]) == 1
    req_id = bob_in["incoming"][0]["req_id"]
    assert bob_in["incoming"][0]["login"] == "alice"

    # bob cannot accept someone else's... here alice's request is to bob, so bob CAN.
    # carol tries to act on bob's request id -> forbidden
    forbid = client.post("/api/friends/accept", json={"request_id": req_id}, headers=_auth_headers(carol_t))
    assert forbid.status_code == 403

    # bob accepts
    assert client.post("/api/friends/accept", json={"request_id": req_id}, headers=_auth_headers(bob_t)).status_code == 200

    # both sides see each other as friends
    alice_f = client.get("/api/friends", headers=_auth_headers(alice_t)).get_json()
    bob_f = client.get("/api/friends", headers=_auth_headers(bob_t)).get_json()
    assert [f["login"] for f in alice_f["friends"]] == ["bobbob"]
    assert [f["login"] for f in bob_f["friends"]] == ["alice"]
    assert not alice_f["incoming"] and not alice_f["outgoing"]

    # search now shows relation = friend
    s = client.get("/api/users/search?q=bob", headers=_auth_headers(alice_t)).get_json()["users"]
    assert [u["relation"] for u in s if u["login"] == "bobbob"] == ["friend"]

    # round 2: carol -> alice, alice declines
    assert client.post("/api/friends/request", json={"friend_id": alice_id}, headers=_auth_headers(carol_t)).status_code == 200
    alice_in2 = client.get("/api/friends", headers=_auth_headers(alice_t)).get_json()
    c_req = alice_in2["incoming"][0]["req_id"]
    assert client.post("/api/friends/decline", json={"request_id": c_req}, headers=_auth_headers(alice_t)).status_code == 200
    assert not client.get("/api/friends", headers=_auth_headers(alice_t)).get_json()["incoming"]

    # round 3: alice -> carol, alice cancels her own outgoing request
    assert client.post("/api/friends/request", json={"friend_id": carol_id}, headers=_auth_headers(alice_t)).status_code == 200
    alice_out = client.get("/api/friends", headers=_auth_headers(alice_t)).get_json()
    c_req2 = alice_out["outgoing"][0]["req_id"]
    # canceling someone else's outgoing request is forbidden
    wrong = client.post("/api/friends/cancel", json={"request_id": c_req2}, headers=_auth_headers(carol_t))
    assert wrong.status_code == 403
    assert client.post("/api/friends/cancel", json={"request_id": c_req2}, headers=_auth_headers(alice_t)).status_code == 200
    assert not client.get("/api/friends", headers=_auth_headers(alice_t)).get_json()["outgoing"]
    # declining someone else's outgoing request is also forbidden
    assert client.post("/api/friends/request", json={"friend_id": carol_id}, headers=_auth_headers(alice_t)).status_code == 200
    c_req3 = client.get("/api/friends", headers=_auth_headers(carol_t)).get_json()["incoming"][0]["req_id"]
    wrong_d = client.post("/api/friends/decline", json={"request_id": c_req3}, headers=_auth_headers(bob_t))
    assert wrong_d.status_code == 403

    # remove friend: alice removes bob
    assert client.post("/api/friends/remove", json={"friend_id": bob_id}, headers=_auth_headers(alice_t)).status_code == 200
    assert not client.get("/api/friends", headers=_auth_headers(alice_t)).get_json()["friends"]
    assert not client.get("/api/friends", headers=_auth_headers(bob_t)).get_json()["friends"]
    # idempotent
    assert client.post("/api/friends/remove", json={"friend_id": bob_id}, headers=_auth_headers(alice_t)).status_code == 200


@patch("api.index.get_db_engine")
@patch("api.index._check_ai_rate", return_value=False)
@patch("api.index._check_db_rate", return_value=False)
def test_weekly_top(_rate, _ai_rate, mock_engine):
    engine = _make_engine()
    mock_engine.return_value = engine
    client = app.test_client()
    alice_t = _register(client, "alice", "alice@test.local")
    bob_t = _register(client, "bobbob", "bob@test.local")

    alice_me = client.get("/api/auth/me", headers=_auth_headers(alice_t)).get_json()
    bob_me = client.get("/api/auth/me", headers=_auth_headers(bob_t)).get_json()
    alice_id, bob_id = alice_me["id"], bob_me["id"]

    # make them friends
    assert client.post("/api/friends/request", json={"friend_id": bob_id}, headers=_auth_headers(alice_t)).status_code == 200
    req = client.get("/api/friends", headers=_auth_headers(bob_t)).get_json()["incoming"][0]["req_id"]
    assert client.post("/api/friends/accept", json={"request_id": req}, headers=_auth_headers(bob_t)).status_code == 200

    # seed activity: bob 10 actions today, alice 3 today, carol irrelevant (not shown)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO web_activity_log (user_id, day, module, actions) "
            "VALUES (:u, :d, 'math', :a) ON CONFLICT (user_id, day, module) DO UPDATE SET actions = actions + :a"
        ), {"u": bob_id, "d": today, "a": 10})
        conn.execute(text(
            "INSERT INTO web_activity_log (user_id, day, module, actions) "
            "VALUES (:u, :d, 'math', :a) ON CONFLICT (user_id, day, module) DO UPDATE SET actions = actions + :a"
        ), {"u": alice_id, "d": today, "a": 3})

    weekly = client.get("/api/friends/weekly", headers=_auth_headers(alice_t))
    assert weekly.status_code == 200
    items = weekly.get_json()["weekly"]
    names = {it["login"]: it for it in items}
    assert names["bobbob"]["actions"] == 10
    assert names["alice"]["actions"] == 3
    assert items[0]["login"] == "bobbob"

    # unauth
    assert client.get("/api/friends/weekly").status_code == 401