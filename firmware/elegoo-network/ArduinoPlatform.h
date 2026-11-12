#pragma once
// Integration adapter, not an application/sketch. Requires reviewed matching S3
// source. Candidate core pin: espressif:esp32@2.0.17; native compile unverified.
#include <WiFi.h>
#include <Preferences.h>
#include "NetworkCore.h"
namespace charlie_elegoo {
class ArduinoPlatform : public Platform {
  Preferences preferences;
  struct Record {
    uint32_t schema;
    Credentials credentials;
    uint32_t checksum;
  };
  static uint32_t checksum(const Credentials& credentials) {
    // Corruption detection only; encryption/physical protection is a separate gate.
    uint32_t value=2166136261u;
    const auto* bytes=reinterpret_cast<const uint8_t*>(&credentials);
    for (unsigned i=0;i<sizeof credentials;++i)value=(value^bytes[i])*16777619u;
    return value;
  }
 public:
  bool begin() { return preferences.begin("charlie-net",false); }
  bool startRecoveryAP(const char* configuredName, const char* privateSecret) {
    if (!configuredName || !privateSecret || strlen(privateSecret)<12) return false;
    WiFi.persistent(false); // explicit NVS owner; don't persist pending credentials
    if (!WiFi.mode(WIFI_AP_STA)) return false;
    return WiFi.softAP(configuredName,privateSecret);
  }
  void associate(const Credentials& credentials) override {
    WiFi.begin(credentials.ssid,credentials.password);
  }
  bool joined() const override { return WiFi.status()==WL_CONNECTED; }
  bool targetMatches(const Credentials& credentials) const override {
    return WiFi.SSID()==credentials.ssid;
  }
  void disconnectStation() override { WiFi.disconnect(false,false); }
  bool load(Credentials& credentials) override {
    if (preferences.getBytesLength("active")!=sizeof(Record))return false;
    Record record{};
    bool good=preferences.getBytes("active",&record,sizeof record)==sizeof record
      && record.schema==1 && valid(record.credentials)
      && record.checksum==checksum(record.credentials);
    if (good)credentials=record.credentials;
    wipe(record.credentials);
    return good;
  }
  bool commit(const Credentials& credentials) override {
    if (!valid(credentials))return false;
    Record record{};
    record.schema=1;record.credentials=credentials;record.checksum=checksum(credentials);
    // Single NVS blob replacement is transactional in ESP-IDF. No other namespace,
    // legacy NVS, SPIFFS, partitions or boot selection is modified.
    bool good=preferences.putBytes("active",&record,sizeof record)==sizeof record;
    wipe(record.credentials);
    return good;
  }
};
} // namespace charlie_elegoo
