# Session tactical learning and sensory recovery

Parent: c97e4978aa0b91335a94ab5e5531273e9d2cd8a8, verified against the remote feature branch before publication. Continues controller sandbox f6f23a78cb9a45ae7b4a2be5751e4790884f5a2e and recorded sensory/startup milestone c97e4978aa0b91335a94ab5e5531273e9d2cd8a8. All new execution is host software simulation or loopback transport. No Pi, physical gameplay, servo motion, firmware deployment or learned physical policy activation occurred.

## Existing real-time owner

The normal Robotron entry point remains experiments.ppal.play_robotron. Current camera observations flow through existing calibration, recognition, VisualAgency/SpriteTracker, WorldState, Forebrain and Hindbrain, then the existing controller transport and subsequent observed response windows. main.py owns the separate normal developmental lifecycle; it does not launch Robotron. Neither application is replaced.

Normal Hindbrain now enables bounded session-local tactical feedback. The default constructor retains the frozen baseline for direct callers and comparisons. It generates observed-geometry alternatives to the existing chooser action: continuation, movement directions, current visual firing opportunities and combinations. Existing rescue/survival goals remain Forebrain's responsibility. A completed fresh two-endpoint response window with the same confirmed controlled track can support or contradict a signed-motion prediction. Provisional identity, missing frames, late responses, mismatched origins and incomplete windows remain unresolved. A displacement association is not proof of causal action effect or score improvement.

After an eligible contradiction, the existing Hindbrain can try a different currently safe option using bounded per-action histories. Current imminent threats, mandatory evasion and unsafe-observation neutral behavior override experimentation. Existing qualified policy guards remain in force. An action changed by those guards, firing normalization or an existing commissioned experiment updates the prospective prediction before execution. No joystick command, deployment grant or durable policy is issued by the Learning Executive. Session adaptation is not independent qualification, and is intentionally reset on process restart or identity/coordinate interruption. Original evidence survives those resets.

Reflection/Meditation remain retrospective activities in existing separate developmental ownership, including published resource yielding. The fast chooser has no Executive turn, meditation, journal search, model training or network lookup. Tests poison Executive.develop and retrospective reconstruction while exercising tactical decisions. The already existing diagnostic shadow chooser is unchanged and never supplies transport commands.

## Durable prediction, action and outcome

The normal runner commits each tactical question, prediction, final selected action, source observation, goal/intent and policy trace before executing it. Actual controller timing and input execution follow. Subsequent outcomes retain original prediction identities, tracked displacement, response eligibility and uncertainty. Steps include chooser wall latency and separate persistence latency. Recording uses the existing EvidenceJournal; episode acquisition merges its original immutable records with original commitment times and sources. Importing/restarting/copying a recording does not turn it into another independent experience or recompute its predictions. Existing Reflection/MemoryGateway/Evaluator acquisition is reused. Score qualification remains separate.

The original failed-start image and report from marathon-20261008-031501/game-01 remain unchanged. Source archive SHA256 c6894512e8a79898bbd158f957d22113f1580138bc9d373f67a92209e2208635; preserved PNG SHA256 60a53ec71812431a4edb5e8a5524da104a66f7e8a16ccca62362572ff173c2bb. The image still classifies unknown and is not an operator-verified title reference. Startup learning, tactical contradictory/supported response tests and title matching demonstrations are controlled fixtures, not physical learning successes.

## Bounded sensory recovery

Initial sensory preparation and recording-before-exploration are supplied by the preceding milestone. During operation a lightweight border brightness/clipping monitor requires three consecutive major deviations before requesting reacquisition, with at most two attempts. This is a coarse impairment detector, not a guarantee of optical quality. Controls are neutralized before optical preparation. Existing camera ownership, exposure/focus/geometry optimization and browser preview remain intact; no physical viewpoint movement occurs. Exhaustion preserves failure and asks for assistance.

A new coordinate epoch retires original active tracks without recycling IDs, interrupts the pending tactical prediction as unresolved and re-enters existing agency recovery. Existing score worker receives calibration updates in FIFO order without resetting accumulated score history. This avoids treating coordinate changes as player motion or a new game. Stable imaging on changing native game scenes and reacquisition during a real session still require separately authorized validation.

Journal congestion fails closed; one already captured overflow image is preserved for finalization after controls close. Tests cover saturation, ordered predictions/outcomes, lossless pixels, orphaned captures and reopening without extra records. An unavailable journal closes the camera before controller creation. No timeout or resource gate is removed.

