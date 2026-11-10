#include "MotorBridge.h"
#include <sys/socket.h>
#include <esp_system.h>
#include <driver/uart.h>
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
  session_.close();client_.stop();tcp_.reset();uart_.reset();gate_.clear();pulseActive_=false;pulseTxPending_=false;
}
void MotorBridge::begin(const char* legacyFactoryName,const char* commandKey) {
  strncpy(commandKey_,commandKey,sizeof(commandKey_)-1);
  strncpy(factoryName_,legacyFactoryName,sizeof(factoryName_)-1);
  Serial2.setTxBufferSize(512);
  Serial2.begin(9600,SERIAL_8N1,3,40); // candidate pin contract; NOT hardware qualified
  server_.begin();server_.setNoDelay(true);
  pinMode(46,OUTPUT);
  writeUart("{\"N\":100}");
  // Official startup marker is bracketed by STOP; it never authorizes a session.
  writeUart("{Factory}");stopPending_=true;writeUart("{\"N\":100}");
}
void MotorBridge::tick(uint32_t now) {
  if(pulseActive_ && pulseTxPending_) {
    // UART transmit completion, not enqueue time, bounds when UNO can parse '}'.
    if(uart_wait_tx_done(UART_NUM_2,0)==ESP_OK){pulseTxPending_=false;pulseAt_=now;}
    else if(uint32_t(now-pulseAt_)>=100)closeClient(); // stalled transmit: fail closed
  }
  if(pulseActive_ && !pulseTxPending_ && uint32_t(now-pulseAt_)>=pulseDuration_){pulseActive_=false;stopPending_=true;}
  // STOP always precedes new traffic and survives session close/reconnect.
  if(stopPending_)writeUart("{\"N\":100}");
  if(server_.hasClient()) {
    WiFiClient incoming=server_.available();
    if(session_.connected() || stopPending_)incoming.stop();
    else {
      client_=incoming;tcp_.reset();uart_.reset();
      session_.open(now);sentHeartbeat_=now;
      uint8_t random[16];esp_fill_random(random,sizeof(random));char nonce[33]{};
      for(unsigned i=0;i<16;++i)snprintf(nonce+2*i,3,"%02x",random[i]);
      gate_.begin(commandKey_,nonce);char challenge[64];snprintf(challenge,sizeof(challenge),"{Challenge:%s:%lu}",nonce,static_cast<unsigned long>(now));
      if(!sendClient(challenge) || !sendClient("{Heartbeat}"))closeClient();
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
      else if(stopFrame(frame)) {
        pulseActive_=false;pulseTxPending_=false;gate_.cancel();
        // Canonical N1 tagged STOP preserves existing Pi exact-ACK handling.
        if(Serial2.availableForWrite()<static_cast<int>(strlen(frame))){closeClient();break;}
        if(stopPending_)writeUart("{\"N\":100}");
        writeUart(frame);
      }
      else if(!strncmp(frame,"{Auth:",6)) {
        if(!gate_.header(frame,now)){closeClient();break;}
      }
      else {
        const int duration=commandDuration(frame);
        if(!session_.mayForward() || stopPending_ || pulseActive_ || duration<0 || !gate_.consume(frame,now)
            || uart_wait_tx_done(UART_NUM_2,0)!=ESP_OK
            || Serial2.availableForWrite()<static_cast<int>(strlen(frame))) {closeClient();break;}
        writeUart(frame);
        if(duration>0){pulseActive_=true;pulseTxPending_=true;pulseAt_=now;pulseDuration_=duration;}
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
