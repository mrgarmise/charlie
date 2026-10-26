> **2026-10-24 continuation:** The operator supplied the existing controller
> timing evidence (approximately 0.92 seconds) and directed software recovery
> using the October 22 sources, without another physical trial unless a specific
> correction needs it. Standing gameplay authorization remains effective; the
> historical separate-approval wording below does not override it. See
> [current software verification and evidence limits](../native-resume-20261024/README.md).

# PR #9 native border recovery — 22 October 2026

Recovery assignment: https://github.com/mrgarmise/charlie/pull/9#issuecomment-6330939115

Base: PR #9 bb77fb681965cd32e23456c45b1e86d94724ffba, whose runtime parent
is installed d6ef07b0b5a5959feedf50ef7f53a7fa026e29c6. Recovery changes only
preflight and marathon orchestration, plus tests and this handoff. PR #5
7dcea80, PR #7 83112b4 and PR #8 b4f2588 were inspected through their current
GitHub descriptions and the selected implementations present in this base.
This does not import their entire branches or qualify their inactive artifacts.

## Authentic failure and correction

Original source, preserved unchanged:
`/home/five/charlie-native-trials/learning-20261022-025334/development-20261022-025335/game-01`.
This attempt completed zero games. Its supervisor exiting normally does not
establish a completed episode. Focus was locked at 2.0; repeated geometry had
six stable observations. The last single-frame discovery discarded that result.

`tests/fixtures/native-border-20261022` contains byte-identical copies of the
failure PNG, the earlier EV -3 PNG and sensory report. `provenance.json` records
SHA-256 identities. The failure PNG reproduces `No complete game border found`;
the earlier EV -3 PNG independently passes the detector within 12 pixels of the
stable calibration. Regression replay deliberately presents these archived frames
in a new order. It proves retry behavior, not an authentic later successful frame
or recovery of a live trial.

Final image verification now allows at most four fresh reads within the existing
sensory deadline. Every accepted frame must pass existing full-field discovery,
all edge and endpoint support gates, <=12 pixel agreement with stable geometry,
positive finite sharpness/focus, and >=50 detail pixels. A supported moved rectangle
fails immediately. Persistent misses, incomplete FOV and bad detail fail closed.
Stable corners only rank independently supported candidates; they never replace
current visible border evidence. Every attempt retains quality and geometry
rejections, and rejected fresh frames are saved as `sensory-final-rejected-NN.png`.
Manual focus, score evidence, terminal and START authority remain independent.

## Runtime capability matrix

| Capability | Implemented and selected runtime path | Guarded/inactive or missing artifact | Physical status of this recovery |
|---|---|---|---|
| Camera/geometry/focus | `camera_session`, continuous `eyes.sources`, `sensory_preflight`; fresh geometry, exposure, manual lock 2.0 | WB absolute color fidelity unqualified; no servo or focus sweep | Archived failure reproduced; new live sequence untested |
| SELF | `play_robotron`, temporal tracking, causal movement/body discovery, bounded recovery | Shot-origin projectile SELF opt-in, omitted here; no identity from geometry alone | End-to-end tactical SELF not established by failed launch |
| Game over/restart | `episode_observer`, `game_evidence`, `safe_to_restart`, sealed per-episode evidence | Unknown/zero-reserve observations cannot authorize START; ambiguous boundary stops | Game 1 to playable Game 2 remains untested |
| Score | `ScoreObserver` fixed reader, bounded writer, original frames and temporal acceptance | Accepted score still needs independent outcome verification | Failed launch score unmeasured |
| Neural score/Hailo | PR #8 proposal interfaces and shared optional resource admission selected in integration | Player still constructs default fixed `ScoreObserver`; no qualified neural reader configured here. Authentic corpus/model/HEF qualification and live reader wiring needed before activation | No recovery Hailo inference or score benefit claimed |
| Executive investigations | `LearningExecutive.select`, `select_experiment`, commitments and durable project journal; `--learning-projects`; completed-episode `process_supervised` | Selection can legitimately be blocked/no justified experiment; loading records proves no adaptation | Original launch loaded Oct 2 evidence but selected no experiment; recovery untested live |
| Offline ALA | `--ala-learning` passes bounded foundry work through existing processing after eligible completed episodes | Opt-in investigation, not policy deployment; no automatic physical activation authority supplied | No new authentic completed episode processed here |
| PPAL retained learning | Existing memory/evaluator and episode import/derive; explicit `--learned-policy` guarded loader and retained-response attachment | No qualified physical positioning-policy/semantic manifest supplied; fixed existing gameplay remains selected. Need authentic candidate, evidence dependencies, qualification, physical activation and rollback manifest | No new physical P1 or I1 claim |

