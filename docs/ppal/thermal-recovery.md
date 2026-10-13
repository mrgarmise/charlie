# Developmental thermal suspension and recovery

This is operational recovery within the existing Learning Executive. It does not qualify a candidate, grant physical authority, activate a PPAL policy, or prove learning. The ALA Learning Charter and ALA2 Acceptance Standard remain governing requirements.

## Lifecycle

Development stops at measured temperature **>=75°C** (a configured lower ceiling is permitted; a higher ceiling is rejected). A latched interruption clears only after every available sample is **strictly below 65°C** for **5 seconds**, followed by successful gameplay-ownership and owned-process memory checks. Reheating to 65°C or above during cooling resets stabilization; a later measurement >=75°C interrupts again. Polling takes place within the existing application-owned worker; it invokes no Executive investigation while suspended. The same Executive, journal, commissions, and checkpoints resume afterward.

Defaults and configuration:

| Option | Default | Meaning |
|---|---:|---|
| `--learning-temperature-c` | 75 | Ceiling, restricted to 40..75°C |
| `--learning-recovery-temperature-c` | 65 | Recovery must be strictly below this, which must be below ceiling |
| `--learning-thermal-stabilization` | 5 | Seconds continuously observed cool, 0.1..300 |
| `--learning-cooldown-poll` | 1 | Seconds between suspended resource probes, 0.05..10 |
| `--learning-require-thermal` | ARM Linux automatic | Fail closed if no thermal telemetry; cannot disable this on ARM Linux |
| `--learning-wall-seconds` | 300 for bounded runs | Cooperative deadline covering all turns and waiting |
| `--learning-cooldown-seconds` | 120 for bounded runs | Maximum continuous thermal suspension, including recovery blocked by ownership/memory |

For unbounded normal operation, wall/cooldown deadlines default to absent; the worker can recover without restart. SIGINT/SIGTERM cancellation is checked before cached resource decisions and during interruptible waits (<=0.1s sleep pieces). The existing child supervisor now probes offline resources every supervision cycle (default 0.2s), even without a child heartbeat; preemption uses its existing checkpoint/stop/reap boundary. CPU affinity, process niceness, owned-child memory accounting, worker CPU limit, and gameplay priority remain in force.

Unreadable, invalid, NaN/infinite, negative, or implausible sensor values suspend developmental work conservatively. On ARM Linux (including Raspberry Pi), missing sensors also suspend. A non-ARM desktop without thermal zones may run software validation, explicitly reporting telemetry absent; this cannot qualify native Pi thermal behavior. After any thermal latch, loss of telemetry on any platform remains fail closed. Restart retains the latch and requires a new stabilization interval; monotonic timestamps are not carried between processes. Invalid retained operational JSON also restores a conservative latch.

## Bounded accounting

`--learning-turns N` bounds **N nonthermal attempt slots**, rather than promising N discoveries. A slot includes an eligible Executive attempt or a nonthermal preflight refusal (memory/gameplay). A thermal preflight refusal, a thermal-preempted attempt, and cooldown polling consume no slots. `developmental_attempts` counts actual Executive invocations; `productive_turns` independently counts attempts whose existing Executive reports committed progress. A partially advancing thermal-preempted attempt may count as productive without consuming a slot. Polling never counts as productive. Missing evidence/blocked work can consume slots without progress. Default wall/cooldown deadlines prevent bounded runs from waiting forever.

Deadlines and suspension are cooperative: a filesystem call, hash, existing evaluation, journal projection, constructor, final status fold or fsync already executing cannot be interrupted safely at an arbitrary instruction. Resource checks were added between acquisition units, before candidate dispatch/evaluation, and to every offline child-supervision poll. The per-experiment `--learning-budget` still does not independently bound complete acquisition/status work. Use the outer `timeout` below for a hard operator validation limit; if forced termination occurs, retain all prior durable checkpoints and classify native clean shutdown as unverified. Do not reinterpret timeout as a completed investigation.

## Status and telemetry

`development-operational-status.json` is the authoritative lightweight operational surface: `state`, `reason`, `updated_at`, current resource sample, `thermal.suspended`, thresholds, `stable_for_seconds`, recovery count, run counters, and termination reason. States include `running`, `thermal suspension`, `cooling`, `recovery eligible`, `resumed work`, `other resource blockage`, `worker failure`, `shutdown requested`, and `clean shutdown`. Console messages report state/reason transitions. The ordinary `development-status.json` retains the Executive status and embeds the operational snapshot when normally refreshed; it is deliberately not reconstructed on every cooldown poll.

Telemetry replaces one atomic file, retaining only the latest 100 transition events. Identical polling does not append events. It is never appended to the evidence journal as a new learning observation. Existing checkpoint/yield/progress receipts retain their original semantics and identity deduplication. The separate read-only collector `tools/observe_development_thermal.py` samples the sensor and operational file into a fresh JSONL file, with a bounded duration and no physical capability imports.

## Operator staging and native validation

**Requires separate approval to stage/run this code on Charlie. Nothing below was executed on the Pi for this assignment.** Do not switch the installed application or activate a candidate. Any physical gameplay, servo movement, deliberate heating/stress load, firmware change, or policy activation requires its own explicit approval. No deliberate heating is included.

