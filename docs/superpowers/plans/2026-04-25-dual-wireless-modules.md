# Dual Wireless Modules — Architecture Correction Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the hardware architecture from one wired dual-sensor device to two fully independent wireless modules, each with its own ESP32-C3, MPU6050, and battery.

**Architecture:** Each module advertises a unique BLE name (`PostureMax-Upper` / `PostureMax-Lower`) and streams 2 floats (pitch, roll) per packet. The Python backend maintains two concurrent BLE connections via `asyncio.gather`, combines their streams in `DualBLEManager`, and only classifies posture when both sensors have been heard within the staleness window. One shared firmware sketch uses a compile-time `#define IS_UPPER` flag to set each board's identity.

**Tech Stack:** Same as v2 — Arduino/C++, Python 3, bleak, Flask, SQLite. No changes to classifier, db, logger, state, API, or dashboard.

---

## Files Changed / Created

```
C:\Users\victo\Downloads\pmax software\hardware.md   ← full rewrite (source-of-truth doc)
docs/hardware.md                                      ← copy in repo
firmware/PostureMax/PostureMax.ino                    ← rewrite: single sensor, IS_UPPER flag
backend/config.py                                     ← replace DEVICE_NAME → UPPER/LOWER + STALENESS_S
backend/ble_client.py                                 ← rewrite: DeviceConnection + DualBLEManager
backend/main.py                                       ← update: BLEClient → DualBLEManager
tests/test_ble_client.py                              ← new: unit tests for sync-testable logic
```

**Unchanged:** `classifier.py`, `db.py`, `logger.py`, `state.py`, `api.py`, all dashboard files, all existing tests.

---

## Task 1: Update hardware.md

**Files:**
- Rewrite: `C:\Users\victo\Downloads\pmax software\hardware.md`
- Create: `docs/hardware.md` (copy)

- [ ] **Step 1: Rewrite hardware.md**

Write this exact content to `C:\Users\victo\Downloads\pmax software\hardware.md`:

```markdown
# PostureMax — Hardware Reference

> **For Claude Code:** Hardware is fully assembled and will not be modified. Do not suggest wiring changes. This doc exists so you understand the physical setup and can write firmware/backend code that handles it correctly — including its failure modes.

---

## System Overview

PostureMax uses **two fully independent wireless modules**. There are no wires between them — no shared I2C bus, no shared power rail, no physical connection of any kind.

Each module is self-contained:

| Component | Detail |
|---|---|
| Microcontroller | ESP32-C3 Super Mini (HW-466AB) |
| Expansion board | ESP32-C3 expansion board (for pin access) |
| Sensor | MPU6050 — I2C address `0x68` (default, AD0 floating or grounded) |
| Power | On-board battery |
| Wireless | BLE only |
| Framework | Arduino (not ESP-IDF) |
| Fusion library | MadgwickAHRS (installed via Arduino library manager) |

---

## Module Placement

```
         [neck]
            |
      ┌─────┴─────┐
      │  MODULE A  │  ← Upper module — T5–T7, mid-thoracic
      │ ESP32+IMU  │     between shoulder blades
      └─────┬─────┘
            |
           (no wire — BLE only)
            |
      ┌─────┴─────┐
      │  MODULE B  │  ← Lower module — L3–L5, lumbar
      │ ESP32+IMU  │     just above waistband
      └─────┬─────┘
            |
         [waist]
```

- Both modules mounted vertically, long axis aligned with spine
- Each taped securely to skin or held in a small enclosure
- Both communicate independently over BLE to the laptop backend

---

## BLE Identity

Each module is flashed with the same firmware sketch, differentiated at compile time via `#define IS_UPPER`:

| Module | BLE Advertised Name | IS_UPPER value |
|---|---|---|
| Upper (thoracic) | `PostureMax-Upper` | `1` |
| Lower (lumbar) | `PostureMax-Lower` | `0` |

---

## Known Hardware Failure Modes

