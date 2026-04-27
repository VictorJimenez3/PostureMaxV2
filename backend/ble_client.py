import asyncio
import logging
import struct
import time
from typing import Callable

from bleak import BleakClient, BleakScanner

from backend.config import (
    DEVICE_NAME_UPPER, DEVICE_NAME_LOWER,
    SERVICE_UUID, NOTIFY_UUID, ZERO_UUID,
    SETTLE_TIME_S, ZERO_DURATION_S, STALENESS_S,
)
from backend.classifier import classify
import backend.state as state

# Generic Access — Device Name characteristic
_GATT_DEVICE_NAME = "00002a00-0000-1000-8000-00805f9b34fb"


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
        self._calibrated: bool  = False

    @property
    def pitch(self) -> float:
        return self._pitch

    @property
    def roll(self) -> float:
        return self._roll

    @property
    def calibrated(self) -> bool:
        return self._calibrated

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
                self._zeroing    = False
                self._calibrated = True
                state.add_ble_log(f"{self.device_name} calibrated")

        self._pitch     = pitch_raw - self._ref_pitch
        self._roll      = roll_raw  - self._ref_roll
        self._last_seen = time.monotonic()
        self._on_update()

    async def send_zero(self) -> None:
        if self._client and self._client.is_connected:
            try:
                await self._client.write_gatt_char(ZERO_UUID, b"\x01", response=False)
            except Exception:
                pass  # firmware signal optional; backend zeroing proceeds regardless
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

    async def connect_and_run(self, device) -> None:
        """Connect to an already-found device and stream until disconnected."""
        try:
            state.add_ble_log(f"Connecting to {self.device_name}...")
            async with BleakClient(device) as client:
                self._client       = client
                self._connect_time = time.monotonic()
                await client.start_notify(NOTIFY_UUID, self._on_notify)
                state.set_device_connected(self.role, True)
                state.add_ble_log(f"{self.device_name} connected")
                logging.info("BLE connected: %s", self.device_name)

                while client.is_connected:
                    await asyncio.sleep(0.05)

                state.add_ble_log(f"{self.device_name} disconnected")

        except Exception as exc:
            state.add_ble_log(f"{self.device_name} error: {exc}")
            logging.exception("BLE error (%s)", self.device_name)
        finally:
            self._reset_zero_state()
            self._calibrated = False
            self._client = None
            state.set_device_connected(self.role, False)


