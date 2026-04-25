# PostureMax V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete PostureMax V2 system — ESP32-C3 firmware for dual-sensor BLE streaming, a Python backend for classification and logging, and a web dashboard for real-time monitoring and session history.

**Architecture:** The firmware runs Madgwick sensor fusion at 100Hz and streams 4 raw filtered angles over BLE notifications. The Python backend receives angles via bleak (in a background asyncio thread), computes corrected relative deltas, classifies posture with threshold logic, logs to SQLite at 1Hz, and exposes a Flask REST API. The dashboard is a plain HTML/JS/CSS SPA served by Flask, polling the API at 200ms and rendering charts with Chart.js.

**Tech Stack:** Arduino/C++ (ESP32-C3, MadgwickAHRS, ESP32 BLE Arduino), Python 3 (bleak, Flask, sqlite3, pytest), HTML/CSS/JavaScript (Chart.js CDN)

---

## File Map

```
PostureMaxV2/
├── backend/
│   ├── config.py          # BLE UUIDs, thresholds, constants
│   ├── db.py              # SQLite schema, init, CRUD queries
│   ├── classifier.py      # threshold-based posture classification
│   ├── state.py           # thread-safe shared live state (BLE thread ↔ Flask)
│   ├── ble_client.py      # bleak async BLE client, packet parsing, zero capture
│   ├── logger.py          # 1Hz downsampled session logging + stats
│   ├── api.py             # Flask app factory + REST routes
│   ├── main.py            # entry point: BLE thread + Flask server
│   ├── templates/
│   │   └── index.html     # SPA dashboard (Live Monitor + Session History)
│   └── static/
│       ├── style.css      # clinical minimalist design
│       └── app.js         # polling, gauges, Chart.js history
├── tests/
│   ├── __init__.py
│   ├── test_classifier.py
│   ├── test_db.py
│   ├── test_logger.py
│   └── test_api.py
├── firmware/
│   └── PostureMax/
│       └── PostureMax.ino # full firmware: I2C, Madgwick, BLE notify + zero char
└── requirements.txt
```

---

## Task 1: Project Scaffold + Config

**Files:**
- Create: `requirements.txt`
- Create: `backend/__init__.py`
- Create: `tests/__init__.py`
- Create: `backend/config.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p backend/templates backend/static tests firmware/PostureMax
touch backend/__init__.py tests/__init__.py
```

- [ ] **Step 2: Write requirements.txt**

```
bleak>=0.21.0
flask>=3.0.0
pytest>=8.0.0
```

- [ ] **Step 3: Write backend/config.py**

```python
DEVICE_NAME = "PostureMax"

SERVICE_UUID = "12345678-1234-1234-1234-123456789abc"
NOTIFY_UUID  = "12345678-1234-1234-1234-123456789abd"
ZERO_UUID    = "12345678-1234-1234-1234-123456789abe"

SLOUCH_THRESHOLD  = 15.0   # degrees forward flex
LATERAL_THRESHOLD = 10.0   # degrees lateral lean

LOG_INTERVAL_S  = 1.0    # downsample: log once per second
SETTLE_TIME_S   = 2.0    # discard first 2s after BLE connect (Madgwick settling)
ZERO_DURATION_S = 5.0    # average over 5s for reference capture

DB_PATH = "posturemax.db"
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: packages install without error.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt backend/__init__.py backend/config.py tests/__init__.py
git commit -m "feat: project scaffold and config"
```

---

## Task 2: Posture Classifier (TDD)

**Files:**
- Create: `backend/classifier.py`
- Create: `tests/test_classifier.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_classifier.py
import pytest
from backend.classifier import classify
from backend.config import SLOUCH_THRESHOLD, LATERAL_THRESHOLD

def test_good_posture():
    assert classify(0.0, 0.0) == "good"

def test_slouching_forward():
    assert classify(SLOUCH_THRESHOLD + 1, 0.0) == "slouching_forward"

def test_hyperextended():
    assert classify(-(SLOUCH_THRESHOLD + 1), 0.0) == "hyperextended"

def test_leaning_right():
    assert classify(0.0, LATERAL_THRESHOLD + 1) == "leaning_right"

def test_leaning_left():
    assert classify(0.0, -(LATERAL_THRESHOLD + 1)) == "leaning_left"

def test_at_threshold_boundary_is_good():
    # > not >= means exactly at threshold is still good
    assert classify(SLOUCH_THRESHOLD, 0.0) == "good"
    assert classify(0.0, LATERAL_THRESHOLD) == "good"

def test_pitch_checked_before_roll():
    # slouch takes priority when both exceed thresholds
    assert classify(SLOUCH_THRESHOLD + 1, LATERAL_THRESHOLD + 1) == "slouching_forward"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_classifier.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `classifier` not yet defined.

- [ ] **Step 3: Implement backend/classifier.py**

```python
from backend.config import SLOUCH_THRESHOLD, LATERAL_THRESHOLD

def classify(delta_pitch: float, delta_roll: float) -> str:
    if delta_pitch > SLOUCH_THRESHOLD:
        return "slouching_forward"
    if delta_pitch < -SLOUCH_THRESHOLD:
        return "hyperextended"
    if delta_roll > LATERAL_THRESHOLD:
        return "leaning_right"
    if delta_roll < -LATERAL_THRESHOLD:
        return "leaning_left"
    return "good"
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_classifier.py -v
```

Expected: 7 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/classifier.py tests/test_classifier.py
git commit -m "feat: threshold-based posture classifier with tests"
```

---

## Task 3: Database Layer (TDD)

**Files:**
- Create: `backend/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_db.py
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_db.py -v
```

Expected: `ImportError` — `db` not yet defined.

- [ ] **Step 3: Implement backend/db.py**

