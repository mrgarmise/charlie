# Agent Factory continuation acceptance

Charlie PR #46 continued from `d9937947f37517cc409e8e83147e9909871c0ff3`. Dog PR #5 supplies the unchanged simulation at `f3cec3a4c3aa93582e4540f0c4b5c1c6004e9f43` on Dog PR #3. The optional visual research checkout is Charlie `c192907625ba8ad640fbb5eae3961cbae63893ed`. The original report records the prior UEL and model hashes. Charlie's development checkout does not update the approved runtime, protected scheduler, deployed hardware or release manifest.

| Original and continuation requirement | Status | Source and verification |
| --- | --- | --- |
| Existing Executive, capability intake and model fallback | PARTIAL | The opt-in subclass commissions a root or ranks trusted alternatives. The CLI supplies goals. The runtime goal-intake path, live structured model adapter and model timeout are outstanding. |
| Organization contracts and bounded delegation | PASS | Versioned registry and JSON proposals, scoped children, validation, transactional expansion, 12 nodes and bounded ancestry, tested in `test_agent_factory.py`. |
| Durable lifecycle and attempt budgets | PARTIAL | Leased attempts, pause/resume, cancellation, restart fencing, atomic precharge and retirement evidence. Root budget is work units. Broader scheduling concurrency, memory/storage admission, and trial-level restart inside a worker remain pending. |
| Existing pub/sub and evidence | PASS | `LifecyclePublication` projects ordered ledger transitions onto the existing bounded StimulusBus observation stream. Subscribers can miss records and recover from the SQLite cursor. The existing EvidenceJournal retains terminal lineage. |
| Existing protected scheduler and reflection binding | PARTIAL | The native scheduler is an exact-Qwen consultation gate tied to kernel leases and display acknowledgement. Development work still executes through the factory worker loop. A separate generic development admission interface and connection to the normal reflection turn remain pending. No consultation slot is repurposed. |
| Dog organization and valid objective outcome | PASS | The root delegates replay, transfer and search supervisors, and search delegates evaluation. Transfer evidence selects 16 instead of eight training attempts. The 24 total attempts finish with no accepted policy and no physical claim. |
| Rollover success and trial-count target | SUPERSEDED | The revised mission accepts a valid negative simulation result. |
| Distinct existing capability | PASS | The UEL visual pan/tilt rig executes its original held-out trajectory evaluator. Calibrated and fixed baseline teams use the same scenario and work units. |
| Persistent organizational learning | PARTIAL | A negative simulator outcome changes the next selection after restart. Learned selection yields 0.206 px held-out RMS against 70.590 px from the frozen selection. This is one known simulated delay class, and the evidence does not establish generalization across new calibration regimes. |
| Visual digital twin, Discovery Engine and skill registry | PARTIAL | Existing visual replay and rig adapters execute. No Discovery Engine adapter or candidate registry write was exercised. Synthetic alignment supplies no physical calibration. |
| Operator controls and dashboard | PARTIAL | Authenticated existing read-only Missions snapshot, pause/resume/cancel and deterministic CLI explanation. A continuously pushed dashboard and disconnect recovery under experiment are pending. |
| Isolation and independent acceptance | PARTIAL | Trusted fixed command, process group termination, CPU/address-space limits and bounded wall time. OS device/network isolation is unverified. The local namespace probe failed with `NETLINK_ROUTE socket: Operation not permitted`. No native qualification or hardware is required or claimed. |
| Draft delivery and rollback | PASS | PR #46 and Dog #5 remain drafts. Stop or discard the disposable development checkout, preserving its exported evidence. There is no deployed change to undo. |

## Reproduce

From the Charlie development checkout with the visual and Dog checkouts above, use the setup in [REPORT.md](REPORT.md). The same development database is required to compare retained and frozen selection.

```sh
python -m tools.agent_factory_demo /tmp/agent-completion.sqlite rollover dynamic-rollover
python -m tools.agent_factory_demo /tmp/agent-completion.sqlite baseline rig
python -m tools.agent_factory_demo /tmp/agent-completion.sqlite learned rig
python -m tools.agent_factory_demo /tmp/agent-completion.sqlite frozen rig --frozen
python -m tools.agent_factory_demo /tmp/agent-completion.sqlite rollover explain
```

Run `pause`, `resume`, or `cancel` with the same database and mission identifier. After resuming, repeat the original launch command. The active Dog subprocess checks its lease and terminates its process group when interrupted. Retried work spends its original allocation again.

The successful development sequence took 1.59 seconds for Dog and 0.37–0.43 seconds per rig mission on the Linux development host, peaking at 56,740 KiB RSS and leaving a 90,112-byte ledger. These are host measurements. The simultaneous runtime headroom and latency limits on the Pi remain unmeasured. The [evidence export](completion-evidence.json) records the selected team, dependency digests, trial seeds and separately evaluated outcomes.

The next integration boundary is a generic admission hook for the actual development lifecycle and kernel-denied device/network access. Neither requires changing Dog's outcome or authorizing equipment.
