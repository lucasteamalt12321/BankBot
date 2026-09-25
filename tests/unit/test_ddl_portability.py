def test_ddl_preserves_native_syntax_on_postgres():
    import api.index as idx
    from sqlalchemy import create_engine

    pg = create_engine("postgresql://u:p@h/db")  # engine object only, no connect
    sql = "CREATE TABLE IF NOT EXISTS web_users (id SERIAL PRIMARY KEY, login VARCHAR(64) UNIQUE,\ncreated_at TIMESTAMPTZ DEFAULT NOW())"
    out = idx._ddl(sql, pg)
    assert "SERIAL PRIMARY KEY" in out
    assert "AUTOINCREMENT" not in out
    assert "TIMESTAMPTZ" in out
    assert "NOW()" in out

    alt = idx._ddl("ALTER TABLE t ADD COLUMN IF NOT EXISTS col BIGINT", pg)
    assert "ADD COLUMN IF NOT EXISTS" in alt


def test_ddl_rewrites_for_sqlite():
    import api.index as idx
    from sqlalchemy import create_engine

    sq = create_engine("sqlite://")
    sql = "CREATE TABLE IF NOT EXISTS web_users (id SERIAL PRIMARY KEY, login VARCHAR(64) UNIQUE,\ncreated_at TIMESTAMPTZ DEFAULT NOW())"
    out = idx._ddl(sql, sq)
    assert "INTEGER PRIMARY KEY AUTOINCREMENT" in out
    assert "SERIAL" not in out
    assert "TIMESTAMP" in out and "TIMESTAMPTZ" not in out
    assert "CURRENT_TIMESTAMP" in out

    alt = idx._ddl("ALTER TABLE t ADD COLUMN IF NOT EXISTS col BIGINT", sq)
    assert "ADD COLUMN IF NOT EXISTS" not in alt
    assert "ADD COLUMN col BIGINT" in alt


def test_ensure_tables_idempotent_on_sqlite(tmp_path):
    import api.index as idx
    from unittest.mock import patch
    from sqlalchemy import create_engine, text

    sq = create_engine(f"sqlite:///{tmp_path / 'ddl.db'}")
    logged = []

    def _cap(tag, lvl, msg):
        logged.append(msg)

    with patch.object(idx, "log_error", _cap):
        for _ in range(2):
            idx._ensure_web_auth_tables(sq)
            idx._ensure_social_tables(sq)
            idx._ensure_family_tables(sq)
    assert not [m for m in logged if "error" in m.lower() or "Traceback" in m], logged
    with sq.connect() as conn:
        tables = [r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).all()]
    assert {"web_users", "friend_requests", "rooms"} <= set(tables)


def test_ensure_ddl_column_is_noop_when_column_exists():
    import api.index as idx
    from sqlalchemy import create_engine, text

    sq = create_engine("sqlite://", connect_args={"check_same_thread": False})
    with sq.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, col TEXT DEFAULT 'x')"))
    with sq.connect() as conn:
        idx._ensure_ddl_column(conn, "t", "col TEXT DEFAULT 'x'", sq)
        idx._ensure_ddl_column(conn, "t", "extra INTEGER DEFAULT 0", sq)
        conn.commit()
    with sq.connect() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(t)")).all()}
    assert "extra" in cols