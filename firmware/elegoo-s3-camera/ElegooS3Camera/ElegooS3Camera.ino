// Build-only candidate. NOT HARDWARE QUALIFIED. See ../ACCEPTANCE.md.
#include <Arduino.h>
#include <esp_system.h>
#include "Identity.h"
#include "NetworkRuntime.h"
#include "ProvisioningServer.h"
#include "MotorBridge.h"
#include "CameraWebServer_AP.h"
static Identity identity;
static NetworkRuntime network;
static MotorBridge bridge;
static CameraWebServer_AP camera;
static char deviceId[32]{};
static char enrollment[7169]{};
static size_t enrollmentSize=0;
static bool enrollmentOverflow=false;
static void bridgeTask(void*){for(;;){bridge.tick(millis());vTaskDelay(pdMS_TO_TICKS(2));}}
void setup() {
  Serial.begin(115200);Serial.setDebugOutput(false);
  uint8_t mac[6];esp_read_mac(mac,ESP_MAC_WIFI_STA);
  snprintf(deviceId,sizeof(deviceId),"elegoo-%02x%02x%02x%02x%02x%02x",mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
  pinMode(0,INPUT_PULLUP); // candidate BOOT-button input; physical acceptance required
  bool enrolled=identity.begin(deviceId);
  const uint32_t began=millis();
  while(!enrolled) {
    // No AP, camera, motor UART or TCP server before valid physical enrollment.
    // Press BOOT AFTER normal boot while sending one bounded USB enrollment line.
    const bool authorized=uint32_t(millis()-began)<60000 && digitalRead(0)==LOW;
    if(!authorized && enrollmentSize){wipeBytes(enrollment,sizeof(enrollment));enrollmentSize=0;enrollmentOverflow=false;}
    for(unsigned count=0;Serial.available() && count<256;++count) {
      const char c=Serial.read();
      if(!authorized){wipeBytes(enrollment,sizeof(enrollment));enrollmentSize=0;enrollmentOverflow=false;continue;}
      if(c=='\n') {
        enrollment[enrollmentSize]=0;
        enrolled=!enrollmentOverflow && !strncmp(enrollment,"ENROLL ",7) && identity.enroll(enrollment+7,deviceId);
        wipeBytes(enrollment,sizeof(enrollment));enrollmentSize=0;enrollmentOverflow=false;
        Serial.println(enrolled?"Enrollment accepted":"Enrollment rejected");
      } else if(enrollmentSize<sizeof(enrollment)-1)enrollment[enrollmentSize++]=c;
      else enrollmentOverflow=true;
    }
    delay(2);
  }
  if(!network.begin(identity.record())){Serial.println("Network initialization failed");return;}
  if(!startProvisioningServer(network,identity.record())){Serial.println("HTTPS initialization failed");return;}
  if(!camera.CameraWebServer_AP_Init())Serial.println("Camera unavailable; authenticated recovery remains available");
  const uint64_t chip=ESP.getEfuseMac();char legacyName[13];
  snprintf(legacyName,sizeof(legacyName),"%04X%08X",static_cast<uint16_t>(chip>>32),static_cast<uint32_t>(chip));
  bridge.begin(legacyName,identity.record().commandKey);
  if(xTaskCreatePinnedToCore(bridgeTask,"charlie-uart-owner",6144,nullptr,6,nullptr,1)!=pdPASS)
    Serial.println("Bridge task unavailable");
}
void loop(){delay(1000);}
