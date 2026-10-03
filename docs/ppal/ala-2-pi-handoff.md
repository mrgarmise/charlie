# ALA-2 continuation and Pi handoff — 2026-10-02

ALA-2 remains open. This continuation starts from `d10cc2fa26bafe48375d36ac2cd70c569d3d1a18`, preserves the existing Reflection → Evaluator → Executive → chooser → Foundry → deployment path, and addresses independent evaluation, artifact transport and Torch-free Pi operation. It supplies no movement/firing strategy and initiates no physical game.

## Preserved checkpoint and evidence

The branch initially resolved to exactly `d10cc2f`. Its original regression reproduced **473 passing tests** on the new host before the additional validation work. The controlled semantic demonstration and 59-versus-100 epoch findings in [ala-2-operational.md](ala-2-operational.md) remain preserved; they were not regenerated or relabeled as physical performance.

The attached `ALA-2-evidence-followup.tar.gz` has SHA-256 `e0f04ab7fd114cdc6dc93d11f6ceb45118c98cb47b717c8e9abc5a0004992a00`, identical to the previously saved follow-up archive. Its journal contains 81 records with valid canonical content IDs. Its manifest files were inspected without running the archived investigation. It preserves the earlier metadata retrieval follow-up, references external ALA-1 pixels/weights and does not contain an independently validated Robotron classifier. Neither that archive nor the original rejection was overwritten. The later duration result remains validation-only, with its final test sealed.

## Changes and practical limits

* `learning.portable` exports the existing authorized classifier weights to bounded, non-pickle NumPy tensors. It implements the same stride-2 convolution, ReLU/exact GELU, pooling, linear layer, RGB resizing and softmax. Training remains on a Torch-capable host. Export checks 12 deterministic generated transport probes against the frozen Torch model and appends transport provenance to the existing journal. It does not reopen held-out images, train, grant authority or count as independent scientific evidence.
* A bundle contains `weights.npz`, `learning-evidence.sqlite3` and `semantic-activation.json`. Paths are relative to the bundle; original candidate/checkpoint identities and all journal documents remain unchanged. A SQLite backup includes committed state. Loading verifies the current local activation, transport lineage and weight hash. NumPy inference abstains near admission and class-tie boundaries to account for finite numeric tolerance. Probe parity is not an exhaustive proof on every possible input; candidate-specific physical qualification remains necessary.
* `--learned-semantics` uses either the existing Torch manifest or a verified NumPy bundle. No new controller, tracking pass, SELF authority, game-state detector or tactical chooser was introduced. Baseline operation still requires no Torch. Physical loading of a portable candidate additionally requires readiness naming `runtime: numpy-small-cnn-v1` and its exact `portable_sha256`; a Torch cadence approval cannot authorize a different inference runtime.
* `CapabilityDeployment.rollback(..., to_baseline=True)` explicitly releases to baseline even if a prior activation's historical host checkpoint is unavailable. Ordinary previous-model rollback retains its original weight verification. Existing rollback invalidation and refusal to reactivate a revoked proposal remain in effect.
* A new dataset/model version cannot recertify previously consulted final-test games. The cycle detects overlap through source episodes, original capture hashes, pixel hashes and independent group IDs; unavailable historical isolation also blocks certification. Metrics remain diagnostic, marked `fresh_final_evidence: false`; both semantic and offline-shadow deployment are denied. Exact-plan crash recovery reuses the original completed evaluation rather than counting it as another test. Legacy accepted activations are preserved, not retroactively rewritten.
* `learning.readiness` reads journals without schema changes, reports current resource availability and Robotron label coverage, and optionally times 16-crop inference batches on preserved PNG inputs. It opens no camera, sends no controller/START command, trains nothing and grants no readiness. Timing does not establish controller release, camera ownership, terminal boundaries, processing recovery or thermal/contention behavior.
* The three tests that assumed an executable CNN plan without Torch now explicitly require Torch. Separate no-Torch tests verify durable project retention, clear resource deferral, read-only auditing and NumPy inference. Missing Torch does not silently activate a candidate or resolve an experiment.

The portable bundle's journal is the local activation/rollback authority after transfer. It is a snapshot, **not a live source-host revocation feed**. Use one operational writer. Source-host rollback must be transferred before a subsequent Pi episode, or invoke local baseline rollback. Do not run source and Pi as independent deployment writers. Copy the whole bundle; do not combine a manifest, journal and weights from different exports or overwrite a Pi journal that contains later local rollback history.

## Pi update without touching the original checkout

Use the full published commit SHA from the handoff message. From `~/Projects/charlie`, fetch the branch, then execute the script from that exact Git object:

```bash
cd ~/Projects/charlie
git fetch origin feature/agency-first-self
# PUBLISHED_SHA is the full independently tested commit in the handoff message.
git show PUBLISHED_SHA:tools/prepare_ala2_pi.sh | bash -s -- PUBLISHED_SHA
```

The script creates `$HOME/charlie-ala2-<first-12-SHA-characters>` as a detached worktree and uses the original `~/Projects/charlie/.venv/bin/python`. It refuses an existing destination, requires ancestry from `d10cc2f`, refuses active gameplay, runs all regressions and writes `ala2-regression.txt` plus `ala2-readiness.json`. Test failure stops the handoff. It performs no reset, clean, stash, package replacement, evidence migration or gameplay activation. Existing `robotron-runs`, `robotron-evidence`, `head2_sessions` and local modifications remain in `~/Projects/charlie`. Evidence paths supplied to later offline tools must point there explicitly; the new worktree intentionally has no copied physical evidence.

