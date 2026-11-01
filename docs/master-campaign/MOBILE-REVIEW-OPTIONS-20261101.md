# Preserve review options in mobile startup

The normal primary/object entrypoint already forwards --human-questions and
--model-learning to its Executive child. The separate mobile ability entrypoint
constructs the same DevelopmentLifecycle directly and previously omitted those
options. This correction forwards only explicitly enabled options to that
existing lifecycle; defaults and all hardware admission remain unchanged.

Tests run all four option combinations through main.py's controlled mobile
replay. Exactly one lifecycle/Executive receives the shared journal, four
fixture observations are imported, synthetic observations create no human
question, and no capability activates. Normal question/answer/restart coverage
also passes. Focused result: 13 passed. Independent full and acquisition/mobile
contracts run on the published tree. No native/hardware/autonomy claim.

This is additive to #22 and inherits every source/campaign draft/no-merge hold.
No hardware, service, original notebook, model or policy is activated.
