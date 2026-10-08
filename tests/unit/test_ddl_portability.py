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


# --- сериализация холодного старта ------------------------------------------
#
# Vercel поднимает несколько инстансов одновременно, и два параллельных
# _ensure_* на одной таблице уходили в DeadlockDetected. Лок обязан быть
# ПЕРВОЙ командой соединения: после CREATE/DELETE таблица уже занята другим
# процессом, и взаимное ожидание "таблица <-> advisory lock" и есть deadlock.


class _SpyResult:
    def first(self):
        return None

    def all(self):
        return []


class _SpyConn:
    def __init__(self):
        self.statements: list[str] = []

    def execute(self, statement, *args, **kwargs):
        # Параметры тоже пишем: ключ advisory-локи уезжает биндом, а не текстом.
        self.statements.append(f"{statement} || args={args} kwargs={kwargs}")
        return _SpyResult()

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _SpyEngine:
    """Минимальный engine: пишет SQL по соединениям, ничего не выполняет."""

    def __init__(self, name="postgresql"):
        from types import SimpleNamespace

        self.dialect = SimpleNamespace(name=name)
        self.connections: list[_SpyConn] = []

    def connect(self):
        conn = _SpyConn()
        self.connections.append(conn)
        return conn


def test_universe_ddl_takes_advisory_lock_before_any_ddl():
    import api.index as idx
    from unittest.mock import patch

    engine = _SpyEngine()
    with patch.object(idx, "log_error", lambda *a, **k: None):
        idx._ensure_universe_tables(engine)

    first = engine.connections[0].statements[0]
    assert "pg_advisory_xact_lock" in first, engine.connections[0].statements
    # Ключ ровно тот, что держался в проде, и берётся до CREATE TABLE.
    assert str(idx._LOCK_UNIVERSE) in first
    assert "CREATE TABLE" not in first


def test_dnd_ddl_takes_advisory_lock_before_any_ddl():
    import api.index as idx
    from unittest.mock import patch

    engine = _SpyEngine()
    with patch.object(idx, "log_error", lambda *a, **k: None):
        idx._ensure_dnd_tables(engine)

    main = engine.connections[0]
    assert "pg_advisory_xact_lock" in main.statements[0], main.statements
    assert str(idx._LOCK_DND) in main.statements[0]
    # Отдельный ключ от universe: порядок взятия одинаков во всех процессах,
    # каскадного ожидания "лок A ждёт лок B, лок B ждёт лок A" не бывает.
    assert idx._LOCK_DND != idx._LOCK_UNIVERSE


def test_advisory_lock_is_skipped_on_sqlite():
    import api.index as idx

    engine = _SpyEngine(name="sqlite")
    idx._pg_advisory_lock(engine.connect(), engine, idx._LOCK_DND)
    assert engine.connections[0].statements == []


def test_ensure_universe_tables_idempotent_on_sqlite(tmp_path):
    import api.index as idx
    from unittest.mock import patch
    from sqlalchemy import create_engine, text

    sq = create_engine(f"sqlite:///{tmp_path / 'universe.db'}")
    logged = []
    with patch.object(idx, "log_error", lambda tag, lvl, msg: logged.append(msg)):
        for _ in range(2):
            idx._ensure_universe_tables(sq)
    assert not [m for m in logged if "error" in m.lower()], logged
    with sq.connect() as conn:
        rows = conn.execute(text("SELECT count(*) FROM daily_prayer_log")).scalar()
        idx_row = conn.execute(text(
            "SELECT count(*) FROM sqlite_master WHERE type='index' AND name='ux_daily_prayer_log_user_date'"
        )).scalar()
    assert rows == 0
    # Дедуп раньше падал на SQLite (`DELETE ... USING` - не его синтаксис),
    # из-за чего уникальный индекс там не создавался вовсе.
    assert idx_row == 1


def test_universe_dedup_drops_duplicate_rows_before_unique_index(tmp_path):
    """Таблица, созданная миграцией 009 (без inline UNIQUE), держит дубли.

    Их обязан почистить дедуп, иначе CREATE UNIQUE INDEX не пройдёт.
    """
    import api.index as idx
    from unittest.mock import patch
    from sqlalchemy import create_engine, text

    sq = create_engine(f"sqlite:///{tmp_path / 'dupes.db'}")
    with sq.begin() as conn:
        conn.execute(text("CREATE TABLE daily_prayer_log (user_id BIGINT NOT NULL, prayer_date DATE NOT NULL)"))
        conn.execute(text(
            "INSERT INTO daily_prayer_log VALUES (1, '2026-01-01'), (1, '2026-01-01'), (2, '2026-01-02')"
        ))

    logged = []
    with patch.object(idx, "log_error", lambda tag, lvl, msg: logged.append(msg)):
        idx._ensure_universe_tables(sq)

    assert not [m for m in logged if "error" in m.lower()], logged
    with sq.connect() as conn:
        rows = conn.execute(text(
            "SELECT user_id, prayer_date FROM daily_prayer_log ORDER BY user_id"
        )).all()
    assert [(r[0], r[1]) for r in rows] == [(1, "2026-01-01"), (2, "2026-01-02")]