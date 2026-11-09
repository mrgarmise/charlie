#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include "NetworkCore.h"
#include "FrameParser.h"
#ifndef CHARLIE_ENABLE_MOTOR_FORWARDING
#define CHARLIE_ENABLE_MOTOR_FORWARDING 0
#endif
// One UART writer. Provisioning has no reference to this object.
class MotorBridge {
  WiFiServer server_{100};
  WiFiClient client_;
  charlie_elegoo::FrameParser tcp_, uart_;
  charlie_elegoo::ControlSession session_;
  bool stopPending_=true;
  bool factoryLinked_=false;
  uint32_t sentHeartbeat_=0, factoryAt_=0;
  char factoryName_[13]{};
  static MotorBridge* owner_;
  static void stopCallback();
  void writeUart(const char* frame); // the ONLY Serial2.write site
  bool sendClient(const char* frame);
  void closeClient();
 public:
  MotorBridge():session_(stopCallback){owner_=this;}
  void begin(const char* legacyFactoryName);
  void tick(uint32_t now);
  bool connected() const {return session_.connected();}
};