Handle all of these in code — do not assume clean operation:

| Failure | Cause | How to handle |
|---|---|---|
| I2C dropped reading | Bus noise | Skip that frame silently — do not crash, do not feed bad data to filter |
| Sensor shifts mid-session | Movement, tape loosening | Re-zero always available and responsive |
| BLE drops mid-session | Range, interference | Firmware auto-advertises on disconnect; backend auto-reconnects |
| One module loses power | Dead battery | Backend detects staleness, pauses classification, waits for reconnect |
| Madgwick slow to converge | First ~2s after boot | Do not transmit during first 2 seconds |

---

## Firmware Constraints

- Loop rate: **100Hz** (10ms) — sensor polled every loop
- Madgwick filter: one instance, initialized at 100Hz
- Only **pitch and roll** are used — yaw is ignored
- Transmit over BLE: `[pitch, roll]` as 2 floats (8 bytes)
- BLE connection interval: set to minimum supported value
- BLE mode: notifications
- Two BLE characteristics:
  - **Notify characteristic** — streams angle packet every loop
  - **Write characteristic** — receives zero trigger (0x01), averages 5s of still data

---

*Last updated: April 2026*
```

- [ ] **Step 2: Copy to docs/hardware.md**

Copy the same content to `C:\Users\victo\PostureMaxV2\docs\hardware.md`.

- [ ] **Step 3: Commit**

```bash
git add docs/hardware.md
git commit -m "docs: rewrite hardware.md for dual independent wireless modules"
```

---

## Task 2: Update config.py

**Files:**
- Modify: `backend/config.py`

- [ ] **Step 1: Replace config.py entirely**

```python
DEVICE_NAME_UPPER = "PostureMax-Upper"
DEVICE_NAME_LOWER = "PostureMax-Lower"

SERVICE_UUID = "12345678-1234-1234-1234-123456789abc"
NOTIFY_UUID  = "12345678-1234-1234-1234-123456789abd"
ZERO_UUID    = "12345678-1234-1234-1234-123456789abe"

SLOUCH_THRESHOLD  = 15.0   # degrees forward flex
LATERAL_THRESHOLD = 10.0   # degrees lateral lean

LOG_INTERVAL_S  = 1.0    # downsample: log once per second
SETTLE_TIME_S   = 2.0    # discard first 2s after BLE connect (Madgwick settling)
ZERO_DURATION_S = 5.0    # average over 5s for reference capture
STALENESS_S     = 2.0    # pause classification if either sensor silent for this long

DB_PATH = "posturemax.db"
```

- [ ] **Step 2: Run existing tests to confirm no regressions**

```bash
pytest -v
```

Expected: all 26 tests PASS. (No existing test imports DEVICE_NAME directly.)

- [ ] **Step 3: Commit**

```bash
git add backend/config.py
git commit -m "feat: split DEVICE_NAME into UPPER/LOWER, add STALENESS_S"
```

---

## Task 3: Rewrite Firmware

**Files:**
- Rewrite: `firmware/PostureMax/PostureMax.ino`

- [ ] **Step 1: Replace firmware/PostureMax/PostureMax.ino**

```cpp
#include <Wire.h>
#include <MadgwickAHRS.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// ── Identity ──────────────────────────────────────────────────────────────
// Set IS_UPPER to 1 when flashing the thoracic (upper back) module.
// Set IS_UPPER to 0 when flashing the lumbar (lower back) module.
#define IS_UPPER 1

#if IS_UPPER
  #define DEVICE_NAME "PostureMax-Upper"
#else
  #define DEVICE_NAME "PostureMax-Lower"
#endif

// ── UUIDs (must match backend/config.py) ─────────────────────────────────
#define SERVICE_UUID "12345678-1234-1234-1234-123456789abc"
#define NOTIFY_UUID  "12345678-1234-1234-1234-123456789abd"
#define ZERO_UUID    "12345678-1234-1234-1234-123456789abe"

