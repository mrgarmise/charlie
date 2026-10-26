# Native foreground Game 1 → Game 2 procedure

Status: **PREPARED, NOT READY pending actual host prerequisites**. The wrapper's
software fixtures pass, but Codex has not qualified host ownership, controller
neutral/release, independent physical stop, or native socket tests. No physical
trial has started. Standing operator gameplay authorization already applies;
these are technical readiness checks, not another ordinary-game permission request.

Use the ordinary **Pi desktop/console terminal as five**, outside Codex's restricted
execution process. The runner uses that terminal's legitimate native permissions.
No sudo, sandbox escape, new service, restart policy or background command bridge
is installed or needed. Codex may close after source preparation; the foreground
runner and Charlie's existing process watchdogs operate independently of Codex.

The inspected Eyes SSH launcher only owns passive preview; the example offline
systemd unit runs the offline Executive. Neither is a qualified gameplay runner.
Codex can create Unix sockets but cannot connect to the host system/user bus or
tmux socket; AF_INET creation is denied. Saved Eyes metadata is stale and cannot
certify a current owner. These are **Codex access limits, not native device failures**.
See `host-mechanisms.json` and `native-readiness.json` for exact receipts.

## 1. Verify the isolated source and run native device-free checks

The handoff creates a detached, clean checkout at
`/home/five/charlie-native-foreground-20261021`. Match its full SHA to the delivered
publication receipt before continuing. This preserves the frozen reference and
every existing worktree. Do not substitute the moving PR head during a trial.

Copy into the ordinary Pi terminal:

```bash
set -euo pipefail
CODE=/home/five/charlie-native-foreground-20261021
PYTHON=/home/five/Projects/charlie/.venv/bin/python
SHA=$(git -C "$CODE" rev-parse HEAD)
printf 'Trial source: %s\n' "$SHA"
test -z "$(git -C "$CODE" status --porcelain)"
AUDIT=$(mktemp -d /home/five/charlie-native-preflight-XXXXXXXX)
TRIAL=/home/five/charlie-native-trials/foreground-$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p /home/five/charlie-native-trials
printf 'Preflight evidence: %s\nTrial evidence: %s\n' "$AUDIT" "$TRIAL"
CHARLIE_AUDIT_CODE="$CODE" bash /home/five/charlie-native-integration-evidence-20261020/sandbox.sh \
  -m pytest -q tests/test_buffered_recording.py tests/test_robotron_agency_integration.py \
  tests/test_controller_sandbox.py tests/test_ppal_arcade_transport.py \
  tests/test_deferred_measurement_review.py tests/test_marm.py tests/test_passive_eyes.py \
  tests/test_ppal_hands.py tests/test_robotron.py tests/test_score_review_queue.py \
  -p no:cacheprovider --junitxml="/work/native-socket-${AUDIT##*/}.xml" \
  > "$AUDIT/socket-tests.log" 2>&1
cp "/home/five/charlie-native-integration-evidence-20261020/native-socket-${AUDIT##*/}.xml" "$AUDIT/socket-tests.xml"
test -z "$(git -C "$CODE" status --porcelain)"
```

That existing bwrap launcher hides physical devices and does not unshare the
host network. When invoked from a legitimate native terminal it can exercise
ordinary loopback sockets without permitting tests to touch hardware. Expect
153 tests and **zero failures, errors or skips**, including all 34 formerly blocked
socket cases. A denied check remains blocked; never change assertions or run
legacy hardware tests to obtain a pass. The wrapper checks exact coverage against
the original failed-case list. The filename under `/work` is an output mapping,
not an execution escape. Use a new filename if preserving an earlier native run.
Do not proceed if the test command fails; retain its log/XML.

## 2. Actual host prerequisites the operator must verify

Collect a read-only host inventory (this does not open camera/controller devices):

