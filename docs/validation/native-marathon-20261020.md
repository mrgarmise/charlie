# Native marathon reconciliation — October 20, 2026

## Decision

Software corrections and device-free native qualification are recorded below. Live
marathon readiness is **NOT YET DEMONSTRATED**. No complete game, transition,
score improvement, physical controller action or new learning investigation was
performed in this audit. The target remains three complete games, offline
meditation, then three complete games. A timed partial run cannot count.

Both `ALA_LEARNING_CHARTER.md` and `ALA2_ACCEPTANCE_STANDARD.md` were read before
implementation. Operational reliability, retained learning and performance are
separate claims. Existing architectures and physical authorization gates remain.

## Native identity and preservation

Actual platform: Raspberry Pi 5 Model B Rev 1.0, ARM64 Linux
6.18.50+rpt-rpi-2712, Python 3.13.5, OpenCV 4.10.0. Interpreter:
`/home/five/Projects/charlie/.venv/bin/python`. This sandbox exposes no
`/dev/video*`, `/dev/media*`, `/dev/ttyACM*` or Hailo device nodes. Its PID namespace
starts at `codex-linux-sandbox`; host process/camera ownership and service
activation cannot be established from its process list. There is no basis for
calling any checkout the currently running hardware process.

| Checkout / role | Starting SHA | Branch | Ending status |
| --- | --- | --- | --- |
| `/home/five/Projects/charlie`, original main checkout | bb40d02d3a128706e204cfd8e636fb1a9c5fd21b | feature/agency-first-self | Untouched; untracked head2_sessions/ and robotron-evidence/ preserved |
| Last October 17 gameplay worktree, charlie-fast-self-validation | 73169db9ad2648ca7e4088979d22905900052c6a | fix/pr5-spawn-prior-serialization | Untouched, clean |
| Current local PR #8, charlie-score-sampler | d45cce134e10d342f64a4d33f8baf9fcc1a41b01 | feature/hailo-score-reader | Untouched, clean; matches remote at initial inspection |
| Native PR #7 recovery, charlie-ala2-recovery-20261019 | 365bc84ca7f2b02cde94a3f604b2f957bb66a6f9 | recovery/ala2-20261019 | Untouched, clean; remote PR head is 83112b4b9d20f97178a6494f09f48713d4210344 |
| Camera lifecycle worktree | 9eeba7ca2ed69a412ab39b7f03c292842103edc6 | native-camera-lifecycle-validation | Untouched |
| Native restart worktree | a785c9f745bd0645dd01ac70af3beb5a8d44d37b | feature/native-marathon-restart | Untouched |
| Progress watchdog worktree | 3723132e0a7643d24b7670c202aba0f4a1acee12 | detached | Untouched |
| Terminal restart worktree | 9e423e982a2f9b9a244c7126543fb4b04debb465 | detached | Untouched |
| Active vision checkout | 87779558b78aeb5b36d4c3bc1eceed7831201e95 | feature/active-vision | Untouched; untracked recovery/ preserved |

Development occurs only in `/home/five/charlie-marathon-audit-20261020` on
`recovery/native-marathon-20261020`. Git SSH initially failed on system-config
permissions; bypassing that config still failed DNS. The GitHub connector
provided PR metadata and all 40 text patches for PR #5 head
`8c96db003b87246ee6b0f9dc9918cb42af726370`, based on
`d74d7a620c39104ce58fb2c9551381543a66b5f2`. All 16 published tested-source
hashes matched the reconstructed baseline. Six original raw images were copied
from the preserved October 17 game and matched its published manifest exactly.
Compressed historical test logs and baseline JSONL/report summaries were not
reconstructed. Local baseline commit `b197bb9` is explicitly a reconstruction,
not the remote commit. Only reviewed delta files are eligible for publication
on top of the exact remote PR #5 head with an expected-head lease.

