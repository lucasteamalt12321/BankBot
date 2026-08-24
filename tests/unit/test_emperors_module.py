"""Unit tests for the core.history module and the /emperors web page."""

from core.history import EMPERORS, EVENTS, PERSONS
from core.history.emperors import (
    RULERS,
    emperor_by_id,
    events_for_emperor,
    persons_for_emperor,
)

VALID_EMPEROR_IDS = {e.id for e in EMPERORS}
VALID_RULER_IDS = {r.id for r in RULERS}


def test_emperors_count_and_ids():
    assert len(EMPERORS) == 5
    assert VALID_EMPEROR_IDS == {
        "alexander_i", "nicholas_i", "alexander_ii", "alexander_iii", "nicholas_ii"
    }


def test_rulers_count():
    assert len(RULERS) >= 30
    assert "rurik" in VALID_RULER_IDS
    assert "putin" in VALID_RULER_IDS


def test_emperor_reigns_ordered():
    reigns = [e.reign for e in EMPERORS]
    assert reigns == ["1801–1825", "1825–1855", "1855–1881", "1881–1894", "1894–1917"]


def test_events_have_valid_emperor_and_note():
    assert len(EVENTS) >= 100
    for ev in EVENTS:
        assert ev.emperor_id in VALID_RULER_IDS
        assert ev.title
        assert ev.note, f"event {ev.title} has no note"
        assert 1 <= ev.importance <= 5


def test_persons_have_valid_emperor_and_description():
    assert len(PERSONS) >= 100
    for p in PERSONS:
        assert p.emperor_id in VALID_RULER_IDS
        assert p.name
        assert p.description, f"person {p.name} has no description"
        assert 1 <= p.importance <= 5


def test_no_duplicate_persons():
    names = [p.name for p in PERSONS]
    assert len(names) == len(set(names))


def test_no_duplicate_events():
    keys = [(ev.year, ev.title) for ev in EVENTS]
    assert len(keys) == len(set(keys))


def test_every_emperor_has_items():
    for e in EMPERORS:
        assert events_for_emperor(e.id), f"{e.name} has no events"
        assert persons_for_emperor(e.id), f"{e.name} has no persons"


def test_every_ruler_has_items():
    for r in RULERS:
        assert events_for_emperor(r.id), f"{r.name} has no events"
        assert persons_for_emperor(r.id), f"{r.name} has no persons"


def test_key_rulers_have_more_items_than_minor_ones():
    def total_items(ruler_id):
        return len(events_for_emperor(ruler_id)) + len(persons_for_emperor(ruler_id))

    key_rulers = {"vladimir_i", "yaroslav", "ivan_iii", "ivan_iv", "peter_i", "catherine_ii", "stalin", "putin"}
    minor_rulers = {"igor", "olga", "svyatoslav", "kalita", "godunov", "paul_i"}
    key_total = sum(total_items(r) for r in key_rulers)
    minor_total = sum(total_items(r) for r in minor_rulers)
    assert key_total >= minor_total * 2
    for r in key_rulers:
        assert total_items(r) >= 6, f"{r} has too few items for a key ruler"


def test_emperor_by_id():
    assert emperor_by_id("alexander_i").name == "Александр I"
    assert emperor_by_id("nope") is None


def test_known_person_mappings():
    by_name = {p.name: p.emperor_id for p in PERSONS}
    assert by_name["М. И. Кутузов"] == "alexander_i"
    assert by_name["А. С. Пушкин"] == "nicholas_i"
    assert by_name["Ф. М. Достоевский"] == "alexander_ii"
    assert by_name["П. И. Чайковский"] == "alexander_iii"
    assert by_name["П. А. Столыпин"] == "nicholas_ii"


def test_emperors_page_renders(client=None):
    from api.index import app

    c = app.test_client()
    resp = c.get("/emperors")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "История" in body
    assert "Тренажёр" in body
    assert "Александр I" in body
    assert "Николай II" in body
    assert "__DATA__" not in body, "data placeholder not substituted"


def test_emperors_page_has_two_algorithms():
    from api.index import app

    c = app.test_client()
    body = c.get("/emperors").get_data(as_text=True)
    assert 'id="algo-select"' in body
    assert 'value="deck"' in body
    assert 'value="flash"' in body
    assert 'value="counter"' in body
    assert "function pickFlash" in body
    assert "function pickCounter" in body
    assert "emperors_flash" in body
    assert "|| 'flash'" in body, "flash should be the default algorithm"


def test_emperors_page_flash_priority():
    from api.index import app

    c = app.test_client()
    body = c.get("/emperors").get_data(as_text=True)
    assert "function pickFlash" in body
    assert "prio = 0" in body
    assert "prio = 1" in body
    assert "prio = 2" in body
    assert "Date.now() + 60000" in body, "wrong answer should schedule a repeat in 1 minute"


def test_emperors_page_contains_data():
    from api.index import app

    c = app.test_client()
    body = c.get("/emperors").get_data(as_text=True)
    assert "Манифест об отмене крепостного права" in body
    assert "М. И. Кутузов" in body
    assert '"alexander_ii"' in body


