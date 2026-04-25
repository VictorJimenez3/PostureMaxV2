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
