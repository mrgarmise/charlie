# ALA-2 interrupted-session recovery

Recovered from remote `b750a9f6dee7ebe1c3ba32ccbcad2ef9226735db` on
`feature/agency-first-self`, independently observed before cloning and before
publication. CAL-1 / `feature/active-vision` was neither checked out nor modified.
Physical authorization remains false. ALA-2 remains incomplete.

## Recovered state and evidence

The published history already contains LearningExecutive, Reflection,
MemoryGateway/MARM outbox, Evaluator, append-only evidence, meditation candidate
generation, independent evaluation, guarded offline/semantic deployment,
rollback and certified complete-game comparison admission. The lost
`learning.retrospective` command was absent; it has been restored around those
mechanisms. No winning strategy, new perception model or parallel learning
architecture was supplied.

Recovered `Charlie-ALA2-retrospective-20261003.tar.gz`: four episode journals,
177 main notebook records, evaluator, memories, question queue, reports and
frozen candidate artifacts. All 177 main-journal content IDs and its exact file
bytes survived copying and execution. Original published findings remain
unchanged. Original archives, including duplicate uploads, were retained.
Read-only verification covered 18 archived journal copies: 12 unique journal
files holding 122,510 records (these are records, not independent experiences).
Four distinct games contain captures, agency, commands and planning evidence.
Three contain saved meditation; the 015817 game has no saved meditation to import.
Archived retrospective links and tracker beliefs remain unverified.

| Game | Reported HUD value | SELF unknown / observations | Unique transports | Fire transports | Complete-game qualified |
|---|---:|---:|---:|---:|---|
| 003511 | 1,000 | 35 / 81 | 37 | 30 | No |
| 005944 | 1,200 | 239 / 380 | 123 | 96 | No |
| 012801 | 3,500 | 253 / 347 | 109 | 74 | No |
| 015817 | 3,300 | 244 / 365 | 115 | 86 | No |

These are preserved subsystem reports, not independently observed scores.
Historical user reports and estimates remain separate. No death was inferred
from SELF loss, and no physical effect was inferred from transport acceptance.

## Actual execution and learning outcomes

Restored command recovery against all four archives: **177 records, zero new
investigations**. Retry: **177 records, zero new investigations**. It verifies
relocated source manifests and exact saved meditation hashes before reuse.
Completed work was recovered rather than regenerated.

The preserved notebook has ten resolved investigations: seven question-recurrence
retrievals and three meditation-motion candidate investigations. The previous
session's eight new investigations are included in that total, not additional
work claimed for this recovery. Executive/Reflection questions cover ownership,
action effects, death observability, uncertainty, semantic coverage, startup
latency and score attribution. Four distinct episodes support recurrence of
reported gaps; they do not establish causes.

Charlie-originated tentative findings include uncertainty/reacquisition gating
as one explanation of inactivity, unverified semantic coverage as one limit on
rescue planning, and reader retention/error as one explanation of reported score
differences. Alternatives and provenance remain in the original notebook and
[published findings](ala-2-retrospective-findings.md).

Three saved meditations generated three bounded velocity-smoothing alternatives
each (0.35, 0.65, 0.85), retaining existing horizon and speed bounds. Nine frozen
context-specific artifacts are three parameter alternatives, not nine improved
capabilities. All three real candidate investigations remain **unresolved / not
eligible**: no independently verified trajectories, fresh sealed final evidence
or operational shadow qualification. Previously used train, validation and
consulted-final episodes remain used. No real deployment was authorized.

Executive now owns durable investigation bookmarks and commissions offline
dispatch only after selecting a project and validating the exact chooser plan.
Discovery supplies evidence; Reflection generates hypotheses; the Executive
prioritizes; existing capability execution evaluates and returns outcomes to
the Executive, Evaluator and memory. A dispatch interrupted before execution
resumes the same bookmark and prediction. No historical bookmark is backdated.

The first restored-command attempt missed legacy ingestion markers because
they were observations rather than events. It repeated six cheap retrieval
checks, not model final evaluations, and retained a separate 310-record notebook.
The corrected implementation searches both record kinds; regression coverage
prevents recurrence. Both that attempt and the untouched original are preserved.

## Independent validation

Host: x86_64, Python 3.12.14, NumPy 2.3.5, OpenCV 5.0.0, no Torch.

