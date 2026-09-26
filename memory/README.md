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
Run sync again after an outage. Capture does no network I/O; a control loop can
keep running while an independent sync process delivers the queue.

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
