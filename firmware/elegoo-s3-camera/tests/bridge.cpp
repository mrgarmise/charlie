#include "../ElegooS3Camera/MotorBridge.h"
#include <cassert>
#include <algorithm>
static int connectPeer(){int peer=socket(AF_INET,SOCK_STREAM,0);assert(peer>=0);sockaddr_in address{};address.sin_family=AF_INET;address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);address.sin_port=htons(bridgePort);assert(::connect(peer,reinterpret_cast<sockaddr*>(&address),sizeof(address))==0);return peer;}
static void put(int peer,const char* text){assert(::send(peer,text,strlen(text),0)==static_cast<int>(strlen(text)));}
int main(){
 MotorBridge bridge;bridge.begin("0123456789AB","AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA");assert(Serial2.baud==9600 && Serial2.rx==3 && Serial2.tx==40);
 assert(Serial2.writes.size()==3 && Serial2.writes[0]=="{\"N\":100}" && Serial2.writes[1]=="{Factory}");
 assert(Serial2.writes.back()=="{\"N\":100}");
 int peer=connectPeer();bridge.tick(0);assert(bridge.connected());assert(WiFi.stations==0);
 char heartbeat[128]{};assert(::recv(peer,heartbeat,sizeof(heartbeat),MSG_DONTWAIT)>11);assert(strstr(heartbeat,"{Challenge:0102030405060708090a0b0c0d0e0f10:0}"));assert(strstr(heartbeat,"{Heartbeat}"));
 // A second TCP client cannot replace the actual owner.
 int second=connectPeer();bridge.tick(1);assert(bridge.connected());::close(second);
 put(peer,"{Heartbeat}");bridge.tick(2);
 // Signed exact pulse uses Python-generated HMAC and the real host mbedTLS.
 const auto before=Serial2.writes.size();put(peer,"{Auth:1:100:717b702dfe9caccb73829fbe4cf81eea230efc4b2c391aac8b3505e0b5c351cd}");put(peer,R"({"N":2,"H":"pulse1","D1":3,"D2":20,"T":100})");bridge.tick(3);
 assert(bridge.connected());assert(Serial2.writes.size()==before+1);assert(Serial2.writes.back()==R"({"N":2,"H":"pulse1","D1":3,"D2":20,"T":100})");
 const auto stops=std::count(Serial2.writes.begin(),Serial2.writes.end(),"{\"N\":100}");
 put(peer,"{Heartbeat}");bridge.tick(102);assert(std::count(Serial2.writes.begin(),Serial2.writes.end(),"{\"N\":100}")==stops);
 bridge.tick(103);assert(Serial2.writes.back()=="{\"N\":100}");
 // A sequence replay closes and schedules STOP, even with a valid MAC.
 put(peer,"{Auth:1:100:717b702dfe9caccb73829fbe4cf81eea230efc4b2c391aac8b3505e0b5c351cd}");bridge.tick(104);assert(!bridge.connected());bridge.tick(105);::close(peer);
 peer=connectPeer();bridge.tick(10);assert(bridge.connected());put(peer,"{\"N\":");bridge.tick(11);
 ::close(peer);bridge.tick(12);bridge.tick(13);assert(!bridge.connected());
 // Partial data from the old client cannot be replayed by a new client.
 peer=connectPeer();bridge.tick(20);put(peer,"100}");bridge.tick(21);assert(bridge.connected());
 // Associated Wi-Fi/AP status is deliberately irrelevant to heartbeat stopping.
 WiFi.stations=3;bridge.tick(4020);assert(!bridge.connected());bridge.tick(4021);assert(Serial2.writes.back()=="{\"N\":100}" || Serial2.writes.back()=="{WA_OK}");::close(peer);
 // Factory queries run with no TCP client and no out-of-scope client variable.
 const char* query="{BT_detection}{WA_detection}";for(const char* p=query;*p;++p)Serial2.input.push_back(*p);
 bridge.tick(4030);assert(std::find(Serial2.writes.begin(),Serial2.writes.end(),"{BT_OK}")!=Serial2.writes.end());
 assert(std::find(Serial2.writes.begin(),Serial2.writes.end(),"{0123456789AB}")!=Serial2.writes.end());
 // A congested UART retains STOP priority across reconnect.
 Serial2.capacity=0;peer=connectPeer();bridge.tick(4040);::close(peer);bridge.tick(4041);
 Serial2.capacity=7;const auto pendingWrites=Serial2.writes.size();
 for(const char* p="{BT_detection}";*p;++p)Serial2.input.push_back(*p);
 int replacement=connectPeer();bridge.tick(4042);assert(Serial2.writes.size()==pendingWrites);assert(!bridge.connected());::close(replacement);
 Serial2.capacity=512;bridge.tick(4043);assert(Serial2.writes.back()=="{\"N\":100}");
}
