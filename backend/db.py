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
