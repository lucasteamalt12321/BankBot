"""Tests for GD co-op: a level completed by two players (GD-08).

Attribution model: GD players are keyed by the GD nick on an approved
submission, so the co-op partner is credited at read time from
``submissions.partner_nick`` instead of writing extra ``level_completions``
rows (whose ``UNIQUE(user_id, level_id)`` would break for two partners on one
level). Consequence asserted here: a rejected co-op run credits nobody.
"""

import io
from unittest.mock import patch

import pytest
from sqlalchemy import text

from api.index import app
from tests.unit.test_web_portal_e2e import _auth_headers, _make_engine, _promote_admin


def _submit(c, headers, level_name="Tartarus", partner=None, gd_nick=None, difficulty=None):
    data = {"level_name": level_name}
    data["media"] = (io.BytesIO(b"\x00\x01\x02fake-video"), "run.mp4")
    if partner is not None:
        data["partner_nick"] = partner
    if gd_nick is not None:
        data["gd_nickname"] = gd_nick
    if difficulty is not None:
        data["difficulty"] = difficulty
    return c.post("/api/gd/submit", data=data, headers=headers, content_type="multipart/form-data")


def _seed_user(conn, uid, login, gd_nick=None):
    conn.execute(
        text("INSERT INTO web_users (id, login, password_hash, gd_nickname) VALUES (:id, :login, 'x', :nick)"),
        {"id": uid, "login": login, "nick": gd_nick},
    )


@patch("api.index.get_db_engine")
def test_gd_coop_partner_credited_after_approval(mock_engine):
    """An approved co-op run credits the level to both players."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
    level_id = index_api.add_gd_level("Tartarus", 1, "Extreme Demon")
    token = index_api._create_session(1)
    headers = _auth_headers(token)

    resp = _submit(c, headers, partner="Neon")
    assert resp.status_code == 200
    sub_id = resp.get_json()["submission_id"]

    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT username, partner_nick FROM submissions WHERE id = :sid"), {"sid": sub_id}
        ).mappings().first()
    assert row["username"] == "Riot"
    assert row["partner_nick"] == "Neon"

    # Nothing is credited before moderation.
    assert c.get("/api/gd/player/Neon").get_json()["found"] is False

    assert index_api.approve_gd_submission_db(sub_id, 1) is True

    owner = c.get("/api/gd/player/Riot").get_json()
    partner = c.get("/api/gd/player/Neon").get_json()
    assert owner["found"] is True
    assert [x["id"] for x in owner["completions"]] == [level_id]
    # Owner is credited on their own run, so no co-op badge on their side.
    assert owner["completions"][0]["is_coop"] is False
    assert partner["found"] is True
    assert [x["id"] for x in partner["completions"]] == [level_id]
    # The partner sees the level credited with a co-op badge naming the other player.
    assert partner["completions"][0]["is_coop"] is True
    assert partner["completions"][0]["coop_with"] == "Riot"
    # Both players earn the same points for the level.
    assert owner["points"] == partner["points"] > 0


@patch("api.index.get_db_engine")
def test_gd_coop_rejected_run_credits_nobody(mock_engine):
    """A rejected co-op submission must not credit the partner."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
    index_api.add_gd_level("Tartarus", 1, "Hard")
    token = index_api._create_session(1)
    sub_id = _submit(c, _auth_headers(token), partner="Neon").get_json()["submission_id"]

    assert index_api.reject_gd_submission_db(sub_id, 1) is True

    # The owner keeps a profile card (they have a web account) but the rejected run
    # must credit no levels to either player.
    assert c.get("/api/gd/player/Riot").get_json()["completions"] == []
    assert c.get("/api/gd/player/Neon").get_json()["found"] is False
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM level_completions")).scalar() == 0


