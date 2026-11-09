#include "ProvisioningServer.h"
#include "SetupAssets.h"
#include "AuthPolicy.h"
#include <esp_https_server.h>
#include <cJSON.h>
#include <sys/socket.h>
#include <netinet/in.h>
static NetworkRuntime* runtime_=nullptr;
static const IdentityRecord* identity_=nullptr;
static esp_err_t reply(httpd_req_t* req,int code,const char* message) {
  httpd_resp_set_status(req,code==200?"200 OK":code==401?"401 Unauthorized":code==409?"409 Conflict":code==503?"503 Service Unavailable":"400 Bad Request");
  httpd_resp_set_hdr(req,"Connection","close");httpd_resp_set_type(req,"application/json");httpd_resp_set_hdr(req,"Cache-Control","no-store");
  httpd_resp_set_hdr(req,"X-Content-Type-Options","nosniff");
  return httpd_resp_send(req,message,HTTPD_RESP_USE_STRLEN);
}
static bool permitted(httpd_req_t* req) {
  char host[96]{},origin[128]{};
  if(httpd_req_get_hdr_value_str(req,"Host",host,sizeof(host))!=ESP_OK)return false;
  String name=String(identity_->device)+".local";
  const String supplied(host);
  const String station=WiFi.localIP().toString(),ap=WiFi.softAPIP().toString();
  if(supplied!=name && supplied!=name+":443" && supplied!=station && supplied!=station+":443"
      && supplied!=ap && supplied!=ap+":443")return false;
  if(httpd_req_get_hdr_value_len(req,"Origin")>0) {
    if(httpd_req_get_hdr_value_str(req,"Origin",origin,sizeof(origin))!=ESP_OK || String(origin)!="https://"+supplied)return false;
  }
  return true;
}
static bool authorized(httpd_req_t* req) {
  if(!permitted(req))return false;
  char provided[80]{};
  if(httpd_req_get_hdr_value_str(req,"Authorization",provided,sizeof(provided))!=ESP_OK)return false;
  const bool accepted=validBearer(provided,identity_->token);
  wipeBytes(provided,sizeof(provided));return accepted;
}
static bool field(cJSON* body,const char* name,char* target,size_t size) {
  auto* item=cJSON_GetObjectItemCaseSensitive(body,name);
  if(!cJSON_IsString(item) || strnlen(item->valuestring,size)>=size)return false;
  strcpy(target,item->valuestring);return true;
}
static esp_err_t networkHandler(httpd_req_t* req) {
  static uint32_t lastDenied=0;
  if(!authorized(req)) {
    // Server has one socket slot; bounded denial delay adds no unbounded state.
    if(uint32_t(millis()-lastDenied)<250)vTaskDelay(pdMS_TO_TICKS(25));
    lastDenied=millis();return reply(req,401,"{\"error\":\"authenticated device request required\"}");
  }
  ApiJob job;ApiReply result;
  const bool prepare=!strcmp(req->uri,"/v1/network/prepare");
  if(req->method==HTTP_POST) {
    char type[40]{};char body[513]{};
    if(req->content_len<1 || req->content_len>512 || httpd_req_get_hdr_value_len(req,"Transfer-Encoding")
        || httpd_req_get_hdr_value_str(req,"Content-Type",type,sizeof(type))!=ESP_OK || strcmp(type,"application/json"))
      return reply(req,400,"{\"error\":\"bounded JSON required\"}");
    size_t received=0;const uint32_t began=millis();
    while(received<req->content_len) {
      if(uint32_t(millis()-began)>=2000){wipeBytes(body,sizeof(body));return reply(req,400,"{\"error\":\"request expired\"}");}
      int size=httpd_req_recv(req,body+received,req->content_len-received);
      if(size<=0){wipeBytes(body,sizeof(body));return reply(req,400,"{\"error\":\"incomplete request\"}");}
      received+=size;
    }
    if(memchr(body,0,received) || strstr(body,"\\u0000")){wipeBytes(body,sizeof(body));return reply(req,400,"{\"error\":\"invalid JSON\"}");}
    const char* end=nullptr;
    cJSON* json=cJSON_ParseWithOpts(body,&end,true);
    bool valid=cJSON_IsObject(json) && cJSON_GetArraySize(json)==(prepare?4:1)
      && field(json,"transaction",job.transaction,sizeof(job.transaction));
    if(prepare) {
      auto* lease=cJSON_GetObjectItemCaseSensitive(json,"lease_seconds");
      valid=valid && cJSON_IsNumber(lease) && lease->valuedouble==lease->valueint && lease->valueint>=1 && lease->valueint<=90
        && field(json,"ssid",job.credentials.ssid,sizeof(job.credentials.ssid))
        && field(json,"password",job.credentials.password,sizeof(job.credentials.password))
        && charlie_elegoo::valid(job.credentials);
      if(valid)job.leaseSeconds=lease->valueint;
    }
    // Duplicate or unknown keys cannot satisfy the exact schema.
    unsigned seen=0;
    for(cJSON* item=json?json->child:nullptr;item;item=item->next) {
      unsigned bit=item->string && !strcmp(item->string,"transaction")?1:
        prepare && item->string && !strcmp(item->string,"ssid")?2:
        prepare && item->string && !strcmp(item->string,"password")?4:
        prepare && item->string && !strcmp(item->string,"lease_seconds")?8:0;
      if(!bit || (seen&bit))valid=false;seen|=bit;
      if(item->valuestring)wipeBytes(item->valuestring,strlen(item->valuestring));
    }
    cJSON_Delete(json);wipeBytes(body,sizeof(body));
    if(!valid){charlie_elegoo::wipe(job.credentials);return reply(req,400,"{\"error\":\"request schema rejected\"}");}
    job.operation=prepare?ApiOperation::Prepare:ApiOperation::Confirm;
    if(!prepare) {
      sockaddr_in local{};socklen_t length=sizeof(local);
      if(getsockname(httpd_req_to_sockfd(req),reinterpret_cast<sockaddr*>(&local),&length)==0 && local.sin_family==AF_INET)
        job.localAddress=local.sin_addr.s_addr;
    }
  }
  if(!runtime_->request(job,result)){charlie_elegoo::wipe(job.credentials);return reply(req,503,"{\"error\":\"network owner unavailable\"}");}
  charlie_elegoo::wipe(job.credentials);
  if(!result.ok)return reply(req,409,"{\"error\":\"transaction rejected\"}");
  cJSON* output=cJSON_CreateObject();
  if(req->method==HTTP_GET) {
    cJSON_AddStringToObject(output,"device_id",identity_->device);
    cJSON_AddBoolToObject(output,"joined",result.joined);
    cJSON_AddBoolToObject(output,"verified",result.verified);
    cJSON_AddStringToObject(output,"transaction",result.transaction);
    cJSON_AddStringToObject(output,"ssid",result.ssid);
  } else {
    cJSON_AddBoolToObject(output,prepare?"accepted":"verified",true);
    cJSON_AddStringToObject(output,"transaction",result.transaction);
  }
  char* encoded=cJSON_PrintUnformatted(output);cJSON_Delete(output);
  if(!encoded)return reply(req,503,"{\"error\":\"resource unavailable\"}");
  const auto sent=reply(req,200,encoded);cJSON_free(encoded);
  if(prepare && sent==ESP_OK)runtime_->acknowledge(result.sequence);
  return sent;
}
static esp_err_t page(httpd_req_t* req) {
  if(!permitted(req))return reply(req,401,"{\"error\":\"host denied\"}");
  httpd_resp_set_hdr(req,"Cache-Control","no-store");httpd_resp_set_hdr(req,"Referrer-Policy","no-referrer");
  httpd_resp_set_hdr(req,"Content-Security-Policy","default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
  httpd_resp_set_hdr(req,"X-Content-Type-Options","nosniff");
  const bool script=!strcmp(req->uri,"/setup.js");
  httpd_resp_set_type(req,script?"application/javascript":"text/html; charset=utf-8");
  return httpd_resp_send(req,script?SETUP_JS:SETUP_HTML,HTTPD_RESP_USE_STRLEN);
}
bool startProvisioningServer(NetworkRuntime& runtime,const IdentityRecord& identity) {
  runtime_=&runtime;identity_=&identity;
  httpd_ssl_config_t config=HTTPD_SSL_CONFIG_DEFAULT();
  config.port_secure=443;config.httpd.server_port=443;config.httpd.ctrl_port=32770;
  config.httpd.max_open_sockets=1;config.httpd.max_uri_handlers=6;
  config.httpd.stack_size=12288;config.httpd.recv_wait_timeout=2;config.httpd.send_wait_timeout=2;
  config.cacert_pem=reinterpret_cast<const uint8_t*>(identity.certificate);config.cacert_len=strlen(identity.certificate)+1;
  config.prvtkey_pem=reinterpret_cast<const uint8_t*>(identity.privateKey);config.prvtkey_len=strlen(identity.privateKey)+1;
  httpd_handle_t server=nullptr;
  if(httpd_ssl_start(&server,&config)!=ESP_OK)return false;
  struct Route {const char* path;httpd_method_t method;esp_err_t(*handler)(httpd_req_t*);};
  const Route routes[]={{"/setup",HTTP_GET,page},{"/setup.js",HTTP_GET,page},
    {"/v1/network",HTTP_GET,networkHandler},{"/v1/network/prepare",HTTP_POST,networkHandler},
    {"/v1/network/confirm",HTTP_POST,networkHandler}};
  for(const auto& route:routes){httpd_uri_t uri={};uri.uri=route.path;uri.method=route.method;uri.handler=route.handler;
    if(httpd_register_uri_handler(server,&uri)!=ESP_OK){httpd_ssl_stop(server);return false;}}
  return true;
}
