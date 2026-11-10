#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include "NetworkCore.h"
#include "FrameParser.h"
#include "CommandGate.h"
// One UART writer. Provisioning has no reference to this object.
class MotorBridge {
  WiFiServer server_{100};
  WiFiClient client_;
  charlie_elegoo::FrameParser tcp_, uart_;
  charlie_elegoo::ControlSession session_;
  CommandGate gate_;
  char commandKey_[65]{};
  bool pulseActive_=false,pulseTxPending_=false;
  uint32_t pulseAt_=0,pulseDuration_=0;
  // Completion ACK is emitted AFTER the UNO stops. Bound its loop/serial slack;
  // this is a fallback deadline, never a change to the requested UNO duration.
  static constexpr uint32_t pulseCompletionSlack_=80;
  char pulseAck_[38]{};
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
  void begin(const char* legacyFactoryName,const char* commandKey);
  void tick(uint32_t now);
  bool connected() const {return session_.connected();}
};
