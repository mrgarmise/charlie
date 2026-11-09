# S3 camera integration report

Mission source: missions/library-archive-20261109, original MISSION.md SHA256
2b7c62a3a2e8e92052b4c448be74e3715255546672718a999b3e6fe9bd896b5b.
Owner explicitly selects UMRT a920130 as candidate, accepting unknown installed-source
equivalence. Integration is based on reviewed PR29 b71cd3d, with PR28 c8a7a8d as the
separate peer. New isolated branch; original PR28/29 heads verified unchanged.

## Implemented and host tested

Complete camera sketch, real WiFi/Preferences, TLS443 provisioning, physical identity
enrollment, recovery AP/STA, browser ticket to explicitly authorized pinned Charlie
verification, bounded actual-session TCP/UART bridge, preserved camera/UI assets and
partition geometry. Default motor forwarding is OFF; legacy motor HTTP is closed.
See PROVENANCE.md for every deliberate behavior difference and ownership constraint.

Local initial validation:23 Python checks including real headless browser download and
pinned TLS handoff, no skips; five strict C++17/UBSan suites (framing/auth/power-loss/
closed bridge/forwarding bridge) passed. Both bridge variants use real loopback sockets
and a UART stub. Prior network-core regressions pass. Partition/header admission tests
were added afterward; final counts/independent CI are recorded in the draft PR ledger.
Actual ESP32 runtime endpoints are native compiled, not executed by host TLS fixtures.
No physical safe-stop, radio, sensor or on-device security claim follows from them.

## First native builds — historical baseline, NOT HARDWARE QUALIFIED / DO NOT FLASH

Native cross-compilation ran on the Pi aarch64 host with isolated Arduino CLI1.2.2,
Arduino-ESP32 2.0.17, bundled xtensa-esp32s3 GCC8.4.0 and ESP-IDF4.4.7. No upload or
serial command ran. Candidate app slot limit0x330000 (3,342,336 bytes).

| Candidate | Actual .bin bytes | SHA256 | Slot headroom |
|---|---:|---|---:|
| OPI PSRAM | 3,135,600 | fcdca1356b73a38737818b524eb10952afca955f0886f584dd0467dfefccdce5 | 206,736 |
| QSPI PSRAM | 3,134,256 | 447683ce670dd850413bcfc1aea62804f6707737bcb2cfb9edefaab5dfe17f08 | 208,080 |

Both builds have the same sketch-source hash:
7003862f85a80e05552b4fd5574004e3fedc136f37c65b0d1065e080fca6ec99.
FQBN: esp32:esp32:esp32s3:FlashSize=8M,PartitionScheme=default_8MB,PSRAM=opi
(or enabled for QSPI),USBMode=hwcdc,CDCOnBoot=cdc,FlashMode=qio. C++ extra flag
-std=gnu++17. The checked-in partitions.csv overrides the default table and the
build script checks every label/type/subtype/flag/offset/size against the original
six entries. No NVS/SPIFFS image or combined full-flash image is produced.

Build command used (replace opi/qspi paths accordingly):
```sh
python3 firmware/elegoo-s3-camera/tools/build.py \
 --cli /tmp/elegoo-toolchain/arduino-cli --config-file /tmp/elegoo-toolchain/arduino-cli.yaml \
 --arduino-data /tmp/elegoo-toolchain/data --build-dir /tmp/elegoo-toolchain/build-final-opi --psram opi --clean
```

The /tmp/elegoo-toolchain path points to the permitted private workspace disk:
/home/five/charlie-ops/firmware-backups/elegoo-esp32s3/s3-integration-build-toolchain-20261109/.
Actual binaries are build-final-opi/ElegooS3Camera.ino.bin and
build-final-qspi/ElegooS3Camera.ino.bin under that directory. Build-report.json,
image-info.txt, ELF/map and verbose compile logs are retained there. These are
real generated candidates, not placeholders, and are intentionally outside Git.

esptool4.5.1 image_info validates the generated checksum and appended digest; image
header is ESP32-S3 chip9, DIO80MHz/8MiB. Both generated tables match the original
NVS0x9000/0x5000, otadata0xe000/0x2000, app0 0x10000/0x330000,
app1 0x340000/0x330000, SPIFFS0x670000/0x180000, coredump0x7f0000/0x10000.
No bootloader/OTA/security compatibility is inferred from that match. The core's
prebuilt application descriptor carries arduino-lib-builder/IDF4.4.7 labels; the
source/commit and whole-file SHA above identify this candidate, not that generic label.

Linker globals initially91,280 bytes, leaving236,400 bytes before runtime allocations.
SDKCONFIG_LWIP_MAX_SOCKETS=16; caps are camera2/stream1/TLS1 plus bounded TCP/mDNS.
TLS connection budget roughly40KiB per IDF, TLS stack12KiB, network8KiB, bridge6KiB.
Camera buffers use PSRAM when present and optional face processing is off initially.
Full camera/TLS/WiFi/model peak heap, stack watermarks and wire timing remain unmeasured.
No claim that this estimate proves native load stability or physical stopping is made.

## Preserved failures and limits

- Initial sandbox DNS prevented CLI/dependency download; isolated tool downloads
  succeeded through normal authorized tool access, without changing sandbox policy.
- Installing the full ESP32 package exceeded the4GiB /tmp tmpfs. Task-only compiler
  files were moved to the permitted workspace disk and the same /tmp path retained
  as a symlink. Installation then completed; no runtime/system configuration changed.
