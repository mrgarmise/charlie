#pragma once
#include <cstddef>
#include <cstdint>
inline void esp_fill_random(void* target,size_t size){static uint8_t seed=0;auto* bytes=static_cast<uint8_t*>(target);for(size_t i=0;i<size;++i)bytes[i]=++seed;}
