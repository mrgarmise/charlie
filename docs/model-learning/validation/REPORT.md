# Software validation receipts

All host commands used `/home/five/Projects/charlie/.venv/bin/python` from
`/home/five/charlie-model-learning`, with `-p no:cacheprovider`.
Environment: Python 3.13.5, numpy 2.2.4, OpenCV 4.10.0, Pillow 11.1.0,
pytest 9.1.1. No physical capability was initialized.

Initial runtime: local 1cf0fb9f70bd84aa1ef217caabd0b294b317bd03 and published
5c0d51a61fb5bb7e358140cbb07278de3b24f091 have identical tree
237b1ad71d08d3afe90d4acd0631933d15d53ad3.

- Full host command: `python -m pytest tests -q -p no:cacheprovider --junitxml=/tmp/charlie-model-learning-full.xml`.
  Both `CHARLIE_MODEL_LEARNING_SHARED_BUS=/tmp/charlie-pr13-bus.py` and
  `CHARLIE_MODEL_LEARNING_SHARED_GATEWAY=/tmp/charlie-pr14-human.py` were set.
  **1,244 passed, 24 skipped, 34 failed**, 480.47 seconds. All 34 failures are
  `PermissionError: [Errno 1] Operation not permitted` at sandbox-denied socket
  operations. No other failures occurred. Original log/XML are retained as gzip.
- Baseline comparison: exact failed node IDs were replayed on unchanged master
  bcf8082f6319c63c4bd6bcceeab5faea37241654 in
  `/tmp/charlie-model-learning-baseline` with the same Python/environment.
  Command: `python -m pytest -q -p no:cacheprovider --junitxml=/tmp/charlie-model-learning-baseline-failures.xml NODE_IDS`.
  `socket-denied-nodes.json` contains the exact argument array, including escaped
  newline parameters. **The same 34 nodes failed**, all with the same permission
  error, in 2.47 seconds. No socket restriction or safety test was relaxed.
- Independent focused CI on published initial runtime:
  https://github.com/mrgarmise/charlie/actions/runs/40783733776 — **30 passed**,
  zero skipped/failed, 28.28 seconds. Exact pinned #13 bus and #14 gateway source
  compatibility, actual training worker and two-version rollback were exercised.
  Artifact: https://github.com/mrgarmise/charlie/actions/runs/40783733776/artifacts/12858138073 .
- Initial broad independent CI:
  https://github.com/mrgarmise/charlie/actions/runs/40783733556 — status was still
  RUNNING when this receipt was written; do not count as passing.

The second increment binds commissions to the actual Executive selection,
invalidates cached incumbent interpretations when source changes, rechecks
current user qualification policy, bounds provenance/scratch disk, adds a saved
localization-proposal replay and a disposable combined-stack CI job.

Second-increment host command (same two exact-source environment variables):
`python -m pytest tests/test_model_learning.py tests/test_model_learning_shared_bus.py tests/test_model_learning_shared_gateway.py -q -p no:cacheprovider --junitxml=/tmp/charlie-model-learning-increment-2.xml`.
**31 passed**, zero skipped/failed, 47.36 seconds. Runtime/test SHA-256 identities
are in `increment-2-source-sha256.json`; log/XML retained as gzip.

`synthetic-cycle-model-card.json`, if present, is explicitly synthetic. It records
a real Executive-originated controlled worker/evaluator/rejection path, not an
authentic accuracy result. The authentic normal-application run instead returns
NEEDS_LABELS, persists the request and leaves activation empty. Its commands:

```bash
python -m learning.model_learning --state /tmp/charlie-model-learning-authentic import-fixtures
python main.py --offline --model-learning --learning-state /tmp/charlie-model-learning-authentic --learning-turns 1 --learning-budget 2 --learning-wall-seconds 20
python -m learning.model_learning --state /tmp/charlie-model-learning-authentic baseline
```

No authentic candidate was trained. The reused incumbent is 5/5 on existing
regression labels; independent generalization, real unknown recall, transition
quality, complete Executive-originated authentic training, gameplay benefit and
Pi/Hailo acceptance remain unestablished.
