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
                             duration_s, float(self._good) * LOG_INTERVAL_S, good_pct, good_pct)

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
            duration_s, float(self._good) * LOG_INTERVAL_S, good_pct,
            avg_pitch, avg_roll, self._max_dev, good_pct,
        )
        sid = self._session_id
        self._session_id = None
        return sid
