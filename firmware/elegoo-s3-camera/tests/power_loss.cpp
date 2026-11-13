#include "../ElegooS3Camera/NetworkCore.h"
#include <cassert>
#include <string>
using namespace charlie_elegoo;
struct Persistent : Platform {
 Credentials stored{};bool exists=false,online=false,target=false,writeOk=true;unsigned commits=0;
 void associate(const Credentials&)override{}
 bool joined()const override{return online;}
 bool targetMatches(const Credentials&)const override{return target;}
 void disconnectStation()override{online=false;}
 bool load(Credentials& c)override{c=stored;return exists;}
 bool commit(const Credentials& c)override{++commits;if(!writeOk)return false;stored=c;exists=true;return true;}
};
int main(){Persistent p;Credentials first;strcpy(first.ssid,"fixture-original");for(int i=0;i<20;++i)first.password[i]=char('a'+i);
 p.stored=first;p.exists=true;Credentials next=first;strcpy(next.ssid,"fixture-target");
 const char* id="0123456789abcdef0123456789abcdef";
 {NetworkCore before(p);before.begin();assert(before.prepare(next,id,0,30));before.tick(1);p.online=true;p.target=true;before.tick(2);assert(before.state()==State::Joined);}
 // Reboot before confirmation loses only RAM staging, not original credentials.
 {NetworkCore after(p);after.begin();assert(!*after.transactionId());assert(!strcmp(p.stored.ssid,"fixture-original"));assert(p.commits==0);}
 {NetworkCore before(p);before.begin();assert(before.prepare(next,id,10,30));before.tick(11);p.online=true;p.target=true;before.tick(12);assert(!before.confirm(id,false,13));assert(before.confirm(id,true,14));}
 {NetworkCore after(p);after.begin();assert(!*after.transactionId());assert(!strcmp(p.stored.ssid,"fixture-target"));assert(p.commits==1);}
 // Bad association expires and cannot persist a target; recovery is bounded.
 {p.online=false;p.target=false;NetworkCore n(p);n.begin();assert(n.prepare(first,id,20,1));n.tick(21);n.tick(1020);assert(n.state()==State::Recovery);assert(!strcmp(p.stored.ssid,"fixture-target"));}
 wipe(first);wipe(next);wipe(p.stored);
}