```python
import sqlite3
from typing import Optional

def get_conn(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id            TEXT PRIMARY KEY,
            start_time    TEXT NOT NULL,
            end_time      TEXT,
            duration_s    REAL,
            good_s        REAL,
            good_pct      REAL,
            avg_delta_pitch REAL,
            avg_delta_roll  REAL,
            max_deviation REAL,
            score         REAL
        );
        CREATE TABLE IF NOT EXISTS readings (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id    TEXT NOT NULL,
            timestamp     TEXT NOT NULL,
            posture_state TEXT NOT NULL,
            delta_pitch   REAL NOT NULL,
            delta_roll    REAL NOT NULL,
            upper_pitch   REAL NOT NULL,
            upper_roll    REAL NOT NULL,
            lower_pitch   REAL NOT NULL,
            lower_roll    REAL NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );
    """)
    conn.commit()

def create_session(conn: sqlite3.Connection, session_id: str, start_time: str) -> None:
    conn.execute("INSERT INTO sessions (id, start_time) VALUES (?, ?)",
                 (session_id, start_time))
    conn.commit()

def insert_reading(conn: sqlite3.Connection, session_id: str, timestamp: str,
                   posture_state: str, delta_pitch: float, delta_roll: float,
                   upper_pitch: float, upper_roll: float,
                   lower_pitch: float, lower_roll: float) -> None:
    conn.execute(
        """INSERT INTO readings
           (session_id, timestamp, posture_state, delta_pitch, delta_roll,
            upper_pitch, upper_roll, lower_pitch, lower_roll)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, timestamp, posture_state, delta_pitch, delta_roll,
         upper_pitch, upper_roll, lower_pitch, lower_roll),
    )
    conn.commit()

def finalize_session(conn: sqlite3.Connection, session_id: str, end_time: str,
                     duration_s: float, good_s: float, good_pct: float,
                     avg_delta_pitch: float, avg_delta_roll: float,
                     max_deviation: float, score: float) -> None:
    conn.execute(
        """UPDATE sessions
           SET end_time=?, duration_s=?, good_s=?, good_pct=?,
               avg_delta_pitch=?, avg_delta_roll=?, max_deviation=?, score=?
           WHERE id=?""",
        (end_time, duration_s, good_s, good_pct,
         avg_delta_pitch, avg_delta_roll, max_deviation, score, session_id),
    )
    conn.commit()

def get_session_history(conn: sqlite3.Connection, limit: int = 50):
    cur = conn.execute(
        "SELECT * FROM sessions WHERE end_time IS NOT NULL ORDER BY start_time DESC LIMIT ?",
        (limit,),
    )
    return [dict(r) for r in cur.fetchall()]

def get_session(conn: sqlite3.Connection, session_id: str) -> Optional[dict]:
    cur = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,))
    row = cur.fetchone()
    return dict(row) if row else None

def get_session_readings(conn: sqlite3.Connection, session_id: str):
    cur = conn.execute(
        "SELECT * FROM readings WHERE session_id=? ORDER BY timestamp ASC",
        (session_id,),
    )
    return [dict(r) for r in cur.fetchall()]
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_db.py -v
```

Expected: 6 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/db.py tests/test_db.py
git commit -m "feat: SQLite database layer with sessions and readings tables"
```

---

## Task 4: Thread-Safe Live State

**Files:**
- Create: `backend/state.py`

No separate unit test — state is exercised through API tests in Task 7.

- [ ] **Step 1: Implement backend/state.py**

```python
import threading
from typing import Optional

class _State:
    def __init__(self):
        self.connected: bool = False
        self.posture_state: str = "unknown"
        self.delta_pitch: float = 0.0
        self.delta_roll: float = 0.0
        self.upper_pitch: float = 0.0
        self.upper_roll: float = 0.0
        self.lower_pitch: float = 0.0
        self.lower_roll: float = 0.0
        self.session_id: Optional[str] = None
        self.session_start: Optional[str] = None
        self.session_duration_s: float = 0.0
        self.session_good_s: float = 0.0
        self.session_good_pct: float = 0.0
        self.session_score: float = 0.0
        self.zero_trigger: bool = False

_s = _State()
_lock = threading.Lock()

def get_state() -> dict:
    with _lock:
        return {
            "connected":     _s.connected,
            "posture_state": _s.posture_state,
            "delta_pitch":   _s.delta_pitch,
            "delta_roll":    _s.delta_roll,
            "upper_pitch":   _s.upper_pitch,
            "upper_roll":    _s.upper_roll,
            "lower_pitch":   _s.lower_pitch,
            "lower_roll":    _s.lower_roll,
        }

def get_session_state() -> dict:
    with _lock:
        return {
            "session_id": _s.session_id,
            "duration_s": _s.session_duration_s,
            "good_s":     _s.session_good_s,
            "good_pct":   _s.session_good_pct,
            "score":      _s.session_score,
        }

def update_live(connected: bool, posture_state: str,
                delta_pitch: float, delta_roll: float,
                upper_pitch: float, upper_roll: float,
                lower_pitch: float, lower_roll: float) -> None:
    with _lock:
        _s.connected     = connected
        _s.posture_state = posture_state
        _s.delta_pitch   = delta_pitch
        _s.delta_roll    = delta_roll
        _s.upper_pitch   = upper_pitch
        _s.upper_roll    = upper_roll
        _s.lower_pitch   = lower_pitch
        _s.lower_roll    = lower_roll

def update_session(session_id: str, session_start: str,
                   duration_s: float, good_s: float,
                   good_pct: float, score: float) -> None:
    with _lock:
        _s.session_id           = session_id
        _s.session_start        = session_start
        _s.session_duration_s   = duration_s
        _s.session_good_s       = good_s
        _s.session_good_pct     = good_pct
        _s.session_score        = score

def set_disconnected() -> None:
    with _lock:
        _s.connected     = False
        _s.posture_state = "unknown"

def request_zero() -> None:
    with _lock:
        _s.zero_trigger = True

def consume_zero_trigger() -> bool:
    with _lock:
        if _s.zero_trigger:
            _s.zero_trigger = False
            return True
        return False
