# Best of Charlie 0.1.0 — software consolidation, native acceptance pending

GitHub `master` is the authoritative integrated **source**, not a claim about what runs on Charlie. The source manifest is `release/capabilities.json`. The immutable tag is `best-of-charlie-v0.1.0` after successful release CI. Obtain the exact source SHA using `git rev-parse HEAD`; obtain the tag SHA using `git rev-parse best-of-charlie-v0.1.0^{commit}`. Publication receipts are separate from historical feature reports.

This release brings the real application-owned ALA Executive, Robotron development, Active Vision/CAL-1, and offline score feedback together. It defaults to **offline** operation. Native performance, original October 10 feedback ingestion, natural thermal recovery and full ALA-2 acceptance remain outstanding. Source inclusion grants no physical authority. The governing charter and acceptance standard are retained at repository root from the supplied project attachments; their text governs every claim here.

## Release identities and controls

| Identity | Authoritative observation |
|---|---|
| Source | GitHub master commit and immutable release tag |
| Installed | `~/.local/share/charlie/releases/current/installed-release.json`; exact source commit and file hashes |
| Running | Local `/proc` executable, checkout, PID/start ticks; matching Executive startup receipt when available. A checkout SHA alone is not proof of its startup revision |
| Development | Independent `feature/*` branches; original branches remain preserved |
| Persistent state | Existing original `~/.local/share/charlie/development`, independent of all release directories |

Historical Pi checkout `/home/five/charlie-ala2-bae659f60b0e` at `6ba21fb9b56e492a85bf3b7fc2e9b5fb63ab9789` is the user-supplied last-known ALA installation. It is **not a verified current running identity**. The native host has not been accessible in this assignment. No service, native checkout, original notebook, firmware or policy has been changed.

Operator commands use the selected Python environment:

```bash
PYTHON=/path/to/verified/python
APP=/path/to/verified/charlie
"$PYTHON" "$APP/tools/charlie" status
"$PYTHON" "$APP/tools/charlie" readiness
"$PYTHON" "$APP/tools/charlie" worktrees --repo "$APP"
```

`python -m charlie_ops status` from the chosen checkout is equivalent. JSON includes actual dependency versions, local thermal readings, service command/unit paths, running processes, notebook identity anchor, checkpoint, Executive and operational state, capabilities, permissions not established, and divergence from the last fetched master ref. Arbitrary environment variables and command arguments are not dumped. Unknown values remain unknown. Status/readiness initialize neither a new notebook nor a hardware controller. Historical status files are retained observations, not proof that their PID is alive. Remote freshness requires `git fetch origin` separately.

## Integration decisions

The 184-commit ALA/Robotron lineage ending at `f4800705df74ca496073f5e783d1b250d1e9ff3a` was reviewed by history, runtime changes, provenance, dependency boundaries and regression tests. Its source diff from master has 1,023 paths, primarily preserved historical reports, fixtures, sprite knowledge, and the requested learning/Robotron capabilities. Existing master functionality is retained; there is no blanket merge of every branch. The separate Active Vision lineage was reconciled against its common ancestor `bae659f60b0e396999caa85b763ce0f1622bd540`. Firmware source is included disarmed; no firmware is installed.

| Capability | Selected source | Integration / acceptance |
|---|---|---|
| Memory, PPAL framework, sprite recognition | memory → PPAL → score-tracker ancestry | Included; authentic PPAL policy learning remains open |
| Causal SELF, reacquisition | agency-first-self `708a1f6` and later native camera history | Included; qualification and source identity boundaries retained |
| Camera optics, persistent camera session | autonomous-camera-calibration `6e927e2`, camera lifecycle `9eeba7c` | Included; fresh metadata and episode recorder preserved |
| Terminal transitions, fresh authorized restart | prompt-terminal-restart `9e423e9` plus native-terminal-forensics `8c001e7` | Included; recorded GAME OVER cue and positive transition required; high-score/attract pages alone grant no START |
| Executive, history recovery, independent priority | causal-acceptance `4bca038` | Included; complete learning acceptance not inferred |
| Thermal recovery | `1895bc7`, final `f480070` | Included in the same lifecycle, acquisition and supervised evaluation |
| Active Vision / CAL-1 / neck health | active-vision `c08a9a5` | Included; commissioning, electrical, profile and motion gates preserved |
| Human score review and bounded exemplars | score-feedback integration `721af8c`, report `b1d1ef1` | Selected paths integrated; no live activation, missing October 10 originals |
| Native terminal forensics and scheduled handoff | implementation `8c001e7`, branch report `ad613a9` | Included after clean compatibility merge and targeted regression; native acceptance remains outstanding |
| Alternate failed-discovery boundary recovery | persistent-agency-recovery `0aadb65`, marathon-boundary `6117531` | Deferred: conflicts with newer guarded terminal/SELF retirement; original branches preserved |
| Early PPAL vision focus | `591c732` | Superseded by later PPAL/Active Vision architecture; branch retained |