An optional read-only audit of an existing learning root uses the new checkout as the working directory and the existing Python environment:

```bash
PYTHONPATH="$PWD" ~/Projects/charlie/.venv/bin/python -m learning.readiness \
  --root ~/Projects/charlie/learning-runs/ala-1 \
  --output ./ala2-existing-evidence-readiness.json
```

If that learning root is absent, the report says so; it does not recreate its evidence. Choose the actual preserved root if it differs. Existing reports are never overwritten by this CLI. Do not rerun `learning.validate_continuation` merely to recreate the preserved duration demonstration.

## Candidate export, offline activation validation and rollback

There is currently **no qualified Robotron candidate to activate**. The following tools accept a real previously authorized candidate; they do not create an authorization policy. Controlled-lab candidates remain ineligible for physical loading.

On the Torch training host, after independently evaluated Robotron evidence, passing shadow integration and separate authorization exist:

```bash
python -m learning.portable \
  --manifest /absolute/path/to/authorized/semantic-activation.json \
  --output /absolute/path/to/new-pi-bundle
```

The destination must be new. Transfer the entire directory to the Pi, retaining its name and three files. On the Pi, with no game running:

```bash
PYTHONPATH="$PWD" ~/Projects/charlie/.venv/bin/python -m learning.readiness \
  --manifest /absolute/path/to/new-pi-bundle/semantic-activation.json \
  --crops /absolute/path/to/preserved/crop-pngs \
  --output ./ala2-candidate-inference-readiness.json
```

This validates local activation/artifact integrity and measures offline inference. It does not authorize a live run. A timing-only report must not be labeled as full physical readiness. The existing readiness contract still needs all five independently evidenced checks: `processing_recovery`, `controller_release`, `terminal_boundaries`, `camera_ownership`, `operational_cadence`; for NumPy it also needs the exact runtime and weight hash. New readiness is attached through the existing separate deployment authority and activation path; changing manifest JSON is not activation.

To revoke a transferred capability locally, without camera or gameplay:

```python
from memory.evidence import EvidenceJournal
from learning.deployment import CapabilityDeployment
journal = EvidenceJournal('/absolute/path/to/new-pi-bundle/learning-evidence.sqlite3')
try:
    CapabilityDeployment(journal).rollback(
        'ppal-semantics', reason='Operator release to baseline',
        authorization={'source': 'Pi operator', 'target': 'ppal-semantics'},
        to_baseline=True)
finally:
    journal.close()
```

The old manifest then fails activation checks. Physical use through the existing `--learned-semantics` option remains contingent on independent Robotron-domain evaluation, matching runtime-specific readiness and a separate explicit authorization to start armed gameplay. No armed command is supplied as a presently ready next step.

## Acceptance status and next evidence

| Original acceptance component | Status after this continuation |
|---|---|
| Charlie-originated bounded hypotheses, interventions, resolutions and next questions | Preserved demonstrated path; finite supported methods, not broad scientific invention |
| Learning finding → independent evaluation → shadow → guarded operational change → rollback | Controlled-lab demonstration preserved; portable inference and baseline release additionally tested |
| Fresh independent final evidence for new operational admission | Reuse guard implemented; actual fresh Robotron evaluation still absent |
| Active evidence acquisition/clarification | Existing recorded-crop extraction and annotation ingestion preserved; independent Robotron labels missing |
| Adaptive Executive prioritization | Existing declared heuristic retained; learned value-of-information and broad hypothesis/representation search unfinished |
| Real 59/100-epoch finding | Preserved validation-only improvement; no new independent final result or deployment |
| Robotron operational recognition/capability gain | Not demonstrated |
| Pi Python 3.13.5/Torch-free compatibility | Host Python 3.13.5 regression passed; ARM64/cadence/hardware qualification still required |
| Reliable official-score evaluation | Existing preregistered analyzer retained; independent reader/final-boundary qualification missing |
| Learning-derived physical score improvement | Not demonstrated; zero new physical games |

Next useful evidence is independently verified `human`/`threat` crop observations across isolated physical games, or an independently validated observational labeling capability. UNKNOWN, provisional SELF and learned predictions cannot supply those labels. Fresh final games must remain separate from training/validation and already consulted finals. These are observations, not a manually supplied winning strategy.

After a candidate qualifies, preserve candidate/baseline versions and the camera/game/system/measurement conditions in the existing [physical score protocol](ala-2.md#physical-score-comparison-protocol). Preregister randomized complete-game blocks before trials. Unknown, contradictory, partial or missing final scores remain inconclusive; do not privilege a person or reader, select favorable games or substitute survival/reconstruction accuracy for official score. A short readiness marathon does not establish powered score improvement.

Broader causal synthesis, learned value-of-information, reward-grounded role discovery, fresh-final representation/preprocessing search and learning-derived strategy deployment remain original acceptance gaps. ALA-2 is not complete.

## Validation

Final full suite: **482 passed in 47.80 seconds**, Python 3.12.14 with Torch, x86_64. Python **3.13.5 without Torch: 461 passed, 19 skipped in 42.07 seconds**, x86_64. The skips explicitly cover Torch-dependent execution; no failures are suppressed with expected-failure markers. Diff checking, Python compilation and shell syntax/usage validation also passed. Tests include CNN numeric parity for multiple depths, kernels and activations; end-to-end laboratory export; source-host removal and bundle relocation; no-Torch loading; artifact tampering; local rollback; final-test reuse rejection; read-only audit; and preserved tracking, agency, score, startup, recovery and Executive regressions. No ARM64, camera/controller contention, thermal or physical score result is inferred from x86 host tests.
