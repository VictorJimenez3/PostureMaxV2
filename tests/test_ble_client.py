import struct
import time
import pytest
from backend.db import get_conn, init_db
from backend.logger import SessionLogger
from backend.ble_client import DeviceConnection, DualBLEManager
import backend.state as state
from backend.config import STALENESS_S


@pytest.fixture
def db(tmp_path):
    conn = get_conn(str(tmp_path / "t.db"))
    init_db(conn)
    return conn


@pytest.fixture
def manager(db):
    lg = SessionLogger(db)
    return DualBLEManager(lg)


# ── DeviceConnection unit tests ────────────────────────────────────────────

def test_device_parses_8_byte_packet():
    dc = DeviceConnection("PostureMax-Upper", "upper", lambda: None)
    dc._connect_time = 0.0   # settled (monotonic >> SETTLE_TIME_S)
    data = struct.pack("<ff", 5.0, -2.0)
    dc._on_notify(None, bytearray(data))
    assert dc.pitch == pytest.approx(5.0)
    assert dc.roll == pytest.approx(-2.0)


def test_device_skips_short_packet():
    dc = DeviceConnection("PostureMax-Upper", "upper", lambda: None)
    dc._connect_time = 0.0
    dc._on_notify(None, bytearray(b"\x00" * 7))
    assert dc.pitch == 0.0
    assert dc.roll == 0.0


def test_device_skips_during_settle():
    dc = DeviceConnection("PostureMax-Upper", "upper", lambda: None)
    dc._connect_time = time.monotonic()   # just connected — within SETTLE_TIME_S
    data = struct.pack("<ff", 5.0, 2.0)
    dc._on_notify(None, bytearray(data))
    assert dc.pitch == 0.0   # unchanged


def test_device_applies_reference():
    dc = DeviceConnection("PostureMax-Upper", "upper", lambda: None)
    dc._connect_time = 0.0
    dc._ref_pitch = 3.0
    dc._ref_roll  = 1.0
    data = struct.pack("<ff", 8.0, 4.0)
    dc._on_notify(None, bytearray(data))
    assert dc.pitch == pytest.approx(5.0)   # 8.0 - 3.0
    assert dc.roll  == pytest.approx(3.0)   # 4.0 - 1.0


def test_device_is_fresh_when_recently_seen():
    dc = DeviceConnection("PostureMax-Upper", "upper", lambda: None)
    dc._last_seen = time.monotonic()
    assert dc.is_fresh is True


def test_device_is_stale_when_not_seen():
    dc = DeviceConnection("PostureMax-Upper", "upper", lambda: None)
    dc._last_seen = time.monotonic() - (STALENESS_S + 1.0)
    assert dc.is_fresh is False


def test_device_on_notify_sets_fresh(monkeypatch):
    dc = DeviceConnection("PostureMax-Upper", "upper", lambda: None)
    dc._connect_time = 0.0
    dc._last_seen = 0.0
    data = struct.pack("<ff", 1.0, 0.0)
    dc._on_notify(None, bytearray(data))
    assert dc.is_fresh is True


# ── DualBLEManager._on_data unit tests ─────────────────────────────────────

def _make_fresh(dc):
    dc._last_seen = time.monotonic()


def _make_stale(dc):
    dc._last_seen = time.monotonic() - (STALENESS_S + 5.0)


def test_dual_no_classify_when_upper_stale(manager):
    _make_stale(manager._upper)
    _make_fresh(manager._lower)
    manager._upper._pitch = 20.0   # would be slouching if classified
    manager._lower._pitch = 0.0
    # set connected so we can verify it gets cleared
    state.update_live(True, "good", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    manager._on_data()
    assert state.get_state()["connected"] is False


def test_dual_no_classify_when_lower_stale(manager):
    _make_fresh(manager._upper)
    _make_stale(manager._lower)
    state.update_live(True, "good", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    manager._on_data()
    assert state.get_state()["connected"] is False


def test_dual_classifies_good_posture(manager):
    _make_fresh(manager._upper)
    _make_fresh(manager._lower)
    manager._upper._pitch = 5.0;  manager._upper._roll = 0.0
    manager._lower._pitch = 0.0;  manager._lower._roll = 0.0
    # delta_pitch = 5 - 0 = 5 (< SLOUCH_THRESHOLD=15) → good
    manager._on_data()
    s = state.get_state()
    assert s["connected"] is True
    assert s["posture_state"] == "good"


def test_dual_classifies_slouching(manager):
    _make_fresh(manager._upper)
    _make_fresh(manager._lower)
    manager._upper._pitch = 20.0;  manager._upper._roll = 0.0
    manager._lower._pitch = 0.0;   manager._lower._roll = 0.0
    # delta_pitch = 20 - 0 = 20 (> SLOUCH_THRESHOLD=15) → slouching_forward
    manager._on_data()
    assert state.get_state()["posture_state"] == "slouching_forward"


def test_dual_starts_session_on_first_classify(manager, db):
    from backend.db import get_session_history
    _make_fresh(manager._upper)
    _make_fresh(manager._lower)
    manager._upper._pitch = 0.0;  manager._upper._roll = 0.0
    manager._lower._pitch = 0.0;  manager._lower._roll = 0.0
    assert manager._logger._session_id is None
    manager._on_data()
    assert manager._logger._session_id is not None


def test_dual_ends_session_when_stale(manager, db):
    _make_fresh(manager._upper)
    _make_fresh(manager._lower)
    manager._upper._pitch = 0.0;  manager._upper._roll = 0.0
    manager._lower._pitch = 0.0;  manager._lower._roll = 0.0
    manager._on_data()   # start session
    sid = manager._logger._session_id
    assert sid is not None

    _make_stale(manager._upper)
    manager._on_data()   # should end session
    assert manager._logger._session_id is None