Original notebook SHA-256:
`7c942b2a5977142ba093bfe2b2238d8d37573438e55b9c8cab5f566bb44ae6ae`.
A separate byte copy passed SQLite `integrity_check` and `EvidenceJournal.verify`:
3,247 records, no new records. No original notebook, archive, recovery-source Git
metadata, score review or operational source file was written. The shared Git
repository gained the isolated worktree, reconstruction commit and recovery ref;
ordinary destination Git index caches may refresh during status checks. The older
migration source-index preservation exception remains unresolved; this work does
not claim to repair or erase it.

Local receipts: `/home/five/charlie-marathon-audit-evidence-20261020/`.
Tests use a read-only code/library bind, disposable home/state, synthetic devices
and a private PID namespace. Repository-root legacy hardware tests are excluded;
the full eligible suite is `pytest tests`.

## Feature reconciliation

"Present" below means code exists in that checkout; it does not imply activation
or physical qualification. Native fixtures exercise software with fake devices.

| Capability | Implemented / historical origin | Tested | Installed / activated | Qualified / missing |
| --- | --- | --- | --- | --- |
| One camera session over games, release before reflection | 9eeba7c; retained in PR #5 base and #8 | Native lifecycle fixtures | Present in 73169db/#8; absent original bb40 camera_session module; running identity unknown | Live Game 1→2→3 pending |
| Continuous bounded producer and pinned FIRE observations | PR #5 8c96db0 | Native stream/overflow/cancellation fixtures | Present only audit reconstruction among inspected operational checkouts; absent 73169db and #8 | Camera delivery/ownership/focus and live causal timing pending |
| Batched perception, cheap supported-SELF screen path, bounded controller overlap | PR #5 8c96db0 | Native archived CPU benchmark and fixtures | Not deployed by this audit | Sustained meaningful 8–12/s pending |
| Terminal/postgame/title sequence and attract rejection | 9e423e9 and later guarded integration | Fake playable-game and attract sequence tests | Retained in PR #5/#8 code; activation unknown | Authentic terminal/restart confirmation pending |
| Bounded reacquisition / neutral-only brief occlusion | Existing agency plus PR #5 | Native agency/stream tests | New stream behavior absent last gameplay checkout | Demonstration-player discrimination and SELF recovery pending |
| Completed-work watchdog and interrupted handoff | 3723132 and later base | Native progress/campaign tests | Present PR #5/#8; no service activated | Long native processing and interruption qualification pending |
| Durable game boundary, source seal, no restart on uncertain evidence | Lifecycle/restart integration; game_evidence | Native journal and lifecycle fixtures | PR #5/#8 present; original bb40 lacks game_evidence module | Authentic completion and clean interruption pending |
| Offline thermal suspension/resumption | Existing learning/resources and worker; f480070 history | Native thermal fixtures | Existing PR #5/#8 code; worker not activated | Gameplay thermal controller is not proved by offline-worker controls; live continuous resource monitoring required |
| Score proposal worker, original raw evidence, review/export | Existing fixed reader and PR #8 | Separate PR #8 historical native/host receipts | Local #8 current; no model activation here | Authentic trained-model benefit, independent final score and attribution pending |
| Executive recurrence learning / retained tactical diagnostics | PR #7 native recovery | Preserved causal controls and fresh-process diagnostic replay | Isolated recovery state; not operationally deployed | Ledger supported by explicit Hindbrain interface; ordinary player does not pass retained tactical_memory; I1 pending |
| Category projection/index optimization and immutable import retry repair | PR #7 74e740f / 993f635 | Preserved native equivalence/receipt controls | PR #7 recovery only; not broadly transplanted into PR #5/#8 | Useful offline throughput work remains a coordinated integration item; original read-only journal must not be migrated |
| Startup prior integer-key serialization | Pi 73169db, incorporated in PR #5/#7 | Durable journal regression | Preserved, not duplicated | No evidence reset required |