Set `THERMAL_SHA` to the published feature-branch commit reported in the engineering handoff. Set `PYTHON` to the approved native Charlie interpreter with the existing offline dependencies. Preserve the installed `/home/five/charlie-ala2-bae659f60b0e` checkout and original notebook.

```bash
set -eu
: "${THERMAL_SHA:?Set the published thermal repair SHA}"
: "${PYTHON:?Set the approved native Charlie Python executable}"
SOURCE=/home/five/Projects/charlie
CHECKOUT="/home/five/charlie-ala2-thermal-${THERMAL_SHA:0:12}"
git -C "$SOURCE" fetch origin feature/ala2-thermal-recovery
git -C "$SOURCE" worktree add --detach "$CHECKOUT" "$THERMAL_SHA"
cd "$CHECKOUT"
test "$(git rev-parse HEAD)" = "$THERMAL_SHA"
test -z "$(git status --porcelain)"
"$PYTHON" -c 'import platform, numpy, PIL; print(platform.platform(), platform.python_version())'
RUN="/home/five/Projects/charlie/thermal-validation-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir "$RUN"
STATE="$RUN/state"
export STATE
"$PYTHON" - <<'PY'
import fcntl, os, shutil
from pathlib import Path
original=Path('/home/five/.local/share/charlie/development')
# Refuse a live owner; never stop it or copy a changing SQLite notebook.
with (original/'offline.lock').open('r') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    shutil.copytree(original,os.environ['STATE'])
PY
"$PYTHON" tools/inspect_developmental_progress.py "$STATE" > "$RUN/before.json"
"$PYTHON" -m pytest -q tests/test_thermal_recovery.py tests/test_development_resources.py \
  -o junit_family=xunit1 --junitxml="$RUN/native-deterministic-tests.xml" > "$RUN/native-deterministic-tests.txt" 2>&1
# Deterministic injection on Pi is software validation, not authentic cooling.
vcgencmd measure_temp > "$RUN/temperature-before.txt"
vcgencmd get_throttled > "$RUN/throttled-before.txt"
"$PYTHON" tools/observe_development_thermal.py --state "$STATE" \
  --output "$RUN/thermal-observations.jsonl" --seconds 330 --interval 1 &
OBSERVER=$!
# Read-only archives; copied notebook; no offline-improvement authorization.
set +e
/usr/bin/time -v -o "$RUN/time.txt" timeout --signal=TERM --kill-after=15s 315s \
  nice -n 10 "$PYTHON" main.py --offline --learning-state "$STATE" \
  --episode-root /home/five/Projects/charlie/robotron-runs \
  --learning-turns 4 --learning-budget 2 --learning-interval .05 \
  --learning-temperature-c 75 --learning-recovery-temperature-c 65 \
  --learning-thermal-stabilization 5 --learning-require-thermal \
  --learning-wall-seconds 300 --learning-cooldown-seconds 120 \
  > "$RUN/console.txt" 2>&1
RESULT=$?
set -e
printf '%s\n' "$RESULT" > "$RUN/exit-status.txt"
kill -TERM "$OBSERVER" 2>/dev/null || true
wait "$OBSERVER" || true
vcgencmd measure_temp > "$RUN/temperature-after.txt"
vcgencmd get_throttled > "$RUN/throttled-after.txt"
cp "$STATE/development-operational-status.json" "$RUN/final-operational-status.json"
"$PYTHON" tools/inspect_developmental_progress.py "$STATE" > "$RUN/after.json"
"$PYTHON" tools/validate_developmental_restart.py "$RUN/before.json" "$RUN/after.json" \
  > "$RUN/continuity.json"
```

The observer has an independent 330-second bound. Outer timeout exit 124 is a timeout, not normal completion; SIGKILL escalations do not prove clean shutdown. Archive/notebook imports remain original retained evidence, never new gameplay. Original paths in checkpoints are valid only while their hash-bound bytes remain available. A copy is not a new learning identity.

Native acceptance needs: code/environment provenance; timestamped incident sensor readings >=75°C; no expensive child activity while suspended; unchanged original evidence/documents and retained project/commission/candidate/checkpoint identities; measurements remaining <65°C for >=5s; recovery eligibility then resource-clear resumption under the same owner/commission; reheat/ownership/memory controls; responsive shutdown and restart continuity; and zero physical authority/controller activity. If no authentic thermal interruption occurs naturally during approved offline work, **native recovery remains NOT YET DEMONSTRATED**. Do not alter notebook flags or mock native readings to manufacture that observation. Existing blocked work may remain blocked after cooling; recovery does not supply missing evidence.

To investigate the historical hour-long duration after approval, run the existing `tools/profile_development.py --profile` with a fresh output and the same approved archive/budget, under an outer timeout. That utility starts a fresh notebook, so it does not reproduce the cost of the 3247-record retained notebook. For a retained-copy profile, replace the main command above with `"$PYTHON" -m cProfile -o "$RUN/retained.prof" main.py ...` using identical offline arguments; do not mix profiled/unprofiled timing claims. Retain timing, CPU/RSS/IO, source sizes, input inventory, console transitions and `.prof` output. Review cumulative cost in acquisition, source verification, SQLite projections, status and fsync. The historical incident has no contemporaneous profile; a later reproduction can identify current cost, not retroactively prove its cause.