@patch("api.index.get_db_engine")
def test_gd_coop_partner_nick_is_case_insensitive(mock_engine):
    """The partner is credited regardless of the casing used in the form."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
    index_api.add_gd_level("Tartarus", 1, "Hard")
    token = index_api._create_session(1)
    sub_id = _submit(c, _auth_headers(token), partner="nEoN").get_json()["submission_id"]

    assert index_api.approve_gd_submission_db(sub_id, 1) is True

    partner = c.get("/api/gd/player/Neon").get_json()
    assert partner["found"] is True
    assert len(partner["completions"]) == 1
    assert partner["completions"][0]["coop_with"] == "Riot"


@patch("api.index.get_db_engine")
def test_gd_coop_level_not_double_counted(mock_engine):
    """Solo + co-op on the same level counts once and prefers the solo badge."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
        _seed_user(conn, 2, "second", "Neon")
    index_api.add_gd_level("Tartarus", 1, "Hard")
    tokens = [_auth_headers(index_api._create_session(1)), _auth_headers(index_api._create_session(2))]

    solo = _submit(c, tokens[1], partner=None).get_json()["submission_id"]
    coop = _submit(c, tokens[0], partner="Neon").get_json()["submission_id"]
    assert index_api.approve_gd_submission_db(solo, 1) is True
    assert index_api.approve_gd_submission_db(coop, 1) is True

    partner = c.get("/api/gd/player/Neon").get_json()
    assert partner["found"] is True
    assert len(partner["completions"]) == 1, "one level must not be counted twice"
    # Solo completion exists, so the row is not labelled as a co-op run.
    assert partner["completions"][0]["is_coop"] is False
    assert partner["completions"][0]["coop_with"] is None


@patch("api.index.get_db_engine")
def test_gd_coop_partner_has_no_level_completions_row(mock_engine):
    """Attribution is read-time only: no level_completions row for the partner.

    Writing one would need ``UNIQUE(user_id, level_id)`` relaxed, which would be
    a production migration for no gain — the submission stays the only source
    of truth for moderation.
    """
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
    index_api.add_gd_level("Tartarus", 1, "Hard")
    token = index_api._create_session(1)
    sub_id = _submit(c, _auth_headers(token), partner="Neon").get_json()["submission_id"]

    assert index_api.approve_gd_submission_db(sub_id, 1) is True

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT user_id, player_name FROM level_completions")).mappings().all()
    assert [(r["user_id"], r["player_name"]) for r in rows] == [(1, "Riot")]


@patch("api.index.get_db_engine")
def test_gd_coop_rejects_self_and_bad_nicks(mock_engine):
    """Partner nick equal to your own, over-long or with control chars -> 400."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
    index_api.add_gd_level("Tartarus", 1, "Hard")
    headers = _auth_headers(index_api._create_session(1))

    resp = _submit(c, headers, partner="Riot")
    assert resp.status_code == 400
    assert "совпадает с вашим" in resp.get_json()["error"]

    resp = _submit(c, headers, partner="riot")
    assert resp.status_code == 400, "self-coop must be rejected case-insensitively"

    resp = _submit(c, headers, partner="N" * 51)
    assert resp.status_code == 400
    assert "слишком длинный" in resp.get_json()["error"]

    resp = _submit(c, headers, partner="Bad\x07Nick")
    assert resp.status_code == 400
    assert "недопустимые символы" in resp.get_json()["error"]

    # Nothing was persisted by any of the rejected attempts.
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM submissions")).scalar() == 0


@patch("api.index.get_db_engine")
def test_gd_coop_partner_may_be_barely_valid(mock_engine):
    """A 50-char nick and surrounding whitespace are accepted and trimmed."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
    index_api.add_gd_level("Tartarus", 1, "Hard")
    nick = "N" * 50
    resp = _submit(c, _auth_headers(index_api._create_session(1)), partner=f"  {nick}  ")
    assert resp.status_code == 200
    sub_id = resp.get_json()["submission_id"]
    with engine.begin() as conn:
        assert conn.execute(
            text("SELECT partner_nick FROM submissions WHERE id = :sid"), {"sid": sub_id}
        ).scalar() == nick


@patch("api.index.get_db_engine")
def test_gd_coop_visible_on_level_completions(mock_engine):
    """The level page API exposes the co-op partner to render the badge."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
    level_id = index_api.add_gd_level("Tartarus", 1, "Hard")
    token = index_api._create_session(1)
    sub_id = _submit(c, _auth_headers(token), partner="Neon").get_json()["submission_id"]
    assert index_api.approve_gd_submission_db(sub_id, 1) is True

    data = c.get(f"/api/gd/level/{level_id}/completions").get_json()
    by_name = {u["player_name"]: u for u in data["completions"]}
    assert by_name["Riot"]["is_coop"] is True
    assert by_name["Riot"]["coop_with"] == "Neon"
    # Raw column name must not leak into the public payload.
    assert "partner_nick" not in by_name["Riot"]


@patch("api.index.get_db_engine")
def test_gd_coop_partner_seen_by_moderator(mock_engine):
    """The moderation queue shows the partner so the admin can judge one shared proof."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
        _seed_user(conn, 3, "boss", "Admin")
        conn.execute(text("UPDATE web_users SET is_admin = 1 WHERE id = 3"))
    index_api.add_gd_level("Tartarus", 1, "Hard")
    token = index_api._create_session(1)
    _submit(c, _auth_headers(token), partner="Neon")

    resp = c.get("/api/gd/moderate", headers=_auth_headers(index_api._create_session(3)))
    assert resp.status_code == 200
    rows = resp.get_json()["submissions"]
    assert [r["partner_nick"] for r in rows] == ["Neon"]

    # The moderation panel and the submit form expose the co-op controls.
    body = c.get("/gd").get_data(as_text=True)
    assert 'id="sub-partner"' in body
    assert "partner_nick" in body


