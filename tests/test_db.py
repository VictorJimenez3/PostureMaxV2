import os, sqlite3, tempfile
import pytest
from backend.db import (
    get_conn, init_db, create_session, insert_reading,
    finalize_session, get_session_history, get_session,
    get_session_readings,
)

@pytest.fixture
def conn(tmp_path):
    path = str(tmp_path / "test.db")
    c = get_conn(path)
    init_db(c)
    yield c
    c.close()

def test_tables_created(conn):
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    assert "sessions" in tables
    assert "readings" in tables

def test_create_and_get_session(conn):
    create_session(conn, "s1", "2026-04-25T10:00:00")
    row = get_session(conn, "s1")
    assert row["id"] == "s1"
    assert row["start_time"] == "2026-04-25T10:00:00"
    assert row["end_time"] is None

def test_insert_reading(conn):
    create_session(conn, "s1", "2026-04-25T10:00:00")
    insert_reading(conn, "s1", "2026-04-25T10:00:01",
                   "good", 2.0, 1.0, -10.0, 0.5, -12.0, -0.5)
    rows = get_session_readings(conn, "s1")
    assert len(rows) == 1
    assert rows[0]["posture_state"] == "good"
    assert rows[0]["delta_pitch"] == 2.0

def test_finalize_session(conn):
    create_session(conn, "s1", "2026-04-25T10:00:00")
    finalize_session(conn, "s1", "2026-04-25T10:30:00",
                     1800.0, 1440.0, 80.0, 3.5, 1.2, 22.1, 80.0)
    row = get_session(conn, "s1")
    assert row["score"] == 80.0
    assert row["end_time"] == "2026-04-25T10:30:00"

def test_history_excludes_open_sessions(conn):
    create_session(conn, "s1", "2026-04-25T10:00:00")  # open, no end_time
    create_session(conn, "s2", "2026-04-25T11:00:00")
    finalize_session(conn, "s2", "2026-04-25T11:30:00",
                     1800.0, 1400.0, 77.8, 4.0, 2.0, 20.0, 77.8)
    history = get_session_history(conn)
    assert len(history) == 1
    assert history[0]["id"] == "s2"

def test_history_ordered_newest_first(conn):
    create_session(conn, "old", "2026-04-20T10:00:00")
    finalize_session(conn, "old", "2026-04-20T10:30:00",
                     1800.0, 900.0, 50.0, 5.0, 3.0, 25.0, 50.0)
    create_session(conn, "new", "2026-04-25T10:00:00")
    finalize_session(conn, "new", "2026-04-25T10:30:00",
                     1800.0, 1440.0, 80.0, 2.0, 1.0, 18.0, 80.0)
    history = get_session_history(conn)
    assert history[0]["id"] == "new"
