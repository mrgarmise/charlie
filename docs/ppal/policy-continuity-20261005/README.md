# PPAL qualified-policy continuity — 2026-10-05

Continuation of ALA-2 on `feature/agency-first-self`, directly based on verified
published checkpoint `da8d603664e7dc56a0f2a9dea824b4da985a976e`.
The architecture, normal Learning Executive, original notebook and core chooser
remain intact. No camera, controller, firmware or physical policy was activated.

## Reproduced defects and resulting behavior

`reproduced.txt` and `reproduced.xml` preserve all four failing regressions on
the published parent, before functional changes:

* Restoring a previous policy replaced its original bounded activation grant with
  a rollback request, making the restored manifest unloadable. Rollback now
  retains the original grant and records the separate rollback authorization and
  restored activation identity. Existing qualification and artifact integrity are
  checked before restoration; an offline rollback cannot restore physical authority.
  Repeating the same rollback request is idempotent rather than subsequently
  removing the restored version.
  An authorization-only rollback revokes the replaced activation grant while
  retaining the restored proposal, so a removed grant cannot be silently reused.
* Reusing an active proposal ignored changed authority. Every requested domain
  is now checked; changed grants pass the existing qualification/activation gates.
  A missing domain, physical readiness or compatible runtime produces a durable
  blocked acquisition request, without replacing the active manifest or silently
  inheriting the old grant. Repeated requests are deduplicated.
* The synthetic normal PPAL entry point required a manually selected manifest.
  Both existing PPAL entry points now share a startup-only loader which discovers
  `CHARLIE_LEARNING_STATE/ppal-policy.json`. An explicit path takes precedence.
  Invalid artifacts or corrupt SQLite notebooks retain baseline behavior and
  report the error. The closed-loop diary includes `policy_load_error`.

The five core modules used for policy runtime qualification have not changed.
There is no meditation, Executive turn, journal search, policy load or network
operation added to `Forebrain.update()` or `Hindbrain.decide()`. Previous measured
decision-latency distributions remain applicable to the unchanged decision code;
no new Pi latency or physical performance claim is made here.

## Evidence and provenance

All new policy contracts are explicitly constructed interface fixtures. They use
the existing controlled dataset and original committed prediction references,
but the strategic contracts/evaluations themselves are labeled fixtures. They
are not authentic Charlie-originated strategic discoveries or independently
measured Robotron improvements.

Acceptance runs the actual `experiments.ppal.run_closed_loop` synthetic entry
point twice without a policy argument. It discovers the persisted qualified
fixture, selects the fixture's survival goal, records the matching activation
identity, and leaves the evidence notebook unchanged. Existing acceptance also
covers the autonomous normal-application developmental cycle, motion candidate
qualification, changed offline decisions, immediate-threat override, shot-model
compatibility and restart. No intermediate developmental stages are manually
commissioned by the new entry-point test.

The authentic retained notebook, original October collision evidence, October 4
experience, captures, commissions and earlier failure records are untouched.
See `../qualified-policy-20261005/README.md` for the prior authentic audit,
autonomous controlled cycle, measured decision distributions and remaining
evidence dependencies. Authentic retained investigations remain unqualified;
complete-game score improvement remains UNKNOWN and ALA-2 remains open.

## Validation

Final focused acceptance: **17 passed in 4.63 seconds**, preserved in
`focused.txt` and `focused.xml`. Final complete independently available offline
suite: **559 passed, 19 skipped in 88.79 seconds**, preserved in `final.txt` and
`final.xml.gz`. All 19 skips require unavailable Torch. The final suite ran on
Linux x86_64 against the final functional code; it includes the existing normal
application developmental-loop acceptance as well as the new continuity tests.
`full*.xml.gz` retain intermediate successful runs, not the final-code authority.
Diff checks, Python compilation and guarded shell syntax checks passed.

Reproduce with the installed project dependencies:

```sh
python -m pytest tests/test_ppal_policy_continuity.py tests/test_qualified_ppal_policy.py -q
CHARLIE_IDENTITY_ACCEPTANCE_ROOT=/path/to/preserved/identity-evidence python -m pytest tests -q -rs
```

## Normal startup and guarded native acceptance

Set `CHARLIE_LEARNING_STATE` to the existing developmental state. Normal
`main.py` owns developmental turns; existing PPAL entry points load qualified
results locally at startup. Synthetic PPAL uses `RecordingSink`, never an arcade
transport. Camera/physical use still requires the separate existing capability
authorization and independently measured candidate/runtime readiness.

On the Pi, retain the existing notebook and run the established guarded updater
and `bash tools/accept_episode_identity_pi.sh <exact-published-SHA>` as documented
in the parent acceptance instructions. The script now includes the continuity
regressions. It exports the original history, checks architecture and revision,
runs unarmed tests, executes two bounded normal-app runs against the original
state, and verifies durable progress/restart. It grants no deployment authority.
Do not overwrite dirty native changes or start with an empty notebook. A pending
advancing investigation is not a completed steady-state acceptance; inspect the
retained progress report. Prior interrupted native acceptance remains a failure
record, not a pass. Native validation of this checkpoint is pending.

Physical acceptance requires separate explicit authorization for complete games,
controller/movement execution and the particular qualified policy activation,
with camera ownership, readiness and rollback checks. Complete-game score must
be independently measured under comparable frozen baseline/candidate conditions;
software fixture goals, survival or prediction metrics cannot replace that test.
