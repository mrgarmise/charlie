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
