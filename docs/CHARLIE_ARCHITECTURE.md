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
