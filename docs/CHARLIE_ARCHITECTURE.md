# Charlie Architecture

Charlie is an embodied AI agent, not a single model.

```text
environment
    |
    v
perception  ---> working state
    |              |
    |              v
    +--------> cognition / planner <--------> durable memory (MARM)
                   |                              ^
                   v                              |
             goals / intent                      |
                   |                              |
                   v                              |
             learning (PPAL) --------------------+
                   |
                   v
                action
                   |
                   v
        chassis / head / display / controller
```

## Responsibilities

**Perception** turns cameras, sensors, recognition, and other inputs into usable
state.

**Cognition/planning** decides what matters and what Charlie should do. An LLM
can be one reasoning component here; the LLM is not Charlie.

**Durable memory (MARM)** preserves retrievable history across processes,
sessions, models, and future upgrades. This is where Charlie's continuity lives.

**PPAL** learns action policy and behavior from experience. Its local
`experiments/ppal/memory.py` remains appropriate for transition logs; selected
episodes can later be promoted to durable memory.

**Action** converts intent into hardware/software commands.

This boundary lets us replace a vision model, LLM, PPAL version, chassis, or
controller without replacing Charlie's accumulated history.

## Asynchronous human information interface (draft)

The existing `memory.learning_projects.LearningExecutive` can submit typed,
evidence-derived information needs through `HumanInteractionGateway`.
Question lifecycle, human answers and requester review observations are additive
records in the existing `EvidenceJournal`; no second Executive, memory store,
scheduler or actuator authority is created. The loopback web service renders
those records and accepts schema-validated, source-attributed, fallible answers.
Normal producer/consumer attachment and native acceptance remain pending.
See [contract and operator runbook](human-interaction/README.md) and
[acceptance receipts](human-interaction/ACCEPTANCE.md). PR #13's newer canonical
sensory ownership architecture must be preserved when this focused branch is
reconciled; this addition does not replace that unmerged architecture.