No historical recovery branch was merged wholesale. No implementation is marked
obsolete merely because its newer integration exists; old branches and failed
runs remain rollback/provenance evidence. PR #8 is a separate master-based score
branch: it intentionally does not yet supply PR #5's streaming gameplay engine.
Score architecture/concurrent Work commits were not overwritten. Before eventual
cross-branch integration, reconcile observation_camera/score_observer interfaces,
single camera/resource ownership, shutdown and saved-frame scoring together.

## Established defects and repairs

1. `PiCameraSource._stream_capture` accepted `lens_position=NaN`: its absolute
   difference comparison was false. Require a finite non-boolean numeric lens
   before accepting existing manual 2.0 ± .05 / Idle criteria. Invalid metadata
   now fails closed; confidence/qualification thresholds are unchanged.
2. `CycleMetrics.decision` admitted the same exposure timestamp under another
   observation ID, a reordered recent exposure, and boolean timestamps. Require
   finite non-boolean numbers and strictly increasing accepted exposure time.
   These cases cannot inflate meaningful-update evidence anymore. This changes
   measurement, not tactical selection or learning.

Before fixes: targeted controls **3 failed, 4 passed**. After fixes: focused
native suite **165 passed**, one existing JUnit-format warning, 88.35 seconds.
Full native suite: **1,294 passed, 34 failed, 24 skipped**, 669.70 seconds.
Every failure occurs at sandbox-denied TCP/HTTP socket creation (`EPERM`), before
the application behavior can be tested. An independent bare-socket diagnostic
reproduced the denial. These remain failures requiring an ordinary-terminal
rerun, not passes. The qualification receipt lists every failed/skipped test and
reason; compressed full/focused/pre-fix logs and the hardware-free launcher are
retained alongside it. One existing warning concerns JUnit property formatting.
The 24 skips comprise 19 Torch-related cases (including a module collection
skip), three Node/browser cases and two original-archive acceptance cases.
See [exact qualification and skip/failure list](native-marathon-20261020/qualification.json)
and [frozen tested source hashes](native-marathon-20261020/tested-source.json).
No confidence gate, control lease, controller budget, restart permission or
learned-policy authorization was relaxed.

Installed Picamera2 0.3.37 source confirms numeric `capture_request(wait=...)`
timeouts and explicit request release support. The current exposure-start
calculation subtracts ExposureTime from SensorTimestamp, consistent with the
[Raspberry Pi Picamera2 manual](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf).
This API/source check is unarmed; it does not measure camera/display latency.

## Measured performance and authentic negative result

Native saved-pixel CPU benchmark, six hash-matched October 17 playfields, four
passes (24 samples/stage), BLAS/OMP thread limits 1. These are paired existing
legacy/new paths in the recovered PR #5 implementation, not a new live run.

| Stage | Native median | Native p95 |
| --- | --- | --- |
| Full terminal classifier | 210.59 ms | 216.53 ms |
| Hypothetical supported-SELF screen | 2.26 ms | 2.49 ms |
| Legacy region/template classification | 77.48 ms | 80.01 ms |
| Batched detection/classification | 69.40 ms | 71.23 ms |
| Class-free detection | 22.72 ms | 23.70 ms |
| Tracking/belief | 2.32 ms | 4.13 ms |

Batching reduced paired median cost about 10.4%; supported-SELF screen scheduling
avoided about 208 ms of terminal investigation in its hypothetical context.
The benchmark's `native:false` means no live native camera path was exercised;
execution platform was the actual Pi. It explicitly supplies hypothetical SELF
and tactical inputs. It cannot establish actual SELF, fresh observation rate,
camera latency, controller/display delay or complete-game benefit. No speed gain
is attributed to the two validation fixes.

The bounded accessible archive inventory found 16 game reports: four observation
uncertainties, three time limits, four reports claiming GAME OVER, one sensory
deadline refusal, two refused STARTs and two geometry refusals. These are report
classifications, not 16 independent games or four independently qualified ends.
The claimed ends retain legacy rules and unresolved attribution; they do not
establish three consecutive qualified native games. Inventory paths/results are
preserved in `archive-report-inventory.json` outside Git.

