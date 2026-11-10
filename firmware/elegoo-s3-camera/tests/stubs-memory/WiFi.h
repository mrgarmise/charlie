#pragma once
// Deterministic transport for production MotorBridge tests. No OS sockets/devices.
#include <sys/socket.h>
#include <deque>
#include <string>
#include <vector>
#include <cstdint>
inline bool memoryIncoming=false,memoryConnected=false;
inline std::deque<char> memoryInput;
inline std::vector<std::string> memoryOutput;
inline int charlieMemorySend(int,const char* data,size_t size,int) {
  if(!memoryConnected)return -1;
  memoryOutput.emplace_back(data,size);return static_cast<int>(size);
}
class WiFiClient {
  bool present_=false;
 public:
  WiFiClient()=default;
  explicit WiFiClient(bool present):present_(present){}
  explicit operator bool()const{return present_ && memoryConnected;}
  bool connected()const{return static_cast<bool>(*this);}
  int fd()const{return 0;}
  void stop(){if(present_)memoryConnected=false;present_=false;}
  int available()const{return memoryInput.size();}
  int read(){char c=memoryInput.front();memoryInput.pop_front();return c;}
};
class WiFiServer {
 public:
  explicit WiFiServer(int){}
  void begin(){}
  void setNoDelay(bool){}
  bool hasClient()const{return memoryIncoming;}
  WiFiClient available(){memoryIncoming=false;memoryConnected=true;return WiFiClient(true);}
};
struct TestWiFi {int stations=0;int softAPgetStationNum()const{return stations;}};
inline TestWiFi WiFi;
#define send charlieMemorySend
