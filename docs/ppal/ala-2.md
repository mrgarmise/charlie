# ALA-2 implementation milestone: evidence-directed investigations

This is an independently testable **partial ALA-2 milestone**, not completion of the ALA-2 acceptance cycle. No physical score improvement, improved recognizer, or production gameplay change has been demonstrated. The governing objective remains official Robotron score.

## Verified baseline and actual gaps

The isolated implementation worktree began at published `4d86d4d` on `feature/agency-first-self`. The [complete ALA-1 report](ala-1.md), [preserved demonstration](ala-1-demonstration.json), [October 2 physical audit](physical-learning-audit.md), companion evidence and [Executive audit](learning-executive-audit.md) were inspected alongside executable paths. Existing local work and `run_camera.py` were not reset or edited.

The actual reusable path is `Reflection → Experience → MemoryGateway/Evaluator → LearningExecutive → experiment_return chooser → CapabilityRegistry → ModelFoundry → E/E prediction/resolution → Evaluator/Executive feedback`. Meditation supplies retrospective interpretations and questions, not verified identity. Persistent project interruption, independent evidence-unit accounting, controlled CNN training, immutable recovery, separate shadow authorization and rollback already exist. There is no executing autonomous code-modification loop or production learned-model adapter in this checkout.

ALA-1's actual CNN failed its train-only baseline: held-out MSE approximately 0.01699 versus 0.00350. It remains rejected. Reflection stored a model-failure question, but that question had no executable diagnostic follow-up. Evidence collection/clarification were only capability descriptions. Automatic CNN alternatives were fixed. Portfolio terms were declared heuristics. Production learning-to-action, adaptive broad experimental synthesis and reliable official-score measurement were missing; class names did not supply them.

## Extended mechanisms

* Existing Reflection now generates two tentative model-failure explanations with different observable signatures: a fitting/generalization gap and optimization still progressing at its resource boundary. It does not inspect the history to select an expected answer. Supporting evaluation IDs, competing explanations and assumptions are preserved. These are a finite generic diagnostic vocabulary, not unrestricted scientific invention.
* The same Evaluator-first chooser commits a prospective **retrieval** prediction and an exact executable plan. Registry invocation retrieves frozen training history, compares the signature and resolves honestly. This is not a historical forecast of the original CNN result, a new independent physical experiment, or a new final-test evaluation.
* Optional `--review-questions` accepts previously unspecified categories from existing episode Reflection. One retrieval discriminates recurrence versus an episode-specific gap. Duplicate contexts cannot create independent episodes; missing source identity produces UNKNOWN. Complementary explanations are not counted as separate experiments.
* Existing Executive selects projects, records actual resolutions, updates memory and pauses completed retrieval work. Identical evidence cannot repeat a completed trial. New versioned context evidence permits reassessment. The existing bounded job budget remains; pending projects survive restart. This is serial scheduling, not concurrent training or competing controller writers.
* Offline retrieval forecasts carry an explicit boot clock domain. Historical monotonic timestamps are retained, referenced through consolidation, and never compared to the new host's clock. An interrupted forecast across a reboot resolves UNKNOWN rather than fabricating deadline continuity. Same-domain recovery reuses committed outcomes.

No parallel memory, tracker, Executive, hypothesis database, controller, question queue or reflection service was introduced. The new files are small capability and provenance adapters under existing mechanisms. PPAL, AgencyTracker, provisional SELF, score-worker isolation, camera ownership, physical experiment hook and START/supervisor safeguards remain unchanged.

## Physical score comparison protocol

`experiments/comparison/robotron.py` extends the existing comparison analyzer. Before games, commit a frozen `Plan` with official score as primary metric, learning provenance, candidate/baseline versions, camera/game/system/measurement conditions, trial count, metric bounds, margin, alpha and randomized temporal-block order. Candidate and baseline must remain frozen during evaluation. Tuning data and final trials must be separate. Physical Robotron randomness is not reset or falsely represented as an identical seeded starting state.

The adapter consumes append-only consolidated `robotron_evaluation_episode` records after preregistration. Each needs a unique physical source episode, scheduled slot/policy, matching conditions, confirmed terminal boundary and final score observations with independent validation references, capture hash and timestamp. No observer or source receives priority. Unknown or conflicting scores, partial games, changed conditions, missing guardrails and missing scheduled games produce an inconclusive result; repeated episodes are rejected. No favorable trials are silently dropped. Existing conservative bounded paired-difference intervals are reused. Large score bounds can require many trials; a 3-game readiness marathon is not automatically a powered performance comparison.

This analyzer does **not** certify a reader merely because a qualification string/reference was supplied. Independent measurement validation is an external prerequisite. The historical 3500 versus 2400 and 3300 versus 1300 observations remain separate and unqualified for a definitive score comparison. The real score corpus's 4/14 readable result is still a measurement limitation. No new score labels or special adjudication rules were installed.

The protocol never captures, sends START, changes policy or authorizes deployment. Offline Pi validation of processing recovery and physical readiness are still prerequisites for any unattended armed marathon.

## Reproduction and boundaries

For an existing local learning root with its notebook and artifacts:

```bash
python -m pytest tests -q
PYTHONPATH="$PWD" python -m learning.cycle \
  --output learning-runs/ala-1 --diagnostics-only \
  --review-questions --budget-seconds 30 --max-jobs 8
```

This uses the existing persistent Evaluator/project stores. Keep originals; use copies and isolated MemoryGateway/Evaluator/project stores when reproducing the archived demonstration. Diagnostics-only mode requires no PyTorch or relocated pixel paths and performs no camera/START operation. `ala-report.json` and `ala-report.md` expose alternatives, priorities, forecasts, results and durable projects. An insufficient evidence/resource outcome remains valid.

Still unimplemented: learned value-of-information calibration; broad explanatory synthesis; executable visual-example/clarification acquisition; adaptive model/preprocessing refinement with a fresh independent final test; concurrent resource leases; production validated-model/policy adapters; learning-derived gameplay strategy deployment; actual before/after physical score comparison. Diagnostic retrieval changes the next investigation, but is not evidence of improved Robotron operation. Storing a conclusion is not operational learning.

ALA-2's full hypothesis → intervention → independent validation → approved operational change → physical score comparison cycle remains open. The remaining work must use Charlie's evidence and mechanisms rather than a manually supplied winning strategy.
