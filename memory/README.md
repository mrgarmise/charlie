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

`JsonlStore` is a local staging backend with a `MemoryStore` protocol. Point it
at a persistent path outside the repository when running on Charlie. The MARM
storage adapter can implement the same `save()` method once its write API and
local installation are verified. JSONL is append-only; repeated runs append
records, so the consuming store should deduplicate by source/evidence/subject.

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

Connect a verified MARM writer to `MemoryStore`, and let the cognition layer
retrieve relevant memories before planning. As real PPAL outcome/reward signals
arrive, feed them as explicit outcome experiences; keep raw transitions in PPAL.
