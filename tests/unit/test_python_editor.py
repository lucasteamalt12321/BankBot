"""Tests for the Python Editor module (/editor): documents, jedi hints, sandbox run."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from api.index import app, _ensure_pyed_tables


@pytest.fixture(autouse=True)
def _reset_ai_rate():
    from api.index import _AI_RATE_LIMITS
    _AI_RATE_LIMITS.clear()
    yield
    _AI_RATE_LIMITS.clear()


def _make_engine():
    """In-memory SQLite engine with only the auth + rate-limit tables.

    ``pyed_documents`` is created by the production ``_ensure_pyed_tables`` so the
    real DDL (and its SQLite rewriting) is exercised by every test.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
    _ensure_pyed_tables(engine)
    return engine


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _register(client, login):
    r = client.post(
        "/api/auth/register",
        json={"login": login, "password": "pass1234", "email": f"{login}@test.local"},
    )
    body = r.get_json()
    assert r.status_code == 200, body
    return body["token"]


def _user_id(engine, login):
    with engine.connect() as conn:
        return int(conn.execute(
            text("SELECT id FROM web_users WHERE login = :l"), {"l": login}
        ).scalar())


def _rows(engine, sql, params=None):
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params or {}).mappings().fetchall()]


def _fill_rate_limit(engine, key, count):
    """Pre-fill the limiter with fresh rows (stale ones get pruned by the helper)."""
    import time
    now = time.time()
    with engine.begin() as conn:
        for _ in range(count):
            conn.execute(text("INSERT INTO rate_limits (key, ts) VALUES (:k, :ts)"),
                         {"k": key, "ts": now})


def _require_jedi():
    return pytest.importorskip("jedi", reason="jedi is required for LSP hints")


# ── DDL + page ────────────────────────────────────────────────────────────

def test_pyed_ddl_is_idempotent():
    """``_ensure_pyed_tables`` must be safe to call on every cold start."""
    engine = _make_engine()
    _ensure_pyed_tables(engine)
    _ensure_pyed_tables(engine)
    indexes = _rows(engine, "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'pyed_documents'")
    names = {row["name"] for row in indexes}
    assert "uq_pyed_documents_user_name" in names
    assert "ix_pyed_documents_user" in names


def test_editor_page_renders():
    _make_engine()
    client = app.test_client()
    r = client.get("/editor")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Редактор Python" in body
    assert "codemirror@6.0.1" in body
    assert "@codemirror/lang-python" in body
    assert "/api/pyed/complete" in body
    assert "__DEFAULT_CODE__" not in body
    assert "__KEYWORDS__" not in body
    assert "__PLACEHOLDER__" not in body


# ── documents CRUD ────────────────────────────────────────────────────────

def test_documents_crud():
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _register(client, "pyed_user")

        r = client.post("/api/pyed/documents", json={"name": "main.py", "content": "print(1)"},
                        headers=_auth(token))
        assert r.status_code == 200, r.get_json()
        doc_id = r.get_json()["id"]
        assert r.get_json()["reopened"] is False

        r = client.get(f"/api/pyed/documents/{doc_id}", headers=_auth(token))
        assert r.status_code == 200
        assert r.get_json()["content"] == "print(1)"

        r = client.put(f"/api/pyed/documents/{doc_id}", json={"content": "print(2)"},
                       headers=_auth(token))
        assert r.status_code == 200
        assert _rows(engine, "SELECT content FROM pyed_documents WHERE id = :i", {"i": doc_id})[0]["content"] == "print(2)"

        r = client.get("/api/pyed/documents", headers=_auth(token))
        assert r.status_code == 200
        assert [d["name"] for d in r.get_json()["documents"]] == ["main.py"]

        r = client.delete(f"/api/pyed/documents/{doc_id}", headers=_auth(token))
        assert r.status_code == 200
        assert _rows(engine, "SELECT id FROM pyed_documents") == []

        assert client.delete(f"/api/pyed/documents/{doc_id}", headers=_auth(token)).status_code == 404