- First native compile failed because the adapted camera .cpp needed an explicit
  Arduino.h include after its WiFi-owning header was removed. Fixed and native builds
  succeeded. Full logs retained; no fabricated image size/checksum or suppressed error.
- Local socket restrictions were tested through device-free loopback execution. The
  first browser run skipped absent Playwright; a separate private venv/Chromium was
  installed and the complete browser/TLS suite then passed without skips.

Hardware compatibility remains unknown: actual camera/PSRAM interface, pin wiring,
GPIO0 physical enrollment, GPIO46 factory LED, installed Arduino UART/N100 behavior,
local failsafe, secure boot/encryption/eFuses, active OTA boot slot, AP channels, subnet
conflicts and radio/TLS/memory load. Both PSRAM binaries are candidates, not alternatives
to flash experimentally. ACCEPTANCE.md defines the separate supervised evidence gates.

No flash, deploy, merge, live Pi network change, service restart, RP2040 access or
physical actuation occurred. Approved runtime remains f3304c588a893a953e34e5c4d00bd5f9bfb18f19.
The original private8MiB backup remains unchanged with SHA256 c196e9077be06b3f61f6acfcf66219fe0535b60ae1d26183c43b2de80ff25c5b.

## First independent CI and pinned runner correction

Published implementation commit61164585f8ce84e415e7ad7b4e402c779ba3130c.
Independent native builds passed on x86_64:
https://github.com/mrgarmise/charlie/actions/runs/42708236101 .
OPI3,135,264 bytes / SHA2562969130d08c8b3a0ea6f15206053f4d02cda52c1276c9e908fd22f1755cfdf08;
QSPI3,133,920 bytes / SHA2561f7cfb45f3a426ed4e4e267cbab1649284d1b3d6261ebcb40c981326d80253ff.
Same sketch-source hash7003862f85a80e05552b4fd5574004e3fedc136f37c65b0d1065e080fca6ec99.
Native binaries can differ with host/build paths and embedded ELF metadata; no
bitwise cross-host reproducibility is claimed. Both geometry/integrity/slot gates pass.

That run's host job failed BEFORE tests because ubuntu-latest selected Ubuntu26.04,
unsupported by pinned Playwright1.56.0. No sanitizer/browser tests were counted as
passing in that failed job. Corrected runner to supported Ubuntu24.04; dependencies
remain pinned and no test is skipped or weakened. Original failed log retained.

Baseline asset audit also confirms original embedded gzip21,403 bytes expands to
117,582 bytes, while original plain camera_index.html is117,101 bytes. This upstream
difference is preserved, not silently regenerated. The actual served asset is the
unchanged embedded gzip. No fork network defaults occur in its decompressed content.

A fresh separate checkout of published6116458 native-built OPI successfully:
3,135,600 bytes, SHA2567629a448195d6347e7170715bcbad08d6a24e27d3f6a43ce692b8a89b7929174,
same sketch-source hash. Byte comparison with the original local build confirms
identical executable/data payload: only the embedded ELF SHA256 field0xb0..0xcf
and dependent checksum/digest footer differ, as expected from debug/build-path
metadata. Exact binaries/hashes remain distinguished; no digest was fabricated or
rewritten to appear reproducible. The clean-checkout artifact is retained under
build-independent-opi/ outside Git, with its own command/log/image-info receipt.

## Final canonical-record candidate — NOT HARDWARE QUALIFIED / DO NOT FLASH

The identity blob is now zeroed across fields AND structure padding before its
checksum and atomic NVS write. The offline enrollment generator refuses Git working
trees so token-bearing extensionless peer records cannot be accidentally staged.
A new refusal test passes. Camera/control protocols and original PR28/29 are unchanged.

| Local aarch64 artifact | .bin bytes | SHA256 | Slot headroom |
|---|---:|---|---:|
| build-release-opi/ElegooS3Camera.ino.bin | 3,135,616 | 9a765c635ab53ac213836453277e4dd63b13fb47cebdc8760a55cdb715e9a5a8 | 206,720 |
| build-release-qspi/ElegooS3Camera.ino.bin | 3,134,272 | d80d58a60b734a2d7c92ec253bd33f4c2795d0b5108dceedca1044a5db7ad00b | 208,064 |

Both builds pass native integrity/partition/header/slot gates, source SHA256
a6c0c2cab3425a2120d04e79fcdc04581d3a50c855377c5b98af4e6276c07f6c.
Actual files and their build-report/image-info/ELF/map/logs are under the private
s3-integration-build-toolchain-20261109 directory described above. No binary or
private enrollment material is staged or uploaded. These images enable no motor
forwarding and remain unqualified for flashing.

Pre-hardening exact commit93a3aa7d03d55ac53e2bad766d40506459317615 independent CI
https://github.com/mrgarmise/charlie/actions/runs/42708912007 passed both native
variants,29 Python/browser/TLS tests (zero skips), five ASan+UBSan C++ suites,
prior core regressions and131 existing contracts. Artifact13715616164 (host JUnit)
ZIP SHA256 f51401be02a8f04ba0ba615274cc3270054c5c33326c544b3f982b85035df05d;
build-report artifact13715086907 ZIP SHA256
c5854f4b9d2c865870a02480377c85087f06158569d629d79aa01f792ce10c67.
Final exact-head independent results are maintained in draft PR30's acceptance ledger
and the private s3-camera-integration-evidence-20261109 directory. Hardware gates in
ACCEPTANCE.md remain mandatory; no installation or physical qualification occurred.
