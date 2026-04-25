#include <Wire.h>
#include <MadgwickAHRS.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// UUIDs must match backend/config.py
#define SERVICE_UUID "12345678-1234-1234-1234-123456789abc"
#define NOTIFY_UUID  "12345678-1234-1234-1234-123456789abd"
#define ZERO_UUID    "12345678-1234-1234-1234-123456789abe"

#define ADDR_UPPER 0x68
#define ADDR_LOWER 0x69

#define LOOP_HZ      100
#define LOOP_MS      (1000 / LOOP_HZ)
#define SETTLE_MS    2000    // discard first 2 s of filter output
#define ZERO_DUR_MS  5000    // 5 s zero capture window

Madgwick filterUpper, filterLower;

BLECharacteristic* pNotifyChar = nullptr;
BLECharacteristic* pZeroChar   = nullptr;
bool deviceConnected = false;

// Zero capture state
bool         zeroing      = false;
unsigned long zeroStartMs = 0;
float        zeroAccum[4] = {0, 0, 0, 0};  // upper_p, upper_r, lower_p, lower_r
int          zeroSamples  = 0;

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

// Triggered when backend writes 0x01 to ZERO_UUID
class ZeroCB : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    std::string val = c->getValue();
    if (!val.empty() && (uint8_t)val[0] == 0x01) {
      zeroing      = true;
      zeroStartMs  = millis();
      zeroAccum[0] = zeroAccum[1] = zeroAccum[2] = zeroAccum[3] = 0.0f;
      zeroSamples  = 0;
      Serial.println("Zero capture started");
    }
  }
};

// ── MPU6050 helpers ────────────────────────────────────────────────────────
static void initMPU(uint8_t addr) {
  Wire.beginTransmission(addr);
  Wire.write(0x6B);   // PWR_MGMT_1
  Wire.write(0x00);   // clear sleep bit
  Wire.endTransmission(true);
}

// Returns false on I2C error — caller should skip that frame silently
static bool readMPU(uint8_t addr,
                    float& ax, float& ay, float& az,
                    float& gx, float& gy, float& gz) {
  Wire.beginTransmission(addr);
  Wire.write(0x3B);   // ACCEL_XOUT_H
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(addr, (uint8_t)14) < 14) return false;

  int16_t raw[7];
  for (int i = 0; i < 7; i++)
    raw[i] = (int16_t)((Wire.read() << 8) | Wire.read());

  // raw[3] is temperature — skip
  ax = raw[0] / 16384.0f;   // ±2 g range
  ay = raw[1] / 16384.0f;
  az = raw[2] / 16384.0f;
  gx = raw[4] / 131.0f;    // ±250 °/s range
  gy = raw[5] / 131.0f;
  gz = raw[6] / 131.0f;
  return true;
}

// ── Setup ──────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Wire.begin();
  delay(100);

  // Verify both sensors are present and have distinct addresses
  Wire.beginTransmission(ADDR_UPPER);
  bool upperOk = (Wire.endTransmission() == 0);
  Wire.beginTransmission(ADDR_LOWER);
  bool lowerOk = (Wire.endTransmission() == 0);

  if (!upperOk || !lowerOk) {
    Serial.println("ERROR: one or both sensors not found — check I2C wiring");
    while (true) delay(1000);
  }

  initMPU(ADDR_UPPER);
  initMPU(ADDR_LOWER);
  filterUpper.begin(LOOP_HZ);
  filterLower.begin(LOOP_HZ);

  // BLE setup
  BLEDevice::init("PostureMax");
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
  pAdv->setMinPreferred(0x06);   // request minimum connection interval
  BLEDevice::startAdvertising();

  bootMs = millis();
  Serial.println("PostureMax ready — advertising as 'PostureMax'");
}

// ── Main loop (100 Hz) ─────────────────────────────────────────────────────
void loop() {
  unsigned long t0 = millis();

  float ax1, ay1, az1, gx1, gy1, gz1;
  float ax2, ay2, az2, gx2, gy2, gz2;

  bool ok1 = readMPU(ADDR_UPPER, ax1, ay1, az1, gx1, gy1, gz1);
  bool ok2 = readMPU(ADDR_LOWER, ax2, ay2, az2, gx2, gy2, gz2);

  // Always update filters when reads succeed (keeps them converged)
  if (ok1) filterUpper.updateIMU(gx1, gy1, gz1, ax1, ay1, az1);
  if (ok2) filterLower.updateIMU(gx2, gy2, gz2, ax2, ay2, az2);

  bool settled = (millis() - bootMs) >= SETTLE_MS;

  if (settled && deviceConnected && ok1 && ok2) {
    float upperPitch = filterUpper.getPitch();
    float upperRoll  = filterUpper.getRoll();
    float lowerPitch = filterLower.getPitch();
    float lowerRoll  = filterLower.getRoll();

    // Accumulate zero reference
    if (zeroing) {
      zeroAccum[0] += upperPitch;
      zeroAccum[1] += upperRoll;
      zeroAccum[2] += lowerPitch;
      zeroAccum[3] += lowerRoll;
      zeroSamples++;

      if (millis() - zeroStartMs >= ZERO_DUR_MS) {
        zeroing = false;
        Serial.printf("Zero captured over %d samples\n", zeroSamples);
      }
    }

    // Pack as 4 little-endian floats and notify
    float packet[4] = { upperPitch, upperRoll, lowerPitch, lowerRoll };
    pNotifyChar->setValue(reinterpret_cast<uint8_t*>(packet), 16);
    pNotifyChar->notify();
  }

  // Pace loop to 100 Hz
  unsigned long elapsed = millis() - t0;
  if (elapsed < LOOP_MS) delay(LOOP_MS - elapsed);
}