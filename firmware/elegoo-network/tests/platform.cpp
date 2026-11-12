#include "../ArduinoPlatform.h"
#include <cassert>
using namespace charlie_elegoo;
int main() {
  ArduinoPlatform p;
  assert(p.begin());
  assert(!p.startRecoveryAP("test-recovery",nullptr));
  // Generated fixture-only secret; never configured on an actual network.
  char secret[21]{};for(int i=0;i<20;++i)secret[i]=char('a'+i);
  assert(p.startRecoveryAP("test-recovery",secret));
  assert(WiFi.ap && WiFi.wifiMode==WIFI_AP_STA && !WiFi.persistentEnabled);
  Credentials c;std::strcpy(c.ssid,"fixture-network");std::strcpy(c.password,secret);
  Credentials loaded;
  assert(!p.load(loaded));
  p.associate(c);assert(p.joined() && p.targetMatches(c));assert(Preferences::active.empty());
  p.disconnectStation();assert(WiFi.ap && !WiFi.station);
  assert(p.commit(c));assert(p.load(loaded));assert(std::strcmp(loaded.ssid,c.ssid)==0);
  auto old=Preferences::active;Preferences::fail=true;
  std::strcpy(c.ssid,"other-fixture");assert(!p.commit(c));assert(Preferences::active==old);
  Preferences::active.back()^=1;assert(!p.load(loaded));
  wipe(c);wipe(loaded);
}
