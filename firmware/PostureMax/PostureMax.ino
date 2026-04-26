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
