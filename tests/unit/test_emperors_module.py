"""Unit tests for the core.history module and the /emperors web page."""

from core.history import EMPERORS, EVENTS, PERSONS
from core.history.emperors import emperor_by_id, events_for_emperor, persons_for_emperor

VALID_EMPEROR_IDS = {e.id for e in EMPERORS}


def test_emperors_count_and_ids():
    assert len(EMPERORS) == 5
    assert VALID_EMPEROR_IDS == {
        "alexander_i", "nicholas_i", "alexander_ii", "alexander_iii", "nicholas_ii"
    }


def test_emperor_reigns_ordered():
    reigns = [e.reign for e in EMPERORS]
    assert reigns == ["1801–1825", "1825–1855", "1855–1881", "1881–1894", "1894–1917"]


def test_events_have_valid_emperor_and_note():
    assert len(EVENTS) >= 45
    for ev in EVENTS:
        assert ev.emperor_id in VALID_EMPEROR_IDS
        assert ev.title
        assert ev.note, f"event {ev.title} has no note"


def test_persons_have_valid_emperor_and_description():
    assert len(PERSONS) >= 40
    for p in PERSONS:
        assert p.emperor_id in VALID_EMPEROR_IDS
        assert p.name
        assert p.description, f"person {p.name} has no description"


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
    assert "Императоры России" in body
    assert "Тренажёр" in body
    assert "Александр I" in body
    assert "Николай II" in body
    assert "__DATA__" not in body, "data placeholder not substituted"


def test_emperors_page_contains_data():
    from api.index import app

    c = app.test_client()
    body = c.get("/emperors").get_data(as_text=True)
    assert "Манифест об отмене крепостного права" in body
    assert "М. И. Кутузов" in body
    assert '"alexander_ii"' in body
