# Charlie Memory

Memory is a first-class Charlie subsystem. It sits beside perception, cognition,
learning (PPAL), and action rather than inside any one of them.

## Layers

- **Working memory**: current observations/state; transient.
- **PPAL experience log**: dense action/state/reward transitions used by learning.
- **Charlie durable memory (MARM)**: important experiences, decisions, people,
  places, outcomes, learned facts, and project history.
- **Raw archives**: video, telemetry, CSV/JSONL logs. These are evidence, not
  automatically memories.

MARM is deliberately outside `experiments/ppal/`. PPAL may contribute selected
experience summaries to MARM and may retrieve relevant memories later, but PPAL
does not own Charlie's identity/history.

## Memory formation rule

Do **not** store every frame or servo movement. Promote an event when it is
novel, useful later, changes Charlie's model of something, records a success or
failure worth learning from, or concerns an important person/object/place/goal.

A durable memory should capture:

- what Charlie perceived or was told;
- what Charlie was trying to do;
- what action/decision mattered;
- what happened;
- confidence/source;
- links/tags for the subsystem involved.

The initial `MemoryFormer` is implemented in `memory/former.py`. Producers send
`Experience` records with explicit source, outcome, confidence and evidence.
Routine observations are dropped; selected `CandidateMemory` records carry the
selection reason and importance. The former does not infer causal success from
adjacent observations. Repeated identical events are suppressed within one run.

## Try the PPAL adapter

From the repository root:

```bash
python3 -m experiments.ppal.run --log /tmp/ppal-transitions.jsonl \
  --memory-log /tmp/charlie-selected.jsonl
```

`--memory-log` is optional. PPAL's dense transition logger still records every
transition, while `memory/ppal.py` selects observed changes for Charlie. PPAL-0
uses scripted frames and null rewards: an absent target is recorded as "no
longer visible," never as a confirmed rescue. Producers can also submit facts,
decisions, and explicit outcomes using `MemoryFormer.consider()`.

## Send memories to MARM

MARM must be installed and running on the same machine for the default URL.
Start it with `marm-memory start`. If authentication is enabled, supply the
server's existing key via `MARM_API_KEY` in the environment (never in Git).

```bash
# Capture locally, including when MARM is unavailable:
python3 -m experiments.ppal.run --log /tmp/ppal-transitions.jsonl --marm-outbox

# Deliver the pending memories:
python3 -m memory.sync
```

The outbox defaults to `~/.local/share/charlie/memory-outbox.sqlite3`.
Use `--marm-outbox PATH` and `memory.sync --outbox PATH` to choose another file.
The sync command accepts `--url http://127.0.0.1:8001` (server root, without
`/mcp`), `--timeout 10`, and `--limit 100`; `CHARLIE_MARM_URL` can set the URL.
On the Pi, enable automatic delivery for the current user:

```bash
bash memory/install_sync_timer.sh
systemctl --user status charlie-memory-sync.timer
```

The user timer invokes sync every minute after the first run. Its service reads
optional `~/.config/charlie/marm.env` with `MARM_API_KEY=...` and/or
`CHARLIE_MARM_URL=...` when the local MARM server requires those settings.
Only the current user's service reads this file; keep its permissions private.
The timer keeps retrying after an outage. Capture does no network I/O; the
control loop continues while the sync service delivers the queue.

`MarmOutbox` implements `MemoryStore.save()`. It queues the full memory record
and writes through MARM's public `POST /marm_log_entry`, explicitly scoped to
project `charlie` and session `charlie-experiences`. Source, confidence, importance,
selection reason, tags, evidence and formation time are preserved as readable
metadata in the entry. Optional project/session constructor arguments support
other producers without changing their memory-selection code.

Sync prints delivered, pending, log-only and error counts/status. A nonzero exit
means delivery failed; queued entries are retained. A `log_only` count means
MARM confirmed the durable log but returned no semantic-memory ID. The receipt
is retained and the log is not resent; inspect MARM's indexing before assuming
semantic recall is available.

Confirmed records remain locally for audit and are not resent after restart.
Saving the same candidate twice is idempotent locally. Delivery is **at least
once**, not exactly once: if the server writes but the connection fails before
acknowledgment, a later retry can duplicate the remote log. Each entry includes
a stable Charlie ID for reconciliation. New runs have distinct formation times.
The outbox serializes sync processes with a Linux file lock (Pi/Mint supported).