PR #1 is historical memory/PPAL work now represented by selected descendant history. PR #3 remains the original conditional score-feedback milestone, whose authentic feedback acceptance has not occurred. This consolidation incorporates its safe offline code while preserving that limitation; neither PR is silently treated as independently accepted.

Three Active Vision conflicts were reconciled explicitly. `ObservedCamera` retains both recording/fresh-frame identity and neck observations on the same frame. `play_robotron` retains recorder/watchdog finalization and adds neck service cleanup without repeating camera/controller closure. `main.py` retains the Executive child, restart supervision and thermal options while adding CAL-1 shared-frame handling, initial attention update, disabled-by-default mobile sidecar and `ExitStack` cleanup. Startup failures close resources before the Executive child is joined. Offline startup imports no controller or camera.

Score integration preserves newer original-session import receipts instead of replacing them with the older review branch's implementation. It adds bounded glyph extraction, exact-image relocation, human label import, numeric-string accuracy metrics and guarded review navigation. All candidates remain offline and unqualified. No evidence or commission identity is replaced.

## Architecture and learning claims

The Executive uses a durable append-only evidence journal, JSONL memory, SQLite Evaluator state and project/commission histories. It chooses investigations using objective/uncertainty/cost/risk plus independent retained resolved outcomes. Priority changes have historical offline causal controls; code presence or thermal resumption does not satisfy the whole E1 mission. Reflection commissions track reconstruction; Meditation keeps source-digested checkpoints. Failed/invalid results remain evidence dependencies, not completed work. Evaluator qualification and deployment require independent evidence and explicit target authority; rollback history remains separate.

PPAL contains distinct perception, semantic planning and tactical action interfaces. Tactical retained prediction feedback and qualified local policy adapters exist; do not describe them as SARSA/Q-learning without the corresponding selected code. Hand-coded fallback choices and changing observations are not evidence of learned action preferences. Score exemplars change digit recognition under explicit offline load; they do not alter the action policy or authorize gameplay.

| Mission gate | Consolidation result |
|---|---|
| E1 — Executive experience causally changes later decisions | NOT YET DEMONSTRATED for full original acceptance; historical offline controls retained, native forward investigation remains required |
| P1 — retained authentic gameplay causally changes later PPAL decisions | NOT YET DEMONSTRATED; candidate/software controls cannot replace native authentic causal comparison |
| I1 — independently qualified improvement changes PPAL through guarded integration | NOT YET DEMONSTRATED; no live policy activation authorized here |
| Complete-game Robotron comparison | NOT YET DEMONSTRATED; frozen independent complete games and authorized native execution required |
| October 10 score corrections | NOT RECOVERED here; original Pi review store must be examined |
| Natural native thermal suspension/resumption | NOT YET DEMONSTRATED; no manufactured heating permitted |

ALA-2 remains open. Historical positive results, failures and inconclusive observations remain individually identifiable in `docs/ppal/` and are not overwritten by this release label.

## Thermal integration

The existing ResourceGuard limits development to at most 75°C, strict `<65°C` for five continuous seconds, gameplay priority and memory clearance. Invalid/missing Pi telemetry latches conservative suspension. Threshold violations and gameplay interruptions reset continuous stabilization. Restart preserves the suspension but requires a fresh monotonic stabilization interval. Operational events are bounded and deduplicated in `development-operational-status.json`; they are not appended as learning observations.

