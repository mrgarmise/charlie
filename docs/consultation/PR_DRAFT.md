# Add bounded safe-idle activation for Executive local consultation

Adds an additional default-off approval gate for real local Qwen3 1.7B calls from
Charlie's existing Executive worker. Plain `--llm-consultation` stays shadow-only.
Admission requires independent native prerequisites, consent, a finite safe-idle
window, exact resident model/service identity and kernel resource bounds. There
is no prewarm, model switch, remote fallback or actuator capability. Answers remain
unverified; unknown completion is latched across provider restarts, and successful
unload/immutable journal retention are acknowledged before clearing the latch.

This is a stacked continuation of #27 at b0c04ad, preserving #23/#26/#27 and the
approved operational runtime. Ordinary time-critical sensing is not supported by
this real transport path because stock Ollama lacks atomic resident-only admission.
Native service qualification, exact approved-runtime tree reconciliation and
stationary acceptance remain pending. No merge, deployment or hardware authority.

Local clean-checkout validation of cb4879d: 119 consultation tests, 131 contracts,
1846 full-suite passes with 27 skips and zero failures/errors. The final evidence
commit changes documentation/evidence only. Earlier failed runs remain recorded;
GitHub CI must be checked after publication and is not yet claimed passed.

Implementation/evidence: docs/consultation/OPERATIONAL_REPORT.md
Native acceptance and rollback: docs/consultation/OPERATIONAL_ACCEPTANCE.md
Separate promotion manifest: docs/consultation/PROMOTION_RECONCILIATION.md
