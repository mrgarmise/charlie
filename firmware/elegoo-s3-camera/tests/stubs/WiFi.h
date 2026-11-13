#pragma once
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <netinet/in.h>
#include <unistd.h>
#include <poll.h>
#include <memory>
#include <cerrno>
#include <cassert>
struct TestSocket {int value=-1;~TestSocket(){if(value>=0)::close(value);}};
inline int bridgePort=0;
class WiFiClient {
  std::shared_ptr<TestSocket> socket_;
 public:
  WiFiClient()=default;
  explicit WiFiClient(int fd):socket_(std::make_shared<TestSocket>()){socket_->value=fd;}
  explicit operator bool()const{return socket_ && socket_->value>=0;}
  int fd()const{return *this?socket_->value:-1;}
  bool connected()const{char c;const int n=::recv(fd(),&c,1,MSG_PEEK|MSG_DONTWAIT);return n>0 || (n<0 && (errno==EAGAIN || errno==EWOULDBLOCK));}
  void stop(){if(*this){::close(socket_->value);socket_->value=-1;}}
  int available()const{int count=0;::ioctl(fd(),FIONREAD,&count);return count;}
  int read(){char c=0;return ::recv(fd(),&c,1,MSG_DONTWAIT)==1?c:-1;}
};
class WiFiServer {
  int fd_=-1;
 public:
  explicit WiFiServer(int candidatePort){assert(candidatePort==100);}
  ~WiFiServer(){if(fd_>=0)::close(fd_);}
  void begin(){fd_=::socket(AF_INET,SOCK_STREAM,0);assert(fd_>=0);sockaddr_in addr{};addr.sin_family=AF_INET;addr.sin_addr.s_addr=htonl(INADDR_LOOPBACK);addr.sin_port=0;
    assert(::bind(fd_,reinterpret_cast<sockaddr*>(&addr),sizeof(addr))==0);assert(::listen(fd_,2)==0);socklen_t len=sizeof(addr);::getsockname(fd_,reinterpret_cast<sockaddr*>(&addr),&len);bridgePort=ntohs(addr.sin_port);}
  void setNoDelay(bool){}
  bool hasClient()const{pollfd p{fd_,POLLIN,0};return ::poll(&p,1,0)>0;}
  WiFiClient available(){return WiFiClient(::accept(fd_,nullptr,nullptr));}
};
struct TestWiFi {int stations=0;int softAPgetStationNum()const{return stations;}};
inline TestWiFi WiFi;