The real `DevelopmentLifecycle.reflect_experience` executes existing track Meditation. Its progress callback checks the same guard during reconstruction and preserves commission/context/source identities and checkpoint. Source hashing now streams 1MiB chunks and probes resources between chunks instead of allocating/reading the entire tracks file unchecked. Acquisition uses the guard through its existing investigation interface. Experiment selection launches the existing offline evaluator worker through `progress_supervision.supervise`, with independent resource probes **before launch and every parent poll**, even if the child publishes no heartbeat. Preemption stops, escalates and reaps the worker before returning to cooldown. The normal application owns one Executive child and the notebook's existing kernel lock excludes another writer.

Short filesystem, JSON, SQLite and individual library calls remain cooperative boundaries rather than instantaneous hard preemption. Worker cleanup escalates through existing watchdog grace intervals. An uninterruptible kernel wait cannot be repaired in Python and must not be represented as successful recovery. The native hour-long run remains unexplained without contemporaneous timing/temperature data; thermal waiting alone has not been proven to account for its duration. Default bounded runs now have 300s wall and 120s cooldown deadlines, but a monolithic call may overrun a cooperative deadline until the next check.

The deterministic controls run real Meditation code over **engineering fixtures**, verify partial checkpoint/commission continuity under injected heat, hold-hot polling with no duplicate evidence, cool and resume the retained investigation, then restart and repeat. They are software controls, not authentic thermal observations or new learning evidence. A native thermal observation guide is `docs/ppal/thermal-recovery.md`.

## Persistent history and backup

The designated original active notebook remains `/home/five/.local/share/charlie/development`; its current native contents and ownership require operator verification. Original October 9 failures and the 3,247-record historical native continuity report are retained through existing handoffs. Robotron originals remain under `/home/five/Projects/charlie/robotron-runs`. Human review history is expected at `/home/five/.local/share/charlie/score-review/learning-evidence.sqlite3`; the October 10 exact rows, distinct image count, finalization and consumption cannot be asserted from a historical handoff mentioning 16 status/8 annotation records.

No notebook migration or blind merging is performed. A validation copy is never an alternative authoritative history. Backups refuse a held Executive lock or a referencing active process, copy SQLite through its backup API (including committed WAL data), preserve JSON/checkpoints and record artifact hashes, SQLite integrity and original evidence digests. Symlink evidence requires an explicit provenance plan. Backup retains the existing lock inode and never appends to the source. Cross-application review writers must also be stopped under separate approval for a consistent global snapshot.

```bash
STATE=/home/five/.local/share/charlie/development
BACKUP=/home/five/charlie-backups/development-$(date -u +%Y%m%dT%H%M%SZ)
# Only after approved clean shutdown of all notebook/review writers:
"$PYTHON" "$APP/tools/charlie" --state "$STATE" backup "$BACKUP"
"$PYTHON" "$APP/tools/charlie" verify-backup "$BACKUP"
```

There is no automatic restore or migration command. Restoration must use a separate reviewed identity/integrity plan while all writers are stopped. Preserve the original directory as rollback evidence; never overwrite it blindly.

## Release, deployment and rollback

Concurrent development uses `feature/<purpose>` branches from fetched master. Create temporary worktrees only for actual isolated execution; capture status, unpushed commits and evidence before retiring them. Changes reach master through a reviewed integration PR, scoped `tests/` regressions and relevant native gates. Included but unaccepted capabilities stay disabled. Each release increments both manifest version and tag. The software workflow tests the integration PR; after verified master publication, its tag job creates the tag without moving any existing tag. It never deploys.

Deployment below is an **operator procedure requiring separate Pi deployment approval**; it has not been executed on Charlie. Staging is application-only and creates no firmware change. State and release directories are separate. A managed symlink changes atomically under a release lock; any running process retains its old version until a separately approved restart. Reject tampered source and unexpected staged files. Keep the previous release as rollback, independently from state backups.

