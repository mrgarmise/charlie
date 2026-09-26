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

MARM's writes are explicit, so Charlie's future cognition layer should contain a
memory-former that decides which working experiences deserve promotion.

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

## Future integration

The cognition/agent layer should use MARM recall before planning when past
experience may matter, and write a concise durable memory after significant
outcomes. PPAL can later add a promotion adapter that summarizes selected
transitions/episodes instead of copying its JSONL stream wholesale.