@patch("api.index.get_db_engine")
def test_gd_coop_partner_appears_in_top_players(mock_engine):
    """Regression: a pure co-op partner used to be missing from the leaderboard.

    ``get_gd_players`` aggregates ``level_completions``, where co-op partners have
    no row by design, so the partner scored 0 and did not appear at all — the
    level was visible only on the submitter's side.
    """
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
    index_api.add_gd_level("Tartarus", 1, "Hard")
    token = index_api._create_session(1)
    sub_id = _submit(c, _auth_headers(token), partner="Neon").get_json()["submission_id"]

    # Before approval nobody is on the board from this run.
    names_before = {p["player_name"] for p in c.get("/api/gd/players?limit=200").get_json()}
    assert "Neon" not in names_before

    assert index_api.approve_gd_submission_db(sub_id, 1) is True

    board = {p["player_name"]: p for p in c.get("/api/gd/players?limit=200").get_json()}
    assert "Riot" in board and "Neon" in board
    assert board["Neon"]["points"] == board["Riot"]["points"] > 0
    assert board["Neon"]["total_approved"] == 1
    assert board["Neon"]["web_login"] is None, "co-op partner is not the submitter's account"


@patch("api.index.get_db_engine")
def test_gd_coop_top_players_dedup_vs_own_completion(mock_engine):
    """Co-op and a solo completion of the same level count once in the top."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
        _seed_user(conn, 2, "second", "Neon")
    index_api.add_gd_level("Tartarus", 1, "Hard")
    solo = _submit(c, _auth_headers(index_api._create_session(2))).get_json()["submission_id"]
    coop = _submit(c, _auth_headers(index_api._create_session(1)), partner="Neon").get_json()["submission_id"]
    assert index_api.approve_gd_submission_db(solo, 1) is True
    assert index_api.approve_gd_submission_db(coop, 1) is True

    board = {p["player_name"]: p for p in c.get("/api/gd/players?limit=200").get_json()}
    neon = board["Neon"]
    solo_points = index_api._gd_level_points(1)
    assert neon["points"] == solo_points, "one level must be worth points once"
    assert neon["total_approved"] == 1


@patch("api.index.get_db_engine")
def test_gd_coop_top_players_ignores_rejected(mock_engine):
    """A rejected co-op run puts nobody on the leaderboard."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
    index_api.add_gd_level("Tartarus", 1, "Hard")
    sub_id = _submit(c, _auth_headers(index_api._create_session(1)), partner="Neon").get_json()["submission_id"]
    assert index_api.reject_gd_submission_db(sub_id, 1) is True

    assert c.get("/api/gd/players?limit=200").get_json() == []


