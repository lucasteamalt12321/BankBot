"""Unit tests for the core.informatics (informatics) module and the /informatics web page."""

from core.informatics import (
    MATH_TOPICS,
    task_by_id,
    tasks_for_topic,
    get_random_task,
    get_tasks_by_difficulty,
)

ALL_TASK_IDS = [task.id for topic in MATH_TOPICS for task in topic.tasks]


def test_topics_count():
    assert len(MATH_TOPICS) == 9


def test_topic_ids():
    assert [t.id for t in MATH_TOPICS] == [
        "lesson1", "lesson2", "lesson3", "lesson4", "lesson5",
        "lesson6", "lesson7", "lesson8", "lesson9",
    ]


def test_topic_names_in_russian():
    for t in MATH_TOPICS:
        assert t.name, f"topic {t.id} has no name"
        assert t.description, f"topic {t.id} has no description"
        assert len(t.tasks) == 5, f"topic {t.id} should have 5 tasks, got {len(t.tasks)}"


def test_task_ids_unique():
    assert len(ALL_TASK_IDS) == len(set(ALL_TASK_IDS))


def test_task_fields_filled():
    for task_id in ALL_TASK_IDS:
        task = task_by_id(task_id)
        assert task is not None
        assert task.question, f"task {task_id} has no question"
        assert task.answer is not None, f"task {task_id} has no answer"
        assert task.explanation, f"task {task_id} has no explanation"
        assert task.difficulty in ("легкая", "средняя", "сложная")


def test_every_topic_id_matches_prefix():
    for task_id in ALL_TASK_IDS:
        prefix = task_id.split("_")[0]
        assert prefix in {t.id for t in MATH_TOPICS}, f"task {task_id} has unknown prefix"


def test_task_by_id():
    assert task_by_id("lesson1_o1").id == "lesson1_o1"
    assert task_by_id("nope") is None


def test_tasks_for_topic():
    tasks = tasks_for_topic("lesson2")
    assert tasks is not None and len(tasks) == 5
    assert tasks_for_topic("nope") is None


def test_get_random_task():
    for _ in range(20):
        task = get_random_task()
        assert task.id in ALL_TASK_IDS


def test_get_tasks_by_difficulty():
    easy = get_tasks_by_difficulty("легкая")
    assert easy
    for task in easy:
        assert task.difficulty == "легкая"
    assert get_tasks_by_difficulty("nope") == ()


def test_informatics_page_renders(client=None):
    from api.index import app

    c = app.test_client()
    resp = c.get("/informatics")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Информатика" in body
    assert "Изучить" in body
    assert "Тренажер" in body
    assert "ОГЭ" in body
    assert "lesson1" in body
    assert "__TOPICS_DATA__" not in body, "topics data placeholder not substituted"
    assert "__FIRST_TOPIC__" not in body, "first topic placeholder not substituted"
    assert "{topic.name}" not in body, "JS template literal not interpolated"
    assert "* {{ margin" not in body, "CSS contains f-string double braces ({{ }})"
    assert "* { margin" in body, "CSS is invalid: single braces expected"


def test_math_url_redirects_to_informatics():
    from api.index import app

    c = app.test_client()
    resp = c.get("/math")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/informatics")


def test_informatics_page_contains_topic_data():
    from api.index import app
    import json
    import re

    c = app.test_client()
    body = c.get("/informatics").get_data(as_text=True)
    m = re.search(r"const topicsData = (\{.*?\});\n", body, re.S)
    assert m, "topicsData JS object not found"
    data = json.loads(m.group(1))
    topic_ids = {t["id"] for t in data["topics"]}
    assert topic_ids == {t.id for t in MATH_TOPICS}
    for t in data["topics"]:
        assert t["name"] in body
        assert len(t["tasks"]) == 5, f"topic {t['id']} should expose 5 tasks"
        for task in t["tasks"]:
            assert task["question"]
            assert task["answer"] is not None
            assert task["explanation"]
    assert len(data["allTaskIds"]) == len(ALL_TASK_IDS)