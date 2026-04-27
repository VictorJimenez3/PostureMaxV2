# Graph Report - .  (2026-04-26)

## Corpus Check
- Corpus is ~14,254 words - fits in a single context window. You may not need a graph.

## Summary
- 159 nodes · 278 edges · 13 communities detected
- Extraction: 62% EXTRACTED · 38% INFERRED · 0% AMBIGUOUS · INFERRED: 106 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_BLE Connection & State Management|BLE Connection & State Management]]
- [[_COMMUNITY_Flask API & Database Layer|Flask API & Database Layer]]
- [[_COMMUNITY_DeviceConnection & Dual BLE Logic|DeviceConnection & Dual BLE Logic]]
- [[_COMMUNITY_Plans, Config & Docs|Plans, Config & Docs]]
- [[_COMMUNITY_Posture Classifier|Posture Classifier]]
- [[_COMMUNITY_Session Logger|Session Logger]]
- [[_COMMUNITY_Firmware & Hardware|Firmware & Hardware]]
- [[_COMMUNITY_Dashboard JavaScript|Dashboard JavaScript]]
- [[_COMMUNITY_API Tests|API Tests]]
- [[_COMMUNITY_BLE Client Properties|BLE Client Properties]]
- [[_COMMUNITY_Config Module|Config Module]]
- [[_COMMUNITY_Backend Package|Backend Package]]
- [[_COMMUNITY_Tests Package|Tests Package]]

## God Nodes (most connected - your core abstractions)
1. `DeviceConnection` - 15 edges
2. `DualBLEManager` - 12 edges
3. `PostureMax V2 Implementation Plan` - 12 edges
4. `SessionLogger` - 11 edges
5. `classify()` - 10 edges
6. `create_session()` - 9 edges
7. `get_conn()` - 8 edges
8. `Dual Wireless Modules Architecture Correction Plan` - 8 edges
9. `finalize_session()` - 7 edges
10. `_make_fresh()` - 7 edges

## Surprising Connections (you probably didn't know these)
- `client()` --calls--> `create_app()`  [INFERRED]
  tests\test_api.py → backend\api.py
- `test_device_is_fresh_when_recently_seen()` --calls--> `DeviceConnection`  [INFERRED]
  tests\test_ble_client.py → backend\ble_client.py
- `test_device_is_stale_when_not_seen()` --calls--> `DeviceConnection`  [INFERRED]
  tests\test_ble_client.py → backend\ble_client.py
- `test_good_posture()` --calls--> `classify()`  [INFERRED]
  tests\test_classifier.py → backend\classifier.py
- `test_slouching_forward()` --calls--> `classify()`  [INFERRED]
  tests\test_classifier.py → backend\classifier.py

## Hyperedges (group relationships)
- **Dual Independent Wireless Module System** — hardware_upper_module, hardware_lower_module, hardware_esp32c3, hardware_mpu6050, hardware_madgwick [EXTRACTED 1.00]
- **PostureMax V2 Python Backend Stack** — v2plan_classifier, v2plan_db_layer, v2plan_session_logger, v2plan_flask_api, v2plan_state_module, v2plan_ble_client_original, requirements_bleak, requirements_flask, requirements_pytest [EXTRACTED 1.00]
- **Dual BLE Architecture Refactor** — dual_plan_device_connection, dual_plan_dual_ble_manager, dual_plan_config_update, dual_plan_firmware_rewrite, dual_plan_staleness_check [EXTRACTED 1.00]

## Communities

### Community 0 - "BLE Connection & State Management"
Cohesion: 0.08
Nodes (17): DualBLEManager, Runs two DeviceConnections concurrently and combines their data., Connect briefly and read the GATT Device Name characteristic., Scan once and return the BLEDevice for dc, or None.         Falls back to servic, Scan -> connect -> reconnect loop for one device., Log a 'both connected' message once when both sensors are live,         and a 'r, Connect to an already-found device and stream until disconnected., _run_ble() (+9 more)

### Community 1 - "Flask API & Database Layer"
Cohesion: 0.16
Nodes (21): create_app(), create_session(), finalize_session(), get_conn(), get_session(), get_session_history(), get_session_readings(), init_db() (+13 more)

