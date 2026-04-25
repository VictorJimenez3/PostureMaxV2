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
                pass  # reconnect silently
            finally:
                state.set_disconnected()
                if self._logger._session_id is not None:
                    self._logger.end_session()
                self._client = None

            await asyncio.sleep(2.0)
