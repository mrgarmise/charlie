#pragma once
#include <Arduino.h>
#include <Preferences.h>
struct IdentityRecord {
  uint32_t schema=0;
  char device[32]{};
  char certificate[2048]{};
  char privateKey[2048]{};
  char token[65]{};
  char recoverySecret[65]{};
  uint32_t checksum=0;
};
class Identity {
  IdentityRecord record_;
  Preferences storage_;
  static bool validate(const IdentityRecord&,const char* expected);
 public:
  bool begin(const char* expected);
  bool enroll(const char* json,const char* expected); // physical USB gated caller only
  const IdentityRecord& record() const {return record_;}
};
void wipeBytes(void* data,size_t size);
