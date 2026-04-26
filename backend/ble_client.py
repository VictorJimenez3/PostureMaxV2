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
