# Graph Report - .  (2026-04-25)

## Corpus Check
- Corpus is ~12,560 words - fits in a single context window. You may not need a graph.

## Summary
- 142 nodes · 249 edges · 13 communities detected
- Extraction: 61% EXTRACTED · 39% INFERRED · 0% AMBIGUOUS · INFERRED: 97 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Database & Sessions|Database & Sessions]]
- [[_COMMUNITY_Dual BLE Architecture Plan|Dual BLE Architecture Plan]]
- [[_COMMUNITY_Live State & Posture Logic|Live State & Posture Logic]]
- [[_COMMUNITY_DeviceConnection (BLE)|DeviceConnection (BLE)]]
- [[_COMMUNITY_BLE Client Entry Points|BLE Client Entry Points]]
- [[_COMMUNITY_Session Logger|Session Logger]]
- [[_COMMUNITY_Flask API & Tests|Flask API & Tests]]
- [[_COMMUNITY_Posture Classifier|Posture Classifier]]
- [[_COMMUNITY_Hardware & Firmware Docs|Hardware & Firmware Docs]]
- [[_COMMUNITY_Dashboard JavaScript|Dashboard JavaScript]]
- [[_COMMUNITY_Config|Config]]
- [[_COMMUNITY_Backend Package|Backend Package]]
- [[_COMMUNITY_Tests Package|Tests Package]]

## God Nodes (most connected - your core abstractions)
1. `DeviceConnection` - 15 edges
2. `SessionLogger` - 11 edges
3. `classify()` - 10 edges
4. `PostureMax V2 Implementation Plan` - 10 edges
5. `create_session()` - 9 edges
6. `DualBLEManager` - 8 edges
7. `get_conn()` - 8 edges
8. `finalize_session()` - 7 edges
9. `_make_fresh()` - 7 edges
10. `init_db()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `create_app()` --calls--> `get_conn()`  [INFERRED]
  backend\api.py → backend\db.py
- `create_app()` --calls--> `init_db()`  [INFERRED]
  backend\api.py → backend\db.py
- `main()` --calls--> `create_app()`  [INFERRED]
  backend\main.py → backend\api.py
- `client()` --calls--> `create_app()`  [INFERRED]
  tests\test_api.py → backend\api.py
- `test_device_is_fresh_when_recently_seen()` --calls--> `DeviceConnection`  [INFERRED]
  tests\test_ble_client.py → backend\ble_client.py

## Hyperedges (group relationships)
- **Dual Independent Wireless Module System** — hardware_module_upper, hardware_module_lower, hardware_esp32c3, hardware_mpu6050, hardware_madgwick [EXTRACTED 1.00]
- **PostureMax V2 Python Backend Stack** — v2plan_classifier, v2plan_db_layer, v2plan_session_logger, v2plan_flask_api, v2plan_state_module, v2plan_ble_client_original, requirements_bleak, requirements_flask, requirements_pytest [EXTRACTED 1.00]
- **Dual BLE Architecture Refactor** — dual_plan_device_connection, dual_plan_dual_ble_manager, dual_plan_config_update, dual_plan_firmware_rewrite, dual_plan_staleness_check [EXTRACTED 1.00]

## Communities

### Community 0 - "Database & Sessions"
Cohesion: 0.2
Nodes (18): create_session(), finalize_session(), get_conn(), get_session(), get_session_history(), get_session_readings(), init_db(), insert_reading() (+10 more)

### Community 1 - "Dual BLE Architecture Plan"
Cohesion: 0.14
Nodes (20): DeviceConnection Class, DualBLEManager Class, Rationale: asyncio.gather for Concurrent BLE, Staleness Check (STALENESS_S), Firmware Constraints (100Hz, 8-byte packet), MadgwickAHRS Sensor Fusion Filter, bleak (BLE Python library), Flask (Python web framework) (+12 more)

### Community 2 - "Live State & Posture Logic"
Cohesion: 0.2
Nodes (13): Called synchronously from _on_notify whenever either device updates., get_state(), set_disconnected(), _State, update_live(), _make_fresh(), _make_stale(), test_dual_classifies_good_posture() (+5 more)

### Community 3 - "DeviceConnection (BLE)"
Cohesion: 0.27
Nodes (9): DeviceConnection, Manages one BLE connection to a single-sensor PostureMax module., test_device_applies_reference(), test_device_is_fresh_when_recently_seen(), test_device_is_stale_when_not_seen(), test_device_on_notify_sets_fresh(), test_device_parses_8_byte_packet(), test_device_skips_during_settle() (+1 more)

### Community 4 - "BLE Client Entry Points"
Cohesion: 0.18
Nodes (5): DualBLEManager, Runs two DeviceConnections concurrently and combines their data., main(), _run_ble(), manager()

### Community 5 - "Session Logger"
Cohesion: 0.28
Nodes (7): SessionLogger, update_session(), db(), test_end_session_finalizes_stats(), test_record_before_start_is_noop(), test_record_downsamples_to_1hz(), test_start_session_creates_db_row()

### Community 6 - "Flask API & Tests"
Cohesion: 0.18
Nodes (4): create_app(), consume_zero_trigger(), client(), test_zero_sets_trigger()

### Community 7 - "Posture Classifier"
Cohesion: 0.29
Nodes (9): classify(), Classify posture based on corrected spine angle deltas.      Args:         delta, test_at_threshold_boundary_is_good(), test_good_posture(), test_hyperextended(), test_leaning_left(), test_leaning_right(), test_pitch_checked_before_roll() (+1 more)

### Community 8 - "Hardware & Firmware Docs"
Cohesion: 0.25
Nodes (11): Dual Wireless Modules Correction Plan, Config: DEVICE_NAME_UPPER/LOWER + STALENESS_S, Firmware Rewrite: IS_UPPER Flag + Single Sensor, BLE Identity (IS_UPPER Flag), ESP32-C3 Microcontroller, Hardware Failure Modes, Lower Module (PostureMax-Lower), Upper Module (PostureMax-Upper) (+3 more)

### Community 9 - "Dashboard JavaScript"
Cohesion: 0.53
Nodes (4): angleToPercent(), clamp(), formatDuration(), updateLive()

### Community 10 - "Config"
Cohesion: 1.0
Nodes (0): 

### Community 11 - "Backend Package"
Cohesion: 1.0
Nodes (0): 

### Community 12 - "Tests Package"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **14 isolated node(s):** `Manages one BLE connection to a single-sensor PostureMax module.`, `Runs two DeviceConnections concurrently and combines their data.`, `Called synchronously from _on_notify whenever either device updates.`, `Classify posture based on corrected spine angle deltas.      Args:         delta`, `Flask (Python web framework)` (+9 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Config`** (1 nodes): `config.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Backend Package`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Tests Package`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `classify()` connect `Posture Classifier` to `Live State & Posture Logic`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **Why does `DualBLEManager` connect `BLE Client Entry Points` to `Live State & Posture Logic`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Why does `DeviceConnection` connect `DeviceConnection (BLE)` to `BLE Client Entry Points`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `DeviceConnection` (e.g. with `test_device_parses_8_byte_packet()` and `test_device_skips_short_packet()`) actually correct?**
  _`DeviceConnection` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `SessionLogger` (e.g. with `main()` and `manager()`) actually correct?**
  _`SessionLogger` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `classify()` (e.g. with `._on_data()` and `test_good_posture()`) actually correct?**
  _`classify()` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `create_session()` (e.g. with `.start_session()` and `test_history_returns_finished_sessions()`) actually correct?**
  _`create_session()` has 8 INFERRED edges - model-reasoned connections that need verification._