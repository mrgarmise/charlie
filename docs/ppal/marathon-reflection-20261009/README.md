# Gameplay-first developmental marathon

Parent: independently fetched `feature/agency-first-self` at `f422718a79e08225a170ecac5d4671c4f4095e74`. This extends the existing marathon, episode adapter, normal lifecycle and Learning Executive. No second gameplay app, planner, evidence owner, meditation manager or agenda scheduler.

## Preserved native interruption (operator-supplied)

`robotron-runs/development-20261009-024021` was interrupted during autonomous learning between games. Operator reported GAME OVER confirmation, observed 1,100 points, effective early movement/shooting, later SELF uncertainty, prolonged neutral control, and little apparent deliberate family rescue. These are operator observations for investigation, not independently qualified complete-game score or causal strategy findings.

Operator SQLite integrity checks: experiment commitments 4 records; original session 1,503; correlated retrospective replay 12,066; processed episode journal 13,752. The archive/databases were not supplied to this host or located by the Library search. Counts and intact native state have **not** been reverified here, reconstructed from summaries, edited or discarded. New offline recovery reads original captures/session.json and resumes the existing sibling game evidence directory. Preserve the native run, commitments, processing-config/chunk/progress files and all notebooks before native update. Do not delete an output directory to retry. Native incomplete capture seals remain the capture owner's recovery responsibility; reflection will block rather than invent writer completion.

## Ownership and execution

`--developmental --learning-projects --play-first` records each game path and prospective experiment before starting the existing player. It retains normal preflight, SELF acquisition, controller restrictions, resource/no-progress supervision, independently sealed recording receipt and evidenced terminal-screen gate. It performs **no** retrospective import, replay, direct meditation or autonomous learning between games (including a requested seed, which is deferred). Existing evaluated prior memories/Executive projects can supply bounded precommitted experiments; they are not new developer strategies. Outcomes remain in original recordings for subsequent resolution. An interrupt bookmarks the attempted game and retains unresolved commitments; it never preemptively resolves them before offline evidence is available.

A kernel resource claim spans the whole gameplay phase, including idle gaps between player children. The existing ResourceGuard makes normal background development yield. A crashed process releases the claim automatically; it is resource ownership, not physical authorization. Required evidence-writer completion and game-over confirmation still control any next START. Failure/uncertainty stops the series; requested game count is not permission to bypass those gates. No diagnostic duration is added by the new mode. An unconfirmed final game is explicitly uncertain, not marathon completion.

After the series stops, the same module releases primary resources and resumes existing supervised evidence processing. `reflection-progress.json` records capture/content/manifests, per-episode completion hashes, uncertainty and durable yields separately from original `session.json`. The importer resolves live commitments before replay. Hash-bound atomic 100-unit cursors allow large JSONL/report-step imports to skip committed prefixes. Cursors are bookkeeping, not progress findings or independent experiences. Failures within a chunk roll back its observations and cursor together. Original session journal records retain their IDs/timestamps; correlated replay remains replay. Prior JSON/Markdown processing artifacts (including interrupted configurations/reports) are preserved by their exact content hashes under sibling `processing-history` before replacement. A completed authentic meditation artifact is retained and checked against its exact tracks source; it is not recomputed or discarded by the deferred importer.

The deferred importer leaves deeper meditation to **normal LearningExecutive.develop()**, through existing DevelopmentLifecycle. Exact project history is consolidated into the existing normal notebook. A hash-bound acquisition handoff supplies episode locations and retained project IDs. If the normal app already owns the notebook, the marathon returns `executive_owned` and that owner consumes the handoff on its next eligible turn; a competing Executive is never started. Otherwise the existing normal lifecycle performs bounded `--reflection-turns` (default 12), preserving commissions/checkpoints/findings/requests and physical authorization FALSE. `checkpointed` means a bounded phase completed, **not** that every investigation or evaluation is finished. Candidate evaluation/readiness/authorization/rollback remain unchanged. No deployment authority is passed to this handoff.

