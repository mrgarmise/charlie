#include "../NetworkCore.h"
#include <cassert>
#include <string>
#include <vector>
using namespace charlie_elegoo;
struct Fake : Platform {
  bool online=false, target=false, stored=false, writeOk=true;
  Credentials saved{};
  std::vector<std::string> events;
  void associate(const Credentials&) override {events.push_back("associate");}
  bool joined() const override {return online;}
  bool targetMatches(const Credentials&) const override {return target;}
  void disconnectStation() override {events.push_back("disconnect-station-only");}
  bool load(Credentials& c) override {c=saved; return stored;}
  bool commit(const Credentials& c) override {events.push_back("commit"); if(writeOk){saved=c; stored=true;} return writeOk;}
};
Credentials credential() {
  Credentials c;
  std::strcpy(c.ssid,"fixture-network");
  // Algorithmic test-only bytes; no stored network password or personal secrets.
  for(unsigned i=0;i<20;++i)c.password[i]=char('a'+i);
  return c;
}
static int stops=0;
void stop() {++stops;}
int main() {
  const char* id="0123456789abcdef0123456789abcdef";
  auto c=credential();
  { // Acceptance is not association or end-to-end confirmation.
    Fake f; NetworkCore n(f); n.begin();
    assert(n.prepare(c,id,0,60)); assert(n.state()==State::Accepted); assert(f.events.empty());
    assert(!n.prepare(c,id,1,90)); n.tick(1); assert(n.state()==State::Joining);
    f.online=true; f.target=false; n.tick(2); assert(n.state()==State::Joining);
    f.target=true; n.tick(3); assert(n.state()==State::Joined);
    assert(!n.confirm(id,false,4)); assert(!f.stored);
    assert(!n.confirm("ffffffffffffffffffffffffffffffff",true,4));
    assert(n.confirm(id,true,5)); assert(f.stored); assert(n.state()==State::Verified);
    f.online=false; n.tick(6); assert(n.state()==State::Recovery);
  }
  { // Bad credentials/loss/lease expiry keep old persistent credentials.
    Fake f; f.saved=c; f.stored=true; NetworkCore n(f); n.begin();
    assert(n.prepare(c,id,100,1)); n.tick(101); n.tick(1100);
    assert(n.state()==State::Recovery && f.stored);
    assert(f.events[f.events.size()-2]=="disconnect-station-only");
    assert(f.events.back()=="associate");
  }
  { // Timer wrap and expired confirmation.
    Fake f; NetworkCore n(f); assert(n.prepare(c,id,0xfffffff0u,1));
    f.online=true; f.target=true; n.tick(0xfffffff1u);
    assert(!n.confirm(id,true,1000)); n.tick(1000); assert(n.state()==State::Recovery);
  }
  { // Power/commit failure leaves previous record valid.
    Fake f; f.saved=c; f.stored=true; f.writeOk=false; NetworkCore n(f); n.begin();
    assert(n.prepare(c,id,0,10)); f.online=true;f.target=true;n.tick(1);
    assert(!n.confirm(id,true,2)); assert(n.state()==State::Recovery); assert(f.stored);
  }
  { // Actual session close/heartbeat, regardless of Wi-Fi association/AP count.
    ControlSession s(stop); assert(s.open(0)); assert(!s.mayForward());
    s.heartbeated(1); assert(s.mayForward()); assert(!s.open(2));
    s.tick(3999,true); assert(s.mayForward()); s.tick(4001,true);
    assert(!s.mayForward() && stops==1); s.heartbeated(4002); assert(!s.mayForward());
    assert(s.open(4003)); assert(!s.mayForward()); s.heartbeated(4004);
    s.tick(4005,false); assert(stops==2);s.close();assert(stops==2);
    assert(factoryLink(false,true)); assert(!factoryLink(false,false));
    assert(factoryLink(true,false));
  }
}