def test_documents_isolated_between_users():
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        owner = _register(client, "pyed_owner")
        other = _register(client, "pyed_other")
        doc_id = client.post("/api/pyed/documents", json={"name": "secret.py", "content": "x = 1"},
                             headers=_auth(owner)).get_json()["id"]

        assert client.get(f"/api/pyed/documents/{doc_id}", headers=_auth(other)).status_code == 404
        assert client.put(f"/api/pyed/documents/{doc_id}", json={"content": "y = 2"},
                          headers=_auth(other)).status_code == 404
        assert client.delete(f"/api/pyed/documents/{doc_id}", headers=_auth(other)).status_code == 404
        assert client.get("/api/pyed/documents", headers=_auth(other)).get_json()["documents"] == []
        assert _rows(engine, "SELECT content FROM pyed_documents")[0]["content"] == "x = 1"


def test_document_create_reopens_existing_name():
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _register(client, "pyed_reopen")
        first = client.post("/api/pyed/documents", json={"name": "a.py", "content": "1"},
                            headers=_auth(token)).get_json()
        second = client.post("/api/pyed/documents", json={"name": "a.py", "content": "2"},
                             headers=_auth(token)).get_json()
        assert second["id"] == first["id"]
        assert second["reopened"] is True
        assert _rows(engine, "SELECT content FROM pyed_documents")[0]["content"] == "2"


def test_document_name_is_sanitised():
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _register(client, "pyed_name")
        r = client.post("/api/pyed/documents", json={"name": " ../../etc/passwd  ", "content": ""},
                        headers=_auth(token))
        assert r.status_code == 200, r.get_json()
        assert r.get_json()["name"] == "passwd"
        assert client.post("/api/pyed/documents", json={"name": "   "},
                           headers=_auth(token)).status_code == 400


def test_document_rename_conflict_rejected():
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _register(client, "pyed_rename")
        a = client.post("/api/pyed/documents", json={"name": "a.py", "content": ""},
                        headers=_auth(token)).get_json()["id"]
        b = client.post("/api/pyed/documents", json={"name": "b.py", "content": ""},
                        headers=_auth(token)).get_json()["id"]
        r = client.put(f"/api/pyed/documents/{a}", json={"content": "", "name": "b.py"},
                       headers=_auth(token))
        assert r.status_code == 409
        assert _rows(engine, "SELECT name FROM pyed_documents WHERE id = :i", {"i": b})[0]["name"] == "b.py"


def test_unauthenticated_requests_get_login_modal_flag():
    """A bare 401 would render a banner; ``auth_required`` opens the login modal."""
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        for path, method in (
            ("/api/pyed/documents", "get"),
            ("/api/pyed/documents", "post"),
            ("/api/pyed/documents/1", "put"),
            ("/api/pyed/documents/1", "delete"),
            ("/api/pyed/complete", "post"),
            ("/api/pyed/signature", "post"),
            ("/api/pyed/hover", "post"),
            ("/api/pyed/lint", "post"),
            ("/api/pyed/run", "post"),
        ):
            r = getattr(client, method)(path, json={})
            assert r.status_code == 401, path
            assert r.get_json()["auth_required"] is True, path


# ── LSP hints (jedi) ──────────────────────────────────────────────────────

def test_complete_after_dot():
    _require_jedi()
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _register(client, "pyed_lsp")
        code = 's = "a"\ns.up'
        r = client.post("/api/pyed/complete", json={"code": code, "line": 2, "column": 4},
                        headers=_auth(token))
        assert r.status_code == 200, r.get_json()
        labels = {item["label"] for item in r.get_json()["items"]}
        assert "upper" in labels
        upper = next(i for i in r.get_json()["items"] if i["label"] == "upper")
        assert upper["type"] in ("method", "function")
        assert "upper" in (upper["doc"] or "").lower()


def test_complete_returns_builtin_and_keywords():
    _require_jedi()
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _register(client, "pyed_kw")
        r = client.post("/api/pyed/complete", json={"code": "pri", "line": 1, "column": 3},
                        headers=_auth(token))
        assert r.status_code == 200
        labels = {item["label"] for item in r.get_json()["items"]}
        assert "print" in labels


