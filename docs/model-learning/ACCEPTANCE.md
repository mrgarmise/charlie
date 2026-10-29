# Acceptance and integration audit

Base: `master` bcf8082f6319c63c4bd6bcceeab5faea37241654. Isolated branch:
`feature/executive-model-learning`, checkout `/home/five/charlie-model-learning`.
The original agency checkout and its untracked capture/evidence directories were
left untouched. No merge, rebase, deployment or hardware operation occurred.

Live GitHub API inspection on 2026-10-28 verified these open draft dependencies:

| PR | Examined head | Status at inspection |
|---|---|---|
| #8 Hailo score proposals | b4f258853964edbc3e442f9332675d5ebd7007e9 | both latest workflows successful |
| #10 pet Executive | 9c1319d2800749d19cd5086f34ba4643276d90a7 | latest software workflow successful |
| #12 shared sensory contracts | ae09f52d1a1f65de2bcb923cb7d112d666fb5798 | latest sensory audit successful |
| #13 unified integration | 08ae83f7a6f54a7b0acefc4f240df784f176573e | all three latest workflows successful |
| #14 human gateway | 4bb3bffecffea0d6e294485132f42f5e96f4c506 | browser/security and software workflows successful |

These are inspected GitHub statuses, not certification of installed hardware.
#13's previously pending audit rerun is now successful; #14's final head also
passed its workflows. Existing PRs #3/#5/#6/#7/#9/#11 and all newer open heads
were enumerated, not overwritten. Fetch/push by local Git is unavailable:
SSH public-key authentication failed and shell HTTPS cannot resolve github.com.
Connected GitHub tools provide read/publication access without changing remotes.

Canonical ownership was checked against #13 `docs/CHARLIE_ARCHITECTURE.md`,
#13 `stimulus/bus.py`, and #14 `memory/human_interaction.py` and its runbook.
Existing Robotron owners are PPAL Eyes/CameraSession; phase logic is
`experiments/ppal/robotron_screen_state.py`; scoring remains its existing HUD,
ScoreObserver and temporal acceptance path. Existing ALA uses
`learning/cycle.py`, `foundry.py`, `datasets.py`, `resources.py`,
`memory/learning_projects.py`, and `learning/deployment.py`. This increment uses
the existing Executive, journal, resource lifecycle and deployment owner. It
registers a different perception-task artifact format rather than misrepresenting
existing reconstruction/CNN artifacts as screen-state classifiers.

The source inventory additionally found 8,969 image files across 44 top-level
origins in the old Robotron-runs tree: 137 raw_* files, 122 review JPEGs and
6,519 tracking crops (these counts overlap categories and do not assert unique
original exposures). A one-recording historical file has 37 human track-identity
labels, including one player and flagged mixed/bad-box cases. Its hash and label
counts are retained in `source-inventory.json`; it supplies neither phase truth
nor independently verified localization boxes. `localization-proposals.json`
reuses the existing saved blob proposals on eight rectified frames (138 boxes),
retains UNKNOWN semantics and makes no detector/track accuracy claim.

The mission's PR #8 private score corpus/HEF and PR #6/Vision Lab detector work
are independent. No score labels, ONNX/HEF, Hailo admission, motion firmware,
controller leases or model defaults were changed. No camera, serial, RP2040,
ELEGOO or controller capability is opened by the new validation commands.

## Observed evidence

`authentic-baseline.json` preserves exact admitted derived/current-image hashes,
original source hashes/provenance, capture sessions, labels and incumbent output.
Six authentic repository frames, three sessions; five reviewed regression labels
(two menu, two gameplay, one terminal) from two sessions; one unlabeled original
startup failure from a third. This is the **admitted corpus**, not a claim that
all stored frames in Charlie's many archives were independently reviewed.
Additional developmental and capture archives exist but were not promoted into
semantic truth from filenames or tracker identity-loss labels.

The existing incumbent matches all five existing fixture labels (a reused 5/5
regression result, not independent accuracy). The third-session startup remains
unknown. No genuine unknown/OOD ground-truth example or complete timed sequence
was admitted. There is no legal three-way, class-covered authentic split here.
No trained candidate, authentic heldout confusion matrix, calibration estimate,
transition score, native inference cost, improved gameplay or Hailo qualification
is claimed. The visible baseline report includes host costs for this replay;
they include load/rectification and cannot be compared to native pipeline FPS.

The normal offline application's actual LearningExecutive discovered the retained
unknown startup evidence, proposed/selected a model-learning investigation and
persisted NEEDS_LABELS with rationale. It closed normally with no activation.
A separate synthetic-only software test exercises Executive initiation, real
bounded subprocess fitting, parent-side heldout evaluation, registration, safe
rejection, MemoryGateway outcome handoff and restart. That is plumbing evidence,
not the mission's authentic end-to-end training acceptance.

## Remaining gates and native procedure

1. Gather/review authentic title/menu, gameplay, terminal and unknown examples
   from separate capture sessions with unchanged authoritative capture ownership.
   Bind source hashes, calibration, session/time and human attribution. Include
   temporal transitions and difficult/OOD scenes. Assign sessions before training.
2. Run the normal offline Executive path; verify an actual gap selected training
   against other eligible work. Independently compare frozen holdout metrics,
   false positives, abstention, failure images, latency and retained model card.
   Refresh final evidence for future qualification rather than recycling test data.
3. Reconcile this draft's additive `main.py`, `learning/lifecycle.py`,
   `memory/learning_projects.py` and `learning/deployment.py` hooks with #13/#14.
   Run full combined-stack regressions; source-file adapter compatibility alone
   does not establish that integration. Attach actual authoritative evidence
   bookmarks and the asynchronous review UI to the same notebook. No extra feeder.
4. Review explicit human gateway answers, independent qualification and runtime
   identity; activate only `perception-shadow`. Test an earlier known-good pointer
   and rollback under subscriber load, missing artifacts and restart. Monitor
   errors/abstention; preserve incumbent scoring and phase decisions.
5. On an accessible Pi 5, first make a read-only checkout/environment/device
   inventory and backup existing notebook/config/model pointers. Do not install
   over an active checkout. Replay saved frames on CPU with cameras/motors closed;
   measure latency distributions, peak RSS, CPU, thermals and concurrent reader
   continuity. Match artifact/preprocessing/source digests and rollback receipts.
6. Physical gameplay or movement requires a separately authorized supervised
   native procedure with current controller/deadman, RP2040 and ELEGOO readiness,
   STOP/loss behavior and an independent cutoff. This mission authorizes software
   validation only; no physical acceptance is implied by its test passes.
7. Consider Hailo only after CPU need is measured. Inspect compatible export,
   actual DFC compilation/runtime, preprocessing/output parity, shared admission,
   native concurrent resource cost and rollback. An ONNX file is not Hailo proof.

Live Pi/device access was not attempted: it is unnecessary for the authorized
host software phase and no connected native hardware tool is available here.
The authentic training cycle, full combined-stack integration, live subscriptions,
object localization, timed transitions, statistical calibration, monitoring-driven
rollback and native/hardware acceptance remain pending. Keep the PR draft.