## Reproduce without physical action

On host or Pi, these tests use mocked camera/controllers and loopback sockets only, even where the simulated normal entry point is passed --arm:

```bash
python -m pytest tests/test_controller_sandbox.py tests/test_robotron_exploration.py tests/test_sensory_recording.py tests/test_real_time_tactical_learning.py tests/test_robotron_agency_integration.py tests/test_qualified_ppal_policy.py -q
python tools/benchmark_tactical_feedback.py --output /tmp/charlie-tactical-benchmark.json
```

The benchmark opens neither camera nor controller. It compares 10,000 frozen controlled WorldStates with feedback disabled/enabled, and writes 20 repeated original failed-start images to temporary storage solely to measure recording cost. Copies are explicitly simulated, not independent experience. Reported process CPU time, wall time, latency distributions, RSS and whole-system per-core counters must be interpreted together; per-core counters include unrelated OS load and RSS is the cumulative process high water. Source hashes identify exact measured files in the dirty candidate tree.

For the existing persistent native developmental notebook, first retain original captures/notebook and every previous acceptance/failure report. Inspect local changes and the actual published release before updating an isolated checkout. Do not reset unrelated worktrees or delete the notebook. The existing tools/accept_episode_identity_pi.sh now also runs these new offline regressions and retains its existing unarmed normal main.py lifecycle/restart checks:

```bash
bash tools/accept_episode_identity_pi.sh <exact-published-40-character-SHA>
```

This script requires the established Pi paths and aarch64, exports history before/after even on failure, and does not launch camera/controller gameplay. A successful script must still be interpreted using its continuity classifications; previous incomplete native runs remain failures. Separately authorized native camera preparation/transport readiness and an explicitly authorized arcade session are needed before any live experiment. Viewpoint movement additionally needs independent CAL-1 qualification and motion authority; physical persistent policy activation needs its separate evaluation/readiness/activation gate.

## Remaining acceptance gaps

No authentic independently verified title reference was supplied. Absolute camera color fidelity, native storage throughput/thermal cost, actual physical input mappings at the current installed launcher, and native sensory/tactical responsiveness remain unverified. The published upstream controller/config mapping was audited, not freshly exercised on the physical arcade. No authentic candidate has gained independently verified complete-game score improvement in this work. ALA-2 remains open under the existing frozen baseline, independent complete-game evaluation and rollback requirements.

## Recorded host qualification

Focused final regression: 58 passed in 22.41 seconds. Full independently executed host suite: 657 passed, 20 skipped in 128.58 seconds. Unavailable Torch and the unavailable original October 1 collision capture remain explicit skips. Retained initial results show 11 failures caused by the new assertion reading prediction fields outside their actual payload.expected object; correcting that assertion exposed the recorded fields and the final complete suite passed. No production evidence was rewritten to satisfy it. git diff --check and guarded acceptance shell syntax checks passed.

Measured x86_64 Linux 6.18.44 / Python 3.12.14, pytest 9.1.1, NumPy 2.5.3, OpenCV headless 5.0.0.93, Pillow 12.3.0. Final benchmark ran after the regression suite finished. Initial benchmark reports are preserved to expose timing variation; they overlapped regression activity and are not used as speedup evidence.

| Workload | Samples | Median ms | p95 ms | p99 ms | Maximum ms | Wall seconds | CPU seconds | Peak RSS KiB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 10000 | 0.004348 | 0.005210 | 0.027461 | 1.550981 | 0.0840 | 0.0839 | 15104 |
| tactical | 10000 | 0.054421 | 0.146614 | 0.323496 | 3.174559 | 0.7373 | 0.7366 | 15104 |
| recording | 20 | 91.512175 | 108.264901 | 108.264901 | 109.573043 | 1.9609 | 1.9581 | 27464 |

This adds tactical work; no speedup or native Pi performance improvement is claimed. Chooser measurements exclude camera inference, diagnostic shadow planning, transport, image compression and journal persistence. The much greater recording service cost is an operational bottleneck requiring native microSD measurements. The asynchronous writer overlaps some work but is deliberately finite; it yields controls on congestion. Arbitrary latency thresholds are not used to declare acceptance. Full per-core counters, process CPU/RSS and source hashes are in host-benchmark.json.

The benchmark retained 20 simulated repeated original images with unchanged source hash and resumed recorder numbering at 21. It emitted zero controller commands and independently qualified zero findings. Controlled contradictory windows demonstrate session adaptation, not verified Robotron performance.
