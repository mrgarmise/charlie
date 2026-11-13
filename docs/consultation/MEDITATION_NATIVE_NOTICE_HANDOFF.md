# Native meditation scheduler and RP2040 notice handoff

Mission: draft PR #37, building on #36. Implementation: draft PR #38.
This is a source candidate, not a native qualification or deployment receipt.
The owner's standing authorization is implemented; no fresh per-question consent
is required within an independently admitted window. All native entry points are
explicit opt-in. Example policy and qualification both refuse activation.

## Implemented behavior

The existing Learning Executive reserves a finite meditation window through a
separate root Linux broker. The broker verifies a protected inventory, actual
systemd owners, physical-device descriptors, traffic, deadlines, resources,
client identity and the existing runtime flock. Unknown state refuses admission.
An independent root guardian receives the same flock through SCM_RIGHTS before
PREPARING can be acknowledged. It survives broker or model MainPID death and
holds exclusion until the native model cgroup is independently empty.

The existing serial owner exports `DisplayBridge`; it does not open another port.
RP2040 renders a smooth pixel scroll of `MEDITATING PLEASE WAIT`, acknowledges
session/slot/sequence/phase and expires it on an independent device TTL. Ordinary
labels resume afterward. STOP, calibration, error and link loss override the
notice. Refresh cannot extend the root reservation. An unsupported installed
firmware therefore refuses native admission rather than silently substituting a
host-only warning.

The actual meditation algorithm runs inside the reservation. A window with no
eligible question still warns and meditates without starting the model. At most
one eligible original-source question can use the existing generalized selector
and OperationalProvider. Root independently rediscovers the exact context from
sources outside the Executive's write domain. Manual consultation remains on its
existing approval, user-service and HTTP path. Historical qualification remains
unchanged. Answers remain unverified hypotheses in a separate decision journal;
original evidence is never rewritten.

The native model has a distinct UID, private network namespace, fixed binary and
model digest, fixed request envelope, cgroup resource limits and a preset finite
systemd RuntimeMaxSec. The launcher verifies actual activation plus runtime and
stop bounds fit the absolute reservation before model exec. RuntimeMaxSec is not
changed after startup: systemd's transient setter only accepts these service
properties while the unit is a stub ([systemd source](https://github.com/systemd/systemd/blob/v257/src/core/dbus-service.c)).
The Executive has no direct native model endpoint. Root proxy admits one query
per slot and durably latches submission before dispatch. Four/day, one-hour
cooldown, commission replay and question replay checks are persistent. An
uncertain request is never automatically retried, including after restart.

Resource/owner/policy/deadline monitoring and notice refresh continue during
prewarm. Emergency cancellation kills only the dedicated native model unit
before waiting for normal dispatch. Cleanup verifies actual cgroup emptiness;
clock expiry and a successful stop command alone are insufficient. Clearing is
acknowledged when possible; display loss is recorded as pending independent TTL,
never fabricated as verified clear. Ordinary human request IDs are durably
queued and resume only after independent cleanup. Urgent primary work bypasses
that queue. `primary-done` rechecks physical owners before clearing the STOP
latch. It cannot clear uncertain consultation history.

## Review and validation

See [architecture and priorities](native-notice/ARCHITECTURE.md),
[qualification procedure](native-notice/PI_NATIVE_QUALIFICATION.md), and
[validation evidence](native-notice/VALIDATION.md).
The independent CI workflow executes focused regressions, 131 unified contracts,
and the full suite with normal loopback support and retained JUnit artifacts.
Host tests exercise scheduler behavior with explicitly injected test drivers,
real unprivileged flock/FD transfer, mock systemd/identity probes, the existing
provider lifecycle, display protocol and the real Executive integration. They
do not establish root namespace isolation, physical display visibility, actual
Pi resource behavior, or native kernel cutoff. Those remain qualification work.

## Operational boundary and rollback

No service was installed/enabled/started; no model operation, firmware flash,
motion, merge or deployment was performed. The approved runtime remains at
`d3dca9059233b5f054c4f6f9979085b1422f9674`; launchers, pin, original ledgers and
manual consultation assets remain outside this change. The current original
ledger's 27 held/paused/blocked scopes are not authority to generate a query.
A genuine eligible question must arise from original evidence; do not manufacture
one for acceptance.

Native activation remains prohibited until the separately reviewed qualification
receipt identifies exact code, model and owner inventory. Templates contain
placeholders and disabled flags; copying them is not qualification. Revoke only
the native policy, drain only native units, verify cgroup emptiness and preserve
unknown-completion records during a future authorized rollback. Never clear a
latch to obtain a retry. The approved operational checkout needs no rollback
because this work does not modify it.
