#pragma once
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <deque>
constexpr int SERIAL_8N1=0,OUTPUT=1,HIGH=1,LOW=0;
inline void pinMode(int,int){}
inline void digitalWrite(int,int){}
struct TestSerial {
  std::vector<std::string> writes;
  std::deque<char> input;
  int capacity=512,baud=0,rx=-1,tx=-1;
  void setTxBufferSize(int){}
  void begin(int speed,int,int r,int t){baud=speed;rx=r;tx=t;}
  int availableForWrite()const{return capacity;}
  size_t write(const uint8_t* data,size_t size){writes.emplace_back(reinterpret_cast<const char*>(data),size);return size;}
  int available()const{return input.size();}
  int read(){char c=input.front();input.pop_front();return c;}
};
inline TestSerial Serial2;
