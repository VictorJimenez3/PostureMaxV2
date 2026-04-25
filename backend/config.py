DEVICE_NAME = "PostureMax"

SERVICE_UUID = "12345678-1234-1234-1234-123456789abc"
NOTIFY_UUID  = "12345678-1234-1234-1234-123456789abd"
ZERO_UUID    = "12345678-1234-1234-1234-123456789abe"

SLOUCH_THRESHOLD  = 15.0   # degrees forward flex
LATERAL_THRESHOLD = 10.0   # degrees lateral lean

LOG_INTERVAL_S  = 1.0    # downsample: log once per second
SETTLE_TIME_S   = 2.0    # discard first 2s after BLE connect (Madgwick settling)
ZERO_DURATION_S = 5.0    # average over 5s for reference capture

DB_PATH = "posturemax.db"
