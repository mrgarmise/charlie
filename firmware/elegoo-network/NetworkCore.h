#pragma once
#include <cstdint>
#include <cstring>

// Platform-independent lifecycle. No motor, HTTP, camera or UART writer here.
// The authorized TLS endpoint owns authentication; only LAN confirmation may commit.
namespace charlie_elegoo {
struct Credentials {
  char ssid[33] = {};
  char password[64] = {};
};
inline bool valid(const Credentials& c) {
  const auto s = strnlen(c.ssid, sizeof c.ssid);
  const auto p = strnlen(c.password, sizeof c.password);
  return s > 0 && s <= 32 && p >= 8 && p <= 63;
}
inline void wipe(Credentials& c) {
  volatile unsigned char* p = reinterpret_cast<volatile unsigned char*>(&c);
  for (unsigned i=0; i<sizeof c; ++i) p[i]=0;
}
struct Platform {
  virtual ~Platform() = default;
  virtual void associate(const Credentials&) = 0; // returns immediately
  virtual bool joined() const = 0;
  virtual bool targetMatches(const Credentials&) const = 0;
  virtual void disconnectStation() = 0; // never disables recovery AP
  virtual bool load(Credentials&) = 0;
  virtual bool commit(const Credentials&) = 0; // atomic NVS record, preserve old on error
};
enum class State { Recovery, Accepted, Joining, Joined, Verified };
class NetworkCore {
  Platform& io;
  Credentials active{}, pending{};
  char transaction[33] = {};
  uint32_t started=0, lease=0;
  State state_=State::Recovery;
  bool hasActive=false;
  bool expired(uint32_t now) const { return uint32_t(now-started)>=lease; }
  bool busy() const { return state_==State::Accepted || state_==State::Joining || state_==State::Joined; }
  void recover() {
    io.disconnectStation();
    wipe(pending);
    std::memset(transaction,0,sizeof transaction);
    state_=State::Recovery;
    if (hasActive) io.associate(active);
  }
 public:
  explicit NetworkCore(Platform& platform): io(platform) {}
  NetworkCore(const NetworkCore&)=delete;
  NetworkCore& operator=(const NetworkCore&)=delete;
  ~NetworkCore() { wipe(active); wipe(pending); }
  void begin() {
    hasActive=io.load(active) && valid(active);
    if (hasActive) io.associate(active);
    else wipe(active);
  }
  State state() const { return state_; }
  const char* transactionId() const { return transaction; }
  bool prepare(const Credentials& next, const char* id, uint32_t now, uint32_t seconds) {
    // A second operation never extends an authoritative lease.
    if (busy() || !valid(next) || !id || strnlen(id,33)!=32 || seconds<1 || seconds>90) return false;
    for (unsigned i=0;i<32;++i)
      if (!((id[i]>='0' && id[i]<='9') || (id[i]>='a' && id[i]<='f'))) return false;
    pending=next;
    std::memcpy(transaction,id,33);
    started=now; lease=seconds*1000;
    state_=State::Accepted;
    return true; // response acknowledgement MUST be sent before first tick
  }
  void tick(uint32_t now) {
    if (busy() && expired(now)) { recover(); return; }
    if (state_==State::Accepted) { io.associate(pending); state_=State::Joining; }
    if (state_==State::Joining && io.joined() && io.targetMatches(pending)) state_=State::Joined;
    else if (state_==State::Joined && (!io.joined() || !io.targetMatches(pending))) state_=State::Joining;
    // Normal surprise loss does not create a new transaction or alter recovery AP.
    else if (state_==State::Verified && !io.joined()) state_=State::Recovery;
  }
  bool confirm(const char* id, bool receivedOnTargetLan, uint32_t now) {
    if (state_!=State::Joined || expired(now) || !receivedOnTargetLan || !id ||
        strnlen(id,33)!=32 || std::strcmp(id,transaction)!=0 ||
        !io.joined() || !io.targetMatches(pending)) return false;
    if (!io.commit(pending)) { recover(); return false; }
    active=pending; hasActive=true; wipe(pending); state_=State::Verified;
    return true;
  }
};

// Bound to the ACTUAL accepted TCP client, never AP count or WiFi.status().
// Caller resets frame buffers when the client changes and feeds only complete
// {Heartbeat} frames here. Disconnect/overflow/malformed input ends that session.
// Stop callback must route through the existing single UART writer.
class ControlSession {
  uint32_t heartbeat=0;
  bool active_=false, fresh=false, stopped=true;
  void (*stop_)();
 public:
  explicit ControlSession(void (&stop)()): stop_(stop) {}
  bool open(uint32_t now) {
    if (active_) return false;
    heartbeat=now; active_=true; fresh=false; stopped=false;
    return true;
  }
  void heartbeated(uint32_t now) { if (active_ && !stopped) {heartbeat=now; fresh=true;} }
  void close() {
    if (active_ && !stopped) { stopped=true; stop_(); }
    active_=false; fresh=false;
  }
  void tick(uint32_t now, bool actualClientConnected) {
    if (active_ && (!actualClientConnected || uint32_t(now-heartbeat)>=4000)) close();
  }
  bool mayForward() const { return active_ && fresh && !stopped; }
  bool connected() const { return active_; }
};
// Factory status receives explicit socket state; no reference to a local client.
inline bool factoryLink(bool apStationPresent, bool actualSessionPresent) {
  return apStationPresent || actualSessionPresent;
}
} // namespace charlie_elegoo