The October 11 `development-20261011-192041` session did attempt Game 2 after a
reported Game 1 end: Game 1 returned 0, but Game 2 returned 1 with
`sensory preflight deadline; assistance required`, and the session ended
`unverified_episode_boundary`. The later camera-lifecycle session
`development-20261011-203343` retains `status: running` with one recorded game;
it is not retroactively marked complete. Thus a historical restart attempt is
established, but a reliable completed Game 2 and Game 3 are not.

Preserved `development-20261017-200109` at 73169db remains a failure: 37 agency
observations, median delivery about 1.656/s against 14.902/s sensor cadence, no
confirmed SELF, zero accepted shot votes, zero tactical actions and no confirmed
game-over. Its campaign stopped after one unverified attempt, qualified=0. Reader
100 versus operator-reported 1,500 remains unresolved; neither is independent
complete-game truth. No reliable Game 1→2 or Game 2→3 is established by that run.
Initial sampled temperature was 49.6°C; later test samples were 54–57.3°C. These
isolated samples do not certify sustained thermal/throttling or RSS stability.

## ALA-2 evidence status

Preserve the PR #7 native report and `/home/five/ala2-recovery-20261019` intact.
Historical Executive evidence records the same 19 alternatives, actual evaluation
2.0→1.5 after authentic recurrence evidence, fresh-process reload 1.5, scoped
ablation 2.0, unchanged winner. **E1: scoped prior PASS retained**, not newly
earned here or generalized to score-error explanation.

PR #7 retains 99 linked historical tactical windows from six capture origins;
96 numeric valuations and 84 diagnostic preferences change in controlled replay,
while all returned actions remain unchanged. **P1: scoped retrospective diagnostic
PASS retained**; independent physical identity, prospective generalization and
score benefit remain open. The persistent ledger is accepted by the explicit
`Hindbrain(..., tactical_memory=...)` interface; ordinary player construction does
not supply it. No inference of actual deployed gameplay influence is justified.

Two new fresh OS-process invocations of the existing native replay CLI, using
the unchanged six source journals bound read-only and a byte copy of the strict
retained ledger, reproduced **96 valuation changes / 84 preference changes**.
Their complete JSON outputs matched byte for byte. There were 99 contexts,
zero physical actions and no policy activation. The strict ledger content digest
is `5958d82228acdf7aeca44b15ab3f06d10c06b06ef191d1a0851e815002571da3`.
These replays verify retained diagnostic usability/reload; they are not new
experience, new investigations, held-out tests or additional complete games.

**I1: NOT YET DEMONSTRATED.** No independently qualified candidate went through
authorized physical deployment and downstream influence here. No original
October 9 acceptance, frozen complete-game performance comparison, original Mint
image comparison, or overall ALA-2 closure is claimed. Offline meditation receipts
and archival replays are not new games or independent experience.

## Acceptance procedure — execution requires separate operator authorization

First use an ordinary Pi terminal to identify actual processes, service units,
interpreter and `/proc/<pid>/cwd`, and confirm exclusive camera/controller ownership.
Do not stop an unidentified owner automatically. Check framing, stable detail,
manual focus and current geometry through existing preflight; no saved profile
substitution. Confirm the physical stop/neutral mechanism and operator supervision.
Freeze exact source and interpreter; preserve original journals and any SQLite
sidecars with a quiesced backup. Do not use the reconstructed local baseline as
an exact copy of the remote commit.

After publication, fetch the exact published PR #5 correction into a new clean
worktree. The qualification receipt supplies the exact remote SHA. Below,
`TRIAL_SHA` must be set to that SHA, not a moving branch name. Commands are
**prepared only**, never executed by this audit:

