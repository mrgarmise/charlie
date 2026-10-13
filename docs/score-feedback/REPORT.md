# Score-reader feedback recovery and targeted master integration

Engineering checkpoint, October 13, 2026. **Full acceptance and master merge are blocked by missing authentic feedback/update evidence.** The original notebooks were not modified, no Pi code was deployed, and no gameplay, servo, firmware or PPAL policy was activated.

## Recovery findings

The October 10 mission/handoff identifies `/home/five/.local/share/charlie/score-review/learning-evidence.sqlite3` and reports **16 status records and 8 annotation records**, including visible values 1200, 1300 and 1500. Those are historical reported record counts, not independently verified distinct images. Exact accepted/corrected rows, timestamps, supersession state, finalization and subsequent consumption cannot be determined without that database and its hash-bound photographs.

The uploaded `charlie-terminal-restart.tar.gz` was downloaded and examined: 1560 members, SHA-256 `5e95637c06ace5faa826d97a22b38c6d6e2aa8b9f84b7d23ebdd050f5076f33f`. Its October 11 camera/session and marathon SQLite journals contain **zero human score annotations**. It does not contain the separate October 10 review store. Existing local restored-history material also supplied no corresponding original annotation batch. The Pi filesystem is absent here and `charlie.local` does not resolve. No remote login/credentials are available. Absence in these available artifacts does not establish that the records were lost on the Pi.

See `recovery-ledger.json` and `native-recovery.md` for exact paths and a read-only SQLite/WAL-consistent export preserving IDs, canonical documents, original timestamps, labels and image bytes. Imported-ID matches in the original developmental notebook establish acquisition only, not training or inference. No replacement authentic labels were generated.

## Actual pipeline and repairs

The selected fixed HUD reader extracts a calibrated strip and applies geometric segment/serif rules. Its temporal tracker maintains a score belief; neither originally updates visual recognition from human annotations. ScoreObserver retains original predictions/images and the inspector persists append-only reviews. Existing acquisition can import game/session diaries and the Evaluator can compare candidates, but the separate `score-review/learning-evidence.sqlite3` is not discovered merely by scanning `robotron-runs`. Review existence therefore does not demonstrate acquisition or visual adaptation.

Implemented:

- Additive, explicit review-source acquisition in the existing inspector, including hash-verified image relocation, original ID/document/commit-time preservation, idempotent import receipts and existing Evaluator reconciliation. No investigation agenda is selected.
- A bounded **digit-exemplar candidate** mechanism, using 16x24 binary glyph features extracted through the existing reader. Reviewed images enter development only with explicit training/diagnostic consultation, consistent active labels, independence attestation, exact images, source/session/image partition isolation and channel binding. Digit alignment must agree across reader-selected intensity thresholds; missing/ambiguous alignment is excluded. At most 128 prototypes are retained. No neural-network dependency.
- Immutable candidate artifacts retain reader/extraction and geometry hashes, consulted proposals/annotations, excluded/ambiguous cases, state digest and artifact identity. Loading checks schema, integrity, geometry, extraction version, externally supplied candidate hashes, bounds and fixture admission. Nearby exemplars require a narrow distance and alternative-label margin; adaptation confidence is capped at 0.9. This is a heuristic uncertainty score, not a calibrated probability or a 99% claim.
- Explicit offline candidate replay/evaluation. Normal ScoreObserver retains its baseline reader. No live activation adapter is added; candidates remain unqualified and require independent qualification/authorization/rollback before live use. Later superseding/disputed reviews require a new immutable candidate and reevaluation; a frozen artifact is not silently relabeled.
- Preserve the later ScoreObserver's separate gameplay/non-gameplay beliefs and terminal cutoff so attract/high-score observations cannot replace a supported gameplay score. Scores never establish SELF or terminal status. Legacy calls without phase metadata remain legacy observations, not independent phase qualification.
- Repair stale-photo navigation: clear before identity changes; guard late responses; decode the hash-verified primary before enabling numeric reviews; never reuse missing-photo imagery. Restore saved correction, explanation, reviewer attestation and finality controls. Save acknowledgment precedes advancement; failed writes do not advance. Finality and readable-digit correctness remain separate. Review history is immutable; disputes abstain.
- Extend the existing MemoryEvaluator's descriptive score metrics with numeric exact-match, canonical-string digit edit accuracy, unreadable false positives, high-confidence errors and abstention. Sealed final evaluation remains unavailable; source-overlap and immutable baseline gates remain.

The fixed-reader extraction was refactored to expose its existing glyphs. Default numerical predictions are unchanged on available regression inputs; unknown-digit failures return zero confidence rather than a partial optimistic value. None of these repairs proves autonomous Executive learning or PPAL action-policy adaptation.

## Controlled evidence and authentic recognition results

| Evidence | Result | Limit |
|---|---|---|
| Controlled feedback update/reload/ablation | Fixed pixels read 8400 without state and 9400 after retained exemplar state; restart retains the latter; removing state restores 8400 | Deliberately perturbed **synthetic** reviewer label tests causality only; it is not an authentic correction or a perception-gain claim |
| Disjoint-source software evaluation fixture | Exact-match 0/1 -> 1/1; canonical digit accuracy .75 -> 1; generated data and label perturbation remain explicitly fixture-only | Correlated generated glyphs, no independent physical generalization |
| Two preserved camera-derived JPEGs, historical labels 0 and 100 | Frozen reader 2/2; default integrated reader 2/2; digit metric 1.0 both; no observed regression | Existing camera-derived regression labels, not October 10 feedback; no authentic update applied; no unreadable negatives/held-out groups |
| False positives and confidence | Explicit negative/abstention metric tests pass; candidate confidence cannot exceed .9 | Authentic false-positive, calibration and unreadable-image rates remain unmeasured |
| Native Pi cost | NOT YET DEMONSTRATED | Host single-image timings are recorded descriptively, not a Pi benchmark or reliable speed comparison |

