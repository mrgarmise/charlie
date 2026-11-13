#pragma once
#include <string>
constexpr int WIFI_AP_STA=3, WL_CONNECTED=3;
struct FakeWiFi {
  bool persistentEnabled=true, ap=false, station=false;
  int wifiMode=0;
  std::string network;
  void persistent(bool enabled) {persistentEnabled=enabled;}
  bool mode(int mode) {wifiMode=mode;return true;}
  bool softAP(const char*,const char*) {ap=true;return true;}
  void begin(const char* name,const char*) {network=name;station=true;}
  int status() const {return station?WL_CONNECTED:0;}
  std::string SSID() const {return network;}
  void disconnect(bool disableRadio,bool eraseConfig) {
    if(disableRadio)ap=false;
    if(eraseConfig)network.clear();
    station=false;
  }
};
inline FakeWiFi WiFi;
