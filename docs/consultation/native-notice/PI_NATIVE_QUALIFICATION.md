# Pi native qualification procedure (pending, do not execute as deployment)

This checklist records genuinely native-dependent acceptance for PR #37/#38.
The source mission authorizes implementation and testing, not installation,
flashing, approved-runtime interruption or unattended enablement. No checkbox
below is completed by software CI. Use a separately authorized isolated native
qualification window; collect raw observations and an independent reviewer receipt.

## Prepare the reviewable candidate

1. Pin the reviewed implementation commit in a clean root-protected checkout
   outside `/home` (for example `/opt/charlie-native`). Protect every Python file,
   interpreter/environment and imported dependency against the Executive UID.
   Review the source and all unit hardening with the installed systemd version.
   The configuration examples are deliberately disabled and incomplete.
2. Provision four distinct identities: human owner, Executive, model and existing
   serial owner. The Executive must have only its dedicated group, no effective
   or permitted capabilities, and NoNewPrivs=1. Give it read access to authentic
   original sources, write access only to its separate answer journal and local
   approval-state directory. Do not put source evidence in its write domain.
3. Root owns policy, approval directory, broker socket parent, inventory,
   qualification receipt, scheduler ledger and model binary. Approval JSON may
   be group-readable by the Executive but never writable. Verify symlink,
   parent replacement, peer UID and forged document attacks are refused.
   Owner cancel/primary commands need root or an explicitly reviewed socket ACL;
   they must not grant the Executive owner privileges.
4. Reconcile all nine inventory classes: camera, Hailo, serial, telemetry,
   watchdog, motion, gameplay, human and primary. List every known systemd owner,
   actual scheduled duties and finite inventory validity. Any unknown owner,
   active unit, physical descriptor, outstanding lease or unreconciled traffic
   prevents admission. Current code conservatively rejects established
   non-loopback TCP, including SSH: qualify through a local console or review a
   separate source change, never invent a quiet assertion. The approved runtime
   holding its existing flock also prevents admission; do not stop it merely to
   satisfy this checklist without separate authorization.
5. Integrate `DisplayBridge(existing_controller)` into the qualified existing
   sole serial owner's composition and bounded I/O thread. No new controller,
   port opener, heartbeat producer or motion authority is permitted. Verify its
   service PID is the only process holding the configured serial device.
6. Qualify the candidate RP2040 firmware through the separate approved flashing
   process. Source-only tests cannot establish the currently installed image.
   Read DISPLAY_CAPS and confirm the new protocol is supported. Old firmware
   must fail native admission. Retain firmware identity and physical readback.

## Observe device safety and warning behavior

With motion independently disarmed, capture raw host/device packets and video
of PREPARING, MEDITATING and THINKING. Confirm the full `MEDITATING PLEASE WAIT`
text is legible and smoothly scrolls without refresh restarting its position.
Positive ACK follows rendering, with exact session, slot, sequence and <=2s TTL.
Try duplicate, stale, cross-session, expired, forged ACK and out-of-order packets.
None may revive an expired/STOP-closed warning or admit a consultation.

Verify normal label TTL/restore; empty-question meditation; normal human deferral
and resumption; and emergency priority. Exercise STOP, physical calibration,
error, Pico reboot and serial disconnect during preparation and consultation.
Verify immediate safety precedence, no PWM construction, no movement, independent
device TTL clearing after host/broker death, and a new handshake after reconnect.
Never infer physical visibility solely from an ACK.

## Observe real isolation, bounds and cleanup

Record raw systemd properties, PIDs/start ticks, namespaces, fdinfo locks,
cgroup.procs, temperatures/load/RAM/swap/throttle and monotonic deadlines.

- Prove the Executive cannot connect to model loopback, enter its namespace,
  modify root policy/receipts, call arbitrary model APIs or choose a binary.
  Model private-network behavior must coexist with the unchanged manual path;
  an already-running host model server must refuse native admission.
- Prove reservation holds the exact existing runtime-lock inode continuously.
  Kill issuer, client and model MainPID separately; include a surviving model
  child. Guardian must retain exclusion until the whole model cgroup is empty.
  Inject a guardian RPC failure. A stop return code is never cleanup evidence.
- Verify preset RuntimeMaxSec, actual ActiveEnterTimestampMonotonic and
  TimeoutStopUSec on this Pi/systemd. Delay startup; late activation must refuse
  model exec before prewarm. Kill broker/client during prewarm/inference and
  demonstrate actual kernel cutoff before absolute slot end without extension.
- Revoke policy and create primary/physical deadlines during startup and query.
  Capture independent monitoring and emergency cancellation latency. Verify
  resource pressure, lost thermal probe, swap, throttling and unknown inventory
  abort safely. Guardian must remain bounded by cleanup proof under failure.
- Verify one real eligible original question, exact identity/digest/envelope,
  durable unverified answer, independently empty /api/ps, empty cgroup, clear ACK
  or honestly pending device TTL, released lock, and resumed deferred human IDs.
  Current held questions are not eligible acceptance inputs. Do not mutate their
  eligibility, copy them into fake eligible records or substitute demo evidence.
- Interrupt after submission before answer retention, restart broker and client,
  and demonstrate durable no-retry refusal. Four/day, one-hour cooldown, commission
  and original-question replay must survive restarts. Manual consultation and
  generalized selection regressions must remain green.
- Test `client cancel`/`primary` while prewarm is blocked and a human request is
  queued. Ordinary deferral must not delay urgency. After actual primary work is
  independently quiescent, `primary-done` may reset only the STOP latch; repeated
  unknown completion remains blocked. Clear failures must not delay emergency
  work or falsely report availability.

Use `python -m learning.native_meditation.client status|cancel|primary|primary-done`
only in the authorized qualified environment. The explicit Executive flag is
`--native-meditation`; it is rejected for hardware/replay/pet/manual-approval
combinations. Production CLI offers no fake driver or caller-owned approval mode.

## Receipt and promotion gate

Retain failed runs as well as successful evidence. Independently reconcile exact
code revision, model digest, binary hash, firmware identity, inventory hash,
permissions, native timing and all negative cases. Only then may a separate
review authorize setting `native_scheduler_display_accepted` and policy enabled.
A signed-off acceptance record, not the templates, is the source of those values.
No example unit has an Install section; do not enable unattended startup during
qualification. Any deployment, operational runtime change or unattended promotion
requires its own explicit authorization. Preserve unknown-completion ledger and
approval history through revocation, drain and rollback.
