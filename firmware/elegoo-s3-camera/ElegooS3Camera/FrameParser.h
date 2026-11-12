// Original Charlie bounded framing; candidate legacy {Heartbeat}/brace contract.
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
namespace charlie_elegoo {
class FrameParser {
  char bytes_[257]{};
  size_t size_=0;
  unsigned depth_=0;
  bool quoted_=false, escaped_=false;
  uint32_t began_=0;
 public:
  enum class Result { Partial, Complete, Error };
  void reset() {size_=0;depth_=0;quoted_=false;escaped_=false;bytes_[0]=0;}
  bool expired(uint32_t now) const {return depth_ && uint32_t(now-began_)>=500;}
  const char* frame() const {return bytes_;}
  size_t size() const {return size_;}
  Result feed(char c,uint32_t now) {
    if(!depth_) {
      if(c!='{')return Result::Partial;
      reset();depth_=1;began_=now;bytes_[size_++]=c;return Result::Partial;
    }
    if(expired(now) || size_>=256 || static_cast<unsigned char>(c)<32) {
      reset();return Result::Error;
    }
    if(c==' ' && !quoted_)return Result::Partial; // legacy insignificant spaces
    bytes_[size_++]=c;bytes_[size_]=0;
    if(quoted_) {
      if(escaped_)escaped_=false;
      else if(c=='\\')escaped_=true;
      else if(c=='"')quoted_=false;
    } else if(c=='"')quoted_=true;
    else if(c=='{') {if(++depth_>8){reset();return Result::Error;}}
    else if(c=='}' && --depth_==0)return Result::Complete;
    return Result::Partial;
  }
};
} // namespace charlie_elegoo