```bash
{
  date -u
  cat /proc/1/comm
  id
  ps -eo pid,ppid,user,comm
  systemctl --no-pager list-units --type=service --state=running
  systemctl --user --no-pager list-units --type=service --state=running
  ls -l /dev/video* /dev/media* /dev/v4l-subdev* /dev/hailo* /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || true
  vcgencmd get_throttled
  cat /sys/class/thermal/thermal_zone0/temp
  df -h /home/five
  free -m
} > "$AUDIT/host-inventory.txt" 2>&1
```

In the native terminal, inspect actual owner process command lines, checkout,
interpreter and open device handles. If Charlie Eyes/another player/offline
worker owns a needed device, use its established foreground closing/stop procedure
and preserve any partial evidence first. Never kill broad process-name matches or
trust stale PID files. A user-systemd/tmux endpoint existing is not evidence that
it accepts commands or is an approved gameplay service.

The runner enumerates native same-user /proc device descriptors and refuses a
same-user camera/media/Hailo owner outside the trial tree. It does not require
root access to inspect unrelated system daemons and does not certify other-user
ownership. The actual host review must independently verify other-user device
clients and exclusive camera admission using established host tools/monitoring;
libcamera/current-view acquisition remains mandatory. If that host-wide ownership
review is unavailable, or same-user descriptors cannot be inspected, keep the
trial unarmed. This is missing monitoring qualification, not a hardware fault.
Do not run the gameplay wrapper as root or loosen sandbox rules. An authoritative
host ownership review has not been completed from Codex.

Before signing the technical review, actually verify and record:

- Independent physical emergency-stop path, its current tested operation, and who
  can operate it. A Python process, Ctrl-C, STOP file or Codex is not that path.
- Independent neutral/release behavior on disconnect/lease expiry, actual controller
  endpoint/firmware/service identity, acknowledgment and a tested release procedure.
  The existing Pi player defaults to `charlie-arcade.local:8765`; confirm it is the
  established Xbox service. The runner does not reconfigure it or its firmware.
- Current exclusive camera/device ownership and accessible authoritative monitoring;
  no offline learner or incompatible device client. Fixed camera/head and focus
  remain unchanged. Do not run the old observe script: it requests auto-calibration.
- Visible Robotron display, supported framing/full HUD, fixed focus, current-view
  player preflight, bounded fresh-frame/SELF acquisition, terminal/START safeguards.
- Continuous host monitoring: valid temperature/throttle readings and visible worker
  tree, adequate disk/memory, recording-writer/fresh-frame/controller guards. Verify
  that the proposed ownership reader and independent stop remain available during play.
- Passing native software receipt and exact clean source SHA.

Save the factual review, supporting evidence paths/hashes and actual tested stop
and release procedures in `$AUDIT/host-review.txt`. Do not write a blanket PASS or
invent hardware proofs. No launch is eligible while any item is unknown. This
review attests technical facts; it does not replace independent measurements or
grant permission beyond the standing operator scope.

After that real review, create the machine-readable binding:

```bash
export CODE SHA AUDIT TRIAL
"$PYTHON" - <<'PY'
from pathlib import Path
import hashlib, json, os, time
root=Path(os.environ['AUDIT'])
note=root/'host-review.txt'
if not note.is_file() or not note.read_text().strip():
    raise SystemExit('Actual host review is missing; keep gameplay unarmed')
def proof(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
keys=('independent_physical_stop','independent_neutral_release',
      'controller_identity_and_lease','camera_ownership',
      'display_fixed_focus_and_framing','host_monitoring')
review={'runtime_revision':os.environ['SHA'],'reviewed_at':time.time(),
        'host_boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'proofs':{key:proof(note) for key in keys}}
review['proofs']['software_tests']=proof(root/'socket-tests.xml')
with (root/'review.json').open('x') as out:
    json.dump(review,out,indent=2);out.write('\n')
PY
"$PYTHON" "$CODE/tools/native_robotron_trial.py" \
  --expected-revision "$SHA" --review "$AUDIT/review.json" --output "$TRIAL"
```