```

- [ ] **Step 2: Commit**

```bash
git add backend/state.py
git commit -m "feat: thread-safe shared live state module"
```

---

## Task 5: Session Logger (TDD)

**Files:**
- Create: `backend/logger.py`
- Create: `tests/test_logger.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_logger.py
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
    # monotonic returns: first call=0.0 (last_log init inside start),
    # then 0.0, 0.5, 1.1, 1.5, 2.2 for the five record calls
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_logger.py -v
```

Expected: `ImportError` — `logger` not yet defined.

- [ ] **Step 3: Implement backend/logger.py**

```python
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import backend.state as state
from backend.db import create_session, insert_reading, finalize_session
from backend.config import LOG_INTERVAL_S

class SessionLogger:
    def __init__(self, conn):
        self._conn = conn
        self._session_id: Optional[str] = None
        self._start_time: Optional[datetime] = None
        self._last_log: float = -LOG_INTERVAL_S  # allow immediate first log
        self._total: int = 0
        self._good:  int = 0
        self._pitch_sum: float = 0.0
        self._roll_sum:  float = 0.0
        self._max_dev:   float = 0.0

    def start_session(self) -> str:
        self._session_id = uuid.uuid4().hex[:8]
        self._start_time = datetime.now(timezone.utc)
        self._last_log   = -LOG_INTERVAL_S
        self._total      = 0
        self._good       = 0
        self._pitch_sum  = 0.0
        self._roll_sum   = 0.0
        self._max_dev    = 0.0
        create_session(self._conn, self._session_id, self._start_time.isoformat())
        return self._session_id

    def record(self, posture_state: str, delta_pitch: float, delta_roll: float,
               upper_pitch: float, upper_roll: float,
               lower_pitch: float, lower_roll: float) -> None:
        if self._session_id is None:
            return
        now = time.monotonic()
        if now - self._last_log < LOG_INTERVAL_S:
            return
        self._last_log = now

        timestamp = datetime.now(timezone.utc).isoformat()
        insert_reading(self._conn, self._session_id, timestamp, posture_state,
                       delta_pitch, delta_roll,
                       upper_pitch, upper_roll, lower_pitch, lower_roll)

        self._total += 1
        if posture_state == "good":
            self._good += 1
        self._pitch_sum += delta_pitch
        self._roll_sum  += delta_roll
        dev = (delta_pitch ** 2 + delta_roll ** 2) ** 0.5
        if dev > self._max_dev:
            self._max_dev = dev

        duration_s = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        good_pct   = (self._good / self._total * 100.0) if self._total else 0.0
        state.update_session(self._session_id, self._start_time.isoformat(),
                             duration_s, float(self._good), good_pct, good_pct)

    def end_session(self) -> Optional[str]:
        if self._session_id is None:
            return None
        now_dt     = datetime.now(timezone.utc)
        duration_s = (now_dt - self._start_time).total_seconds()
        good_pct   = (self._good / self._total * 100.0) if self._total else 0.0
        avg_pitch  = (self._pitch_sum / self._total) if self._total else 0.0
        avg_roll   = (self._roll_sum  / self._total) if self._total else 0.0
        finalize_session(
            self._conn, self._session_id, now_dt.isoformat(),
            duration_s, float(self._good), good_pct,
            avg_pitch, avg_roll, self._max_dev, good_pct,
        )
        sid = self._session_id
        self._session_id = None
        return sid
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_logger.py -v
```

Expected: 4 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/logger.py tests/test_logger.py
git commit -m "feat: session logger with 1Hz downsampling and stats"
```

---

## Task 6: Flask API (TDD)

**Files:**
- Create: `backend/api.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api.py
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_api.py -v
```

Expected: `ImportError` — `api` not yet defined.

- [ ] **Step 3: Create backend/templates/index.html (minimal placeholder for now)**

The full HTML is written in Task 9. For the API tests to pass, a minimal template is needed:

```html
<!DOCTYPE html>
<html><head><title>PostureMax</title></head><body>PostureMax</body></html>
```

Save to `backend/templates/index.html`.

- [ ] **Step 4: Implement backend/api.py**

```python
from flask import Flask, jsonify, render_template
import backend.state as state
from backend.db import get_conn, init_db, get_session_history, get_session, get_session_readings
from backend.config import DB_PATH

def create_app(db_path: str = DB_PATH) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    conn = get_conn(db_path)
    init_db(conn)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/status")
    def api_status():
        return jsonify(state.get_state())

    @app.get("/api/session/current")
    def api_session_current():
        return jsonify(state.get_session_state())

    @app.get("/api/session/history")
    def api_session_history():
        return jsonify(get_session_history(conn))

    @app.get("/api/session/<session_id>")
    def api_session_detail(session_id):
        session = get_session(conn, session_id)
        if session is None:
            return jsonify({"error": "not found"}), 404
        readings = get_session_readings(conn, session_id)
        return jsonify({"session": session, "readings": readings})

    @app.post("/api/zero")
    def api_zero():
        state.request_zero()
        return jsonify({"ok": True})

    return app
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
pytest tests/test_api.py -v
```

Expected: 8 tests PASSED.

- [ ] **Step 6: Run full test suite to confirm no regressions**

```bash
pytest -v
```

Expected: all tests PASSED.

- [ ] **Step 7: Commit**

```bash
git add backend/api.py backend/templates/index.html tests/test_api.py
git commit -m "feat: Flask REST API with all endpoints"
```

---

## Task 7: BLE Client

**Files:**
- Create: `backend/ble_client.py`

No automated tests — requires live BLE hardware. Manual verification steps provided.

- [ ] **Step 1: Implement backend/ble_client.py**

