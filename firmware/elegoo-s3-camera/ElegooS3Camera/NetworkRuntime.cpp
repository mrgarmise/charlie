#include "NetworkRuntime.h"
#include "AuthPolicy.h"
bool NetworkRuntime::begin(const IdentityRecord& identity) {
  identity_=&identity;
  jobs_=xQueueCreate(2,sizeof(ApiJob));replies_=xQueueCreate(2,sizeof(ApiReply));api_=xSemaphoreCreateMutex();ready_=xSemaphoreCreateBinary();
  if(!jobs_ || !replies_ || !api_ || !ready_)return false;
  if(xTaskCreatePinnedToCore(task,"charlie-network",8192,this,1,&task_,0)!=pdPASS)return false;
  return xSemaphoreTake(ready_,pdMS_TO_TICKS(5000))==pdTRUE && running_.load();
}
void NetworkRuntime::task(void* value){static_cast<NetworkRuntime*>(value)->run();}
void NetworkRuntime::run() {
  if(!platform_.begin()){vTaskDelete(nullptr);return;}
  char recovery[40];snprintf(recovery,sizeof(recovery),"charlie-%s",identity_->device);
  if(!platform_.startRecoveryAP(recovery,identity_->recoverySecret)){vTaskDelete(nullptr);return;}
  running_.store(true);xSemaphoreGive(ready_);
  core_.begin();
  if(MDNS.begin(identity_->device)) {
    MDNS.setInstanceName(identity_->device);
    MDNS.addService("charlie-elegoo","tcp",443);
    MDNS.addServiceTxt("charlie-elegoo","tcp","id",identity_->device);
  }
  for(;;) {
    const uint32_t now=millis();
    ApiJob job;
    if(xQueueReceive(jobs_,&job,0)==pdTRUE) {
      ApiReply reply;reply.sequence=job.sequence;
      if(static_cast<int32_t>(job.deadline-now)>0) {
        if(job.operation==ApiOperation::Status)reply.ok=true;
        else if(job.operation==ApiOperation::Prepare) {
          reply.ok=core_.prepare(job.credentials,job.transaction,now,job.leaseSeconds);
          if(reply.ok){acceptedSequence_=job.sequence;acceptedAt_=now;acceptedLease_=job.leaseSeconds*1000;}
        } else {
          const bool target=confirmOnTarget(job.localAddress,static_cast<uint32_t>(WiFi.localIP()),static_cast<uint32_t>(WiFi.softAPIP()));
          reply.ok=completedReceipt(core_.state()==charlie_elegoo::State::Verified,platform_.joined(),target,core_.transactionId(),job.transaction)
            || core_.confirm(job.transaction,target,now);
        }
      }
      reply.state=core_.state();reply.verified=reply.state==charlie_elegoo::State::Verified;
      // A pending target is never reported joined merely because the old STA was up.
      reply.joined=platform_.joined() && (reply.state==charlie_elegoo::State::Joined || reply.verified || reply.state==charlie_elegoo::State::Recovery);
      strncpy(reply.transaction,core_.transactionId(),sizeof(reply.transaction)-1);
      if(platform_.joined())WiFi.SSID().toCharArray(reply.ssid,sizeof(reply.ssid));
      xQueueSend(replies_,&reply,0);
      charlie_elegoo::wipe(job.credentials);
    }
    // Acknowledgement receipt precedes association; a lost reply only expires.
    if(core_.state()!=charlie_elegoo::State::Accepted || acknowledged_.load()==acceptedSequence_
        || uint32_t(now-acceptedAt_)>=acceptedLease_)core_.tick(now);
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}
bool NetworkRuntime::request(ApiJob job,ApiReply& reply) {
  if(!api_ || xSemaphoreTake(api_,0)!=pdTRUE)return false;
  job.sequence=++sequence_;job.deadline=millis()+2000;
  ApiReply discard;while(xQueueReceive(replies_,&discard,0)==pdTRUE){}
  bool ok=xQueueSend(jobs_,&job,0)==pdTRUE;
  const uint32_t begin=millis();
  while(ok && uint32_t(millis()-begin)<2000) {
    if(xQueueReceive(replies_,&reply,pdMS_TO_TICKS(20))==pdTRUE && reply.sequence==job.sequence)break;
  }
  ok=ok && reply.sequence==job.sequence;
  charlie_elegoo::wipe(job.credentials);xSemaphoreGive(api_);return ok;
}