def test_complete_on_user_symbol_carries_docstring():
    _require_jedi()
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _register(client, "pyed_sym")
        code = 'def area(r: float) -> float:\n    """Площадь круга."""\n    return 3.14 * r * r\n\nare'
        r = client.post("/api/pyed/complete", json={"code": code, "line": 5, "column": 3},
                        headers=_auth(token))
        assert r.status_code == 200
        item = next((i for i in r.get_json()["items"] if i["label"] == "area"), None)
        assert item is not None
        assert "Площадь круга" in (item["doc"] or "")


def test_lint_reports_syntax_error():
    _require_jedi()
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _register(client, "pyed_lint")
        r = client.post("/api/pyed/lint", json={"code": "def broken(:\n    pass"}, headers=_auth(token))
        assert r.status_code == 200
        errors = r.get_json()["errors"]
        assert errors
        assert errors[0]["line"] >= 1
        assert errors[0]["message"]

        ok = client.post("/api/pyed/lint", json={"code": "x = 1\nprint(x)\n"}, headers=_auth(token))
        assert ok.get_json()["errors"] == []


def test_lint_without_jedi_falls_back_to_compile(monkeypatch):
    """A broken/absent jedi must still surface the SyntaxError from ``compile``."""
    import builtins
    engine = _make_engine()
    from unittest.mock import patch
    real_import = builtins.__import__

    def _no_jedi(name, *args, **kwargs):
        if name == "jedi":
            raise ImportError("no jedi")
        return real_import(name, *args, **kwargs)

    with patch("api.index.get_db_engine", return_value=engine), \
            patch("builtins.__import__", side_effect=_no_jedi):
        client = app.test_client()
        token = _register(client, "pyed_nojedi")
        r = client.post("/api/pyed/lint", json={"code": "if True\n    pass"}, headers=_auth(token))
        assert r.status_code == 200
        errors = r.get_json()["errors"]
        assert errors and "expected" in errors[0]["message"].lower()

        done = client.post("/api/pyed/lint", json={"code": "x = 1"}, headers=_auth(token))
        assert done.get_json()["errors"] == []


def test_hover_returns_type_and_docstring():
    _require_jedi()
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _register(client, "pyed_hover")
        code = 'def area(r):\n    """Площадь."""\n    return r\n\narea(2)\n'
        # head of the call on line 5
        r = client.post("/api/pyed/hover", json={"code": code, "line": 5, "column": 2},
                        headers=_auth(token))
        assert r.status_code == 200
        body = r.get_json()
        assert "area" in body["text"]
        assert "Площадь" in body["doc"]
        assert body["goto"] and body["goto"]["line"] == 1


def test_signature_help_lists_arguments():
    _require_jedi()
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _register(client, "pyed_sig")
        code = 'def add(a, b=2):\n    """Сумма."""\n    return a + b\n\nadd('
        r = client.post("/api/pyed/signature", json={"code": code, "line": 5, "column": 4},
                        headers=_auth(token))
        assert r.status_code == 200
        sigs = r.get_json()["signatures"]
        assert sigs
        assert "add" in sigs[0]["label"]
        assert "a" in sigs[0]["label"]


def test_lsp_endpoints_degrade_without_jedi():
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine), \
            patch("api.index._pyed_script", return_value=(None, None)):
        client = app.test_client()
        token = _register(client, "pyed_deg")
        complete = client.post("/api/pyed/complete", json={"code": "pri", "line": 1, "column": 3},
                               headers=_auth(token))
        assert complete.status_code == 200
        assert complete.get_json()["items"] == []
        assert complete.get_json()["degraded"] is True
        for path in ("/api/pyed/hover", "/api/pyed/signature"):
            r = client.post(path, json={"code": "x = 1", "line": 1, "column": 0}, headers=_auth(token))
            assert r.status_code == 200, path


