# Stationary worktree cutover

## Operator handoff, 19 November 2026

The reported 229 observations qualified the candidate's original recognition path. The later 354 observations exercised a separate guarded launcher. Charlie's last reported normal entry is `~/charlie-ops/start-stationary.sh`, bound to the original worktree. This PR adds an external controller. Checking out the controller has no activation effect. GitHub source-only merge #39 is the parent baseline for this change.

| Identity | Value |
|---|---|
| Candidate SHA / tree | `d7cabfc65b6c25d5d71af7ce5141ab5de828ba4f` / `53f0d945aed1eff2c147612d054917e83dcb1d4f` |
| Master source merge | `57e07eb850b139eda6a5f1a930cc0ef7b5bf5f18` |
| Approved SHA / tree | `d3dca9059233b5f054c4f6f9979085b1422f9674` / `72cd9e4eba5939c181ae88d6ed03d5bbc50527c4` |
| Original pin, launcher and consultation hashes | Constants PIN, ORIGINAL and CONSULT in `tools/runtime_adoption/stationary.py`; checked against preserved controls on every admission |
| Models and firmware | Models remain external. The controller verifies the current manifest and actual HEF before launch. Firmware identification is a native N0 evidence item. No firmware writes. |
| Backup and model hashes | Pending native inspection. Exact digests are written into the request. Existing logs, backup and ledger stay at their original paths. |

## Operator commands

Use a separate, clean checkout of this controller at `~/charlie-activation-control`. Keep it pinned to the independently reviewed PR commit for the lifetime of its approval. The candidate and approved worktrees stay in place. Start with a read-only report.

```bash
ctl() { /usr/bin/python3 -IB "$HOME/charlie-activation-control/tools/stationary_ctl.py" "$@"; }
A=stationary.object_recognition.elegoo_hailo_pico
B=executive.read_only_status
ctl plan
```

`ctl qualify-evidence` checks each JSON observation's source, candidate revision, HEF, frame and motion fields, and counts distinct frames. The original 229-observation log is read directly from `~/charlie-candidate-acceptance/20261116T160554Z/session.log`, verified against its pinned digest and qualification record, and paired with the original regular `exit-code.txt` containing `0`; it has no inline exit footer. Its separate exit record's digest is captured in the evidence report. The later 354-observation operational log must retain its `END ... exit=0` footer. Neither historical evidence file is edited. The 354 log receives a measured digest for the reviewer. No log parser establishes Pico display ACK, exposure timing, host-wide idle or pose. If the Pi has a different log schema, retain the original files and adapt the importer against those bytes.

While stopped, `ctl restore-rehearsal` takes the original ops lock, creates unique backups of both notebooks and operational controls, restores into an isolated directory, and checks SQLite and file identities. It never restores into a working state. The original release archive stays intact. An independent reviewer adds any other applicable scoped backups, including calibration, models, firmware identity, service/environment constraints and manual-consultation policy. Reconcile diverged history before release. The controller checks every original Executive record is present in the separate Batch A notebook.

### Qualification-only native session before release approval

The controller also exposes an **unsigned, supervised N1 measurement command**.
This command does not bypass any release gates: it requires the normal launcher
to be exactly its preserved original bytes, validates source/model and state
lineage, enforces idle ownership and device exclusion under the same runtime
lock, and runs exactly the candidate single-ELEGOO feeder with the same
process-local transport and serial allowlists as the proposed normal launcher.
It writes into a new **copied** Batch A state under `promotion-backups/`,
not either live notebook. It leaves `start-stationary.sh` and `approved.sha`
unchanged and does not issue an approval. Keep all other software and physical
motion disabled; keep hands clear of moving parts, and terminate with Ctrl+C
if unexpected behavior occurs.

Check out the exact reviewed controller commit in a clean
`~/charlie-activation-control` worktree first and rerun its focused tests.
On the Pi's foreground SSH terminal, after positively authorizing this
stationary camera/Hailo/Pico qualification, run:

```bash
env -i HOME=/home/five PATH=/usr/bin:/bin \
  /home/five/Projects/charlie/.venv/bin/python -IB \
  /home/five/charlie-activation-control/tools/stationary_ctl.py qualify-native
```

Expect one bounded 90-second recognition session, automatic 150-second
wall deadline, a new `stationary-qualification-*.log`, a distinct
qualifying state directory, a success footer and a JSON evidence summary.
If the program refuses, fails, or is interrupted, **do not sign an N1
receipt**. Preserve the log and assess the failure. For successful output,
an independent reviewer must examine the bounded profile, the live Pico
display, process/thermal/STOP observations, network/serial restrictions and
the original unchanged launcher. In particular, a success footer and
object observations alone do **not** establish RP2040 ACK or comprehensive
host-level privilege isolation.

The command runs without signed release approval precisely because it is
a manual qualification measurement, not normal operational enablement.
There is no unattended restart, persistent authorization, or service
installation. An untrusted checkout or uncontrolled actor must not be
given the ability to execute arbitrary Python with device privileges.

### Review packet

Use the existing eligible release reviewer and pinned Ed25519 public key. Have the host administrator bind that identity in root-owned `/etc/charlie/stationary-reviewer.pem` and `stationary-reviewer.json` (fields `reviewer` and `sha256`). Only the public key belongs on this path. Preserve review versions outside the active packet directory.

Place inputs under `~/charlie-ops/stationary-review/`:

