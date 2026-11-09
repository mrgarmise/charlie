#include "Identity.h"
#include <cJSON.h>
#include <mbedtls/x509_crt.h>
#include <mbedtls/pk.h>
#include <memory>
#include <new>
void wipeBytes(void* data,size_t size){volatile uint8_t* p=static_cast<volatile uint8_t*>(data);while(size--)*p++=0;}
static uint32_t checksum(const IdentityRecord& record) {
  const uint8_t* bytes=reinterpret_cast<const uint8_t*>(&record);
  uint32_t value=2166136261u;
  for(size_t i=0;i<offsetof(IdentityRecord,checksum);++i)value=(value^bytes[i])*16777619u;
  return value;
}
static bool bounded(const char* value,size_t size) {return value && strnlen(value,size)<size;}
bool Identity::validate(const IdentityRecord& r,const char* expected) {
  if(r.schema!=1 || !bounded(r.device,sizeof(r.device)) || strcmp(r.device,expected)
     || !bounded(r.token,sizeof(r.token)) || strlen(r.token)<43
     || !bounded(r.recoverySecret,sizeof(r.recoverySecret)) || strlen(r.recoverySecret)<20 || strlen(r.recoverySecret)>63
     || !bounded(r.certificate,sizeof(r.certificate)) || !bounded(r.privateKey,sizeof(r.privateKey)))return false;
  for(const char* p=r.token;*p;++p)if(!isalnum(static_cast<unsigned char>(*p)) && *p!='_' && *p!='-')return false;
  mbedtls_x509_crt cert;mbedtls_x509_crt_init(&cert);
  mbedtls_pk_context key;mbedtls_pk_init(&key);
  const bool valid=mbedtls_x509_crt_parse(&cert,reinterpret_cast<const uint8_t*>(r.certificate),strlen(r.certificate)+1)==0
    && mbedtls_pk_parse_key(&key,reinterpret_cast<const uint8_t*>(r.privateKey),strlen(r.privateKey)+1,nullptr,0)==0
    && mbedtls_pk_check_pair(&cert.pk,&key)==0;
  mbedtls_pk_free(&key);mbedtls_x509_crt_free(&cert);return valid;
}
bool Identity::begin(const char* expected) {
  if(!storage_.begin("charlie-id",false) || storage_.getBytesLength("identity")!=sizeof(record_))return false;
  if(storage_.getBytes("identity",&record_,sizeof(record_))!=sizeof(record_)
      || record_.checksum!=checksum(record_) || !validate(record_,expected)) {
    wipeBytes(&record_,sizeof(record_));return false;
  }
  return true;
}
bool Identity::enroll(const char* text,const char* expected) {
  // No existing-identity reset endpoint. Physical recovery requires its own maintenance.
  if(record_.schema==1 || !text || strlen(text)>7168 || strstr(text,"\\u0000"))return false;
  cJSON* body=cJSON_Parse(text);if(!cJSON_IsObject(body)){cJSON_Delete(body);return false;}
  std::unique_ptr<IdentityRecord> allocated(new(std::nothrow) IdentityRecord);
  if(!allocated){cJSON_Delete(body);return false;}
  auto& next=*allocated;next.schema=1;
  struct Field {const char* key;char* target;size_t size;};
  Field fields[]={{"device_id",next.device,sizeof(next.device)}, {"certificate",next.certificate,sizeof(next.certificate)},
    {"private_key",next.privateKey,sizeof(next.privateKey)}, {"token",next.token,sizeof(next.token)},
    {"recovery_secret",next.recoverySecret,sizeof(next.recoverySecret)}};
  bool good=cJSON_GetArraySize(body)==5;
  for(const auto& field:fields){const auto* value=cJSON_GetObjectItemCaseSensitive(body,field.key);
    if(!cJSON_IsString(value) || !bounded(value->valuestring,field.size)){good=false;continue;}
    strcpy(field.target,value->valuestring);
  }
  for(cJSON* value=body->child;value;value=value->next)if(value->valuestring)wipeBytes(value->valuestring,strlen(value->valuestring));
  cJSON_Delete(body);
  good=good && validate(next,expected);
  if(good){next.checksum=checksum(next);good=storage_.putBytes("identity",&next,sizeof(next))==sizeof(next);}
  if(good)record_=next;
  wipeBytes(&next,sizeof(next));return good;
}