def test_emperors_page_has_new_features():
    from api.index import app

    c = app.test_client()
    body = c.get("/emperors").get_data(as_text=True)
    assert 'id="tab-match"' in body
    assert 'id="hint-btn"' in body
    assert 'id="progress-fill"' in body
    assert 'id="stats-card"' in body
    assert "function startMatch" in body
    assert "function placeMatchChip" in body
    assert "pushFlash" in body
    assert "/api/emperors/progress" in body
    assert 'id="debug-panel"' in body
    assert "toggleDebug" in body
    assert "renderDebug" in body
    assert 'value="counter"' in body
    assert "function pickCounter" in body
    assert "function recordAnswer" in body


def test_emperors_page_has_extended_mode_and_importance():
    from api.index import app

    c = app.test_client()
    body = c.get("/emperors").get_data(as_text=True)
    assert "scope-select" in body
    assert "Все правители (Рюрик–Путин)" in body
    assert '"rulers"' in body
    assert '"importance"' in body
    assert "starRow" in body
    assert "toggleScope" in body
    assert "itemsInScope" in body
    assert "distractors.length < 5" in body, "5-option mode should limit distractors"
    assert "opt-count" in body
    assert "toggleOptCount" in body
    assert "Все (хронологически)" in body
    assert "e.key <= '6'" in body, "keyboard handler should support up to 6 options"
    assert "quizScore += (pts.level >= 3) ? 2 : 1" in body, "score gain should depend on difficulty"
    assert "quizScore += (pts.level === 2) ? -2 : -1" in body, "score loss should depend on difficulty"
    assert "diffInfo" in body
    assert "+2/−1" in body, "all rulers / all options difficulty should exist"
    assert "+1/−2" in body, "all rulers / 5 options difficulty should exist"
    assert "+1/−1" in body, "5 emperors difficulty should exist"


def test_emperors_progress_api_save_and_get():
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import StaticPool
    from unittest.mock import patch
    from api.index import app

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE emperors_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                card_key TEXT NOT NULL,
                reps INTEGER NOT NULL DEFAULT 0,
                interval_days INTEGER NOT NULL DEFAULT 0,
                ease REAL NOT NULL DEFAULT 2.5,
                due REAL NOT NULL DEFAULT 0,
                correct_count INTEGER NOT NULL DEFAULT 0,
                wrong_count INTEGER NOT NULL DEFAULT 0,
                counter INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL
            )
        """))
        conn.execute(text("CREATE UNIQUE INDEX uq_emperors_progress_user_card ON emperors_progress(user_id, card_key)"))

    c = app.test_client()
    auth = {"X-Auth-Token": "test-token"}
    with patch("api.index.get_db_engine", return_value=engine), \
         patch("api.index._get_session_user", return_value={"id": 42, "login": "test"}), \
         patch("api.index._auth_token_from_request", return_value="test-token"):
        resp = c.post("/api/emperors/progress", headers=auth, json={
            "cards": {"event::Отмена крепостного права": {"reps": 3, "interval": 7, "ease": 2.5, "due": 100.0, "correct": 3, "wrong": 0, "counter": 3}},
        })
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

        g = c.get("/api/emperors/progress", headers=auth)
        data = g.get_json()
        assert "event::Отмена крепостного права" in data["cards"]
        assert data["cards"]["event::Отмена крепостного права"]["reps"] == 3
        assert data["cards"]["event::Отмена крепостного права"]["counter"] == 3

        r = c.post("/api/emperors/progress", headers=auth, json={"cards": {}, "reset": True})
        assert r.status_code == 200
        g2 = c.get("/api/emperors/progress", headers=auth)
        assert g2.get_json()["cards"] == {}

    anon = c.get("/api/emperors/progress")
    assert anon.get_json()["cards"] == {}
    anon_post = c.post("/api/emperors/progress", json={"cards": {}})
    assert anon_post.status_code == 401


def test_emperors_page_powerup_features():
    from api.index import app

    c = app.test_client()
    body = c.get("/emperors").get_data(as_text=True)
    assert 'id="tab-chrono"' in body, "chronology tab should exist"
    assert 'id="panel-chrono"' in body
    assert "function startChrono" in body
    assert "function chronoPick" in body
    assert "function checkChrono" in body
    assert "chronoState" in body
    assert 'id="qdir-select"' in body, "question-direction selector should exist"
    assert "toggleQDir" in body
    assert "fromRuler" in body, "reverse question mode should exist"
    assert "emperors_qdir" in body
    assert "function levelInfo" in body, "level system should exist"
    assert "Знаток" in body
    assert "function updateStreak" in body
    assert "emperors_streak" in body
    assert "hubTrack('emperors', 1)" in body, "global achievements tracking should exist"
    assert "function eraGroups" in body, "timeline era groups should exist"
    assert "Древняя Русь" in body
    assert "timeline" in body
    assert "animate-correct" in body
    assert "animate-wrong" in body
    assert "function currentStreakCorrect" in body