### Community 2 - "DeviceConnection & Dual BLE Logic"
Cohesion: 0.19
Nodes (20): DeviceConnection, Called synchronously from _on_notify whenever either device updates., Manages one BLE connection to a single-sensor PostureMax module., get_state(), update_live(), _make_fresh(), _make_stale(), test_device_applies_reference() (+12 more)

### Community 3 - "Plans, Config & Docs"
Cohesion: 0.1
Nodes (22): Graphify Knowledge Graph Rules, Config Update DEVICE_NAME_UPPER LOWER plus STALENESS_S, DeviceConnection Class single BLE device manager, DualBLEManager Class concurrent dual BLE connections, main.py Update BLEClient to DualBLEManager, Dual Wireless Modules Architecture Correction Plan, Rationale asyncio gather for Concurrent BLE Connections, Staleness Check STALENESS_S pause classification (+14 more)

### Community 4 - "Posture Classifier"
Cohesion: 0.29
Nodes (9): classify(), Classify posture based on corrected spine angle deltas.      Args:         delta, test_at_threshold_boundary_is_good(), test_good_posture(), test_hyperextended(), test_leaning_left(), test_leaning_right(), test_pitch_checked_before_roll() (+1 more)

### Community 5 - "Session Logger"
Cohesion: 0.36
Nodes (5): SessionLogger, test_end_session_finalizes_stats(), test_record_before_start_is_noop(), test_record_downsamples_to_1hz(), test_start_session_creates_db_row()

### Community 6 - "Firmware & Hardware"
Cohesion: 0.29
Nodes (11): Firmware Rewrite IS_UPPER Flag Single Sensor per Module, BLE Identity via IS_UPPER Compile-Time Flag, ESP32-C3 Super Mini Microcontroller, Hardware Failure Modes, Firmware Constraints 100Hz 8-byte packet pitch+roll only, Lower Module PostureMax-Lower L3-L5 lumbar, MadgwickAHRS Sensor Fusion Filter, MPU6050 IMU Sensor (+3 more)

### Community 7 - "Dashboard JavaScript"
Cohesion: 0.48
Nodes (5): angleToPercent(), clamp(), formatDuration(), updateDevices(), updateLive()

### Community 8 - "API Tests"
Cohesion: 0.29
Nodes (1): client()

### Community 9 - "BLE Client Properties"
Cohesion: 0.5
Nodes (0): 

### Community 10 - "Config Module"
Cohesion: 1.0
Nodes (0): 

### Community 11 - "Backend Package"
Cohesion: 1.0
Nodes (0): 

### Community 12 - "Tests Package"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **23 isolated node(s):** `Manages one BLE connection to a single-sensor PostureMax module.`, `Connect to an already-found device and stream until disconnected.`, `Runs two DeviceConnections concurrently and combines their data.`, `Called synchronously from _on_notify whenever either device updates.`, `Connect briefly and read the GATT Device Name characteristic.` (+18 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Config Module`** (1 nodes): `config.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Backend Package`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Tests Package`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DualBLEManager` connect `BLE Connection & State Management` to `BLE Client Properties`, `DeviceConnection & Dual BLE Logic`?**
  _High betweenness centrality (0.123) - this node is a cross-community bridge._
- **Why does `classify()` connect `Posture Classifier` to `DeviceConnection & Dual BLE Logic`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Why does `DeviceConnection` connect `DeviceConnection & Dual BLE Logic` to `BLE Connection & State Management`, `BLE Client Properties`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `DeviceConnection` (e.g. with `test_device_parses_8_byte_packet()` and `test_device_skips_short_packet()`) actually correct?**
  _`DeviceConnection` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `DualBLEManager` (e.g. with `_run_ble()` and `manager()`) actually correct?**
  _`DualBLEManager` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `SessionLogger` (e.g. with `main()` and `manager()`) actually correct?**
  _`SessionLogger` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `classify()` (e.g. with `._on_data()` and `test_good_posture()`) actually correct?**
  _`classify()` has 8 INFERRED edges - model-reasoned connections that need verification._