@patch("api.index.get_db_engine")
def test_gd_partner_search_finds_known_nicks(mock_engine):
    """The co-op partner picker searches locally known nicks."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
        _seed_user(conn, 2, "second", "hikiktosik")
        _seed_user(conn, 3, "third", "NeonBlade")
    index_api.add_gd_level("Tartarus", 1, "Hard")
    sub_id = _submit(c, _auth_headers(index_api._create_session(1)), partner="Neon").get_json()["submission_id"]
    assert index_api.approve_gd_submission_db(sub_id, 1) is True

    headers = _auth_headers(index_api._create_session(1))

    # Submission owners, recorded partners and account nicks are all searchable.
    found = [n["nick"] for n in c.get("/api/gd/players/search?q=ne", headers=headers).get_json()["nicks"]]
    # substring match also reaches NeonBlade, but the credited Neon comes first
    assert found[:1] == ["Neon"] and "NeonBlade" in found
    assert [n["nick"] for n in c.get("/api/gd/players/search?q=hik", headers=headers).get_json()["nicks"]] == ["hikiktosik"]
    assert "NeonBlade" in [n["nick"] for n in c.get("/api/gd/players/search?q=blade", headers=headers).get_json()["nicks"]]
    # Riot submitted this level, so the search reports his completions.
    riot = [n for n in c.get("/api/gd/players/search?q=riot", headers=headers).get_json()["nicks"] if n["nick"] == "Riot"]
    assert riot and riot[0]["completed"] == 1
    # One character is not enough to scan the whole nick index.
    assert c.get("/api/gd/players/search?q=r", headers=headers).get_json()["nicks"] == []
    assert c.get("/api/gd/players/search?q=zzzz", headers=headers).get_json()["nicks"] == []


@patch("api.index.get_db_engine")
def test_gd_partner_search_requires_login(mock_engine):
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    c = app.test_client()

    assert c.get("/api/gd/players/search?q=ne").status_code == 401


@patch("api.index.get_db_engine")
def test_gd_partner_search_dedupes_case_variants(mock_engine):
    """The same nick in different spellings is one search result."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
    index_api.add_gd_level("Tartarus", 1, "Hard")
    h = _auth_headers(index_api._create_session(1))
    s1 = _submit(c, h, partner="Neon").get_json()["submission_id"]
    s2 = _submit(c, h, partner="NEON").get_json()["submission_id"]
    assert index_api.approve_gd_submission_db(s1, 1) is True
    assert index_api.approve_gd_submission_db(s2, 1) is True

    nicks = c.get("/api/gd/players/search?q=neon", headers=h).get_json()["nicks"]
    assert [n["nick"] for n in nicks].count("Neon") == 1


@patch("api.index.get_db_engine")
def test_gd_coop_form_uses_checkbox_and_search(mock_engine):
    """The submit form drives co-op through a checkbox plus a nick picker."""
    mock_engine.return_value = _make_engine()
    c = app.test_client()
    body = c.get("/gd").get_data(as_text=True)
    assert 'id="sub-coop-toggle"' in body
    assert "2p completion" in body
    assert 'id="sub-partner-nick"' in body, "the sent nick must come from the picked value"
    assert "searchPartner" in body and "pickPartner" in body


@patch("api.index.get_db_engine")
def test_gd_solo_flow_stays_solo(mock_engine):
    """Regression: an ordinary submission has no partner and no co-op flags."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
    level_id = index_api.add_gd_level("Tartarus", 1, "Hard")
    token = index_api._create_session(1)

    resp = _submit(c, _auth_headers(token))
    assert resp.status_code == 200
    sub_id = resp.get_json()["submission_id"]
    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT partner_nick FROM submissions WHERE id = :sid"), {"sid": sub_id}
        ).scalar() is None

    assert index_api.approve_gd_submission_db(sub_id, 1) is True

    profile = c.get("/api/gd/player/Riot").get_json()
    assert profile["completions"] == [
        {**profile["completions"][0], "is_coop": False, "coop_with": None}
    ]
    assert profile["completions"][0]["id"] == level_id


@patch("api.index.get_db_engine")
def test_gd_coop_partner_with_account_keeps_solo_levels(mock_engine):
    """A partner who is also an account holder keeps their own solo levels.

    The persona branch is read first, so without merging the account-side rows a
    co-op player would silently lose their solo completions.
    """
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
        _seed_user(conn, 2, "second", "Neon")
    coop_level = index_api.add_gd_level("Tartarus", 1, "Hard")
    solo_level = index_api.add_gd_level("Bloodbath", 2, "Harder")
    assert coop_level and solo_level

    owner_headers = _auth_headers(index_api._create_session(1))
    partner_headers = _auth_headers(index_api._create_session(2))

    solo = _submit(c, partner_headers, level_name="Bloodbath").get_json()["submission_id"]
    coop = _submit(c, owner_headers, level_name="Tartarus", partner="Neon").get_json()["submission_id"]
    assert index_api.approve_gd_submission_db(solo, 1) is True
    assert index_api.approve_gd_submission_db(coop, 1) is True

    profile = c.get("/api/gd/player/Neon").get_json()
    assert profile["found"] is True
    by_id = {x["id"]: x for x in profile["completions"]}
    assert set(by_id) == {coop_level, solo_level}
    assert by_id[coop_level]["is_coop"] is True
    assert by_id[coop_level]["coop_with"] == "Riot"
    assert by_id[solo_level]["is_coop"] is False


@pytest.mark.parametrize(
    "partner,expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("  Neon  ", "Neon"),
        ("Neon", "Neon"),
        ("n" * 50, "n" * 50),
    ],
)
def test_gd_coop_partner_normalisation(partner, expected):
    """_gd_norm_coop_partner: blank means solo, valid nicks are trimmed."""
    from api.index import _gd_norm_coop_partner

    value, error = _gd_norm_coop_partner(partner, "Riot")
    assert error is None
    assert value == expected


@pytest.mark.parametrize("partner", ["Riot", "riot", "RIOT", " Riot "])
def test_gd_coop_partner_self_rejected(partner):
    from api.index import _gd_norm_coop_partner

    value, error = _gd_norm_coop_partner(partner, "Riot")
    assert value is None
    assert error


def _approve_via_api(c, index_api, sub_id, position=1):
    """Promote the owner to admin and approve through the real HTTP endpoint."""
    _promote_admin(1)
    resp = c.post(
        "/api/gd/moderate/approve",
        json={"submission_id": sub_id, "position": position},
        headers=_auth_headers(index_api._create_session(1)),
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()


@patch("api.index.get_db_engine")
def test_gd_suggested_difficulty_seeds_new_level(mock_engine):
    """The difficulty picked in the submit form seeds the level list on approve."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
    sub_id = _submit(c, _auth_headers(index_api._create_session(1)), difficulty="hard_demon")
    sub_id = sub_id.get_json()["submission_id"]

    # The suggestion is stored on the submission as a human label.
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT difficulty FROM submissions WHERE id = :sid"), {"sid": sub_id}
        ).mappings().first()
    assert row["difficulty"] == "Hard Demon"

    result = _approve_via_api(c, index_api, sub_id, position=1)

    with engine.begin() as conn:
        lv = conn.execute(text("SELECT id, difficulty FROM levels")).mappings().first()
    assert lv["id"] == result["level_id"]
    assert lv["difficulty"] == "hard_demon", "suggested difficulty must reach the list"


