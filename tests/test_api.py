import pytest
from backend.api import create_app
from backend.db import get_conn, init_db, create_session, finalize_session
import backend.state as state

@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, db_path

def test_index_returns_html(client):
    c, _ = client
    r = c.get("/")
    assert r.status_code == 200
    assert b"PostureMax" in r.data

def test_status_shape(client):
    c, _ = client
    r = c.get("/api/status")
    assert r.status_code == 200
    data = r.get_json()
    for key in ("connected", "posture_state", "delta_pitch", "delta_roll"):
        assert key in data

def test_session_current_shape(client):
    c, _ = client
    r = c.get("/api/session/current")
    assert r.status_code == 200
    data = r.get_json()
    assert "duration_s" in data

def test_history_empty(client):
    c, _ = client
    r = c.get("/api/session/history")
    assert r.status_code == 200
    assert r.get_json() == []

def test_history_returns_finished_sessions(client):
    c, db_path = client
    conn = get_conn(db_path)
    create_session(conn, "abc", "2026-04-25T10:00:00")
    finalize_session(conn, "abc", "2026-04-25T10:30:00",
                     1800.0, 1400.0, 77.8, 4.0, 2.0, 20.0, 77.8)
    r = c.get("/api/session/history")
    data = r.get_json()
    assert len(data) == 1
    assert data[0]["id"] == "abc"

def test_session_detail_not_found(client):
    c, _ = client
    r = c.get("/api/session/nonexistent")
    assert r.status_code == 404

def test_session_detail_found(client):
    c, db_path = client
    conn = get_conn(db_path)
    create_session(conn, "abc", "2026-04-25T10:00:00")
    finalize_session(conn, "abc", "2026-04-25T10:30:00",
                     1800.0, 1400.0, 77.8, 4.0, 2.0, 20.0, 77.8)
    r = c.get("/api/session/abc")
    assert r.status_code == 200
    data = r.get_json()
    assert data["session"]["id"] == "abc"
    assert isinstance(data["readings"], list)

def test_zero_sets_trigger(client):
    c, _ = client
    state.consume_zero_trigger()  # drain any leftover
    r = c.post("/api/zero")
    assert r.status_code == 200
    assert state.consume_zero_trigger() is True
