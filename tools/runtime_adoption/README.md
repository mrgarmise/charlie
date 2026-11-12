# Runtime adoption tools

These commands only read source/explicit evidence and print JSON. They do not
replace `charlie_ops`, the local `~/charlie-ops` approval hierarchy, any service,
model provider or runtime owner. There is no apply/deploy/flash/enable command.
Any future mutating mode would need its own review and independently pinned,
signed operator authorization; this mission implements no such mode.

```
python -m tools.runtime_adoption inventory --baseline /home/five/charlie-runtime --candidate /home/five/charlie-runtime-adoption-v2 --ops /home/five/charlie-ops --protected /home/five/.local/share/charlie/development/learning-project-evidence.sqlite3
python -m tools.runtime_adoption plan --manifest docs/runtime-adoption/abilities.json
python -m tools.runtime_adoption release-manifest --manifest CANDIDATE.json
python -m tools.runtime_adoption validate --manifest CANDIDATE.json --inventory INVENTORY.json --receipts CI.json --source-root CHECKOUT --stage source
```

Use explicit original paths; do not redirect output into operational/evidence
locations. A caller may save reports in a new integration evidence directory.
`inventory` emits hashes, not secrets, arbitrary process arguments or environment.
It does not open serial/camera/HTTP, query Ollama, acquire locks, clear markers,
restart services, or create/migrate notebooks. Git optional locks are disabled.
Unknown/inaccessible native owners and installed firmware remain UNKNOWN.

`validate` requires exact SHA/tree/current clean identity, approved baseline pin,
unchanged guarded manual LLM source, preserved evidence, backup identity,
explicit dependency closure, fresh successful exact-head independent CI and
artifact hashes. Master/release/enablement plans additionally require an Ed25519
approval record and operator-pinned public-key digest (`--approval`, `--trust-key`,
`--trust-key-sha256`). No key from an approval document is trusted implicitly.
Canonical signature bytes are UTF-8 JSON with sorted keys and compact separators.
Review records bind schema `charlie-adoption-approval-v2`, candidate SHA/tree,
stage, sorted ability IDs, named reviewer, issued/expiry times (<=7 days).
Verification requires OpenSSL, never a signing key or credential activation.
Only tests generate ephemeral clearly labeled fixture keys.

A successful validation is **eligibility for operator review**, never operational
permission. Native release/enablement needs independently reviewed source-bound
applicable receipts, actual firmware/STOP/ACK/TTL and authentic-question gates.
One ability is selected per enablement plan. Disabled firmware/scheduler source is
not an instruction to install, flash or start it. Current real native receipts
are absent, so those plans refuse. `release-manifest` emits an unapproved,
not-installed BOM; it does not confer approval by serializing a manifest.

Tests: `python -m pytest tests/test_runtime_adoption.py -q`. The CI workflow also
runs baseline manual consultation/historical/generalized/native-negative checks,
contracts, the complete suite and real-browser checks. Native fault timing is
not proved by those software tests.