`python tools/validate_score_camera_regression.py --output /new/regression.json` reproduces the frozen-reader check. `authentic-camera-regression.json` preserves exact image hashes, labels/provenance, baseline source hash, predictions/confidence and host timings. The camera examples are JPEG derivatives of original observations and use diagnostic manually estimated calibration; they are not untouched raw captures or independent final acceptance. No generalization to unseen scores is claimed.

## Integration audit and testing

Rechecked remote master: `c322658586074462ffbded5ccd9db11f96448b0a`. Score-tracker branch: `72f4958d73cae9d29dde81596313984bc51b93e6`, **83 ahead / 0 behind**. Its full diff covers 157 files and approximately 499,000 added lines, including unrelated gameplay, planning, transport, memory, experiments and a large sprite corpus. A full merge is excluded.

Published implementation: `721af8c0ea838e1f759594a9424ca030e3ebdf2e`; [draft PR #3](https://github.com/mrgarmise/charlie/pull/3). A clean published checkout reproduced **56 passes, zero skips/failures**, with identical source tree. Target branch is `feature/score-feedback-master-integration`, created from current master. Selected score components come from the score-tracker lineage and later reviewed implementations at agency `708a1f6b5177497f4e765dd1900fa8407d266d8c` and acceptance `4bca038591a586c70a7f97f50f1af25ef42f6794`. Necessary dependencies are calibration/HUD types, immutable EvidenceJournal/capture-identity primitives, and existing MemoryEvaluator with its type/default-store dependencies. They introduce no running scheduler, physical owner or new agenda. The rest of the 83-commit feature history is not merged. `integration-audit.json` enumerates each selected file, hashes, source versions and exclusions.

Master's preexisting files and PPAL behavior remain unchanged. The targeted tree adds score modules, their direct evidence/evaluator dependencies, an optional dependency file, regression fixtures, tests and recovery documentation. The inspector retains optional motion/performance APIs for compatibility with existing ALA branches, while master without their separate architecture cannot issue independent complete-game certificates. Missing qualification dependencies are reported explicitly; human digit reviews do not silently become complete-game scores.

Validation:

- **56 passed, zero skipped/failed**, entire available targeted master `tests/` suite.
- **74 passed, zero skipped/failed**, focused overlay compatibility against the published current ALA architecture, including notebook acquisition, normal lifecycle/restart, shared motion-review server, score tracker/observer and feedback APIs.
- JavaScript syntax and real UI logic exercised with DOM/HTTP/Image doubles: stale/out-of-order responses, missing images, saved correction/finality restoration, failed save and numeric-button gating. No rendered-browser visual/usability acceptance is claimed.
- Python compilation, CLI help and diff checks pass. Exact commands, environment, timings and compressed JUnit reports are under `validation/`.

Host: Python 3.12.14, pytest 9.1.1, NumPy 2.5.4, Pillow 12.3.0, OpenCV-headless 5.0.0.93. Optional `requirements-score-review.txt` declares these score-review dependencies without Torch or camera/controller drivers. No unrestricted hardware-script collection was run. Compatibility initially exposed a missing shared evidence-queue field; it was restored and the suite rerun successfully. An earlier selected dependency lacked chunked artifact hashing; the actual later primitive was included without weakening verification.

## Acceptance and merge decision

| Criterion | Status |
|---|---|
| Original October 10 records recovered, or absence honestly documented | Absence from available artifacts documented; native store recovery outstanding |
| Ingestion and consumption mechanism verified | PASS in controlled software tests |
| Authentic retained feedback affects subsequent recognition | NOT YET DEMONSTRATED; synthetic causal control passes |
| Regression tests / available camera results | PASS within stated scopes; authentic improvement and Pi cost remain unmeasured |
| Current architecture compatibility | PASS in focused host overlay; native acceptance outstanding |
| Eligible implementation integrated into master | BLOCKED: authentic acceptance evidence missing; tested targeted PR retained |
| Final master merge provenance | No merge performed; master remains at verified base |

Master is currently unprotected with no required status contexts advertised. User merge authorization is present, but is conditional on acceptance. It does not justify bypassing the missing authentic feedback/update comparison. The PR is therefore a clean, tested recoverable integration checkpoint, not a completed merge or accepted milestone. Recover the original bundle, determine distinct images/accepted/corrected/finalization/imported state, apply valid feedback on a working copy, perform same-input retained-state controls and independent held-out checks where available, obtain native cost observations and satisfy any current repository checks before merging. No additional unrelated branch merge, hardware deployment or physical operation is authorized.

This score-reader capability does **not** independently satisfy ALA-2 E1, P1 action-policy learning, I1 guarded Executive-to-PPAL integration, complete-game performance comparison or ALA-2 closure. The attached governing Charter/Acceptance Standard and original mission obligations remain active.
