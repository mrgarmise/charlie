# Batch A supervised development release proposal

Charlie’s owner, administrator and designated reviewer may make one local
approval for the fixed Batch A stationary recognition profile. This proposal
requires explicit owner adoption before use. Signed release and enablement
remain the existing route for the canonical launcher. Autonomous operation,
unattended services, firmware changes, consultation and actuation gain no
authority through this profile.

The controller reuses the native Pico identity and restoration records, the
existing recognition logs, and the verified isolated restore rehearsal that
preserved all 4,648 approved records. The owner evaluates the recorded evidence
and residual root/dialout access in the manually supervised scope. The
remaining targeted N1 session must demonstrate live ACK and visible clear,
observational STOP, device release, thermal/resources and guarded transport.
Offline checks and older-profile logs supply separate evidence.

## Use after explicit policy adoption

From the on-site foreground terminal, define:

```sh
ctl() {
  env -i HOME=/home/five PATH=/usr/bin:/bin \
    /home/five/Projects/charlie/.venv/bin/python -IB \
    /home/five/charlie-supervised-development/tools/stationary_ctl.py "$@"
}
```

1. Keep physical motion prohibited and independently isolate actuator power.
   With the approved runtime stopped, run `ctl supervised-qualify` and confirm
   isolation at its prompt. Observe the missing N1 checks and retain its
   successful exact-profile log. Keep the original device and STOP procedure.
2. Review the printed bindings and the observed N1 checks. Run
   `ctl supervised-approve --qualification-log /absolute/path/to/the/log` and
   type the explicit owner approval once. The local private record binds the
   exact clean controller and candidate, host and boot, Pico USB identity,
   Hailo PCI/driver identity, device nodes, model, notebooks and evidence
   hashes. The owner confirms the installed firmware has not changed since
   its verified readback. The controller does not interrupt the Pico to
   remeasure firmware. A changed boot or hardware identity invalidates the record.
3. Run `ctl supervised-launch` manually. Confirm on-site supervision and motion
   power isolation at each session. The controller rechecks lineage, notebook
   integrity, hardware identity, device idleness and evidence. Sessions share
   the runtime lock and fixed guarded transport/STOP code, run at most 90 seconds
   of recognition with a 150-second application deadline, and use copied state.
   State and logs are retained as development evidence, separate from the live
   notebooks. A foreground interruption or incomplete cleanup blocks retries
   under that approval. Retain the failure record for review.

Stop the development session before returning to the existing launcher.
The canonical launcher and fallback are preserved, so rollback needs no
runtime replacement. To withdraw an approval while stopped, preserve the
private approval JSON as a dated archive outside the active approval path.
Investigate a failed attempt before issuing another owner decision. Root
and authorized dialout processes retain potential direct device access.
Changes to authority, firmware or supervision require requalification.

The existing candidate consultation and audience/retention qualification is
outside this recognition-only release. Retain its separate admission and
evidence requirements. The supervised command grants no Executive status
endpoint or consultation authorization.