// ── Sensor ────────────────────────────────────────────────────────────────
#define ADDR_IMU 0x68   // default MPU6050 address (AD0 floating or grounded)

// ── Timing ────────────────────────────────────────────────────────────────
#define LOOP_HZ      100
#define LOOP_MS      (1000 / LOOP_HZ)
#define SETTLE_MS    2000
#define ZERO_DUR_MS  5000

Madgwick filter;

BLECharacteristic* pNotifyChar = nullptr;
BLECharacteristic* pZeroChar   = nullptr;
bool deviceConnected = false;

bool          zeroing     = false;
unsigned long zeroStartMs = 0;
float         zeroAccum[2] = {0, 0};   // pitch, roll
int           zeroSamples  = 0;

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

class ZeroCB : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    std::string val = c->getValue();
    if (!val.empty() && (uint8_t)val[0] == 0x01) {
      zeroing       = true;
      zeroStartMs   = millis();
      zeroAccum[0]  = zeroAccum[1] = 0.0f;
      zeroSamples   = 0;
      Serial.println("Zero capture started");
    }
  }
};

// ── MPU6050 helpers ────────────────────────────────────────────────────────
static void initMPU() {
  Wire.beginTransmission(ADDR_IMU);
  Wire.write(0x6B);
  Wire.write(0x00);   // wake up
  Wire.endTransmission(true);
}

static bool readMPU(float& ax, float& ay, float& az,
                    float& gx, float& gy, float& gz) {
  Wire.beginTransmission(ADDR_IMU);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(ADDR_IMU, (uint8_t)14) < 14) return false;

  int16_t raw[7];
  for (int i = 0; i < 7; i++)
    raw[i] = (int16_t)((Wire.read() << 8) | Wire.read());

  ax = raw[0] / 16384.0f;
  ay = raw[1] / 16384.0f;
  az = raw[2] / 16384.0f;
  gx = raw[4] / 131.0f;
  gy = raw[5] / 131.0f;
  gz = raw[6] / 131.0f;
  return true;
}

// ── Setup ──────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Wire.begin();
  delay(100);

  Wire.beginTransmission(ADDR_IMU);
  if (Wire.endTransmission() != 0) {
    Serial.println("ERROR: MPU6050 not found — check I2C wiring");
    while (true) delay(1000);
  }

  initMPU();
  filter.begin(LOOP_HZ);

  BLEDevice::init(DEVICE_NAME);
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
  pAdv->setMinPreferred(0x06);
  BLEDevice::startAdvertising();

  bootMs = millis();
  Serial.print("PostureMax ready — advertising as '");
  Serial.print(DEVICE_NAME);
  Serial.println("'");
}

// ── Main loop (100 Hz) ─────────────────────────────────────────────────────
void loop() {
  unsigned long t0 = millis();

  float ax, ay, az, gx, gy, gz;
  bool ok = readMPU(ax, ay, az, gx, gy, gz);

  if (ok) filter.updateIMU(gx, gy, gz, ax, ay, az);

  bool settled = (millis() - bootMs) >= SETTLE_MS;

  if (settled && deviceConnected && ok) {
    float pitch = filter.getPitch();
    float roll  = filter.getRoll();

    if (zeroing) {
      zeroAccum[0] += pitch;
      zeroAccum[1] += roll;
      zeroSamples++;

      if (millis() - zeroStartMs >= ZERO_DUR_MS) {
        zeroing = false;
        Serial.printf("Zero captured over %d samples\n", zeroSamples);
      }
    }

    // Pack as 2 little-endian floats (8 bytes) and notify
    float packet[2] = { pitch, roll };
    pNotifyChar->setValue(reinterpret_cast<uint8_t*>(packet), 8);
    pNotifyChar->notify();
  }

  unsigned long elapsed = millis() - t0;
  if (elapsed < LOOP_MS) delay(LOOP_MS - elapsed);
}
```

- [ ] **Step 2: Commit**

```bash
git add firmware/PostureMax/PostureMax.ino
git commit -m "feat: rewrite firmware for single-sensor per module, IS_UPPER identity flag"
```

> **Flashing note:** Flash with `#define IS_UPPER 1` for the thoracic module, then change to `#define IS_UPPER 0` and reflash for the lumbar module.