class DualBLEManager:
    """Runs two DeviceConnections concurrently and combines their data."""

    def __init__(self, logger) -> None:
        self._logger    = logger
        self._upper     = DeviceConnection(DEVICE_NAME_UPPER, "upper", self._on_data)
        self._lower     = DeviceConnection(DEVICE_NAME_LOWER, "lower", self._on_data)
        # Serialize BLE scans: two concurrent scanners fight over the Windows
        # BLE adapter and both fail silently. One scan at a time fixes this.
        self._scan_lock = asyncio.Lock()

    def _on_data(self) -> None:
        """Called synchronously from _on_notify whenever either device updates."""
        both_fresh = self._upper.is_fresh and self._lower.is_fresh

        if not both_fresh:
            if self._logger._session_id is not None:
                self._logger.end_session()
            state.set_disconnected()
            return

        upper_pitch = self._upper.pitch
        upper_roll  = self._upper.roll
        lower_pitch = self._lower.pitch
        lower_roll  = self._lower.roll
        delta_pitch = upper_pitch - lower_pitch
        delta_roll  = upper_roll  - lower_roll

        both_calibrated = self._upper.calibrated and self._lower.calibrated
        if not both_calibrated:
            # Sensors connected but not yet zeroed — hold classification
            state.update_live(True, "calibrating", delta_pitch, delta_roll,
                              upper_pitch, upper_roll, lower_pitch, lower_roll)
            return

        # Start session on first successfully calibrated reading
        if self._logger._session_id is None:
            self._logger.start_session()

        posture = classify(delta_pitch, delta_roll)

        state.update_live(True, posture, delta_pitch, delta_roll,
                          upper_pitch, upper_roll, lower_pitch, lower_roll)
        self._logger.record(posture, delta_pitch, delta_roll,
                            upper_pitch, upper_roll, lower_pitch, lower_roll)

    async def _read_gatt_name(self, device) -> str | None:
        """Connect briefly and read the GATT Device Name characteristic."""
        try:
            async with BleakClient(device, timeout=6.0) as client:
                data = await client.read_gatt_char(_GATT_DEVICE_NAME)
                return data.decode("utf-8")
        except Exception as exc:
            state.add_ble_log(f"Name probe {device.address}: {exc}")
            return None

    async def _scan_for(self, dc: DeviceConnection):
        """
        Scan once and return the BLEDevice for dc, or None.
        Falls back to service-UUID matching + GATT name probe when the
        advertisement name is truncated (e.g. 'Po' instead of full name).
        """
        exact = None
        # Use dict keyed by address to deduplicate devices seen multiple times
        uuid_candidates: dict = {}
        target = dc.device_name.lower()
        svc_lower = SERVICE_UUID.lower()

        def on_detect(device, adv):
            nonlocal exact
            if exact is not None:
                return
            adv_name = (adv.local_name or device.name or "").lower()
            adv_uuids = [str(u).lower() for u in (adv.service_uuids or [])]
            if adv_name == target:
                exact = device
            elif svc_lower in adv_uuids:
                uuid_candidates[device.address] = device   # deduped by address

        state.add_ble_log(f"Scanning for {dc.device_name}...")
        async with BleakScanner(detection_callback=on_detect):
            await asyncio.sleep(10.0)

        if exact:
            return exact

        candidates = list(uuid_candidates.values())
        if candidates:
            state.add_ble_log(
                f"Found {len(candidates)} PostureMax device(s) with "
                f"truncated name - probing via GATT"
            )
            for cand in candidates:
                name = await self._read_gatt_name(cand)
                if name:
                    state.add_ble_log(f"Probe: {cand.address} -> '{name}'")
                if name and name.lower() == target:
                    state.add_ble_log(
                        f"Matched {dc.device_name} - "
                        f"reflash firmware (setScanResponse(true)) to skip probing"
                    )
                    return cand

        return None

    async def _manage(self, dc: DeviceConnection) -> None:
        """Scan -> connect -> reconnect loop for one device."""
        while True:
            state.consume_retry(dc.role)

            async with self._scan_lock:
                device = await self._scan_for(dc)

            if device is None:
                state.add_ble_log(f"{dc.device_name} not found - will retry")
                # Wait up to 2s but skip the wait if a manual retry is requested
                for _ in range(20):
                    await asyncio.sleep(0.1)
                    if state.consume_retry(dc.role):
                        break
                continue

            await dc.connect_and_run(device)
            # Brief pause before re-scanning so the device has time to re-advertise
            state.add_ble_log(f"Waiting 3s before rescanning {dc.device_name}...")
            await asyncio.sleep(3.0)

    async def _poll_zero(self) -> None:
        while True:
            if state.consume_zero_trigger():
                try:
                    await asyncio.gather(
                        self._upper.send_zero(),
                        self._lower.send_zero(),
                    )
                except Exception as exc:
                    logging.exception("Zero trigger error: %s", exc)
            await asyncio.sleep(0.05)

    async def _auto_calibrate(self) -> None:
        """Wait for Madgwick to fully settle, then auto-zero both sensors."""
        await asyncio.sleep(3.0)
        if not (self._upper.is_fresh and self._lower.is_fresh):
            return  # one disconnected during the wait — abort
        state.add_ble_log("Capturing baseline — hold still in good posture for 5s...")
        try:
            await asyncio.gather(self._upper.send_zero(), self._lower.send_zero())
        except Exception as exc:
            logging.exception("Auto-calibrate error: %s", exc)
        # _calibrated flips to True inside _on_notify once the 5s window closes

    async def _log_heartbeat(self) -> None:
        """Log connection events and trigger auto-calibration on first connect."""
        was_both_connected = False
        while True:
            upper_ok = self._upper.is_fresh
            lower_ok = self._lower.is_fresh
            both = upper_ok and lower_ok
            if both and not was_both_connected:
                state.add_ble_log(
                    "Both sensors connected - sit up straight, calibrating in 3s..."
                )
                was_both_connected = True
                asyncio.create_task(self._auto_calibrate())
            elif not both and was_both_connected:
                who = []
                if not upper_ok:
                    who.append("Upper")
                if not lower_ok:
                    who.append("Lower")
                state.add_ble_log(f"{' & '.join(who)} sensor(s) lost - reconnecting...")
                was_both_connected = False
            await asyncio.sleep(1.0)

    async def run(self) -> None:
        await asyncio.gather(
            self._manage(self._upper),
            self._manage(self._lower),
            self._poll_zero(),
            self._log_heartbeat(),
        )
