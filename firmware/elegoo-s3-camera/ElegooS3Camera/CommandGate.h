#pragma once
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <mbedtls/md.h>
// Authentication is transport admission, never Pi qualification or physical proof.
// One-use MAC: purpose, fresh connection nonce, monotonic sequence, exact frame.
class CommandGate {
  char key_[65]{},nonce_[33]{},tag_[65]{};
  uint32_t sequence_=0,pending_=0,at_=0,deadline_=0;
 public:
  void begin(const char* key,const char* nonce) {
    clear();strncpy(key_,key,64);strncpy(nonce_,nonce,32);
  }
  void clear(){memset(key_,0,sizeof(key_));memset(nonce_,0,sizeof(nonce_));memset(tag_,0,sizeof(tag_));sequence_=pending_=at_=deadline_=0;}
  bool header(const char* frame,uint32_t now) {
    unsigned long number=0,deadline=0;int used=0;char tag[65]{};
    if(pending_ || sscanf(frame,"{Auth:%10lu:%10lu:%64[0123456789abcdef]}%n",&number,&deadline,tag,&used)!=3
        || used!=static_cast<int>(strlen(frame)) || strlen(tag)!=64 || number<=sequence_ || number>UINT32_MAX || deadline>UINT32_MAX
        || uint32_t(deadline-now)==0 || uint32_t(deadline-now)>500)return false;
    // Require canonical decimal to exclude signs, leading zeros and whitespace.
    char canonical[96];snprintf(canonical,sizeof(canonical),"{Auth:%lu:%lu:%s}",number,deadline,tag);
    if(strcmp(canonical,frame))return false;
    pending_=number;at_=now;deadline_=deadline;strcpy(tag_,tag);return true;
  }
  void cancel(){sequence_=pending_>sequence_?pending_:sequence_;pending_=0;memset(tag_,0,sizeof(tag_));}
  bool consume(const char* frame,uint32_t now) {
    if(!pending_ || uint32_t(now-at_)>=500 || uint32_t(deadline_-now)==0 || uint32_t(deadline_-now)>500 || !key_[0] || strlen(nonce_)!=32)return false;
    char message[384];const int size=snprintf(message,sizeof(message),"charlie-elegoo-command-v1\n%s\n%lu\n%lu\n%s",nonce_,static_cast<unsigned long>(pending_),static_cast<unsigned long>(deadline_),frame);
    uint8_t digest[32]{};unsigned difference=0;
    const auto* info=mbedtls_md_info_from_string("SHA256");
    const bool ok=size>0 && size<static_cast<int>(sizeof(message)) && info &&
      mbedtls_md_hmac(info,reinterpret_cast<const unsigned char*>(key_),strlen(key_),
        reinterpret_cast<const unsigned char*>(message),size,digest)==0;
    const char* hex="0123456789abcdef";
    for(unsigned i=0;i<32;++i){difference|=static_cast<unsigned char>(tag_[2*i])^hex[digest[i]>>4];difference|=static_cast<unsigned char>(tag_[2*i+1])^hex[digest[i]&15];}
    sequence_=pending_;pending_=0;memset(tag_,0,sizeof(tag_));memset(digest,0,sizeof(digest));
    return ok && difference==0;
  }
};
// Exact existing Pi serializers only; no arbitrary UNO commands or continuous drive.
// A bounded pulse is independently stopped on-device even with live heartbeats.
inline int commandDuration(const char* frame) {
  int direction=0,pwm=0,duration=0,angle=0,used=0;char id[33]{};
  if(sscanf(frame,"{\"N\":2,\"H\":\"%32[abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789]\",\"D1\":%1d,\"D2\":%2d,\"T\":%3d}%n",id,&direction,&pwm,&duration,&used)==4
      && used==static_cast<int>(strlen(frame)) && direction>=1 && direction<=4 && pwm>=1 && pwm<=35 && duration>=1 && duration<=200)return duration;
  used=0;
  if(sscanf(frame,"{\"N\":5,\"H\":\"%32[abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789]\",\"D1\":1,\"D2\":%3d}%n",id,&angle,&used)==2
      && used==static_cast<int>(strlen(frame)) && angle>=20 && angle<=160)return 0;
  return -1;
}
inline bool stopFrame(const char* frame) {
  if(!strcmp(frame,"{\"N\":100}"))return true;
  int used=0;char id[33]{};
  return sscanf(frame,"{\"N\":1,\"H\":\"%32[abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789]\",\"D1\":0,\"D2\":0,\"D3\":0}%n",id,&used)==1
    && used==static_cast<int>(strlen(frame));
}