def _drain_rate_limits(engine):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM rate_limits"))


def test_lsp_rate_limit():
    _require_jedi()
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _register(client, "pyed_rate")
        uid = _user_id(engine, "pyed_rate")
        _fill_rate_limit(engine, f"pyed_lsp_{uid}", 300)
        r = client.post("/api/pyed/complete", json={"code": "pri", "line": 1, "column": 3},
                        headers=_auth(token))
        assert r.status_code == 429
        assert r.get_json()["ok"] is False
        _drain_rate_limits(engine)


# ── sandbox run ───────────────────────────────────────────────────────────

def test_run_returns_stdout():
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _register(client, "pyed_run")
        r = client.post("/api/pyed/run", json={"code": "print(2 + 2)"}, headers=_auth(token))
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert body["ok"] is True
        assert body["stdout"] == "4"
        assert body["ms"] >= 0


def test_run_reports_stderr():
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _register(client, "pyed_err")
        r = client.post("/api/pyed/run", json={"code": "1 / 0"}, headers=_auth(token))
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is False
        assert "ZeroDivisionError" in body["stderr"]


def test_run_blocks_dangerous_imports():
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _register(client, "pyed_block")
        for code, marker in (
            ("import os\nos.listdir('/')", "Blocked: import os"),
            ("from subprocess import run", "Blocked: from subprocess import is not allowed"),
            ("eval('1+1')", "Blocked: eval() is not allowed"),
        ):
            r = client.post("/api/pyed/run", json={"code": code}, headers=_auth(token))
            assert r.status_code == 200, code
            assert r.get_json()["ok"] is False
            assert marker in r.get_json()["error"], code


def test_run_rejects_empty_and_oversized_code():
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _register(client, "pyed_size")
        assert client.post("/api/pyed/run", json={"code": "   "}, headers=_auth(token)).status_code == 400
        big = "x = 1\n" * 40000
        r = client.post("/api/pyed/run", json={"code": big}, headers=_auth(token))
        assert r.status_code == 400
        assert "большой" in r.get_json()["error"]


def test_run_rate_limit():
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _register(client, "pyed_runrate")
        uid = _user_id(engine, "pyed_runrate")
        _fill_rate_limit(engine, f"pyed_run_{uid}", 20)
        r = client.post("/api/pyed/run", json={"code": "print(1)"}, headers=_auth(token))
        assert r.status_code == 429
        _drain_rate_limits(engine)


def test_sandbox_core_keeps_legacy_string_contract():
    """``_tool_run_python`` must keep its plain-string output for the AI chat."""
    from api.index import _tool_run_python
    assert _tool_run_python("print('hi')") == "hi"
    assert _tool_run_python("1/0").startswith("STDERR:")
    assert _tool_run_python("import os") == "Blocked: import os is not allowed"
    assert _tool_run_python("   ") == "empty code"
    assert _tool_run_python("def f(:") == "Syntax error in code"
    assert _tool_run_python("pass") == "(no output)"


# ── integration with the admin delete-user endpoint ───────────────────────

def test_admin_delete_user_removes_editor_documents():
    engine = _make_engine()
    from unittest.mock import patch
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        admin = _register(client, "pyed_admin")
        victim = _register(client, "pyed_victim")
        admin_id = _user_id(engine, "pyed_admin")
        victim_id = _user_id(engine, "pyed_victim")
        with engine.begin() as conn:
            conn.execute(text("UPDATE web_users SET is_admin = 1 WHERE id = :i"), {"i": admin_id})
        client.post("/api/pyed/documents", json={"name": "victim.py", "content": "x = 1"},
                    headers=_auth(victim))
        assert _rows(engine, "SELECT id FROM pyed_documents")

        r = client.delete(f"/api/admin/users/{victim_id}", headers=_auth(admin))
        assert r.status_code == 200, r.get_json()
        assert _rows(engine, "SELECT id FROM pyed_documents") == []
        assert _rows(engine, "SELECT id FROM web_users WHERE id = :i", {"i": victim_id}) == []
