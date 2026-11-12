#pragma once
#include <cstddef>
#include <cstring>
#include <vector>
struct Preferences {
  inline static std::vector<unsigned char> active;
  inline static bool fail=false;
  bool begin(const char*,bool) {return true;}
  std::size_t getBytesLength(const char*) const {return active.size();}
  std::size_t getBytes(const char*,void* target,std::size_t size) const {
    if(size!=active.size())return 0;
    std::memcpy(target,active.data(),size);return size;
  }
  std::size_t putBytes(const char*,const void* source,std::size_t size) {
    if(fail)return 0;
    const auto* bytes=static_cast<const unsigned char*>(source);
    active.assign(bytes,bytes+size);return size;
  }
};
