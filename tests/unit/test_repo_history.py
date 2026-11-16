"""Tests for the Repo History Reader beta module."""

import datetime as dt
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

from api import repo_history as rh
from api.index import _AI_RATE_LIMITS, app


@pytest.fixture(autouse=True)
def _reset_ai_rate():
    _AI_RATE_LIMITS.clear()
    yield
    _AI_RATE_LIMITS.clear()


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _now_fn(dbapi_conn, _):
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
        created_via VARCHAR(32),
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS web_sessions (
        token VARCHAR(64) PRIMARY KEY,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS rate_limits (
        key TEXT NOT NULL,
        ts DOUBLE PRECISION NOT NULL
    );
    """
    with engine.connect() as conn:
        for stmt in ddl.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.commit()
    return engine


class _FakeResp:
    def __init__(self, status_code=200, payload=None, text_body=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text_body

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _commit(sha="a" * 40, message="feat: something", date="2026-11-10T12:00:00Z"):
    return {
        "sha": sha,
        "commit": {
            "author": {"name": "Dev", "date": date},
            "message": message,
        },
    }


def _ai_resp(text_body="## Итоги\nДобавлено что-то."):
    return _FakeResp(200, {"choices": [{"message": {"content": text_body}}]})


def _github_get_factory(commits_pages, mb_status=None):
    """Mock requests.get: GitHub commits API + raw memory_bank files."""
    mb_status = mb_status or {}

    def _get(url, **kwargs):
        if url.startswith("https://api.github.com/"):
            page = int(kwargs.get("params", {}).get("page", 1))
            idx = page - 1
            batch = commits_pages[idx] if idx < len(commits_pages) else []
            return _FakeResp(200, batch)
        if url.startswith("https://raw.githubusercontent.com/"):
            path = url.split("/HEAD/", 1)[1]
            status = mb_status.get(path, 404)
            return _FakeResp(status, text_body=f"content of {path}")
        raise AssertionError(f"unexpected url {url}")

    return _get


# ── pure functions ──


def test_parse_repo_url_valid():
    assert rh.parse_repo_url("https://github.com/lucasteamalt12321/GAL") == (
        "lucasteamalt12321",
        "GAL",
    )
    assert rh.parse_repo_url("https://github.com/user/repo.git") == ("user", "repo")
    assert rh.parse_repo_url("http://github.com/user/repo/") == ("user", "repo")


@pytest.mark.parametrize(
    "url",
    [
        "",
        None,
        "https://gitlab.com/user/repo",
        "https://github.com/user",
        "javascript:alert(1)",
        "https://127.0.0.1/user/repo",
        "https://github.com.evil.com/user/repo",
        "ftp://github.com/user/repo",
    ],
)
def test_parse_repo_url_invalid(url):
    with pytest.raises(rh.RepoHistoryError):
        rh.parse_repo_url(url)


def test_resolve_period_days():
    since, until, label = rh.resolve_period({"days": 7})
    today = dt.datetime.now(dt.timezone.utc).date()
    assert since == (today - dt.timedelta(days=7)).isoformat() + "T00:00:00Z"
    assert until == today.isoformat() + "T23:59:59Z"
    assert "7" in label


def test_resolve_period_default_and_bad_days():
    _, _, label = rh.resolve_period({})
    assert "7" in label
    for days in (0, -3, 400, "abc"):
        with pytest.raises(rh.RepoHistoryError):
            rh.resolve_period({"days": days})


def test_resolve_period_custom():
    since, until, label = rh.resolve_period(
        {"since": "2026-10-01", "until": "2026-10-31"}
    )
    assert since == "2026-10-01T00:00:00Z"
    assert until == "2026-10-31T23:59:59Z"
    assert "2026-10-01" in label and "2026-10-31" in label


@pytest.mark.parametrize(
    "data",
    [
        {"since": "2026-10-31", "until": "2026-10-01"},
        {"since": "01.10.2026", "until": "2026-10-31"},
        {"since": "2020-01-01", "until": "2026-01-01"},
        {"since": "2026-10-01", "until": "2999-01-01"},
    ],
)
def test_resolve_period_invalid(data):
    with pytest.raises(rh.RepoHistoryError):
        rh.resolve_period(data)


def test_fetch_commits_parses_and_stops_on_short_page():
    pages = [[_commit(message="feat: A"), _commit(sha="b" * 40, message="fix: B")]]
    with patch("api.repo_history.requests.get", side_effect=_github_get_factory(pages)):
        commits, truncated = rh.fetch_commits("u", "r", "s", "t")
    assert not truncated
    assert len(commits) == 2
    assert commits[0]["sha"] == "a" * 7
    assert commits[0]["author"] == "Dev"
    assert commits[0]["message"] == "feat: A"


def test_fetch_commits_truncates_at_cap():
    pages = [[_commit(sha=f"{i:040d}") for i in range(100)] for _ in range(3)]
    with patch("api.repo_history.requests.get", side_effect=_github_get_factory(pages)):
        commits, truncated = rh.fetch_commits("u", "r", "s", "t")
    assert truncated
    assert len(commits) == rh.MAX_COMMITS


def test_fetch_commits_errors():
    with patch("api.repo_history.requests.get", return_value=_FakeResp(404)):
        with pytest.raises(rh.RepoHistoryError) as ei:
            rh.fetch_commits("u", "r", "s", "t")
        assert ei.value.status == 404
    with patch("api.repo_history.requests.get", return_value=_FakeResp(403)):
        with pytest.raises(rh.RepoHistoryError) as ei:
            rh.fetch_commits("u", "r", "s", "t")
        assert ei.value.status == 429


def test_fetch_memory_bank_skips_missing():
    factory = _github_get_factory([], mb_status={"memory_bank/progress.md": 200})
    with patch("api.repo_history.requests.get", side_effect=factory):
        mb = rh.fetch_memory_bank("u", "r")
    assert list(mb) == ["memory_bank/progress.md"]
    assert "progress.md" in mb["memory_bank/progress.md"]


def test_build_prompt_contains_context_and_truncation_note():
    commits = [
        {
            "sha": "abc1234",
            "author": "Dev",
            "date": "2026-11-10T12:00:00Z",
            "message": "feat: X",
        }
    ]
    prompt = rh.build_prompt(
        "u", "r", commits, {"memory_bank/progress.md": "STATUS 77%"}, "7 дн.", False
    )
    assert "u/r" in prompt
    assert "feat: X" in prompt
    assert "STATUS 77%" in prompt
    assert "обрезан" not in prompt
    prompt2 = rh.build_prompt("u", "r", commits, {}, "7 дн.", True)
    assert "обрезан" in prompt2


def test_build_prompt_budget_drops_oldest():
    commits = [
        {
            "sha": f"{i:07d}",
            "author": "Dev",
            "date": "2026-11-10T12:00:00Z",
            "message": "x" * rh._MAX_MSG_CHARS,
        }
        for i in range(200)
    ]
    prompt = rh.build_prompt("u", "r", commits, {}, "7 дн.", False)
    assert "обрезан" in prompt
    assert "0000000" in prompt  # newest kept
    assert "0000199" not in prompt  # oldest dropped


# ── API / page ──


def test_page_renders():
    r = app.test_client().get("/repo_history")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    for marker in ("rhUrl", "rhPeriod", "rhGo", "/api/repo_history/analyze", "Бета"):
        assert marker in html


def test_hub_has_beta_card():
    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        r = app.test_client().get("/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'href="/repo_history"' in html
    assert "'/repo_history': 'repo_history'" in html


def test_analyze_success_anonymous():
    engine = _make_engine()
    pages = [[_commit(message="feat: новая фича")]]
    factory = _github_get_factory(pages, mb_status={"memory_bank/progress.md": 200})
    with (
        patch("api.index.get_db_engine", return_value=engine),
        patch("api.repo_history.requests.get", side_effect=factory),
        patch("api.index._ai_chat", return_value=_ai_resp()) as mock_ai,
    ):
        client = app.test_client()
        r = client.post(
            "/api/repo_history/analyze",
            json={"url": "https://github.com/u/r", "days": 7},
        )
    assert r.status_code == 200
    body = r.get_json()
    assert body["commit_count"] == 1
    assert body["repo"] == "u/r"
    assert body["memory_bank_files"] == ["memory_bank/progress.md"]
    assert "Итоги" in body["summary"]
    prompt = mock_ai.call_args[0][0]["messages"][0]["content"]
    assert "feat: новая фича" in prompt
    assert "content of memory_bank/progress.md" in prompt


def test_analyze_invalid_url():
    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        r = app.test_client().post(
            "/api/repo_history/analyze", json={"url": "https://gitlab.com/u/r"}
        )
    assert r.status_code == 400
    assert "GitHub" in r.get_json()["error"]


def test_analyze_no_commits_skips_ai():
    engine = _make_engine()
    with (
        patch("api.index.get_db_engine", return_value=engine),
        patch(
            "api.repo_history.requests.get",
            side_effect=_github_get_factory([[]]),
        ),
        patch("api.index._ai_chat") as mock_ai,
    ):
        r = app.test_client().post(
            "/api/repo_history/analyze",
            json={"url": "https://github.com/u/r", "days": 7},
        )
    assert r.status_code == 200
    assert r.get_json()["commit_count"] == 0
    assert "не найдено" in r.get_json()["summary"]
    mock_ai.assert_not_called()


def test_analyze_ai_unavailable():
    engine = _make_engine()
    with (
        patch("api.index.get_db_engine", return_value=engine),
        patch(
            "api.repo_history.requests.get",
            side_effect=_github_get_factory([[_commit()]]),
        ),
        patch("api.index._ai_chat", return_value=None),
    ):
        r = app.test_client().post(
            "/api/repo_history/analyze",
            json={"url": "https://github.com/u/r", "days": 7},
        )
    assert r.status_code == 502


def test_analyze_anon_rate_limit_and_user_higher():
    engine = _make_engine()
    factory = _github_get_factory([[_commit()]])
    with (
        patch("api.index.get_db_engine", return_value=engine),
        patch("api.repo_history.requests.get", side_effect=factory),
        patch("api.index._ai_chat", return_value=_ai_resp()),
    ):
        client = app.test_client()
        for _ in range(3):
            r = client.post(
                "/api/repo_history/analyze",
                json={"url": "https://github.com/u/r", "days": 7},
            )
            assert r.status_code == 200
        r = client.post(
            "/api/repo_history/analyze",
            json={"url": "https://github.com/u/r", "days": 7},
        )
        assert r.status_code == 429
        # зарегистрированный пользователь не упирается в анонимный лимит
        reg = client.post(
            "/api/auth/register",
            json={"login": "rh_user", "password": "pass1234"},
        )
        token = reg.get_json().get("token")
        r = client.post(
            "/api/repo_history/analyze",
            json={"url": "https://github.com/u/r", "days": 7},
            headers={"X-Auth-Token": token},
        )
        assert r.status_code == 200


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_page_js_syntax():
    html = app.test_client().get("/repo_history").get_data(as_text=True)
    scripts = []
    rest = html
    while "<script>" in rest:
        start = rest.index("<script>") + len("<script>")
        end = rest.index("</script>", start)
        scripts.append(rest[start:end])
        rest = rest[end:]
    assert scripts
    with tempfile.TemporaryDirectory() as tmp:
        for i, js in enumerate(scripts):
            path = f"{tmp}/s{i}.js"
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(js)
            proc = subprocess.run(
                ["node", "--check", path], capture_output=True, text=True
            )
            assert proc.returncode == 0, proc.stderr
