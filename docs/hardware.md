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