```python
import asyncio
import struct
import time

from bleak import BleakClient, BleakScanner

from backend.config import (
    DEVICE_NAME, NOTIFY_UUID, ZERO_UUID,
    SETTLE_TIME_S, ZERO_DURATION_S,
)
from backend.classifier import classify
import backend.state as state

class BLEClient:
    def __init__(self, conn, logger):
        self._conn   = conn
        self._logger = logger
        self._client = None
        self._connect_time: float = 0.0
        # reference delta angles (updated on zero capture)
        self._ref_delta_pitch: float = 0.0
        self._ref_delta_roll:  float = 0.0
        # zero capture accumulation
        self._zeroing:    bool  = False
        self._zero_start: float = 0.0
        self._zero_pitch: float = 0.0
        self._zero_roll:  float = 0.0
        self._zero_count: int   = 0

    def _on_notify(self, _handle, data: bytearray) -> None:
        if len(data) < 16:
            return  # skip malformed / truncated packet

        if time.monotonic() - self._connect_time < SETTLE_TIME_S:
            return  # Madgwick filter not yet settled

        upper_pitch, upper_roll, lower_pitch, lower_roll = struct.unpack("<ffff", data[:16])

        raw_delta_pitch = upper_pitch - lower_pitch
        raw_delta_roll  = upper_roll  - lower_roll

        # accumulate reference while zeroing
        if self._zeroing:
            self._zero_pitch += raw_delta_pitch
            self._zero_roll  += raw_delta_roll
            self._zero_count += 1
            if time.monotonic() - self._zero_start >= ZERO_DURATION_S:
                if self._zero_count > 0:
                    self._ref_delta_pitch = self._zero_pitch / self._zero_count
                    self._ref_delta_roll  = self._zero_roll  / self._zero_count
                self._zeroing = False

        delta_pitch = raw_delta_pitch - self._ref_delta_pitch
        delta_roll  = raw_delta_roll  - self._ref_delta_roll

        posture = classify(delta_pitch, delta_roll)

        state.update_live(True, posture, delta_pitch, delta_roll,
                          upper_pitch, upper_roll, lower_pitch, lower_roll)
        self._logger.record(posture, delta_pitch, delta_roll,
                            upper_pitch, upper_roll, lower_pitch, lower_roll)

    async def _send_zero(self) -> None:
        if self._client and self._client.is_connected:
            # tell firmware to capture its own reference
            await self._client.write_gatt_char(ZERO_UUID, b"\x01")
        # start backend reference capture concurrently
        self._zeroing    = True
        self._zero_start = time.monotonic()
        self._zero_pitch = 0.0
        self._zero_roll  = 0.0
        self._zero_count = 0

    async def run(self) -> None:
        while True:
            try:
                device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=10.0)
                if device is None:
                    await asyncio.sleep(2.0)
                    continue

                async with BleakClient(device) as client:
                    self._client       = client
                    self._connect_time = time.monotonic()
                    self._logger.start_session()
                    await client.start_notify(NOTIFY_UUID, self._on_notify)

                    while client.is_connected:
                        if state.consume_zero_trigger():
                            await self._send_zero()
                        await asyncio.sleep(0.05)

            except Exception:
                pass  # log or reconnect silently
            finally:
                state.set_disconnected()
                if self._logger._session_id is not None:
                    self._logger.end_session()
                self._client = None

            await asyncio.sleep(2.0)
```

- [ ] **Step 2: Commit**

```bash
git add backend/ble_client.py
git commit -m "feat: async BLE client with zero capture and auto-reconnect"
```

---

## Task 8: Entry Point

**Files:**
- Create: `backend/main.py`

- [ ] **Step 1: Implement backend/main.py**

```python
import asyncio
import threading

from backend.db import get_conn, init_db
from backend.logger import SessionLogger
from backend.ble_client import BLEClient
from backend.api import create_app
from backend.config import DB_PATH

def _run_ble(loop: asyncio.AbstractEventLoop, conn, logger) -> None:
    asyncio.set_event_loop(loop)
    client = BLEClient(conn, logger)
    loop.run_until_complete(client.run())

def main() -> None:
    conn   = get_conn(DB_PATH)
    init_db(conn)
    logger = SessionLogger(conn)

    loop = asyncio.new_event_loop()
    ble_thread = threading.Thread(
        target=_run_ble, args=(loop, conn, logger), daemon=True
    )
    ble_thread.start()

    app = create_app(db_path=DB_PATH)
    print("PostureMax backend running at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, use_reloader=False)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test the server (no hardware needed)**

```bash
python -m backend.main
```

Expected output:
```
PostureMax backend running at http://localhost:5000
 * Running on http://0.0.0.0:5000
```

Open `http://localhost:5000/api/status` in a browser.
Expected JSON: `{"connected": false, "posture_state": "unknown", ...}`

