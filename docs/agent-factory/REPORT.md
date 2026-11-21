# Learning Executive agent factory development increment

## Architecture and authority

The development subclass in `learning/sandbox_executive.py` inherits Charlie’s existing LearningExecutive and adds opt-in factory commissioning. The release-pinned Executive file remains byte-identical to the base revision. Its proposal is a static, validated graph of trusted registered Python algorithms. Dependencies carry hashed evidence, and supervisor links describe ownership. Supervisors cannot presently request children at runtime. The SQLite development database owns graph state and attempt accounting for one sandbox. The production scheduler in `learning/native_meditation/engine.py` is tied to a guarded Qwen reservation, native display acknowledgements and a hardware-aware driver. The sandbox ledger does not attach to that scheduler, the event bus or the memory gateway. Production integration requires a generic lease interface owned by the runtime scheduler. No runtime entry point loads the factory and the demonstration registers only synthetic and simulation algorithms. The factory calls trusted workers synchronously. The roll search uses a separate child process capped at 20 seconds wall time, 18 seconds CPU soft limit and 512 MiB virtual memory, with file writes disabled by a zero file-size limit. This resource wrapper does not isolate devices, network or filesystem reads at the OS boundary. Treat registry code as trusted and run the demo on an isolated development host. The lease fences result writes. It does not interrupt a running process or guarantee that expired work has stopped. Do not expose this registry to model-generated code or production equipment.

## Environment and experiment

Charlie base is source-only PR #39 merge `57e07eb850b139eda6a5f1a930cc0ef7b5bf5f18`. Dog PR #3 branch head is `c2b2ba71502824a5fe5580c89d1e6253af72d655`. The original adapter imports UEL at `cf0842efeaeea4862abdbf46c33977adfc48aa3b`. The roll demonstration also reuses the visual recording ingestion from Charlie visual draft `c192907625ba8ad640fbb5eae3961cbae63893ed`, which stacks on the UEL research line. Dog XML SHA-256 is `ae32a1d981b390fcb113abd0e4f52a1f31710376ab6f9e93ad299cbe28fe70cb`. Python 3.12, MuJoCo 3.3.7 and Gymnasium 1.2.2 ran on Linux x86-64. No Pi performance inference was made.

`dog-baseline.json` contains 32 actual Dog UEL adapter trials with randomized physics, seeds 0–31, two seconds per trial, at most 32 trials per batch invocation. Seed 0 uses a zero command. Remaining seeds use fixed constant command vectors. The existing Dog environment terminates at excessive roll or pitch and its action space only perturbs the standing baseline. An independent fresh-database rerun reproduced all 32 trial results and evidence digests in 1.08 seconds with peak RSS 57,716 KiB on the development host. The maximum sampled roll was 0.02138 rad. This is an inconclusive diagnostic of the existing adapter for the full roll objective. The stacked Dog draft adds a separate, simulation-only mode with continuous rotation and floor-contact evaluation. There was no matching physical replay or calibrated transfer evidence. `offset-baseline.json` demonstrates a synthetic offset goal through the same factory and LE API.

