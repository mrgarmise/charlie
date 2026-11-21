# Learning Executive agent factory development increment

## Architecture and authority

The existing LearningExecutive in `memory/learning_projects.py` commissions the opt-in factory. Its proposal is a static, validated graph of trusted registered Python algorithms. Dependencies carry hashed evidence, and supervisor links describe ownership. Supervisors cannot presently request children at runtime. The SQLite development database owns graph state and attempt accounting for one sandbox. This increment does not connect that database to the existing scheduler, event bus, or memory gateway. No runtime entry point loads the factory and the demonstration registers only synthetic and simulation algorithms. Registered code runs synchronously in the development process. Treat registry code as trusted and run the demo on an isolated development host. The lease fences result writes. It does not interrupt a running process or guarantee that expired work has stopped. Do not expose this registry to model-generated code or production equipment.

## Environment and experiment

Charlie base is source-only PR #39 merge `57e07eb850b139eda6a5f1a930cc0ef7b5bf5f18`. Dog PR #3 branch head is `c2b2ba71502824a5fe5580c89d1e6253af72d655`. The adapter imports UEL from Charlie's independent research checkout at `cf0842efeaeea4862abdbf46c33977adfc48aa3b`. Dog XML SHA-256 is `ae32a1d981b390fcb113abd0e4f52a1f31710376ab6f9e93ad299cbe28fe70cb`. Python 3.12, MuJoCo 3.3.7 and Gymnasium 1.2.2 ran on Linux x86-64. No Pi performance inference was made.

`dog-baseline.json` contains 32 actual Dog UEL adapter trials with randomized physics, seeds 0–31, two seconds per trial, at most 32 trials per batch invocation. Seed 0 uses a zero command. Remaining seeds use fixed constant command vectors. The existing Dog environment terminates at excessive roll or pitch and its action space only perturbs the standing baseline. An independent fresh-database rerun reproduced all 32 trial results and evidence digests in 1.08 seconds with peak RSS 57,716 KiB on the development host. The maximum sampled roll was 0.02138 rad. This is an inconclusive diagnostic of the existing adapter for the full roll objective. A separate model mode with continuous rotation and floor-contact evaluation is required for candidate search. There was no matching physical replay or calibrated transfer evidence. `offset-baseline.json` demonstrates a synthetic offset goal through the same factory and LE API.

## Quickstart

From the Charlie draft checkout, with sibling Charlie UEL and Dog checkouts at the revisions above:

```sh
python -m pip install --target /tmp/charlie-dog-sim -r ../dog/research/fnk0050-sim/requirements.txt
export PYTHONPATH=/tmp/charlie-dog-sim:../charlie-uel:../dog/research/fnk0050-sim
python -m tools.agent_factory_demo /tmp/le-demo.sqlite dog-baseline dog
python -m tools.agent_factory_demo /tmp/le-demo.sqlite dog-baseline status
python -m tools.agent_factory_demo /tmp/le-demo.sqlite dog-baseline cancel
python -m tools.agent_factory_demo /tmp/le-demo.sqlite offset-baseline offset
```

Repeat the identical launch to continue a queued mission after interruption. An outstanding attempt remains fenced until its lease expires. A cancelled mission is terminal, and the kill switch persists for that database. Use a fresh database for a fresh diagnostic.

## Acceptance

| Stage | Status | Evidence and limitation |
| --- | --- | --- |
| Inventory | Partial | Source and model revisions pinned. Full dependency and mission lineage audit pending. |
| Contracts and factory | Partial | Typed registry and graph validation, cycle/role checks and version binding. Goal/evidence contract coverage, discovery and model proposal validation pending. |
| Orchestration | Partial | SQLite claims, stale-write fencing, restart and cancellation tests. Existing scheduler and bus integration, hard interruption, resource isolation and trial-level resume pending. |
| Dog pipeline | Partial | Actual adapter baseline and evidence. Rollover-capable physics, held-out validation, physical replay and transfer pending. |
| Meta-learning and second goal | Partial | Same-factory synthetic offset goal. A persisted ranking changed the next choice after restart versus frozen memory on a synthetic fixture. Authentic experience, held-out improvement, and PPAL qualification remain pending. |
| UX | Partial | Development CLI status and cancellation. Dashboard and authorization integration pending. |
| Regression and adversarial | Partial | 19 focused Charlie tests, 134 unified contracts and 14 Dog simulator tests passed locally. Full regression, browser and process-isolation acceptance pending. The focused tests include a forced process exit after the task claim. |
| Runtime and physical qualification | Blocked | Development-only mission scope. Physical IO and deployment were not exercised. |