Stop the server with Ctrl+C.

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: main entry point — BLE thread + Flask server"
```

---

## Task 9: Dashboard HTML

**Files:**
- Modify: `backend/templates/index.html` (replace the placeholder from Task 6)

- [ ] **Step 1: Replace backend/templates/index.html with full SPA**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>PostureMax</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/static/style.css" />
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body>
  <div class="layout">

    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-logo">PostureMax</div>
      <nav class="sidebar-nav">
        <button class="nav-item active" data-panel="live">Live Monitor</button>
        <button class="nav-item" data-panel="history">Session History</button>
      </nav>
    </aside>

    <!-- Main -->
    <div class="main">

      <!-- Top Bar -->
      <header class="topbar">
        <span class="topbar-title" id="panel-title">Live Monitor</span>
        <div id="connection-banner" class="connection-banner disconnected">Disconnected</div>
      </header>

      <!-- Content -->
      <main class="content">

        <!-- Live Monitor Panel -->
        <div id="panel-live" class="panel">

          <!-- Hero Card -->
          <div id="hero-card" class="hero-card state-unknown">
            <div class="hero-label" id="hero-label">—</div>
            <div class="hero-sub">Current Posture</div>
          </div>

          <div class="card-row">

            <!-- Pitch Gauge -->
            <div class="card gauge-card">
              <div class="card-title">Forward / Backward Flex</div>
              <div class="gauge-wrap">
                <div class="gauge-track">
                  <div class="gauge-fill" id="gauge-pitch"></div>
                  <div class="gauge-center"></div>
                </div>
                <div class="gauge-labels">
                  <span>-30°</span><span>0°</span><span>+30°</span>
                </div>
              </div>
              <div class="gauge-value" id="val-pitch">0.0°</div>
            </div>

            <!-- Roll Gauge -->
            <div class="card gauge-card">
              <div class="card-title">Lateral Lean</div>
              <div class="gauge-wrap">
                <div class="gauge-track">
                  <div class="gauge-fill" id="gauge-roll"></div>
                  <div class="gauge-center"></div>
                </div>
                <div class="gauge-labels">
                  <span>-30°</span><span>0°</span><span>+30°</span>
                </div>
              </div>
              <div class="gauge-value" id="val-roll">0.0°</div>
            </div>

            <!-- Session Stats -->
            <div class="card stats-card">
              <div class="card-title">Current Session</div>
              <div class="stat-row">
                <span class="stat-label">Duration</span>
                <span class="stat-val" id="stat-duration">—</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">Good Posture</span>
                <span class="stat-val" id="stat-good-pct">—</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">Score</span>
                <span class="stat-val" id="stat-score">—</span>
              </div>
              <button class="btn-outline" id="btn-zero">Re-zero Sensors</button>
            </div>

          </div>
        </div>

        <!-- Session History Panel -->
        <div id="panel-history" class="panel hidden">
          <div class="card">
            <div class="card-title">Posture Score Over Time</div>
            <canvas id="chart-score" height="80"></canvas>
          </div>
          <div class="card">
            <div class="card-title">Recent Sessions</div>
            <table class="session-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Duration</th>
                  <th>Score</th>
                  <th>Good %</th>
                </tr>
              </thead>
              <tbody id="session-tbody"></tbody>
            </table>
          </div>
        </div>

      </main>
    </div>
  </div>

  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Verify API tests still pass (template change must not break them)**

```bash
pytest tests/test_api.py -v
```

Expected: all PASSED.

- [ ] **Step 3: Commit**

```bash
git add backend/templates/index.html
git commit -m "feat: full SPA dashboard HTML"
```

---

## Task 10: Dashboard CSS

**Files:**
- Create: `backend/static/style.css`

- [ ] **Step 1: Write backend/static/style.css**

```css
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'Inter', sans-serif;
  -webkit-font-smoothing: antialiased;
  background: #F8FAFC;
  color: #0F172A;
  height: 100vh;
  overflow: hidden;
}

.layout {
  display: flex;
  height: 100vh;
}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
.sidebar {
  width: 260px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid #E2E8F0;
  display: flex;
  flex-direction: column;
  padding: 1.5rem 1rem;
}