@patch("api.index.get_db_engine")
def test_gd_approve_keeps_admin_set_difficulty(mock_engine):
    """Approving another run must not reset a difficulty the admin has set."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
    index_api.add_gd_level("Tartarus", 1, "Extreme Demon")

    h = _auth_headers(index_api._create_session(1))
    first = _submit(c, h, difficulty="easy").get_json()["submission_id"]
    second = _submit(c, h, difficulty="easy").get_json()["submission_id"]
    _approve_via_api(c, index_api, first, position=1)
    _approve_via_api(c, index_api, second, position=1)

    with engine.begin() as conn:
        lv = conn.execute(text("SELECT difficulty FROM levels")).mappings().first()
    assert lv["difficulty"] == "extreme_demon", "the admin's choice wins over a player suggestion"


@patch("api.index.get_db_engine")
def test_gd_approve_without_suggestion_stays_unknown(mock_engine):
    """No suggestion in the submission -> the list still gets the neutral value."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
    sub_id = _submit(c, _auth_headers(index_api._create_session(1))).get_json()["submission_id"]
    _approve_via_api(c, index_api, sub_id, position=1)

    with engine.begin() as conn:
        lv = conn.execute(text("SELECT difficulty FROM levels")).mappings().first()
    assert lv["difficulty"] == "unknown"


@patch("api.index.get_db_engine")
def test_gd_moderation_card_labels_suggested_difficulty(mock_engine):
    """The moderation card presents the submission difficulty as a suggestion."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        _seed_user(conn, 1, "owner", "Riot")
        _seed_user(conn, 3, "boss", "Admin")
        conn.execute(text("UPDATE web_users SET is_admin = 1 WHERE id = 3"))
    sub_id = _submit(
        c, _auth_headers(index_api._create_session(1)), difficulty="insane_demon"
    ).get_json()["submission_id"]

    body = c.get("/gd").get_data(as_text=True)
    assert "Предложенная сложность" in body
    assert "'⭐ Сложность: '" not in body, "old unqualified label must be gone"

    rows = c.get(
        "/api/gd/moderate", headers=_auth_headers(index_api._create_session(3))
    ).get_json()["submissions"]
    assert [r["id"] for r in rows] == [sub_id]
    assert rows[0]["difficulty"] == "Insane Demon"
