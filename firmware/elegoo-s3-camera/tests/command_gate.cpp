#include "../ElegooS3Camera/CommandGate.h"
#include <cassert>
int main(){
 CommandGate gate;const char* key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";const char* nonce="0102030405060708090a0b0c0d0e0f10";const char* frame=R"({"N":2,"H":"pulse1","D1":3,"D2":20,"T":100})";
 gate.begin(key,nonce);assert(!gate.consume(frame,0));
 assert(gate.header("{Auth:1:100:717b702dfe9caccb73829fbe4cf81eea230efc4b2c391aac8b3505e0b5c351cd}",0));assert(gate.consume(frame,1));
 assert(!gate.consume(frame,2));assert(!gate.header("{Auth:1:100:717b702dfe9caccb73829fbe4cf81eea230efc4b2c391aac8b3505e0b5c351cd}",2));
 assert(gate.header("{Auth:2:100:06ccd7b261716e74d6e7ccc2ae53f1df0aef4bbf2444e497cae5edc1cbd1a976}",3));assert(!gate.consume("{\"N\":100}",4));
 gate.begin(key,nonce);assert(gate.header("{Auth:1:100:717b702dfe9caccb73829fbe4cf81eea230efc4b2c391aac8b3505e0b5c351cd}",0));assert(!gate.consume(frame,500));
 gate.begin(key,"00000000000000000000000000000000");assert(gate.header("{Auth:1:100:717b702dfe9caccb73829fbe4cf81eea230efc4b2c391aac8b3505e0b5c351cd}",0));assert(!gate.consume(frame,1));
 gate.clear();assert(gate.header("{Auth:1:100:717b702dfe9caccb73829fbe4cf81eea230efc4b2c391aac8b3505e0b5c351cd}",0));assert(!gate.consume(frame,1));
 assert(commandDuration(frame)==100);
 assert(commandDuration("{\"N\":3,\"D1\":3,\"D2\":20}")==-1);
 // Read-only intent is not permission for arbitrary forwarding. Until installed
 // protocol/timing are bound, these queries cannot bypass the sole UART owner.
 assert(commandDuration(R"({"N":21,"H":"range1","D1":2})")==-1);
 assert(commandDuration(R"({"N":24,"H":"yaw1"})")==-1);
 assert(commandDuration("{\"N\":2,\"H\":\"a\",\"D1\":3,\"D2\":36,\"T\":100}")==-1);
 assert(commandDuration("{\"N\":2,\"H\":\"a\",\"D1\":3,\"D2\":20,\"T\":201}")==-1);
 assert(commandDuration("{\"N\":5,\"H\":\"a\",\"D1\":1,\"D2\":90}")==0);
 assert(commandDuration("{\"N\":5,\"H\":\"a\",\"D1\":1,\"D2\":161}")==-1);
 assert(stopFrame("{\"N\":100}"));assert(stopFrame("{\"N\":1,\"H\":\"stop1\",\"D1\":0,\"D2\":0,\"D3\":0}"));
 assert(!stopFrame("{\"N\":1,\"H\":\"stop1\",\"D1\":0,\"D2\":1,\"D3\":0}"));
 // STOP revokes a pending ticket; expired and far-future device deadlines fail.
 gate.begin(key,nonce);
 assert(!gate.header("{Auth:1:0:0000000000000000000000000000000000000000000000000000000000000000}",0));
 assert(!gate.header("{Auth:1:501:0000000000000000000000000000000000000000000000000000000000000000}",0));
}