.sidebar-logo {
  font-weight: 700;
  font-size: 1.125rem;
  color: #0F172A;
  padding: 0.5rem 0.75rem 1.5rem;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.nav-item {
  width: 100%;
  text-align: left;
  background: none;
  border: none;
  border-radius: 8px;
  padding: 0.625rem 0.75rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: #64748B;
  cursor: pointer;
  transition: background-color 200ms ease-in-out, color 200ms ease-in-out;
}
.nav-item:hover  { background: #F8FAFC; color: #0F172A; }
.nav-item.active { background: #F1F5F9; color: #0F172A; font-weight: 600; }

/* ── Main ────────────────────────────────────────────────────────────────── */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* ── Top Bar ─────────────────────────────────────────────────────────────── */
.topbar {
  height: 64px;
  background: #fff;
  border-bottom: 1px solid #E2E8F0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 2rem;
  flex-shrink: 0;
}

.topbar-title {
  font-weight: 600;
  font-size: 1rem;
}

.connection-banner {
  padding: 0.375rem 1rem;
  border-radius: 9999px;
  font-size: 0.8125rem;
  font-weight: 600;
  transition: all 200ms ease-in-out;
}
.connection-banner.connected    { background: #DCFCE7; color: #16A34A; }
.connection-banner.disconnected { background: #FEE2E2; color: #DC2626; }

/* ── Content ─────────────────────────────────────────────────────────────── */
.content {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.panel.hidden { display: none; }

/* ── Hero Card ───────────────────────────────────────────────────────────── */
.hero-card {
  border-radius: 12px;
  padding: 2.5rem 1.5rem;
  text-align: center;
  transition: all 200ms ease-in-out;
}
.hero-card.state-good    { background: #16A34A; }
.hero-card.state-warning { background: #D97706; }
.hero-card.state-bad     { background: #DC2626; }
.hero-card.state-unknown { background: #E2E8F0; }

.hero-label {
  font-size: 2.5rem;
  font-weight: 700;
  color: #fff;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.hero-card.state-unknown .hero-label { color: #64748B; }

.hero-sub {
  font-size: 0.875rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.8);
  margin-top: 0.5rem;
}
.hero-card.state-unknown .hero-sub { color: #64748B; }

/* ── Card Row ────────────────────────────────────────────────────────────── */
.card-row {
  display: flex;
  gap: 1.5rem;
}
.card-row > .card { flex: 1; }

/* ── Cards ───────────────────────────────────────────────────────────────── */
.card {
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  padding: 1.5rem;
}

.card-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 1rem;
}

/* ── Gauges ──────────────────────────────────────────────────────────────── */
.gauge-wrap { margin-bottom: 0.5rem; }

.gauge-track {
  position: relative;
  height: 12px;
  background: #F1F5F9;
  border-radius: 6px;
  overflow: hidden;
}

.gauge-fill {
  position: absolute;
  top: 0;
  height: 100%;
  width: 4px;
  background: #0F172A;
  border-radius: 2px;
  left: 50%;
  transition: left 100ms ease-out;
}

.gauge-center {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 1px;
  background: #CBD5E1;
}

.gauge-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #94A3B8;
  margin-top: 0.25rem;
}

.gauge-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0F172A;
}

/* ── Stats Card ──────────────────────────────────────────────────────────── */
.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
  border-bottom: 1px solid #F1F5F9;
}
.stat-row:last-of-type { border-bottom: none; }

.stat-label { font-size: 0.875rem; color: #64748B; }
.stat-val   { font-size: 0.875rem; font-weight: 600; color: #0F172A; }

/* ── Re-zero Button ──────────────────────────────────────────────────────── */
.btn-outline {
  margin-top: 1rem;
  width: 100%;
  padding: 0.625rem 1rem;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  background: none;
  font-size: 0.875rem;
  font-weight: 500;
  color: #0F172A;
  cursor: pointer;
  transition: background-color 200ms ease-in-out;
}
.btn-outline:hover { background: #F8FAFC; }

/* ── Session Table ───────────────────────────────────────────────────────── */
.session-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.session-table th {
  text-align: left;
  font-weight: 600;
  color: #64748B;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0 0 0.75rem;
  border-bottom: 1px solid #E2E8F0;
}

.session-table td {
  padding: 0.75rem 0;
  border-bottom: 1px solid #F1F5F9;
  color: #0F172A;
}

.session-table tr:last-child td { border-bottom: none; }

/* ── Score Badge ─────────────────────────────────────────────────────────── */
.score-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
}
.score-good    { background: #DCFCE7; color: #16A34A; }
.score-warning { background: #FEF3C7; color: #D97706; }
.score-bad     { background: #FEE2E2; color: #DC2626; }
```

- [ ] **Step 2: Commit**

```bash
git add backend/static/style.css
git commit -m "feat: clinical minimalist dashboard stylesheet"
```

---

## Task 11: Dashboard JavaScript

**Files:**
- Create: `backend/static/app.js`

- [ ] **Step 1: Write backend/static/app.js**

```javascript
const POLL_MS = 200;

const POSTURE_LABELS = {
  good:               'GOOD',
  slouching_forward:  'SLOUCHING',
  hyperextended:      'HYPEREXTENDED',
  leaning_right:      'LEANING RIGHT',
  leaning_left:       'LEANING LEFT',
  unknown:            '—',
};

const STATE_CLASS = {
  good:              'state-good',
  slouching_forward: 'state-bad',
  hyperextended:     'state-warning',
  leaning_right:     'state-warning',
  leaning_left:      'state-warning',
  unknown:           'state-unknown',
};

let scoreChart = null;

function formatDuration(s) {
  if (s == null || s === 0) return '—';
  const m   = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}m ${String(sec).padStart(2, '0')}s`;
}

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

function angleToPercent(deg) {
  // maps -30..+30 → 0..100 (%) of gauge track
  return ((clamp(deg, -30, 30) + 30) / 60) * 100;
}

async function updateLive() {
  try {
    const [statusRes, sessionRes] = await Promise.all([
      fetch('/api/status'),
      fetch('/api/session/current'),
    ]);
    const status  = await statusRes.json();
    const session = await sessionRes.json();

    // Connection banner
    const banner = document.getElementById('connection-banner');
    if (status.connected) {
      banner.textContent = 'Connected';
      banner.className   = 'connection-banner connected';
    } else {
      banner.textContent = 'Disconnected';
      banner.className   = 'connection-banner disconnected';
    }

    // Hero card state class
    const heroCard  = document.getElementById('hero-card');
    const heroLabel = document.getElementById('hero-label');
    const prevCls   = [...heroCard.classList].find(c => c.startsWith('state-'));
    if (prevCls) heroCard.classList.remove(prevCls);
    heroCard.classList.add(STATE_CLASS[status.posture_state] ?? 'state-unknown');
    heroLabel.textContent = POSTURE_LABELS[status.posture_state] ?? '—';

    // Angle gauges
    const pitchPct = angleToPercent(status.delta_pitch ?? 0);
    const rollPct  = angleToPercent(status.delta_roll  ?? 0);
    document.getElementById('gauge-pitch').style.left = `${pitchPct}%`;
    document.getElementById('gauge-roll').style.left  = `${rollPct}%`;
    document.getElementById('val-pitch').textContent  = `${(status.delta_pitch ?? 0).toFixed(1)}°`;
    document.getElementById('val-roll').textContent   = `${(status.delta_roll  ?? 0).toFixed(1)}°`;

    // Session stats
    document.getElementById('stat-duration').textContent =
      formatDuration(session.duration_s);
    document.getElementById('stat-good-pct').textContent =
      session.good_pct != null ? `${session.good_pct.toFixed(1)}%` : '—';
    document.getElementById('stat-score').textContent =
      session.score != null ? `${Math.round(session.score)}` : '—';

  } catch (_) {
    // network error — keep displaying last known state
  }
}

async function loadHistory() {
  const res      = await fetch('/api/session/history');
  const sessions = await res.json();

  // Score line chart (newest sessions on the right)
  const ordered = [...sessions].reverse();
  const labels  = ordered.map(s => (s.start_time ?? '').slice(0, 10));
  const scores  = ordered.map(s => s.score ?? 0);
  const pointColors = scores.map(s =>
    s >= 70 ? '#16A34A' : s >= 40 ? '#D97706' : '#DC2626'
  );

  const ctx = document.getElementById('chart-score').getContext('2d');
  if (scoreChart) scoreChart.destroy();
  scoreChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Posture Score',
        data: scores,
        borderColor: '#16A34A',
        backgroundColor: 'rgba(22,163,74,0.08)',
        tension: 0.3,
        pointRadius: 5,
        pointBackgroundColor: pointColors,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: {
          min: 0, max: 100,
          grid: { color: '#F1F5F9' },
          ticks: { color: '#64748B' },
        },
        x: {
          grid: { display: false },
          ticks: { color: '#64748B' },
        },
      },
    },
  });

  // Session table (10 most recent)
  const tbody = document.getElementById('session-tbody');
  tbody.innerHTML = sessions.slice(0, 10).map(s => {
    const score = s.score ?? 0;
    const cls   = score >= 70 ? 'score-good' : score >= 40 ? 'score-warning' : 'score-bad';
    const date  = (s.start_time ?? '').slice(0, 16).replace('T', ' ');
    return `<tr>
      <td>${date}</td>
      <td>${formatDuration(s.duration_s)}</td>
      <td><span class="score-badge ${cls}">${Math.round(score)}</span></td>
      <td>${s.good_pct != null ? s.good_pct.toFixed(1) + '%' : '—'}</td>
    </tr>`;
  }).join('');
}

// ── Nav switching ─────────────────────────────────────────────────────────
document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => {
    const panel = btn.dataset.panel;
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.panel').forEach(p => p.classList.add('hidden'));
    document.getElementById(`panel-${panel}`)?.classList.remove('hidden');
    document.getElementById('panel-title').textContent =
      panel === 'live' ? 'Live Monitor' : 'Session History';
    if (panel === 'history') loadHistory();
  });
});

// ── Re-zero button ────────────────────────────────────────────────────────
document.getElementById('btn-zero').addEventListener('click', async () => {
  await fetch('/api/zero', { method: 'POST' });
});

// ── Start polling ─────────────────────────────────────────────────────────
setInterval(updateLive, POLL_MS);
updateLive();
```

- [ ] **Step 2: Start the server and verify the UI manually**

```bash
python -m backend.main
```

Open `http://localhost:5000` in a browser. Verify:
- Sidebar with two nav items renders correctly
- "Disconnected" pill shows in red in top bar
- Hero card shows neutral grey "—" state
- Two gauge bars visible at center position
- Session stats show "—"
- "Re-zero Sensors" button present
- Switch to "Session History" — chart canvas and table render (empty)

Stop server with Ctrl+C.

- [ ] **Step 3: Run full test suite**

```bash
pytest -v
```

Expected: all PASSED.

- [ ] **Step 4: Commit**

```bash
git add backend/static/app.js
git commit -m "feat: dashboard JavaScript — live polling, gauges, history chart"
```

---

## Task 12: Firmware

**Files:**
- Create: `firmware/PostureMax/PostureMax.ino`

No automated test runner for Arduino. Manual flash-and-verify steps provided.

**Required Arduino libraries (install via Library Manager before building):**
- `MadgwickAHRS` by Sebastian Madgwick
- `ESP32 BLE Arduino` (bundled with ESP32 board support)

- [ ] **Step 1: Write firmware/PostureMax/PostureMax.ino**

```cpp
#include <Wire.h>
#include <MadgwickAHRS.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// UUIDs must match backend/config.py
#define SERVICE_UUID "12345678-1234-1234-1234-123456789abc"
#define NOTIFY_UUID  "12345678-1234-1234-1234-123456789abd"
#define ZERO_UUID    "12345678-1234-1234-1234-123456789abe"

#define ADDR_UPPER 0x68
#define ADDR_LOWER 0x69

#define LOOP_HZ      100
#define LOOP_MS      (1000 / LOOP_HZ)
#define SETTLE_MS    2000    // discard first 2 s of filter output
#define ZERO_DUR_MS  5000    // 5 s zero capture window

Madgwick filterUpper, filterLower;

BLECharacteristic* pNotifyChar = nullptr;
BLECharacteristic* pZeroChar   = nullptr;
bool deviceConnected = false;

// Zero capture state
bool         zeroing      = false;
unsigned long zeroStartMs = 0;
float        zeroAccum[4] = {0, 0, 0, 0};  // upper_p, upper_r, lower_p, lower_r
int          zeroSamples  = 0;

unsigned long bootMs = 0;

// ── BLE server callbacks ───────────────────────────────────────────────────
class ServerCB : public BLEServerCallbacks {
  void onConnect(BLEServer*) override {
    deviceConnected = true;
    Serial.println("BLE client connected");
  }
  void onDisconnect(BLEServer*) override {
    deviceConnected = false;
    Serial.println("BLE client disconnected — re-advertising");
    BLEDevice::startAdvertising();
  }
};

// Triggered when backend writes 0x01 to ZERO_UUID
class ZeroCB : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    std::string val = c->getValue();
    if (!val.empty() && (uint8_t)val[0] == 0x01) {
      zeroing      = true;
      zeroStartMs  = millis();
      zeroAccum[0] = zeroAccum[1] = zeroAccum[2] = zeroAccum[3] = 0.0f;
      zeroSamples  = 0;
      Serial.println("Zero capture started");
    }
  }
};

// ── MPU6050 helpers ────────────────────────────────────────────────────────
static void initMPU(uint8_t addr) {
  Wire.beginTransmission(addr);
  Wire.write(0x6B);   // PWR_MGMT_1
  Wire.write(0x00);   // clear sleep bit
  Wire.endTransmission(true);
}

// Returns false on I2C error — caller should skip that frame silently
static bool readMPU(uint8_t addr,
                    float& ax, float& ay, float& az,
                    float& gx, float& gy, float& gz) {
  Wire.beginTransmission(addr);
  Wire.write(0x3B);   // ACCEL_XOUT_H
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(addr, (uint8_t)14) < 14) return false;

  int16_t raw[7];
  for (int i = 0; i < 7; i++)
    raw[i] = (int16_t)((Wire.read() << 8) | Wire.read());

  // raw[3] is temperature — skip
  ax = raw[0] / 16384.0f;   // ±2 g range
  ay = raw[1] / 16384.0f;
  az = raw[2] / 16384.0f;
  gx = raw[4] / 131.0f;    // ±250 °/s range
  gy = raw[5] / 131.0f;
  gz = raw[6] / 131.0f;
  return true;
}

// ── Setup ──────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Wire.begin();
  delay(100);

  // Verify both sensors are present and have distinct addresses
  Wire.beginTransmission(ADDR_UPPER);
  bool upperOk = (Wire.endTransmission() == 0);
  Wire.beginTransmission(ADDR_LOWER);
  bool lowerOk = (Wire.endTransmission() == 0);

  if (!upperOk || !lowerOk) {
    Serial.println("ERROR: one or both sensors not found — check I2C wiring");
    while (true) delay(1000);
  }

  initMPU(ADDR_UPPER);
  initMPU(ADDR_LOWER);
  filterUpper.begin(LOOP_HZ);
  filterLower.begin(LOOP_HZ);

  // BLE setup
  BLEDevice::init("PostureMax");
  BLEServer*  pServer  = BLEDevice::createServer();
  pServer->setCallbacks(new ServerCB());

  BLEService* pService = pServer->createService(SERVICE_UUID);

  pNotifyChar = pService->createCharacteristic(
    NOTIFY_UUID, BLECharacteristic::PROPERTY_NOTIFY);
  pNotifyChar->addDescriptor(new BLE2902());

  pZeroChar = pService->createCharacteristic(
    ZERO_UUID, BLECharacteristic::PROPERTY_WRITE);
  pZeroChar->setCallbacks(new ZeroCB());

  pService->start();

  BLEAdvertising* pAdv = BLEDevice::getAdvertising();
  pAdv->addServiceUUID(SERVICE_UUID);
  pAdv->setScanResponse(false);
  pAdv->setMinPreferred(0x06);   // request minimum connection interval
  BLEDevice::startAdvertising();

  bootMs = millis();
  Serial.println("PostureMax ready — advertising as 'PostureMax'");
}

// ── Main loop (100 Hz) ─────────────────────────────────────────────────────
void loop() {
  unsigned long t0 = millis();

  float ax1, ay1, az1, gx1, gy1, gz1;
  float ax2, ay2, az2, gx2, gy2, gz2;

  bool ok1 = readMPU(ADDR_UPPER, ax1, ay1, az1, gx1, gy1, gz1);
  bool ok2 = readMPU(ADDR_LOWER, ax2, ay2, az2, gx2, gy2, gz2);

  // Always update filters when reads succeed (keeps them converged)
  if (ok1) filterUpper.updateIMU(gx1, gy1, gz1, ax1, ay1, az1);
  if (ok2) filterLower.updateIMU(gx2, gy2, gz2, ax2, ay2, az2);

  bool settled = (millis() - bootMs) >= SETTLE_MS;

  if (settled && deviceConnected && ok1 && ok2) {
    float upperPitch = filterUpper.getPitch();
    float upperRoll  = filterUpper.getRoll();
    float lowerPitch = filterLower.getPitch();
    float lowerRoll  = filterLower.getRoll();

    // Accumulate zero reference
    if (zeroing) {
      zeroAccum[0] += upperPitch;
      zeroAccum[1] += upperRoll;
      zeroAccum[2] += lowerPitch;
      zeroAccum[3] += lowerRoll;
      zeroSamples++;

      if (millis() - zeroStartMs >= ZERO_DUR_MS) {
        zeroing = false;
        Serial.printf("Zero captured over %d samples\n", zeroSamples);
      }
    }

    // Pack as 4 little-endian floats and notify
    float packet[4] = { upperPitch, upperRoll, lowerPitch, lowerRoll };
    pNotifyChar->setValue(reinterpret_cast<uint8_t*>(packet), 16);
    pNotifyChar->notify();
  }

  // Pace loop to 100 Hz
  unsigned long elapsed = millis() - t0;
  if (elapsed < LOOP_MS) delay(LOOP_MS - elapsed);
}
```

- [ ] **Step 2: Open in Arduino IDE and verify it compiles**

In Arduino IDE:
1. Board: `ESP32C3 Dev Module` (or `ESP32-C3 SuperMini`)
2. Sketch → Verify/Compile

Expected: `Done compiling` with no errors.

- [ ] **Step 3: Flash to ESP32-C3 and verify serial output**

1. Connect ESP32-C3 via USB
2. Select correct COM port
3. Upload sketch
4. Open Serial Monitor at 115200 baud

Expected serial output within 2 seconds:
```
PostureMax ready — advertising as 'PostureMax'
```

If instead you see `ERROR: one or both sensors not found`, the I2C wiring needs investigation (both sensors must be connected before this step).

- [ ] **Step 4: Verify BLE advertising with a phone**

Install any BLE scanner app (e.g. nRF Connect). Scan for devices. You should see `PostureMax` in the list.

- [ ] **Step 5: Verify BLE data flows to backend**

Start the backend:
```bash
python -m backend.main
```

Expected serial output on ESP32 after backend connects:
```
BLE client connected
```

Expected in browser at `http://localhost:5000/api/status`:
```json
{"connected": true, "posture_state": "good", ...}
```

- [ ] **Step 6: Commit**

```bash
git add firmware/PostureMax/PostureMax.ino
git commit -m "feat: ESP32-C3 firmware — 100Hz dual MPU6050 Madgwick BLE streaming"
```

---

## Task 13: Final Integration Verification

- [ ] **Step 1: Run full test suite one last time**

```bash
pytest -v
```

Expected: all PASSED.

- [ ] **Step 2: End-to-end smoke test (hardware required)**

1. Flash firmware, verify serial shows `PostureMax ready`
2. Start backend: `python -m backend.main`
3. Open `http://localhost:5000` in browser
4. Confirm connection banner turns green
5. Move upper sensor forward — hero card should turn red with `SLOUCHING`
6. Return to upright — hero card should turn green with `GOOD`
7. Click "Re-zero Sensors" — wait 5 seconds — confirm reference resets
8. Navigate to Session History — confirm a session row appears after ending a session (reconnect/disconnect cycle)

- [ ] **Step 3: Tag the release**

```bash
git tag v2.0.0
git log --oneline
```

---

*End of plan — PostureMax V2*
