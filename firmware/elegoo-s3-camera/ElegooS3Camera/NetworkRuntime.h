#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>
#include <atomic>
#include "ArduinoPlatform.h"
#include "Identity.h"
enum class ApiOperation { Status, Prepare, Confirm };
struct ApiJob {
  uint32_t sequence=0, deadline=0, leaseSeconds=0;
  ApiOperation operation=ApiOperation::Status;
  charlie_elegoo::Credentials credentials;
  char transaction[33]{};
  uint32_t localAddress=0;
};
struct ApiReply {
  uint32_t sequence=0;
  bool ok=false, joined=false, verified=false;
  char ssid[33]{}, transaction[33]{};
  charlie_elegoo::State state=charlie_elegoo::State::Recovery;
};
class NetworkRuntime {
  charlie_elegoo::ArduinoPlatform platform_;
  charlie_elegoo::NetworkCore core_{platform_};
  QueueHandle_t jobs_=nullptr,replies_=nullptr;
  SemaphoreHandle_t api_=nullptr,ready_=nullptr;
  std::atomic<bool> running_{false};
  std::atomic<uint32_t> acknowledged_{0};
  uint32_t sequence_=0, acceptedSequence_=0, acceptedAt_=0, acceptedLease_=0;
  const IdentityRecord* identity_=nullptr;
  TaskHandle_t task_=nullptr;
  static void task(void* self);
  void run();
 public:
  bool begin(const IdentityRecord& identity);
  bool request(ApiJob job,ApiReply& reply);
  void acknowledge(uint32_t sequence){acknowledged_.store(sequence);}
};
