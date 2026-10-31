# Mobile implementation audit — 2026-10-24

Base: master bcf8082f6319c63c4bd6bcceeab5faea37241654. Fresh full clone; clean before branch creation. Branch: feature/mobile-perception-pet-following. Remote branches and open PRs inspected. PRs 6 (Hailo observation bridge), 8 (score reader), 9 (native marathon) remain unmerged; no blanket merge of unrelated experiments.

## Preserved working route

`run_elegoo_head2.py` -> `hardware.elegoo_camera.ElegooCamera` (OV2640 MJPEG, historical URL http://192.168.4.1:81/stream) -> `vision.mobile_face.MobileFaceDetector` (YuNet) -> `behaviors.mobile_face_track.MobileFaceTrackBehavior` -> `motion.mobile_base.MobileBase` -> TCP car driver. This is more complete than the handoff's initial reconnaissance. History: camera latest-frame implementation 44908eb61b2b845dce1f780c56a012cb14e98c13; face behavior/memory 7c3a638a98c6388e15ab5118f1395d8ceaa68119; ddea040 finalizes head tracking and sentry. Existing startup can move pan/chassis; DO NOT run it for unarmed perception checks. Onboard ESP32 detection/enrollment remains reported, not verified.

Read full mobile driver, camera, mobile track, face selection, primary application, charter and ALA2 acceptance, Executive/registry/journal/memory interfaces. Primary Picamera2 camera lease and RP2040 remain separate. Current driver has pan/yaw/pivot/STOP but no verified ranging/forward-duration API or car-local safety qualification. Socket send/ACK does not prove execution or watchdog STOP. Host-only guards cannot qualify motion.

## Qualification inventory

|Capability|Source|Host|Native/current installed|Physical|
|---|---|---|---|---|
|Legacy MJPEG/YuNet/pan/yaw sentry|master + history above|regression pending|unknown|operator reports historical success|
|Primary camera/Robotron/Executive|master|baseline pending|not accessed|not exercised|
|Hailo detection|PR 6 ab58a3d3d3f83a44e77184d329f0e28c1f9cbda8|prior report only|unknown for mobile|unqualified|
|Hailo score|PR 8 b4f258853964edbc3e442f9332675d5ebd7007e9|separate branch|historical HailoRT 4.23.0 only|no mobile qualification|
|Pet/depth/navigation|this mission|pending|unavailable|unqualified|

Host: x86_64 container, Python 3.12. No Pi, car USB, HEF or authentic pet sequences supplied. `charlie.local` does not resolve here. Direct local AP access is not assumed to route to the user's car. No firmware flashing, controller connection, servo or motor calls performed. Installed firmware SHA, current AP/LAN route, capture age, source clock sync, camera pose, Hailo hardware/runtime/HEFs, thermal/power/wiring, ultrasonic freshness and STOP/disconnect behavior are UNKNOWN. These block physical acceptance, not downstream offline implementation.

## Reuse decision

Reuse MJPEG implementation with backward-compatible metadata/reader hardening. Reuse PR 6's exact Hailo detector backend rather than duplicate initialization/postprocessing; add a shared lease and explicit relative-depth adapter. Raw HEF heads or unverified depth layouts fail closed. Model artifacts/licenses are not supplied or claimed qualified. No autonomous execution backend will be installed until a verified bounded car-local protocol and separate authorization exist.
