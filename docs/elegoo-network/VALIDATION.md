# Software validation ledger

Increment 1: host simulations cover LAN priority, stale IP, missing/unreachable
secondary adapter, explicit primary fallback, failed restoration, loss during
provision, bad credentials, wrong identity/certificate, target mismatch, concurrency,
authorization expiry/replay, passive loss/backoff, private storage and secret output.
Dashboard HTTP tests exercise existing authentication and dedicated network-token
isolation with bounded bodies. All endpoints and NetworkManager are simulated.
No physical device or live networking action is part of these tests.

Initial restricted run: 56 passed, 4 loopback-denial skips. Architecture contracts:
131 passed. Added routing-profile and absolute request-deadline hardening afterward;
focused restricted run: 29 passed, 1 loopback skip. Independent CI is configured in
.github/workflows/elegoo-network.yml and runs real loopback HTTP tests and contracts.
See draft PR for exact published commit and CI results. A passing host suite is not
hardware acceptance, installed source compatibility or physical motor stopping.

Remaining: native D-Bus/profile semantics, shared-radio AP channel changes and real
TCP/UART safety must be witnessed through OPERATOR.md. No Arduino toolchain/image
is available; ESP32 image build and size remain explicitly unverified.

Independent first increment exact commit 86c8b0c6a95175c3e102fee6662a027a5343a282:
https://github.com/mrgarmise/charlie/actions/runs/42673187229 — 60 focused passed,
131 contracts passed. Artifact 13699891115 ZIP SHA256
1a86a1e80fd434d3888edeb717adf111aede023771bdcfc83461f08f6cb53769.
The inherited Mobile Body workflow run 42673186780 reports failure with zero jobs;
no test results are available from it. It is not counted as a pass. Dedicated
network validation now also runs the full suite to obtain explicit regression
evidence independently of that unavailable inherited workflow.

Second increment strengthens restoration with a saved address/route/DNS snapshot,
rejects DHCP route injection and exposes only fresh authenticated location hints
for existing owners. These hints never rebind cameras or control sockets or grant
motion; the existing owner must explicitly consume them within its normal lifecycle.