The adapter was checked against MARM 2.52.3 source commit
`f3a9c0749f57541f399476873835474356683d1b`, specifically
`endpoints/logging.py`, `core/models.py`, and `services/log_entry.py` in
[the upstream repository](https://github.com/Lyellr88/marm-memory).
Tests use a local HTTP server with that request/response contract; a live Pi
MARM install still needs an end-to-end write/recall check.

## Install on Charlie

From the Charlie repository:

```bash
bash memory/install_marm.sh
```

Then verify:

```bash
marm-memory doctor
marm-memory status
marm-memory projects status
```

MARM's local data belongs under `~/.marm`, not in this Git repository.

## Agent connection

For one local MCP client, STDIO is simplest:

```bash
codex mcp add marm-memory-stdio -- marm-mcp-stdio
```

For several Charlie agents sharing one memory:

```bash
marm-memory start --profile swarm
codex mcp add marm-memory --url http://localhost:8001/mcp
```

Keep HTTP bound to localhost unless we deliberately configure authentication and
network exposure.

## Next integration

Let the cognition layer retrieve relevant memories before planning. As real PPAL outcome/reward signals
arrive, feed them as explicit outcome experiences; keep raw transitions in PPAL.

## Task memory and head search

`MemoryGateway.remember(Experience(...))` queues selected events from any
Charlie task. `MemoryGateway.recall(query, limit=5)` returns project- and
session-scoped memories; callers should use a short timeout and fall back to
normal behavior when MARM is unavailable. It does not execute recalled text as
instructions.

`run_elegoo_head2.py` now records a face reacquired after a search, with a
run/attempt identifier, the initial search direction, and detector confidence.
This does not identify the person or prove the search caused the detection. At
startup it checks prior outcomes. Only three independent observations favoring
one direction by at least two can bias the initial sentry direction, and recent
face movement/last-seen direction continue to take priority. No actuator limits
or safety rules change. Other tasks can use the same gateway with their own
selection and conservative decision policy.

## Teaching the memory evaluator

`MemoryEvaluator` keeps all candidates in a separate local SQLite database at
`~/.local/share/charlie/memory-evaluation.sqlite3`. A rule-derived importance
score is the initial estimate. It retains routine observations as provisional
rather than discarding them. About five percent of low-priority candidates are
sampled for exploration (deterministically per candidate). No claim is promoted
merely because MARM recalled it.

When a task **actually uses** a memory, call
`gateway.record_decision(decision_id, task, [memory.evaluation_id])`. A task
with a measured comparison may later call
`gateway.assess_decision(decision_id, "helpful" | "harmful", evidence_id,
comparison)`. The evidence ID prevents the same result from being counted
again; multiple memories split one result's credit. Without a comparison,
the outcome remains an episode and does not prove the memory's usefulness.
Tasks can also call `gateway.feedback(memory_id, verdict, evidence_id, reason)`
for independently checked outcomes. These assessments revise category-level
selection, promote some previously overlooked candidates, and can make an
active memory dormant when contrary evidence accumulates. Later positive
evidence can restore it. All evidence is retained.

To inspect and teach Charlie manually:

```bash
python3 -m memory.evaluate list
python3 -m memory.evaluate feedback MEMORY_ID harmful \
  --evidence independent-check-1 --reason "The prediction failed in a comparable situation"
python3 -m memory.evaluate correct MEMORY_ID "Corrected fact" \
  --evidence correction-1 --reason "I checked the source"
```

A correction creates a new sourced memory and supersedes the old claim locally.
MARM remains an append-only archive, so Charlie filters superseded/dormant
memories from task recall rather than silently erasing the history. The
local evaluation database must be backed up alongside the MARM database and
outbox to retain these judgments. Category scores measure *usefulness*, not
whether a claim is factually true; a correction applies to that specific claim.

The Elegoo head uses this mechanism to record which memories contributed to a
chosen search preference. It does not grade the preference automatically: face
reacquisition alone is not a controlled comparison. A later task evaluator can
supply that evidence. PPAL-0's scripted transitions similarly cannot validate
a behavioral lesson; real PPAL outcomes can use the same interface.