- `ci.json` is the exact candidate CI receipt array accepted by the existing adoption validator. Its seven-day freshness rules apply. `controller-ci.json` records the independently verified controller commit, tree, successful conclusion, completed_at epoch and GitHub Actions run URL. Review artifacts against their hashes.
- `inputs.json` supplies an array of absolute `backup_manifests` paths, a `restore_receipt` path and a `gate_receipts` object mapping capability ID, then gate ID, to the individual receipt path. Each native receipt has `ability`, `gate`, `candidate` (SHA and tree), `controller_sha`, `status`, `independent_review` and an `artifacts` object mapping absolute measurement paths to SHA-256. Supply original bytes for each artifact. Protected files must remain immutable. Use snapshots for changing state.
- The independently reviewed restore receipt uses the existing `backup_qualification` schema, exact candidate and backup manifest digests. Retain the rehearsal's observations separately. Include the tested restore and explicit scoped compatibility determination.
- N0 reconciles hardware/boot, installed identities, visible and privileged owners, exact interpreter and alternate execution paths. N1 covers stationary owner/resource/thermal/STOP, scoped recognition and the controller's wire and camera restrictions. N2 verifies state lineage, restart, cleanup, manual consultation, audience and retention. B requires N0/N1/N5 only for its local read-only output. N5 pre-cutover records a scoped accepted measurement and the reviewer’s decision on transfer to this exact controller. Post-switch normal-launch verification is a separate step. Both original and candidate manual LLM native results remain **pending** here. Launch the historical tool only under its existing operator procedure. Keep autonomous consultations, guardian and scheduler disabled.
- To produce a proposal for release use `ctl request`. For one ability use `ctl request "$A"`. Save the outputs as `manifest.json` and `$A.manifest.json` in a fresh packet. Inspect before installing the active packet. Use independently signed adoption-v2 records `release.json` (stage release, abilities []) and `$A.json` (stage enablement, abilities [A]). The existing validator verifies the canonical manifest digest, exact scope and expiry. No program here issues approvals. Preserve A's signed records when adding B.
- If the reviewer needs an additional measurement of the narrower single-camera and restricted-transport profile, obtain supervised native qualification before signing. If the installed interpreter/host permits an unapproved alternate actor to manipulate devices, withhold N0. A Python policy limits the reviewed program; a person with independent raw-device privileges remains a distinct host authority.

### Switch and verification

After completing review and receiving separate operational cutover authorization, execute the single supervised transaction in a foreground terminal:

```bash
ctl enable "$A" && ~/charlie-ops/start-stationary.sh && ctl verify
```

The enable step is the only installation transaction. It checks both signed reviews, source and controller identities, controls, logs, model, notebook lineage, backup/CI and device exclusion under the existing runtime lock. A single atomic rename selects the signed capability set in the normal launcher. The launch command remains **`~/charlie-ops/start-stationary.sh`**. The launcher rejects all arguments and starts the qualified venv in a clean environment. Keep the terminal in the foreground. On the Pi, run one supervised session, then `ctl verify`. Verification checks the normal entry, boot, controller, post-switch session identity, distinct authentic observations, clean Executive shutdown, residual same-user workers and device release. Each physical session creates an exclusive pending record bound to the current launcher and signed grants. A failed or interrupted session retains the record and refuses another launch under the same decisions. Roll back or collect new independent review after diagnosis.

`ctl status` reports selected versus reviewed; `ctl verify` supplies the measured normal-session result. `ctl disable "$B"` retains A. `ctl rollback` restores the original launcher bytes. If the controller, candidate or active registry is damaged, use the independent recovery script from the separately preserved reviewed controller source: `bash ~/charlie-activation-control/tools/stationary_rollback.sh`. Preserve a copy alongside the approved operational controls before cutover. It needs neither candidate code nor review files. Neither rollback runs hardware or changes the pin, either notebook, manual consultation or a service.

## Capability ledger

| Scope | Ledger provenance | Evidence and authority |
|---|---|---|
| A recognition and its shared frame observation | pr-04, pr-10 source only, pr-11, pr-12 plumbing, pr-25 label rendering | Reported 229 and 354, original log bytes pending. Single ELEGOO feeder, Hailo inference, RP2040 labels plus STOP/session/heartbeat. No motion backend. Normal enablement pending. |
| Sensory bounded history, depth | pr-12, pr-13 | No standalone grant. Needs independent retention, provenance and resource tests. |
| B local Executive status | pr-04, pr-21 | Controller supports an independently reviewed local file read while stationary A is selected. No browser, listener, dashboard or human-question grant. Review and enable with the same one-ability commands using B. Roll back B separately. Other B interfaces remain pending. |
| C learning/diagnostics | pr-06–09, pr-15, pr-22 | Source only. Require method-specific evidence provenance, resource guards and durable history. Model promotion, gameplay and unbounded investigations denied. |
| D manual consultation | pr-27, pr-33 | Previously accepted original launcher and source preserved. Candidate hardware/native regression pending. |
| D autonomous consultation | pr-35–38 | Denied. Requires separate eligible-question, independent scheduler, acknowledged notice and native lifecycle qualification. |
| E actuation / firmware / remote control | pr-10, pr-16, pr-26, pr-28–32 | Denied. Requires separately designed enforcement, physical STOP, ownership, rollback and applicable supervised trials. |
| All other ledger abilities | remaining PR and local entries | Source presence grants nothing. Introduce an executable scoped adapter and independently qualify it before adding it to the CLI. |

The candidate's plain object branch normally starts both feeders and a spawned Executive worker. Optional face or dashboard switches can select actuator-owning branches. The controller supplies its own fixed arguments, limits the feeder to ELEGOO and preserves the existing Executive. The parent restricts camera GETs and IP/port, rejects listening/datagrams and limits pyserial writes to the display protocol. Spawned Executive has no network or serial grant. Hash-bound approvals include both application and controller versions. Requalify changed code, hardware, model, boot or authority. This release does not select a managed archive, modify the older launcher for manual consultation, or install any system service.