PR #7 reports scoped historical Executive recurrence and retrospective diagnostic
valuation controls. Those scoped results do not establish recovery-session E1/P1,
physical learned gameplay, I1, or original ALA-2 closure. Governing documents:
`ALA_LEARNING_CHARTER.md` and `ALA2_ACCEPTANCE_STANDARD.md`.

## Normal integrated recovery command

Use an ordinary Charlie terminal, from a clean checkout of this published recovery
revision, with the existing arcade lease release service and verified physical
Xbox emergency stop. No service install/restart, head movement, host-wide ownership
scanner, or review.json is introduced. Existing independent release/stop and fixed
camera ownership prerequisites still apply. The assignment requires separate
express authorization before physical gameplay or physical learned-policy activation;
this work does not execute the following command.

```bash
cd /home/five/charlie-pr9-recovery
/home/five/Projects/charlie/.venv/bin/python -m experiments.ppal.marathon_robotron \
  --arm --recovery-trial --developmental --learning-projects --ala-learning \
  --max-games 2 --qualified-games 2 --focus 2.0 \
  --root "/home/five/charlie-native-trials/recovery-$(date +%Y%m%d-%H%M%S)" \
  --learning-root /home/five/.local/share/charlie/development \
  --campaign-notebook /home/five/.local/share/charlie/development \
  --project-evidence /home/five/.local/share/charlie/development/learning-project-evidence.sqlite3
```

This explicit recovery mode permits 1–2 attempts with matching completion target;
it requires developmental project continuity, rejects baseline-only/play-first
combinations, and preserves learning rather than selecting the observation-only
exception. It does not loosen the ordinary 3–5-game developmental schedule or
qualify a three-game reliability block. It performs eligible processing between
games; camera/controller resources are released first. The next episode creates a
fresh camera owner/preflight, retaining manual 2.0 without a sweep. Game 2 still
requires independently validated terminal/restart evidence. Any failed first
attempt stops; this is not an automatic repeated-START loop. Failed completion
and cleanup return nonzero.

The parent uses the existing progress supervisor `on_poll` and `ResourceGuard`:
75 C stop, required thermal telemetry, 768 MiB owned process memory budget,
throttling flags and 2 GiB evidence disk stop. Checks occur before launch and
once per second independently of child progress. Failure stops the owned process
group; no cooling/resume/retry loop. `recovery-resources.jsonl` retains observations.
This is a bounded use of existing guards, not another host-wide monitor. Server
LEASE is mandatory; only progressing player execute renews it. A frozen worker
cannot be kept armed by resource polling. Ctrl-C uses existing owned cleanup;
physical Xbox remains the independent stop path.

`session.json/features` and startup output explicitly describe selected features.
Episode observations/actions/outcomes remain in each game's `session-evidence.sqlite3`;
`game-evidence.sqlite3` links completion provenance in the existing learning root.
The shared original memory/evaluator and project journal retain Executive state.
Eligible completed episodes enter existing import/derive, Reflection/Meditation and
bounded ALA interfaces through `process_supervised`; eligibility and unresolved
results remain explicit. Failed captures remain diagnostic and confer no learning
or episode success. No original notebook or historical file was changed in this
engineering session. No learned-policy, semantic or Hailo artifact is activated.

## Validation and limits

Final focused selection: **78 passed in 23.83 s**, zero failures/errors/skips.
Related selection: **79 passed, 4 socket setup errors in 17.93 s**. Selections
overlap and are not summed. Compileall and git diff --check pass. Source hashes
and environment are in `validation.json`. See `focused.xml` and `related.xml`. The latter preserves four socket setup errors
(`PermissionError: Operation not permitted`) alongside 79 passes. Earlier operator
153 native socket and 256 ARMv6 arcade passes apply to their tested release, not
this new code. Archived-frame and synthetic software tests do not substitute for
native fresh capture, physical neutral release, complete games, learning adaptation,
independent score/performance, E1/P1/I1, or marathon acceptance.

No camera/controller activation, physical gameplay, service change, learned-policy
activation or main merge occurred. Keep PR #9 draft. Revert the recovery commit
or use pinned d6ef07b for source rollback; preserve new failure receipts and the
original immutable notebooks. Source rollback never authorizes another trial.
