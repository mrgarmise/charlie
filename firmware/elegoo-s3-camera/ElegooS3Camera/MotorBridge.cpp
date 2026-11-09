#include "MotorBridge.h"
#include <sys/socket.h>
MotorBridge* MotorBridge::owner_=nullptr;
void MotorBridge::stopCallback(){if(owner_)owner_->stopPending_=true;}
void MotorBridge::writeUart(const char* frame) {
  if(stopPending_ && strcmp(frame,"{\"N\":100}"))return;
  const size_t size=strlen(frame);
  if(Serial2.availableForWrite()<static_cast<int>(size))return;
  Serial2.write(reinterpret_cast<const uint8_t*>(frame),size);
  if(!strcmp(frame,"{\"N\":100}"))stopPending_=false;
}
bool MotorBridge::sendClient(const char* frame) {
  const size_t size=strlen(frame);
  return client_ && ::send(client_.fd(),frame,size,MSG_DONTWAIT)==static_cast<int>(size);
}
void MotorBridge::closeClient() {
  session_.close();client_.stop();tcp_.reset();uart_.reset();
}
void MotorBridge::begin(const char* legacyFactoryName) {
  strncpy(factoryName_,legacyFactoryName,sizeof(factoryName_)-1);
  Serial2.setTxBufferSize(512);
  Serial2.begin(9600,SERIAL_8N1,3,40); // candidate pin contract; NOT hardware qualified
  server_.begin();server_.setNoDelay(true);
  pinMode(46,OUTPUT);
  writeUart("{\"N\":100}");
}
void MotorBridge::tick(uint32_t now) {
  // STOP always precedes new traffic and survives session close/reconnect.
  if(stopPending_)writeUart("{\"N\":100}");
  if(server_.hasClient()) {
    WiFiClient incoming=server_.available();
    if(session_.connected() || stopPending_)incoming.stop();
    else {
      client_=incoming;tcp_.reset();uart_.reset();
      session_.open(now);sentHeartbeat_=now;
      if(!sendClient("{Heartbeat}"))closeClient();
    }
  }
  session_.tick(now,client_ && client_.connected());
  if(!session_.connected() && client_)closeClient();
  if(session_.connected() && uint32_t(now-sentHeartbeat_)>=1000) {
    sentHeartbeat_=now;if(!sendClient("{Heartbeat}"))closeClient();
  }
  if(tcp_.expired(now) || uart_.expired(now))closeClient();
  for(unsigned count=0;session_.connected() && client_.available() && count<256;++count) {
    const auto result=tcp_.feed(static_cast<char>(client_.read()),now);
    if(result==charlie_elegoo::FrameParser::Result::Error){closeClient();break;}
    if(result==charlie_elegoo::FrameParser::Result::Complete) {
      const char* frame=tcp_.frame();
      if(!strcmp(frame,"{Heartbeat}"))session_.heartbeated(now);
      else if(!strcmp(frame,"{\"N\":100}"))stopPending_=true;
      else {
#if CHARLIE_ENABLE_MOTOR_FORWARDING
        if(!session_.mayForward() || stopPending_ || Serial2.availableForWrite()<static_cast<int>(strlen(frame))) {
          closeClient();break;
        }
        writeUart(frame);
#else
        // Observation-only candidate; no remote operation grants motion admission.
        closeClient();break;
#endif
      }
      tcp_.reset();
    }
  }
  for(unsigned count=0;Serial2.available() && count<256;++count) {
    const auto result=uart_.feed(static_cast<char>(Serial2.read()),now);
    if(result==charlie_elegoo::FrameParser::Result::Error){closeClient();break;}
    if(result==charlie_elegoo::FrameParser::Result::Complete) {
      if(session_.connected()) {if(!sendClient(uart_.frame()))closeClient();}
      else if(!strcmp(uart_.frame(),"{BT_detection}"))writeUart("{BT_OK}");
      else if(!strcmp(uart_.frame(),"{WA_detection}")) {
        char response[16];snprintf(response,sizeof(response),"{%s}",factoryName_);writeUart(response);
      }
      uart_.reset();
    }
  }
  // FactoryTest is separate from TCP state; it cannot authorize forwarding.
  if(uint32_t(now-factoryAt_)>=100) {
    factoryAt_=now;
    const bool linked=charlie_elegoo::factoryLink(WiFi.softAPgetStationNum()>0,session_.connected());
    digitalWrite(46,linked?LOW:((now/100)%2?HIGH:LOW));
    if(linked!=factoryLinked_){writeUart(linked?"{WA_OK}":"{WA_NO}");factoryLinked_=linked;}
  }
}
