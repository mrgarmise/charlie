#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
// Fixed bounds, no content-dependent early return during token comparison.
inline bool validBearer(const char provided[80],const char expected[65]) {
  const size_t length=strnlen(provided,80),target=strnlen(expected,65);
  if(length==80 || length<7 || target<43 || target>64 || strncmp(provided,"Bearer ",7))return false;
  unsigned difference=static_cast<unsigned>((length-7)^target);
  for(size_t i=0;i<65;++i)difference|=static_cast<unsigned char>(i<length-7?provided[i+7]:0)
      ^static_cast<unsigned char>(i<target?expected[i]:0);
  return difference==0;
}

inline bool confirmOnTarget(uint32_t local,uint32_t station,uint32_t recovery) {
  return local!=0 && station!=0 && local==station && local!=recovery;
}

inline bool completedReceipt(bool verified,bool joined,bool target,const char* actual,const char* supplied) {
  return verified && joined && target && actual && supplied && strnlen(actual,33)==32
      && strnlen(supplied,33)==32 && !strcmp(actual,supplied);
}