---

## Task 4: Rewrite BLE Client + New Tests (TDD)

**Files:**
- Rewrite: `backend/ble_client.py`
- Create: `tests/test_ble_client.py`

The old `BLEClient` class is replaced by two classes:
- `DeviceConnection` — manages one BLE device (scan, connect, notify, zero, reconnect)
- `DualBLEManager` — runs two `DeviceConnection`s concurrently, combines their data, manages sessions

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ble_client.py
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_ble_client.py -v
```

Expected: `ImportError` — `DeviceConnection`, `DualBLEManager` not yet defined.

- [ ] **Step 3: Implement backend/ble_client.py**

```python
import asyncio
import logging
import struct
import time
from typing import Callable

from bleak import BleakClient, BleakScanner

from backend.config import (
    DEVICE_NAME_UPPER, DEVICE_NAME_LOWER,
    NOTIFY_UUID, ZERO_UUID,
    SETTLE_TIME_S, ZERO_DURATION_S, STALENESS_S,
)
from backend.classifier import classify
import backend.state as state


class DeviceConnection:
    """Manages one BLE connection to a single-sensor PostureMax module."""

    def __init__(self, device_name: str, role: str, on_update: Callable) -> None:
        self.device_name = device_name
        self.role        = role          # "upper" or "lower"
        self._on_update  = on_update     # called after each valid notify
        self._client     = None
        self._connect_time: float = 0.0
        self._last_seen:    float = 0.0
        self._pitch: float = 0.0
        self._roll:  float = 0.0
        # per-device reference (zeroing)
        self._ref_pitch: float = 0.0
        self._ref_roll:  float = 0.0
        self._zeroing:    bool  = False
        self._zero_start: float = 0.0
        self._zero_pitch: float = 0.0
        self._zero_roll:  float = 0.0
        self._zero_count: int   = 0

    @property
    def pitch(self) -> float:
        return self._pitch

    @property
    def roll(self) -> float:
        return self._roll

    @property
    def is_fresh(self) -> bool:
        return time.monotonic() - self._last_seen < STALENESS_S

    def _on_notify(self, _char, data: bytearray) -> None:
        if len(data) < 8:
            return   # malformed packet
        if time.monotonic() - self._connect_time < SETTLE_TIME_S:
            return   # Madgwick not yet converged

        pitch_raw, roll_raw = struct.unpack("<ff", data[:8])

        if self._zeroing:
            self._zero_pitch += pitch_raw
            self._zero_roll  += roll_raw
            self._zero_count += 1
            if time.monotonic() - self._zero_start >= ZERO_DURATION_S:
                if self._zero_count > 0:
                    self._ref_pitch = self._zero_pitch / self._zero_count
                    self._ref_roll  = self._zero_roll  / self._zero_count
                self._zeroing = False

        self._pitch     = pitch_raw - self._ref_pitch
        self._roll      = roll_raw  - self._ref_roll
        self._last_seen = time.monotonic()
        self._on_update()

    async def send_zero(self) -> None:
        if self._client and self._client.is_connected:
            await self._client.write_gatt_char(ZERO_UUID, b"\x01")
        self._zeroing    = True
        self._zero_start = time.monotonic()
        self._zero_pitch = 0.0
        self._zero_roll  = 0.0
        self._zero_count = 0

    def _reset_zero_state(self) -> None:
        self._zeroing    = False
        self._zero_count = 0
        self._zero_pitch = 0.0
        self._zero_roll  = 0.0

    async def run(self) -> None:
        while True:
            try:
                device = await BleakScanner.find_device_by_name(
                    self.device_name, timeout=10.0
                )
                if device is None:
                    await asyncio.sleep(2.0)
                    continue

                async with BleakClient(device) as client:
                    self._client       = client
                    self._connect_time = time.monotonic()
                    await client.start_notify(NOTIFY_UUID, self._on_notify)

                    while client.is_connected:
                        await asyncio.sleep(0.05)

            except Exception:
                logging.exception("BLE error (%s)", self.device_name)
            finally:
                self._reset_zero_state()
                self._client = None

            await asyncio.sleep(2.0)