```bash
git -C /home/five/Projects/charlie fetch origin feature/fast-projectile-self
git -C /home/five/Projects/charlie worktree add --detach /home/five/charlie-marathon-trial "$TRIAL_SHA"
cd /home/five/charlie-marathon-trial
PYTHON=/home/five/Projects/charlie/.venv/bin/python
test "$(git rev-parse HEAD)" = "$TRIAL_SHA"
test -z "$(git status --porcelain)"
# Camera-only diagnostic, after exclusive ownership is established:
"$PYTHON" -m experiments.ppal.acquisition_profile --native-camera --seconds 10 --output /home/five/charlie-trial-camera-20261020.json
# These commands prepare, then separately arm physical gameplay:
"$PYTHON" -m learning.campaign prepare /home/five/charlie-campaigns/marathon-trial-a --notebook /home/five/.local/share/charlie/development --games 3
"$PYTHON" -m learning.campaign arm /home/five/charlie-campaigns/marathon-trial-a --hours 1
"$PYTHON" -m learning.campaign run /home/five/charlie-campaigns/marathon-trial-a --arm
```

No timed `--game-seconds`, projectile SELF opt-in, learned policy, semantic-model
selector, servo command, firmware change or deployment authority is included.
Existing campaign runs close the camera and checkpoint offline reflection/
meditation before completing. Review the first block's real session and independent
recordings with existing `learning.campaign.qualify_session(session_path)`, plus
operator observation; do not promote fixtures or score-only results. Require
reflection phase `checkpointed` and qualified three-game lifecycle evidence before
authorizing the second block. Then repeat the prepare/arm/run commands with
`marathon-trial-b` and `--games 3`, under a fresh explicit operator authorization.
This preserves the existing expansion gate instead of granting six games now.

For each of six distinct authentic game identities require: independently confirmed
complete game; fresh acknowledged START and playable commencement; separately fresh
game-over and restart permission; meaningful observations/s with supported SELF;
loss/recovery intervals; executed tactical commands and transport/release acknowledgments;
score originals and independent channel/SELF attribution; full recording seals and
durable journal chain; same intended session ownership; temperatures/throttling,
RSS and queue bounds throughout. Suspend/abort on invalid geometry, focus, stale
exposures, unsupported SELF, command/ack/release failure, critical overflow, evidence
failure or unsafe resource state. Never convert loss/timeout into GAME OVER.

Measure offline meditation's distinct inputs, retained outputs and restart/reload.
Any downstream learning claim needs frozen-context controls and independent
qualification. This trial grants no policy activation. Final-temperature-only
telemetry and offline thermal-control unit tests cannot certify live thermal behavior.

To revoke the campaign from a second terminal:

```bash
cd /home/five/charlie-marathon-trial
/home/five/Projects/charlie/.venv/bin/python -m learning.campaign disarm /home/five/charlie-campaigns/marathon-trial-a
```

Use the physical stop/neutral mechanism immediately for urgent hardware risk;
software revocation is cooperative. Preserve interrupted state and reports; never
automatically retry a `playing`/blocked campaign or send another START.

## Rollback and unresolved risks

No installation was replaced, so current rollback requires no operational action.
Leave all original worktrees/notebooks intact. For a future authorized installation,
stop/reap the identified owner, verify neutral release, preserve new evidence and
select an independent checkout of prior PR #5 SHA 8c96db0 or preserved native
73169db. Do not reset/clean shared worktrees, delete partial sessions, restore an
older notebook over new evidence or force-push a concurrent branch. Any gameplay
on the rollback version still requires its own authorization.

Remaining blockers: host process/device access, verified native installation and
exclusive ownership; live continuous capture/focus/framing; reliable SELF and attract
rejection; native command/display attribution; genuine game transitions; sustained
thermal/resource telemetry; independent scores; original-state ALA acceptance;
PR #5/#8 joint integration; and qualified I1 downstream influence. Passing these
software tests is readiness evidence for further inspection, not hardware readiness.