The simulator draft is [Dog PR #5](https://github.com/mrgarmise/dog/pull/5), head `f3cec3a4c3aa93582e4540f0c4b5c1c6004e9f43`, stacked on Dog PR #3. `dog-rollover.json` contains the LE-run search and held-out evaluation. A fresh run independently reproduced the standalone search results in 5.63 seconds with peak RSS 57,872 KiB. The simulator ran 128 training attempts and eight held-out attempts, including 29 commands screened out before stepping. Training reused seed 100 to reduce candidate variance. Holdout used seeds 500–507 with randomized mass, friction, servo slew and delay. The largest sampled roll was 3.19 rad in training and 3.21 rad in holdout. Zero attempts qualified. The bounded demonstration used 136 attempts total. Completing 10,000 would require a persistent trial-level continuation and precharged trial budget, both pending.

The path evaluator uses incremental quaternion rotation around the model's longitudinal axis, with independent checks on initial and final support, simulation clock continuity, joint excursions, model warnings, clearance and sampled contact force. The four-second trace is sampled at the model's 20 ms control period. A modeled full turn has a tolerance of 0.45 rad, and stance requires at least three contacts with the feet, upright cosine at least 0.97 and low base speed. The clearance and force thresholds are screening values for this model, with no measured physical validation. Brief between-sample peaks could go undetected. The research runner writes simulated actuator targets only.

The observation supervisor reads the existing visual-twin recording manifest, verifies frame hashes through that adapter, and reports source counts, missingness and a calibrated reconstruction sample when available. Its bundled recording is synthetic. The transfer worker recovers a known two-sample lag on a synthetic 20 ms fixture and tests the estimate on a second waveform. The held-out squared difference fell from 1.875 rad² to zero over the same window. Frame, period and clock mismatches, missing samples and ambiguous lag are rejected. No physical parameters were updated. A real replay would require paired calibrated timestamps and credible estimates of pose and limb state, with commanded servo targets tagged separately from measured positions.

## Quickstart

From the Charlie draft checkout, with sibling Charlie visual and Dog PR #5 checkouts at the revisions above:

```sh
python -m pip install --target /tmp/charlie-dog-sim -r ../dog/research/fnk0050-sim/requirements.txt opencv-python-headless Pillow
export PYTHONPATH=/tmp/charlie-dog-sim:../charlie-visual:../dog/research/fnk0050-sim
python -m tools.agent_factory_demo /tmp/le-demo.sqlite dog-baseline dog
python -m tools.agent_factory_demo /tmp/le-demo.sqlite dog-rollover rollover
python -m tools.agent_factory_demo /tmp/le-demo.sqlite dog-baseline status
python -m tools.agent_factory_demo /tmp/le-demo.sqlite dog-rollover explain
python -m tools.agent_factory_demo /tmp/le-demo.sqlite dog-baseline cancel
python -m tools.agent_factory_demo /tmp/le-demo.sqlite offset-baseline offset
```

Repeat the identical launch to continue a queued mission after interruption. An outstanding attempt remains fenced until its lease expires. A cancelled mission is terminal, and the kill switch persists for that database. Use a fresh database for a fresh diagnostic.

For an existing development dashboard, export the CLI status to a fixed absolute file and pass its path in `CHARLIE_DEV_FACTORY_VIEW` when starting the usual dashboard. Refresh the existing Missions page with its monitor credential. The endpoint reads exported snapshots, and the CLI remains the place to launch or cancel. Re-export to refresh the view. No environment setting is needed for ordinary dashboard use.

## Acceptance

| Stage | Status | Evidence and limitation |
| --- | --- | --- |
| Inventory | Partial | Source and model revisions pinned. Full dependency and mission lineage audit pending. |
| Contracts and factory | Partial | Typed registry and graph validation, cycle/role checks and version binding. Goal/evidence contract coverage, discovery and model proposal validation pending. |
| Orchestration | Partial | SQLite claims, stale-write fencing, restart and cancellation tests. Existing scheduler and bus integration, hard interruption, resource isolation and trial-level resume pending. |
| Dog pipeline | Partial | Actual adapter baseline, distinct roll search, held-out failure and labeled synthetic transfer. Physical replay, digital-twin update, trial-level checkpointing and closed-loop replanning remain pending. |
| Meta-learning and second goal | Partial | Same-factory synthetic offset goal. A persisted ranking changed the next choice after restart versus frozen memory on a synthetic fixture. Authentic experience, held-out improvement, and PPAL qualification remain pending. |
| UX | Partial | Development CLI status, summary and cancellation. The existing authenticated Missions endpoint and page support an opt-in bounded read-only snapshot. Browser execution and live polling remain pending. Unchanged base and draft each hit a missing Playwright Chromium binary. A system Chromium fallback failed because this environment denies its process socket. |
| Regression and adversarial | Partial | 63 focused Charlie tests, including the pinned release source checks, 134 unified contracts and 19 Dog simulator tests passed locally. Full regression, browser and process-isolation acceptance pending. The focused tests include a forced process exit after the task claim. |
| Runtime and physical qualification | Blocked | Development-only mission scope. Physical IO and deployment were not exercised. |