```bash
git -C "$APP" fetch origin --tags
REVISION=$(git -C "$APP" rev-parse best-of-charlie-v0.1.0^{commit})
RELEASE_ROOT=/home/five/.local/share/charlie/releases
"$PYTHON" "$APP/tools/charlie" --release-root "$RELEASE_ROOT" stage "$REVISION" --repo "$APP"
# Prepare a separate, persistent Python environment; do not write into release source:
python3 -m venv --system-site-packages /home/five/.local/share/charlie/environments/best-of-charlie-0.1.0
PYTHON=/home/five/.local/share/charlie/environments/best-of-charlie-0.1.0/bin/python
"$PYTHON" -m pip install -r "$RELEASE_ROOT/releases/$REVISION/requirements.txt"
"$PYTHON" -m pip check
# Only after approved application deployment, verified state backup and clean shutdown:
"$PYTHON" "$APP/tools/charlie" --release-root "$RELEASE_ROOT" deploy "$REVISION" --approved
"$PYTHON" "$APP/tools/charlie" --state "$STATE" --release-root "$RELEASE_ROOT" readiness
```

A reviewed systemd unit should use the immutable resolved release path and the explicit Python environment, `Environment=PYTHONDONTWRITEBYTECODE=1`, `ExecStart=<PYTHON> <RELEASE>/main.py --offline --learning-state <STATE> --episode-root <ARCHIVE> --learning-require-thermal`. Do not replace the current service or restart it during discovery. Capture `systemctl show charlie.service --property=ActiveState,SubState,MainPID,ExecStart,FragmentPath,DropInPaths` first. A systemd/template example is `release/charlie-offline.service.example`; installing it requires separate deployment approval. This is the same Executive, not a second scheduler. Confirm old writer exit before starting another.

```bash
# Pointer rollback only, after separate rollback approval:
"$PYTHON" "$APP/tools/charlie" --release-root "$RELEASE_ROOT" rollback --approved
"$PYTHON" "$APP/tools/charlie" --state "$STATE" --release-root "$RELEASE_ROOT" readiness
# Service stop/start is independently approved; no command here sends it automatically.
```

Changing code pointers does not restore or rewrite accumulated experience. If state schema compatibility fails, stop and review the original backup and migration plan. Do not start an older writer against incompatible newer state.

## Native inventory and acceptance handoff

First collect read-only observations, using an output directory outside originals:

```bash
OUT=/home/five/charlie-native-validation-$(date -u +%Y%m%dT%H%M%SZ)
mkdir "$OUT"
"$PYTHON" "$APP/tools/charlie" --state "$STATE" --release-root "$RELEASE_ROOT" status > "$OUT/status-before.json"
"$PYTHON" "$APP/tools/charlie" worktrees --repo /home/five/Projects/charlie > "$OUT/worktrees.json"
find /home/five -name .git -prune -print > "$OUT/checkouts.txt"
"$PYTHON" "$APP/tools/inspect_developmental_progress.py" "$STATE" > "$OUT/original-before.json"
vcgencmd measure_temp > "$OUT/temperature.txt"
vcgencmd get_throttled > "$OUT/throttled.txt"
```

For each discovered checkout, collect exact HEAD, remote refs, `git status --porcelain --untracked-files=all`, `git worktree list --porcelain`, and commits not reachable from fetched remotes. Associate each active PID with `/proc/<PID>/exe`, `/proc/<PID>/cwd`, unit paths and whitelisted configuration. Do not print secrets. Directory names do not establish duplication.

When native access is available, run the authorized bounded **offline software acceptance** from the prepared source, using a verified backup copy, no original writer and no hardware initialization. This requires no installed-pointer change or service restart:

```bash
COPY="$OUT/validation-state"
cp -a "$BACKUP" "$COPY"
"$PYTHON" "$APP/tools/inspect_developmental_progress.py" "$COPY" > "$OUT/before.json"
"$PYTHON" "$APP/tools/observe_development_thermal.py" --state "$COPY" --output "$OUT/thermal.jsonl" --seconds 360 --interval 1 &
OBSERVER_PID=$!
nice -n 10 "$PYTHON" "$APP/main.py" --offline --learning-state "$COPY" --episode-root /home/five/Projects/charlie/robotron-runs --learning-turns 4 --learning-budget 2 --learning-interval .05 --learning-require-thermal --learning-wall-seconds 300 --learning-cooldown-seconds 120 > "$OUT/executive.txt" 2>&1
wait "$OBSERVER_PID"
"$PYTHON" "$APP/tools/inspect_developmental_progress.py" "$COPY" > "$OUT/after.json"
"$PYTHON" "$APP/tools/validate_developmental_restart.py" "$OUT/before.json" "$OUT/after.json" > "$OUT/continuity.json"
"$PYTHON" "$APP/tools/charlie" --state "$COPY" status > "$OUT/status-after.json"
# Re-read original and independently compare IDs/digests to original-before.json:
"$PYTHON" "$APP/tools/inspect_developmental_progress.py" "$STATE" > "$OUT/original-after.json"
```

Repeat the bounded Executive invocation against the same copy for restart continuity. Record versions, dependencies, sensor samples, throttling, operational events, attempts/productive turns/polls, source hashes, commission and checkpoint identities and child processes before/during/after. Missing evidence remains blocked. Do not deliberately overheat or generate observations to force recovery. If no natural thermal interruption occurs, native suspension/resumption remains NOT YET DEMONSTRATED. Productive continuation requires actual eligible source evidence; polling cannot meet that criterion.

Recover score records using `docs/score-feedback/native-recovery.md` and `tools/recover_score_reviews.py`: original IDs/timestamps/image hashes, readable corrections versus confirmations, finalized/pending status and actual consumption receipts. Existing two authentic camera-derived JPEG score fixtures remain 2/2 correct before/after, with no authentic feedback applied; this is a regression result, not improvement or held-out generalization. Independent human labels and a held-out partition remain prerequisites for authentic learning metrics. Pi latency/RSS and complete-game score performance remain unmeasured here.

## Cleanup and outstanding work

`inventory-before.json` preserves remote branch SHAs and initial worktree status, including a locally modified camera fixture and unpublished local commits. `worktrees-after.json` reports actual local inventory after consolidation. Original verification directories contain unique historical execution/evidence dependencies; no directory has been retired merely because its Git tree resembles a remote commit. **No historical cleanup is eligible without additional provenance/process/rollback verification.** No deletion, reset, pruning or garbage collection was performed. New temporary verification worktrees can be removed only after their clean tree is published, evidence is archived and no process references them. Feature branches continue independently.

Outstanding: native installed/running/service/environment inventory; original global backup verification; actual thermal and productive continuation; original October 10 labels and authentic before/after recognition; held-out and native performance; older alternative SELF/boundary branch reconciliation; optional Torch worker tests; physical readiness; and complete ALA-2 causal gates. The release is a software-tested integration, **not production-ready native acceptance**.

## Final software validation

The final committed runtime tree `d0db0c82c40bcb0204b05975ae3de97d3578f97a` (published implementation `b4cef5196209e2ddcc5f25d8b242d5579848c551`) passed **1,229 tests, 21 skipped, zero failures in 296.66 seconds** on Linux x86_64 / Python 3.12.14. The explicit scope is `tests/`; hardware diagnostic scripts outside that directory are not collected. Nineteen skipped cases require optional Torch and two require unavailable original archive inputs; exact reasons and JUnit output are preserved under `validation/`. One JUnit property-format warning is observational metadata only. `pip check` reports no dependency conflicts; `git diff --check` passes. The host dependency list records the exact tested versions. No native Pi test is represented as a pass.

Focused interactions passed 80 checks, final operator/thermal changes 40, and final operation-specific checks 11. The real unresponsive offline worker test verifies heat-triggered escalation and reap without a heartbeat. Two previously failing legacy test assumptions were repaired without relaxing safety and passed their four relevant checks. The restored historical notebook's nine-file isolated backup passed artifact hashes, SQLite integrity and append-only record digests; its source remains intact. This does not verify the current Pi original notebook or its current record count.

The exact published thermal source and consolidated implementation were also staged into isolated local immutable release directories, hash-verified, switched through the atomic `current`/`previous` pointers and rolled back successfully. `release-rehearsal.json` records both commit identities and the successful rollback to `f480070`; no service was restarted and no notebook changed. This validates local operator mechanics, not deployment to Charlie or native compatibility of any unexamined state.