The existing offline recovery rule is narrowed to actual offline trial histories: a retained physical actuator outcome must not be paused as an interrupted offline experiment or looked up in an unrelated offline source journal.

## Commands

For a **separately authorized physical arcade session only** (not executed or authorized by this Work session), from the checked-out repository and existing Python environment:

```bash
python -m experiments.ppal.marathon_robotron --developmental --learning-projects --play-first --max-games 3 --focus 1.30 --retry-wait 5 --learning-root "$HOME/.local/share/charlie/development" --reflection-turns 12 --ala-budget 10 --arm
```

This automatically enters reflection after the safe gameplay phase; no separate meditation app is required. Use the actual existing normal notebook path if it differs. Prior accepted optical settings remain session-specific; this does not certify focus 1.30 universally. Existing physical readiness/authority gates remain mandatory.

Offline reflection/resume, with **no --arm, camera or controller**:

```bash
python -m experiments.ppal.marathon_robotron --reflect-session robotron-runs/development-20261009-024021 --learning-root "$HOME/.local/share/charlie/development" --reflection-turns 12 --ala-budget 10 --processing-budget 300
```

For a new marathon substitute its exact printed session directory. A productive import yield returns exit 75; run the identical offline command later to resume its cursor. State must stay in the same learning-root/project notebook once a reflection receipt exists. Existing normal app can continue the handed-off Executive work indefinitely under its resource limits. Observe session `reflection-progress.json` and notebook `development-status.json`. Missing sources/seals or corrupted completion receipts block explicitly. No qualified work remaining may legitimately wait for evidence/authorization.

## Host validation / limitations

Focused qualification of the final source: **93 passed, 6 skipped in 15.91s** (marathon, import, live commitment feedback, projects, supervision, normal lifecycle, resource guards and offline cycle). Final full qualification of the unchanged implementation source: **721 passed, 21 skipped in 187.84s**, exit 0. `qualification.json` binds tested source blobs to implementation commit `95b27870d0637240b511cc7362ea73886f86190d`; complete console/JUnit records are retained losslessly. Compilation and git diff checks passed.

Tests run **controllerless simulated games**, real supervised offline subprocesses, normal Executive turns, occupied-notebook handoff, three independent episode identities and commitment/result dedup, uncertain/missing-report/time-out stops, interrupt bookmarking, rollback within an import chunk, multi-restart 550-observation import, original-history retention, completion receipt rejection, and primary resource release. Authentic October 1 BODY/FIRE extracts supply existing Reflection-generated diagnostic proposals; subsequent games/outcomes are simulated, not physical confirmation or learned SCORE success. No strategy/score improvement is claimed.

Host: x86_64 Python 3.12, isolated pytest/NumPy/Pillow/OpenCV/pyserial dependencies. Native Pi acceptance of this change and resume against the actual 024021 databases remain outstanding. Focused/full-suite transcripts and JUnit evidence accompany qualification. ALA-2 remains open until Charlie-originated learning improves independently verified mean complete-game Robotron SCORE.

## Guarded native software qualification

After the normal evidence-preserving checkout/update of the exact final published checkpoint, use the existing Pi Python environment from the repository directory (no --arm):

```bash
python -m pytest tests/test_marathon_deferred.py tests/test_marathon_robotron.py tests/test_episode_evidence.py tests/test_experiment_return.py tests/test_learning_projects.py tests/test_progress_supervision.py tests/test_normal_learning_lifecycle.py tests/test_development_resources.py tests/test_ala_cycle.py -q
```

Then the offline `--reflect-session` command above may resume the retained native episode. Keep original integrity reports and capture directories intact; preserve a consistent backup of databases before update/resume. Check `reflection-progress.json` source bindings and completion receipts, raw recording seal, unchanged original capture hashes, journal integrity and record-ID continuity. Growing processed journals or advancing retained checkpoints are legitimate; exact record-count equality is not a success condition. No extra independent experience may be inferred from replay counts. Missing qualification/authorization should remain an explicit dependency. If another normal app owns the notebook, observe its acquisition handoff/status instead of relaunching a second Executive.