| Command | Actual result |
|---|---|
| `python -m pytest -q tests` on published checkpoint | 477 passed, 19 skipped; 33.77 s |
| `python -m pytest -q tests` on final implementation | 485 passed, 19 skipped; 34.85 s |
| Targeted recovery, meditation, diagnostics and Executive tests | 39 passed before final two regression additions |
| `python -m compileall -q learning memory/learning_projects.py` | Passed |
| `git diff --check` | Passed |
| `bash -n tools/update_existing_ala2_pi.sh` | Passed |
| `python -m learning.readiness --output ...` | Unarmed; score improvement not demonstrated; hardware gaps reported |

All 19 final skips require Torch. New recovery tests cover partial/torn logs,
source mutation, notebook copy identity, output separation, interrupted import,
Executive bookmark authority, dispatch interruption/retry, legacy markers and
active-gameplay refusal. Existing tests cover independent motion gates,
final-consumption interruption, clock changes, semantic admission, qualified
scores, offline activation and rollback. Controlled trajectories are software
fixtures, never physical Robotron evidence.

An initial unscoped `python -m pytest -q` failed collection on eight legacy
hardware/manual modules outside the supported `tests` directory (missing
MicroPython machine, serial, libcamera and conflicting behaviors import).
Those hardware entry points were not run. A targeted invocation using the
nonexistent filename `tests/test_robotron_comparison.py` ran no tests; the final
full `tests` run includes the actual score-comparison modules. No failed
collection is presented as a passing check.

## Safe reusable command and Pi handoff

On a software host, recover a saved unpacked notebook into a **new** output:

```bash
python -m learning.retrospective \
  --recover-notebook /path/to/charlie-retrospective \
  --output /path/to/new-recovered-notebook \
  --episode /path/to/development-20261002-003511/game-01 \
  --episode /path/to/development-20261002-005944/game-01 \
  --episode /path/to/development-20261002-012801/game-01 \
  --episode /path/to/development-20261002-015817/game-01
```

For later retries omit `--recover-notebook` and reuse that output. New archives
may be supplied with `--episode`; partial archives remain diagnostic. Output
inside an evidence tree is refused. Existing paths in old journal documents
remain historical; relocation is checked by hashes, not rewritten as history.
Concurrent retrospective/cycle workers are refused by the existing offline
lock. Candidate gates remain unchanged.

The existing `tools/update_existing_ala2_pi.sh` accepts the exact newly published
40-character SHA. It fast-forwards only the isolated existing ALA-2 checkout,
refuses tracked changes, runs the supported tests and writes unarmed readiness.
Do not update `/home/five/Projects/charlie` or run old worktree-creation scripts.
New ARM64 validation remains pending; host results do not replace it.

## Remaining acceptance

Independent physical identity/role/trajectory and score-reader qualification,
fresh segregated final evidence, candidate-specific ARM64 cadence, real
camera/controller ownership, reacquisition, terminal handling and rollback
remain pending. Existing complete-game protocol binds score and terminal capture
to qualified episode identity, preserves missing trials, freezes conditions and
policy, and prohibits tuning on final trials. These partial archives cannot
provide a verified complete-game baseline or demonstrate score improvement.

Only after separate physical authorization may qualified candidates enter live
operation and a frozen baseline/candidate complete-game score comparison run.
Survival, rescues, prediction and ownership remain diagnostics; SCORE is primary.
CAL-1 is not required for retrospective work and confers no movement permission.

## Linear-ready progress

- **CHA-5:** Recovered Executive, evidence and memory continuity; restored
  Executive-owned persistent investigation bookmarks and offline dispatch with
  interruption recovery. Original 177-record notebook preserved without repeats.
- **CHA-6:** Recovered four archived games and ten completed investigations.
  Three meditation-originated candidate sets remain blocked by independent
  evidence gates. Restored reusable retrospective command; 485 tests passed,
  19 Torch skips. No real policy qualified or activated.
- **CHA-7:** Complete-game score protocol and deployment/rollback safeguards
  verified in software. No independently qualified complete-game comparison or
  score improvement. ARM64/hardware validation and armed evaluation pending
  separate authorization. ALA-2 remains open.

These are prepared updates, not messages posted to Linear.