The first GitHub runs exposed CI's default shallow checkout: the rollback safety test could not read preserved revision `8777955:rp2040/servos.py`. Local full-history tests passed. The software checkout now fetches complete history, retaining the mandatory rollback test rather than skipping it. Historical source regression tests belong in a full-history checkout; immutable installed release directories are validated by their manifests and the operator/native acceptance commands. The failed CI attempts remain inspectable in GitHub run history.

## Additional terminal integration and operator bootstrap

The native terminal implementation `8c001e7` has parent `9e423e9`; comparison established that it extends the selected terminal code rather than replacing the current ALA. It merged cleanly with the reconciled Active Vision recorder/neck lifecycle. It adds a fixed provenance-bound GAME OVER anchor, diagnostic rejection reasons, fresh supported terminal transitions and an eligible three-game learning handoff. Authentic recorded features are replayed as historical diagnostics, never new independent observations. Targeted and full final checks are reported in GitHub CI; no physical replay/gameplay is performed. The older SELF/boundary branches remain deferred because they conflict with the selected newer retirement and terminal safety behavior.

If the old Pi checkout does not contain the new operator tool, do not switch or update a running checkout in place. After repository fetch, create one **temporary release preparation** worktree at the exact verified release SHA and use its tools. This is isolation for release preparation, not a permanent application checkout per feature. Keep it until deployment/rollback and artifact ownership are verified. The rollback readiness command deliberately uses the retained preparation tool: historical rollback releases may not contain `tools/charlie`.

```bash
REPO=/path/to/existing/charlie-git-repository
git -C "$REPO" fetch origin --tags
REVISION=$(git -C "$REPO" rev-parse best-of-charlie-v0.1.0^{commit})
APP=/home/five/charlie-release-preparation-$REVISION
git -C "$REPO" worktree add --detach "$APP" "$REVISION"
# Continue the staged deployment procedure using this APP and explicit PYTHON.
```

A more precise PPAL audit: Forebrain's rescue/survive fallback and exploration counts are fixed rules/session-local bookkeeping. Hindbrain keeps at most eight signed-response outcomes per action and thirty-two action keys, revising contradicted tactics only for fresh, same-identity completed response windows; identity changes clear those session-local statistics. Its action-history logic is not a persisted SARSA/Q learner. Diary records retain those outcomes, while persistent later decision values require the separate qualified-policy loading pathway and independent runtime/evaluation authority. The optional shot model is a fitted logistic predictor over synthetic shot examples; synthetic success is not authentic PPAL acceptance. MemoryEvaluator separately retains helpful/harmful weighted evidence in SQLite and uses posterior `(1+helpful)/(2+helpful+harmful)` for memory usefulness; that is not a Robotron score reward or an automatically activated policy. Executive priority uses independently grouped retained resolutions to reduce remaining uncertainty as `uncertainty/(1+independent_units)` in its existing objective/value/cost/risk calculation. Thermal telemetry and process status update none of those learning states.

The final terminal cross-feature checks passed **159 tests**. A controlled read-only replay used the same 65 archived October 11 camera observations and source identity with the frozen `9e423e9` classifier versus the integrated recognizer. The baseline found no terminal transition; the integrated reader found a supported transition at capture time `15840.790938`. Both reports explicitly deny physical/START authorization. Exact compressed traces, source hashes and control summary are retained under `validation/terminal-*`. This is a historical recognition-code repair on the recorded scene, not learning or unseen-scene generalization.

After terminal integration, the final available local regression passed **1,251 tests, 21 skipped, zero failures in 303.74 seconds**, against published source `2930086581f7155b87f47413e081255d4927bf5e` / tree `6faa9d418124fc7ca464c21c126f0928fcf8a609`. The earlier 1,229-test receipt remains historical evidence for the preceding core tree; the final full receipt is `validation/final-results.json` and `final-terminal-full.*`. Subsequent report-only commits do not change the tested application code. Native status and ALA acceptance remain unchanged: outstanding.
