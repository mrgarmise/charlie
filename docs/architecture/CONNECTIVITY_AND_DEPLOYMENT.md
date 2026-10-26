# Connectivity and deployment

Contract beneath [Charlie Architecture](../CHARLIE_ARCHITECTURE.md).
All addresses here are **source-configured defaults or historical documentation**,
not proof of reachable hardware. No live Pi/service inventory, serial connection,
camera activation, deployment or firmware write occurred in this audit.

## Channels and process ownership

| Component | Source-defined channel | Owner / present evidence |
|---|---|---|
| Pi 5 integration host | Local Python `main.py`; hardware explicit | Owns application camera feeders and normal cognitive lifecycle. Installed checkout SHA and current processes unknown. |
| IMX708 | Picamera2/libcamera CSI | `_PiCameraDevice` owned by feeder; camera lease admits physical capture. Local bus and passive lossless snapshots serve subscribers. |
| ELEGOO camera | `http://192.168.4.1:81/stream` | `_ElegooCameraDevice` MJPEG reader via feeder; endpoint lease. Wi-Fi association/reachability not checked. |
| ELEGOO command transport | `192.168.4.1:100` TCP | `hardware/elegoo_mobile.py` command connection. `motion/mobile_base.py`/independent safety authority mediate intent; sensing does not authorize connection or movement. |
| pico:ed RP2040 | `/dev/ttyACM0`, 115200 default | `hardware/rp2040_controller.py` serializer owns normal serial connection, READY/protocol capability/heartbeat/status. OS device path may change. |
| Hailo-8L | Local HailoRT / PCIe | `HailoSession` hash validation, exclusive cooperating lock; no raw camera ownership. Installation/runtime version unverified here. |
| Robotron game host | TCP 8765 in `experiments/robotron/live.py` | Target host passed by operator; controller transport differs from camera sensing. Historical host identity described as Pi 4 by mission; current hardware identity unknown. |
| Passive viewer | Local HTTP port 8767 in launcher/viewer | Existing launcher SSH-forwards loopback 8767. Passive snapshot files are same-host monotonic/boot-bound; no generic multi-host clock translation. |
| Birdfeeder eye | No verified endpoint | Planned, no service or credentials inferred. |

Camera consumers can run in the feeder process or use same-host passive snapshots.
There is no requirement to collapse every owner into one OS process. The Pi 5 does
not centrally operate every future remote sensor. Remote hosts need independent
bounded publication, discovery, health and explicit clock mappings.

`setup/charlie_eyes_launcher.py` documents process startup and SSH forwarding;
`setup/install_robotron_pi.sh` documents game-host installation. These scripts are
not evidence of enabled systemd units. Current systemd/startup configuration,
serial owner PID, Wi-Fi pairing, active leases and unpublished native work are
**unknown** without read-only native inspection. The isolated cloud checkout has
no mounted native checkout. Do not stop/restart hardware services to make tests pass.

## Published source and branch reconciliation

GitHub is authoritative for published source, original hardware journals for
observed evidence, and Linear for tracking only. At initial inspection:

| Branch / role | Published SHA |
|---|---|
| `master` | `bcf8082f6319c63c4bd6bcceeab5faea37241654` |
| PR #10 `feature/mobile-perception-pet-following` | `cafe21aa3f6c68080c12a1a5613a92516fdb7167` |
| PR #11 `feature/object-label-picoed-display` | `a19c90822687739f79f69587302006a1bd6364d4` |
| PR #10 ancestor used by PR #11 | `96e651373e513d24b4163b87c5f85bdd5549cf1d` |

PR #11 is stacked on PR #10 but does **not** contain the latter's newest safety
increments. This audit is isolated on `audit/shared-sensory-contracts` based on the
exact PR #11 head, with a PR targeting that feature branch. It neither rewrites
nor merges PR #10/#11. Branch snapshot: [published-branches.txt](audit/published-branches.txt).
Both discussions were empty at inspection. Unpublished work in other sessions or
native worktrees cannot be established from GitHub; inspect those worktrees before
any future deployment/integration. Do not wholesale overwrite main/runtime files
with older PR #11 versions while reconciling PR #10.

## Firmware identity and controlled deployment chain

Required chain: Git repository → verified Pi checkout →
`tools/sync_rp2040.py` → MicroPython RP2040 root and `/lib` → reboot/readback.
The synchronizer uploads support libraries before application dependencies and
reboots. It does **not** prove a live device's exact installed Git identity by
merely returning success. Do not execute it under this audit's authorization.

`rp2040/lib/Pico_ed.py` is the tracked `/lib` source at the examined revision.
`rp2040/*.py` contains application/protocol/display/servo/calibration source.
Extra installed `/lib` files, `boot.py`, local profiles/calibration, and physically
installed bytes may differ and are unknown. Preserve them before any authorized
future sync. Firmware capability replies and READY identify supported behavior,
not full byte-for-byte Git identity. A readback/manifest receipt is still needed.

For a separately authorized maintenance window:

1. Record Git remote, branch, `git rev-parse HEAD`, clean/dirty status, local
   patches and all worktrees on the Pi. Preserve existing logs and running PIDs.
2. Record RP2040 serial owner, firmware handshake/capabilities, and device identity;
   coordinate exclusive maintenance access without introducing a second owner.
3. Back up **all** device root and `/lib` files plus device-local profile/calibration
   data. Hash readback bytes; preserve backup path and original evidence unchanged.
4. Record candidate Git SHA, firmware-source hashes and intended destinations.
   Only after separate permission execute the established sync script.
5. Read back/hash installed files, compare intended manifest and record exceptions;
   record actual `/lib` inventory and preserved local data. Verify READY/heartbeat,
   STOP responsiveness, calibration default-disarmed, protected HEAD B and label
   priority in a stationary, separately authorized test. A successful upload alone
   does not establish any of these observations.
6. On failure, retain failed receipts. Restore the backed-up device files/local
   profiles through the same controlled maintenance channel; verify readback and
   safe boot. Revert the Pi checkout/config independently. Do not use reset/clean
   on another session's worktree.

GP10 remains supervised calibration-only. Preserve electrical isolation, CAL-1,
HEAD B lockout, watchdog/STOP and independent mobility gates. Object labels are
lower priority than safety/status/connection output. Normal Pi labels use
`--hardware --object-label-display rp2040` through the existing AttentionManager
and serial owner; this document is not authorization to run that command.

## Troubleshooting and rollback of this audit

Unavailable frames: check source health/feeder lifetime, lease conflict and published
snapshot age/boot ID first. Do not start a fallback camera from the consumer.
A camera switch closes only its subscription. Stale/faulted publication must not
be replayed as live. Hailo busy/thermal suspension means unavailable inference;
retain the interruption and let independent guards decide recovery.

Audit software rollback is a new `git revert` of the audit commit(s), after
checking a clean isolated worktree. No firmware/device rollback is required by
this mission because no hardware state was changed. Before native use, reconcile
latest PR #10 safety changes and PR #11 subscriber changes; preserve both histories
and rerun the acceptance matrix in [CONFORMANCE.md](CONFORMANCE.md).