class DualBLEManager:
    """Runs two DeviceConnections concurrently and combines their data."""

    def __init__(self, logger) -> None:
        self._logger = logger
        self._upper  = DeviceConnection(DEVICE_NAME_UPPER, "upper", self._on_data)
        self._lower  = DeviceConnection(DEVICE_NAME_LOWER, "lower", self._on_data)

    def _on_data(self) -> None:
        """Called synchronously from _on_notify whenever either device updates."""
        both_fresh = self._upper.is_fresh and self._lower.is_fresh

        if not both_fresh:
            if self._logger._session_id is not None:
                self._logger.end_session()
            state.set_disconnected()
            return

        # Start session on first successful combined reading
        if self._logger._session_id is None:
            self._logger.start_session()

        upper_pitch = self._upper.pitch
        upper_roll  = self._upper.roll
        lower_pitch = self._lower.pitch
        lower_roll  = self._lower.roll

        delta_pitch = upper_pitch - lower_pitch
        delta_roll  = upper_roll  - lower_roll

        posture = classify(delta_pitch, delta_roll)

        state.update_live(True, posture, delta_pitch, delta_roll,
                          upper_pitch, upper_roll, lower_pitch, lower_roll)
        self._logger.record(posture, delta_pitch, delta_roll,
                            upper_pitch, upper_roll, lower_pitch, lower_roll)

    async def _poll_zero(self) -> None:
        while True:
            if state.consume_zero_trigger():
                await asyncio.gather(
                    self._upper.send_zero(),
                    self._lower.send_zero(),
                )
            await asyncio.sleep(0.05)

    async def run(self) -> None:
        await asyncio.gather(
            self._upper.run(),
            self._lower.run(),
            self._poll_zero(),
        )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_ble_client.py -v
```

Expected: all 13 tests PASSED.

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
pytest -v
```

Expected: all tests PASSED (26 previous + 13 new = 39 total).

- [ ] **Step 6: Commit**

```bash
git add backend/ble_client.py tests/test_ble_client.py
git commit -m "feat: dual-device BLE client with staleness check and concurrent connections"
```

---

## Task 5: Update main.py

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Replace backend/main.py**

```python
import asyncio
import threading

from backend.db import get_conn, init_db
from backend.logger import SessionLogger
from backend.ble_client import DualBLEManager
from backend.api import create_app
from backend.config import DB_PATH

def _run_ble(loop: asyncio.AbstractEventLoop, logger) -> None:
    asyncio.set_event_loop(loop)
    manager = DualBLEManager(logger)
    loop.run_until_complete(manager.run())

def main() -> None:
    conn   = get_conn(DB_PATH)
    init_db(conn)
    logger = SessionLogger(conn)

    loop = asyncio.new_event_loop()
    ble_thread = threading.Thread(
        target=_run_ble, args=(loop, logger), daemon=True
    )
    ble_thread.start()

    app = create_app(db_path=DB_PATH)
    print("PostureMax backend running at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, use_reloader=False)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import works**

```bash
python -c "from backend.main import main; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run full test suite**

```bash
pytest -v
```

Expected: all tests PASSED.

- [ ] **Step 4: Commit and tag**

```bash
git add backend/main.py
git commit -m "feat: update main.py to use DualBLEManager"
git tag v2.1.0
```

---

*End of plan — PostureMax dual wireless module correction*
