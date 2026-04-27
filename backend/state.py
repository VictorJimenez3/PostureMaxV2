import threading
import time
from typing import Optional

class _State:
    def __init__(self):
        self.connected: bool = False
        self.upper_connected: bool = False
        self.lower_connected: bool = False
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
        self.retry_upper: bool = False
        self.retry_lower: bool = False
        self.ble_log: list = []          # ring buffer, max 30 entries

_s = _State()
_lock = threading.Lock()

def get_state() -> dict:
    with _lock:
        return {
            "connected":       _s.connected,
            "upper_connected": _s.upper_connected,
            "lower_connected": _s.lower_connected,
            "posture_state":   _s.posture_state,
            "delta_pitch":     _s.delta_pitch,
            "delta_roll":      _s.delta_roll,
            "upper_pitch":     _s.upper_pitch,
            "upper_roll":      _s.upper_roll,
            "lower_pitch":     _s.lower_pitch,
            "lower_roll":      _s.lower_roll,
        }

def get_session_state() -> dict:
    with _lock:
        return {
            "session_id": _s.session_id,
            "session_start": _s.session_start,
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

def set_device_connected(role: str, connected: bool) -> None:
    with _lock:
        if role == "upper":
            _s.upper_connected = connected
        else:
            _s.lower_connected = connected

def set_disconnected() -> None:
    with _lock:
        _s.connected     = False
        _s.posture_state = "unknown"
        _s.session_id    = None

def request_zero() -> None:
    with _lock:
        _s.zero_trigger = True

def consume_zero_trigger() -> bool:
    with _lock:
        if _s.zero_trigger:
            _s.zero_trigger = False
            return True
        return False

def request_retry(role: str) -> None:
    with _lock:
        if role == "upper":
            _s.retry_upper = True
        else:
            _s.retry_lower = True

def consume_retry(role: str) -> bool:
    with _lock:
        if role == "upper" and _s.retry_upper:
            _s.retry_upper = False
            return True
        if role == "lower" and _s.retry_lower:
            _s.retry_lower = False
            return True
        return False

def add_ble_log(msg: str) -> None:
    with _lock:
        _s.ble_log.append({"t": time.strftime("%H:%M:%S"), "msg": msg})
        if len(_s.ble_log) > 30:
            _s.ble_log.pop(0)

def get_ble_log() -> list:
    with _lock:
        return list(_s.ble_log)