The last command is **unarmed inspection**. It must pass. It requires a fresh
same-boot host review (within one hour), verifies proof-file hashes and all 34
native socket cases, and checks source cleanliness and resources. A hash-bound
operator note cannot itself prove a physical stop/release; the real review above
is mandatory. No source or device permissions are modified by this process.

## 3. Qualified learning selection and the single trial launch

No independently qualified physical retained-response candidate is currently
identified. Do not supply the engineering replay attachment as a live policy.
Charlie must originate the eligible investigation/proposal and pass the existing
independent evaluation, activation and Robotron physical-readiness gates.

With no eligible manifest, leave `POLICY_ARGS=()` below. If an eligible manifest
exists, set `POLICY_ARGS=(--learned-policy /absolute/path/to/qualified/ppal-policy.json)`
and repeat unarmed inspection with `"${POLICY_ARGS[@]}"` appended. The policy loader
rejects offline grants, altered candidates, runtime mismatch or revoked activation.
The manifest may contain the retained evidence attachment implemented here; its
compiled values influence actual geometry-qualified positioning choices. Source,
policy, configuration, proof and learning-state identities are frozen before launch
and the marathon rechecks physical admission for each game.

Only after all host prerequisites and the unarmed inspection pass:

```bash
POLICY_ARGS=()
"$PYTHON" "$CODE/tools/native_robotron_trial.py" \
  --expected-revision "$SHA" --review "$AUDIT/review.json" --output "$TRIAL" \
  "${POLICY_ARGS[@]}" --run
```

This is one foreground command, bounded to **at most two complete games**. It
keeps `--baseline-only` to disable commissioned actuator experiments while
allowing an explicit qualified policy. It does not launch a six-game marathon,
background service or automatic replay. Do not close this terminal; Codex can be
closed. Ambient CHARLIE_LEARNING_STATE policy discovery is removed so the declared
policy identity matches the selected policy.

The native wrapper samples once per second: temperature, throttling, worker-tree
RSS/CPU utilization, free memory/disk and device owners; it fsyncs the trace and
stops on missing telemetry, >=75°C, any throttling flags, less than 512 MiB free
memory, worker RSS above a conservative 768 MiB, less than 2 GiB free disk or an
outside same-user device owner. Cross-user ownership remains an independent
host-review responsibility. These are conservative stops, not expanded operating limits.
Charlie retains the existing fresh-frame/stream overflow, controller acknowledgment,
writer-health, neutral/release and completed-work watchdog safeguards. The wrapper
never resumes automatically after cooling or failure. A stricter host condition
or independently verified limit still takes precedence.

## 4. Stop and accept evidence

Normal stop: **Ctrl-C in the runner terminal**. In another ordinary host terminal,
`touch "$TRIAL/STOP"` requests the same bounded software stop (use the exact trial
path printed earlier). Terminal SIGHUP and SIGTERM also trigger owned-process
cleanup. Urgent risk: use the independently tested **physical emergency stop**
immediately; do not wait for software. Never use kill -9 as the normal release
procedure. Verify actual controller neutral acknowledgment and all owned workers
terminated; the wrapper's return code is not that physical proof.

Retain the entire `$TRIAL` directory and `$AUDIT`: frozen identity/review/proof
copies, runner log/result, native-resource trace, all nested marathon sessions,
original images, source journals, progress and controller events, scores,
completion/recording seals and partial/failure evidence. No elapsed-time,
reserve-count or demonstration sprite can establish completion. Independently
accept genuine Game 1 terminal/completion and a fresh acknowledged START plus
playable supported-SELF Game 2. If the lifecycle fails, preserve it, diagnose it
and restore a verified safe state before another attempt. No auto retry.

For rollback, stop and confirm neutral first. Launch the previously qualified
runtime/policy from a separate clean checkout, with a new technical preflight and
fresh output. Omit the learned manifest to disable the learned component; journal
revocation is enforced on reload and does not hot-revoke a cached running episode.
Do not reset learning notebooks or evidence. Block A and Block B remain gated on
independent phase acceptance; no command here starts either three-game block.
