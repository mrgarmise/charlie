# Charlie comparison experiments

Run the synthetic example from the repository root:

```bash
python3 -m experiments.comparison.demo --output /tmp/charlie-comparison-001
```

Choose a new directory for each run. `plan.json` records the hypothesis, context,
policy versions/names, bounded metrics, useful effect size, trial count, and
random seed before any trials. `trials.jsonl` retains results and failures;
`report.json` reports better, worse, or inconclusive. The example is synthetic
and supplies no evidence about Robotron or a physical search.

## Add a task adapter

Implement `version`, `reset(seed) -> initial_state_fingerprint`, and
`run(policy) -> {metric_name: value}`. Each call to reset must restore the entire
relevant state, including policy memory/RNG, and run must finish after a fixed
horizon. Freeze the compared policies during testing. Include policy versions
in the plan's baseline/candidate names. The adapter is responsible for verifying
actual state restoration; an arbitrary matching fingerprint is not proof.

The runner uses distinct seeds, resets before each arm, randomizes baseline vs
candidate order, validates all metric bounds, and stops inconclusively if a
pair fails. A failed episode should be measured as a failure outcome; an
infrastructure error should raise. Never silently omit unfavorable episodes.
A Robotron adapter still needs verified emulator reset, controls, and outcome
measurement. The current scripted PPAL-0 frames are not a valid action-dependent
experiment environment. Physical searches need a separate experimental design
when identical starting states cannot be restored.

## Interpretation

For each metric, compute candidate minus baseline (reverse sign for metrics
where lower is better). Conservative Hoeffding intervals use the predeclared
metric bounds and independent paired trials; a Bonferroni correction allocates
the error budget across metrics. Results are decided only at the fixed horizon.
The primary lower bound must exceed its useful-gain margin and every guardrail
must rule out a loss exceeding its margin. Strong evidence of primary harm or
guardrail harm yields worse. Otherwise the result is inconclusive.

The method assumes the sampled starting situations are independent and relevant
to the specified context. Reusing one state or repeatedly testing plans until a
winner appears does not meet that assumption or preserve the stated error rate.
Use fresh held-out situations for confirmation and a new context for transfer
claims. Intervals are deliberately conservative; inconclusive is not failure
and is not evidence that the choices are equivalent.

## Memory integration

Call `publish(plan, report, gateway)` with a `MemoryGateway` to queue a qualified
experiment outcome through the normal MARM outbox. All statuses are preserved.
Only a real experiment explicitly designated `memory_ablation=True`, with a
previously recorded `decision_id`, can give usefulness feedback to the evaluator.
In such an ablation, baseline and candidate must differ only in the memory advice
being tested. Synthetic results never earn credit for real memories. One complete
experiment provides one weighted assessment split across its contributing memories;
individual frames are not counted as independent evidence. Re-publishing the
same plan/seed cannot repeat the feedback credit.

This runner supports experiments and checks measurements. It does not yet
invent hypotheses, operate the live emulator, validate arbitrary causal claims,
or automatically deploy a winning policy to hardware.
