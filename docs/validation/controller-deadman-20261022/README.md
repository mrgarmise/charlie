# Controller deadman repair — published development candidate, not deployed

**Watchdog active on charlie-arcade: NOT VERIFIED. Physical acceptance: PENDING.**
The ordinary-terminal inspection in `arcade-inspection.txt` confirms ARMv6 host,
systemd ExecStart `/home/five/arcade/launcher.py`, launcher PID 399 and active
Robotron emulator PID 626 at inspection time. These are evidence-time identities,
not a current device assertion. No service or gameplay command was sent during
this preparation. ARMv6 validation and physical release acceptance remain pending.

## Published release and provenance

- Arcade [draft PR #4](https://github.com/mrgarmise/charlie-arcade/pull/4), branch
  `development/controller-lease-20261022`, candidate
  `5ed9cc6fdf66cb22b93ba1587170e8280bc6a417`, direct parent
  `0825f596dc9397e1c6721dc2a38249a0420cde61`.
- Charlie [draft PR #9](https://github.com/mrgarmise/charlie/pull/9), compatible
  runtime `d6ef07b0b5a5959feedf50ef7f53a7fa026e29c6`, direct parent
  `aaf36ac708b8af422a7ffbdfb4f63e0d92bb9774`. Its four changed runtime/test
  files preserve all other integration blobs and the existing stacked base.
- [Exact, short ordinary-terminal handoff](NATIVE-OPERATOR.md): native tests,
  operator-controlled stopped backup/install, physical acceptance, then the
  existing two-game runner. No installation or live activation performed here.

`reconciliation.json` records installed-source SHA256 reconciliation. Authentic
printed launcher/controller bytes match GitHub's exact base; installed catalog
and display hashes match too. Controller SHA256 remains
`344e9886848b5bc437f257a272f08b0df9d6b49fe844dae8b7368dd527cadc8d`.

SSH git clone failed authentication; HTTPS clone failed credentials after its
network restriction was separately cleared. The authenticated GitHub connector
supplied exact commit/tree metadata. `/tmp/charlie-arcade-deadman` is a separate
shallow sparse checkout at the **authentic hash-verified upstream commit** with
verified source/test/config blobs; binary emulator blobs and unrelated documents
were not downloaded. Upstream commit object and complete tree hashes were
reconstructed exactly, without synthetic ancestry. `charlie-arcade.patch` passed
`git apply --check` and was applied there unchanged. The prior source-reconstruction
workspace `/tmp/charlie-arcade-lease` is retained as historical evidence.

Qualification exposed one necessary amendment: the reviewed installer/preflight
allowlist predates the authentic installed launcher/catalog pair. The published
candidate adds that exact pair and exercises preservation and mixed-pair refusal.
`baseline-qualification.patch` is the separate amendment after the original
reviewed patch; neither relaxes service, host, architecture, ROM or source checks.

The server has an exclusive one-second monotonic lease, independent 25 ms poll,
strict bounded ASCII lines, no renewal for invalid/menu traffic and no resumption
on expired connections. LEASE renews without interrupting held state; owner
disconnect and global NEUTRAL release; non-owner disconnect cannot interrupt an
owner. Failed neutral output inhibits actuation and retries release. Synchronous
100 ms taps and OS scheduling can delay polling; no hard real-time or frozen-kernel
protection is claimed. Independent physical stop remains required.

Charlie requires LEASE in the native runner and renews from each progressing
execute(), including unchanged positions, with no autonomous heartbeat. Rejected
renewal closes the connection; stale local timers cannot interrupt renewed holds.
Other clients retain their default protocol behavior, but the new server bounds
all holds. No settings, ROMs, live library, user history or integration branches
other than the requested PR #9 head were changed.

## Evidence

Final publication verification: `arcade-tests-final.xml`: **256 passed plus seven subtests**,
`arcade-unittest-final.txt`: **256 tests, OK, no skips**;
`charlie-tests-native-sockets.xml`: **97 passed**. The existing native prerequisite
selection also passes **153 tests** (`charlie-native-prerequisites.xml`), resolving
the formerly blocked socket cases in this permitted device-free run. These groups
overlap and must not be summed. Restricted reruns are preserved
as `arcade-tests-release.xml` and `charlie-tests-release.xml`; final permitted
socket runs pass, including the real frozen-client case. Compileall, shell syntax
and whitespace checks pass. The earlier receipts below remain historical.

Tests ran on **aarch64**, with synthetic ROM fixtures, fake emulator processes and
recorded controller events. No `/dev/uinput` creation or physical game launch.

| Receipt | Actual result |
| --- | --- |
| `arcade-tests.xml` | 255 passed, 7 subtests passed, 9.59 s; entire fetched source suite including installer preservation/rollback |
| `charlie-tests.xml` | 97 passed, 11.81 s; client renewal/rejection, stale timers, native runner, existing transport and sandbox regressions |
| Cross-repository SIGSTOP test | Real Charlie client executes against real launcher socket worker and controller event generation; stopped with socket open; server releases within the test's 1.4 s observation window and rejects renewal on the expired connection |
| Static checks | compileall, shell syntax, diff whitespace and patch application checks passed |

Lease tests cover ordinary holds/taps, live stalled sockets and partial lines,
continuous renewal without intermediate neutral, exact deterministic expiration,
invalid traffic, simultaneous claims, concurrent clients, both disconnect cases,
global/repeated NEUTRAL and failed neutral output/retry.
`arcade-initial-sandbox-failures.xml` preserves the first broad restricted-socket
run, including the initial mock/source-reconstruction failures corrected before
the passing run. The original reconstructed text had an extra trailing newline;
upstream blob checks corrected it without altering the baseline controller pin.
No ARMv6 test receipt or physical acceptance is claimed.

## 1. Ordinary-terminal read-only inspection (completed; retained command)

From this Charlie checkout in an ordinary terminal (SSH prompts for the password):

```bash
mkdir -p /tmp/controller-lease-operator
ssh five@192.168.1.238 'bash -s' < docs/validation/controller-deadman-20261022/inspect-arcade.sh > /tmp/controller-lease-operator/arcade-inspection.txt
```

The supplied report has been reconciled; retain any later report separately. It contains service/drop-in settings, fresh process
identities, socket inventory, device identities and exact installed source/hashes.
It does not send controller commands. If the local SSH system-config permission
error recurs, use `ssh -F /dev/null five@192.168.1.238 ...` with the same command.

Repository service configuration uses systemd ExecStart
`/usr/bin/python3 /home/five/arcade/launcher.py`, tty1, Restart=on-failure and a
two-second restart delay. Drop-ins set uinput group permissions and wait up to
30 seconds for HDMI. These are repository settings until installed settings are
inspected. A restart is an activation; source copying alone changes no running
Python process.

## 2. Prepare and validate the exact candidate; no service changes

Publication preparation is complete at the exact pins above. For reproduction,
apply `charlie-arcade.patch` then `baseline-qualification.patch` to the exact base.
Keep the installed checkout intact. Use [the pinned native handoff](NATIVE-OPERATOR.md)
in a separate ARMv6 checkout; never deploy a moving branch or historical synthetic commit.

Run `python3 -m unittest discover -s tests -v` with `PYTHONPATH=src:tests` and
`CHARLIE_TEST_ROOT` pointing to an exported checkout containing the reviewed
Charlie client changes. This enables the cross-repository frozen-client test;
do not count its skip as acceptance. Preserve full output, compileall and shell
checks outside both clean checkouts. Run the existing read-only library preflight
when the operator has brought the emulator to a stopped state; it refuses live
RetroArch. Native validation and receipt review precede installation.

## 3. Preserve state before any stop/restart

After source inspection, from an ordinary SSH shell on **charlie-arcade**, save a
fresh inventory and backup in a new directory with enough free disk. Example
backup commands, for the operator to review and execute:

```bash
LEASE_REPORT=$(mktemp -d "$HOME/controller-lease-backup.XXXXXXXX")
systemctl cat charlie-arcade.service > "$LEASE_REPORT/unit.txt"
systemctl show charlie-arcade.service > "$LEASE_REPORT/service-state.txt"
ps -eo pid,ppid,user,lstart,args > "$LEASE_REPORT/processes.txt"
tar -cpf "$LEASE_REPORT/home-before.tar" -C /home/five arcade .config/retroarch RetroArch
```

Also preserve `/etc/systemd/system/charlie-arcade.service*` with metadata, boot ID,
installed revision/dirty diff, source SHA256s, display settings and controller
autoconfiguration. A live archive is not a transactionally consistent database
snapshot: use SQLite's backup API for any active catalog database and retain its
WAL files. Keep the backup outside the installation. Check archive readability
and free space; do not proceed on a partial backup.

This does **not** preserve RetroArch's in-memory game state. If preserving that
state is required, stop here for an operator-selected save-state procedure.
Do not silently end the running game. The operator controls when to exit it and
authorize the service stop. Record what state was actually preserved.

## 4. Separately authorized stopped deployment and rollback

Only after the operator approves stopping the inspected service and native tests
pass, use the existing guarded handoff from the candidate checkout:

```bash
sudo systemctl stop charlie-arcade.service
python3 scripts/preflight_playable_library.py --expected-commit "$LEASE_CANDIDATE" > "$LEASE_REPORT/before.json"
python3 scripts/install_rom_intake.py --expected-commit "$LEASE_CANDIDATE" > "$LEASE_REPORT/install.json"
python3 scripts/preflight_playable_library.py --expected-commit "$LEASE_CANDIDATE" --installed-candidate --baseline-report "$LEASE_REPORT/before.json" > "$LEASE_REPORT/after.json"
```

Set `LEASE_CANDIDATE` to the final 40-character reviewed SHA first. Inspect exit
statuses individually; abort on any failure. Installer refuses a running service,
RetroArch, wrong host/architecture, changed controller or unreviewed installed
modules. Never loosen those checks to force installation. Its install lock,
module backup, SQLite backup and protected-state comparison now include the lease
module. Post-install preflight checks its exact candidate hash. Require unchanged
library/history/protected hashes, `persistent_evidence_preserved: true`, recorded
backup path and `service_started: false`. Leave the service stopped.

Do not rerun fresh-machine `install.sh`: it replaces configuration. Only after
separate operator startup approval, start the existing service at its menu, read
the fresh PID and source hashes, and perform the no-gameplay diagnostic below.
No automatic startup/restart command is supplied as part of the install sequence.

On install failure the guarded installer restores old modules/database, removes
the newly introduced lease file and retains failure evidence. For a later
acceptance failure, stop the service, preserve all new evidence, and restore the
exact modules listed in the backup manifest (remove controller_lease.py only if
the manifest says it did not previously exist). Verify original hashes/config and
SQLite integrity before any operator-approved startup. Preserve post-install DB
history; do not overwrite newer records merely to roll back code. Never use git
reset or reinstall the appliance as rollback.

## 5. Physical neutral-release acceptance — NOT EXECUTED

Operator present, independently verified physical stop available, no game running,
new service at menu, physical Xbox sets PLAYER: CHARLIE without selecting a game.
Identify the existing **Charlie Virtual Controller** event node afresh in
`/proc/bus/input/devices`; never rely on js/event numbering or grab the physical
Xbox. Copy `check-physical-neutral.py` to the arcade host. It opens the selected
event node read-only and queries all eight axes and all key bits with ioctl.

1. On arcade: `python3 check-physical-neutral.py --event /dev/input/eventN`.
   Require `neutral: true` before the test.
2. On Charlie, run the supplied `lease-hold-probe.py --host 192.168.1.238
   --confirm-no-gameplay`. This intentionally holds left/right stick, hat, trigger
   and A and renews every 200 ms. Independently read kernel state for several
   seconds: values must stay held, with no periodic interruption. The neutral
   checker deliberately exits 1 while held; this is an observation, not success.
3. From another Charlie terminal: `kill -STOP <printed-client-pid>`. Verify that
   PID is stopped (`ps -o pid,stat,args -p <pid>`), its TCP socket remains open,
   and the arcade launcher is still running. Do not send NEUTRAL or disconnect
   the probe to make this case pass. Independently sample kernel values and time
   the transition. Require all axes zero and all keys released within 1.4 s of
   STOP; otherwise invoke the operator stop and fail acceptance. Record the actual
   measured latency and independent device output.
4. `kill -CONT <pid>`: the expired renewal must be rejected, cleanup emits only
   NEUTRAL, and held state must not return. Reconnect deliberately for further
   cases. Ctrl-C while renewing tests normal disconnect. Test a second idle
   connection's disconnect does not interrupt the owner; its LEASE/control tokens
   return ERROR. From a second client, NEUTRAL must always release the owner.
5. Record operator, time, boot ID, actual launcher PID, installed module hashes,
   exact client/server revisions, held/neutral device evidence, renewal interval,
   release latency, open-socket/stopped-client evidence and physical stop result.
   Any missing observation is PENDING, not PASS. Do not begin gameplay as part
   of this procedure.

Only a completed native deployment plus this acceptance receipt supports a claim
that the watchdog is active on the appliance. Until then the native gameplay
trial's controller lease/release proofs remain outstanding.
