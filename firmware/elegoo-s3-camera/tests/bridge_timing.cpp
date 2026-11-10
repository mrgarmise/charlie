#include "../ElegooS3Camera/MotorBridge.h"
#include <driver/uart.h>
#include <cassert>
#include <algorithm>
#include <climits>
static constexpr const char* pulse=R"({"N":2,"H":"pulse1","D1":3,"D2":20,"T":100})";
[[maybe_unused]] static constexpr const char* signedPulse="{Auth:1:100:717b702dfe9caccb73829fbe4cf81eea230efc4b2c391aac8b3505e0b5c351cd}";
static void input(const char* s){for(;*s;++s)memoryInput.push_back(*s);}
static void reply(const char* s){for(;*s;++s)Serial2.input.push_back(*s);}
static size_t stops(){return std::count(Serial2.writes.begin(),Serial2.writes.end(),R"({"N":100})");}
static void start(MotorBridge& b,uint32_t base=0,bool finishTx=true){
 Serial2=TestSerial{};memoryInput.clear();memoryOutput.clear();memoryConnected=false;uartTxBusy=false;
 b.begin("0123456789AB","AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA");
 memoryIncoming=true;b.tick(base);input("{Heartbeat}");b.tick(base+1);
 const std::string nonce=memoryOutput.front().substr(11,32);
 const std::string message="charlie-elegoo-command-v1\n"+nonce+"\n1\n100\n"+pulse;
 const std::string key(43,'A');unsigned char digest[32]{};char tag[65]{};
 assert(mbedtls_md_hmac(mbedtls_md_info_from_string("SHA256"),reinterpret_cast<const unsigned char*>(key.data()),key.size(),reinterpret_cast<const unsigned char*>(message.data()),message.size(),digest)==0);
 for(unsigned i=0;i<32;++i)snprintf(tag+i*2,3,"%02x",digest[i]);
 const auto auth="{Auth:1:100:"+std::string(tag)+"}";
 if(nonce=="0102030405060708090a0b0c0d0e0f10")assert(auth==signedPulse);
 input(auth.c_str());input(pulse);b.tick(base+3);assert(b.connected());
 uartTxBusy=true;b.tick(base+49);if(finishTx){uartTxBusy=false;b.tick(base+50);}
}
int main(){
 // UNO cooperative timer uses elapsed>T. Its next loop can follow T by11ms;
 // tagged ACK then needs about12ms at9600baud. Old N100 at150 cancels that mode
 // (and its completion ACK) before the161ms local-stop iteration.
 {
  bool timedMode=true,oldAck=false;
  const unsigned n100Parsed=150+10,nextUnoLoop=161;
  if(n100Parsed<nextUnoLoop)timedMode=false;
  if(timedMode)oldAck=true;
  assert(!oldAck); // Reproduction of the old scheduling race.
  MotorBridge b;start(b);const auto n=stops();
  b.tick(150);b.tick(161);assert(stops()==n && b.connected());
  reply("{pulse1_");b.tick(167);assert(stops()==n);
  reply("ok}");b.tick(174);assert(b.connected());
  assert(memoryOutput.back()=="{pulse1_ok}");b.tick(175);assert(stops()==n+1);
 }
 // Missing, bare, wrong-ID/value and partial ACK cannot defer fallback, even
 // with healthy heartbeats. At expiry the session closes and no ACK is relayed.
 for(const char* ack:{"","{ok}","{other_ok}","{pulse1_error}","{pulse1_"}){
  MotorBridge b;start(b);const auto n=stops();reply(ack);b.tick(170);
  input("{Heartbeat}");b.tick(229);assert(b.connected() && stops()==n);
  b.tick(230);assert(!b.connected() && stops()==n+1);
  const auto sent=memoryOutput.size();reply("{pulse1_ok}");b.tick(231);assert(memoryOutput.size()==sent);
 }
 // Exact but premature completion fails closed.
 {MotorBridge b;start(b);reply("{pulse1_ok}");b.tick(149);assert(!b.connected());b.tick(150);assert(Serial2.writes.back()==R"({"N":100})");}
 // Deadline wins over an ACK buffered at the boundary.
 {MotorBridge b;start(b);reply("{pulse1_ok}");b.tick(230);assert(!b.connected());assert(std::find(memoryOutput.begin(),memoryOutput.end(),"{pulse1_ok}")==memoryOutput.end());}
 // Explicit STOP and disconnect bypass completion slack.
 {MotorBridge b;start(b);input(R"({"N":100})");b.tick(51);assert(Serial2.writes.back()==R"({"N":100})");}
 {MotorBridge b;start(b);memoryConnected=false;b.tick(51);b.tick(52);assert(Serial2.writes.back()==R"({"N":100})");}
 // UART TX stall is independently bounded, without a completion ACK.
 {MotorBridge b;start(b,0,false);const auto n=stops();b.tick(102);assert(b.connected());b.tick(103);assert(!b.connected() && stops()==n+1);}
 // Timer arithmetic remains valid across millis wrap.
 {MotorBridge b;const uint32_t base=UINT32_MAX-100;start(b,base);const auto n=stops();b.tick(base+229);assert(b.connected() && stops()==n);b.tick(base+230);assert(!b.connected() && stops()==n+1);}
}
