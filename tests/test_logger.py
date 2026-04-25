import time
from unittest.mock import patch
import pytest
from backend.db import get_conn, init_db, get_session, get_session_readings
from backend.logger import SessionLogger

@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    conn = get_conn(path)
    init_db(conn)
    return conn

def test_start_session_creates_db_row(db):
    lg = SessionLogger(db)
    sid = lg.start_session()
    row = get_session(db, sid)
    assert row is not None
    assert row["end_time"] is None

def test_record_downsamples_to_1hz(db):
    lg = SessionLogger(db)
    sid = lg.start_session()
    # monotonic returns: 0.0, 0.5, 1.1, 1.5, 2.2 for the five record calls
    with patch("backend.logger.time.monotonic",
               side_effect=[0.0, 0.5, 1.1, 1.5, 2.2]):
        lg.record("good", 2.0, 0.5, -10.0, 0.0, -12.0, -0.5)  # t=0.0 → logs
        lg.record("good", 2.0, 0.5, -10.0, 0.0, -12.0, -0.5)  # t=0.5 → skip
        lg.record("good", 2.0, 0.5, -10.0, 0.0, -12.0, -0.5)  # t=1.1 → logs
        lg.record("good", 2.0, 0.5, -10.0, 0.0, -12.0, -0.5)  # t=1.5 → skip
        lg.record("good", 2.0, 0.5, -10.0, 0.0, -12.0, -0.5)  # t=2.2 → logs
    rows = get_session_readings(db, sid)
    assert len(rows) == 3

def test_end_session_finalizes_stats(db):
    lg = SessionLogger(db)
    sid = lg.start_session()
    with patch("backend.logger.time.monotonic", side_effect=[0.0, 1.1]):
        lg.record("slouching_forward", 18.0, 1.0, -5.0, 0.0, -23.0, -1.0)
        lg.record("good", 3.0, 0.5, -10.0, 0.0, -13.0, -0.5)
    lg.end_session()
    row = get_session(db, sid)
    assert row["end_time"] is not None
    assert row["score"] is not None
    # 1 out of 2 logged rows is good → 50%
    assert abs(row["good_pct"] - 50.0) < 0.01

def test_record_before_start_is_noop(db):
    lg = SessionLogger(db)
    # should not raise
    lg.record("good", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
