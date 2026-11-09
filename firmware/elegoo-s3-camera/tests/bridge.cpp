#include "../ElegooS3Camera/MotorBridge.h"
#include <cassert>
#include <algorithm>
static int connectPeer(){int peer=socket(AF_INET,SOCK_STREAM,0);assert(peer>=0);sockaddr_in address{};address.sin_family=AF_INET;address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);address.sin_port=htons(bridgePort);assert(::connect(peer,reinterpret_cast<sockaddr*>(&address),sizeof(address))==0);return peer;}
static void put(int peer,const char* text){assert(::send(peer,text,strlen(text),0)==static_cast<int>(strlen(text)));}
int main(){
 MotorBridge bridge;bridge.begin("0123456789AB");assert(Serial2.baud==9600 && Serial2.rx==3 && Serial2.tx==40);
 assert(Serial2.writes.back()=="{\"N\":100}");
 int peer=connectPeer();bridge.tick(0);assert(bridge.connected());assert(WiFi.stations==0);
 char heartbeat[32]{};assert(::recv(peer,heartbeat,sizeof(heartbeat),MSG_DONTWAIT)==11);assert(!strcmp(heartbeat,"{Heartbeat}"));
 // A second TCP client cannot replace the actual owner.
 int second=connectPeer();bridge.tick(1);assert(bridge.connected());::close(second);
 put(peer,"{Heartbeat}");bridge.tick(2);
 const auto before=Serial2.writes.size();put(peer,"{\"N\":3, \"D1\":20}");bridge.tick(3);
#if CHARLIE_ENABLE_MOTOR_FORWARDING
 assert(bridge.connected());assert(Serial2.writes.size()==before+1);assert(Serial2.writes.back()=="{\"N\":3,\"D1\":20}");
 ::close(peer);bridge.tick(4);assert(!bridge.connected());bridge.tick(5);assert(Serial2.writes.back()=="{\"N\":100}");
#else
 assert(!bridge.connected());assert(Serial2.writes.size()==before);::close(peer);bridge.tick(4);assert(Serial2.writes.back()=="{\"N\":100}");
#endif
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
