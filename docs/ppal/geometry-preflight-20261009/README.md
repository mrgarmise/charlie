# Original-pixel geometry-preflight correction

Started from independently fetched published feature/agency-first-self 7991731b95a54997b161c64c153c9f68b4f420af. No newer remote commit was present. Other dirty worktrees and original history remained untouched. This changes existing locate()/locate_stable_geometry()/legacy prepare() only; no new camera, planner, learning owner or application.

## Authentic failure and provenance

Original source: robotron-runs/marathon-20261009-004249/game-01. Archive SHA256 277769a3e4d2d106fdab98a80be7c6a8532be75415875314949ed6130cc71a04. Original report identifies 7991731 with a **dirty tree**, not a clean native code checkpoint; it records geometry-preflight failure before gameplay. The separately uploaded settle.py is byte-identical to the published detector. Archive, originals, report, source journal and prior failure remain unmodified. Nine exact original PNGs are retained in tests/fixtures/robotron-geometry-004249, with encoded-byte and decoded-RGB hashes, archive membership and original report/detector hashes in provenance.json. Remaining 110 originals remain preserved in the supplied archive, not recreated or relabeled.

Independent host replay reproduced the supplied 101/119 detections. Twenty returned lower-right corners outside the manually inspected broad playfield band, including the incorrect lower TV edge and the text-height rectangles on 112–113. Those broad visual checks are diagnostic regression bounds, not independently qualified precise trajectories, SELF identity, score or performance labels. The code contains no fixed image coordinates or reference-screen crop.

## Correction and ownership

The existing full-frame Hough/contrast candidate search stays intact and bounded to twelve lines per orientation. The existing 65% overall four-edge support and color-uniformity mode remain. Candidate admission additionally requires the same contrast-supported fraction in each edge's first/last ten-percent spans. Invalid off-frame support is missing evidence, never silently shifted toward a better middle segment. A line crossing most of an edge cannot establish an extrapolated corner. This rejects incomplete text/bezel rectangles without making dim observations count as successes.

Among admitted rectangles, rank whole-perimeter mean support before the weakest edge. The old weakest-edge-only ranking favored the wrong lower edge despite worse perimeter agreement. locate() accepts an optional previous geometry and jitter radius only to rank *currently independently image-supported* candidates. It searches the entire current frame every time. If no nearby supported candidate exists, it selects from the new full-field candidates; it never returns cached corners when current evidence is absent. Both normal locate_stable_geometry() and legacy prepare() supply their local rolling median, not persisted calibration. A miss clears confirmation. A moved camera accumulates six fresh agreeing views at the new position; continuous movement cannot pass.

**Six stable observations and 8 pixels remain unchanged**, as do twenty-four geometry attempts and existing timing/resource/authority gates. No relaxed screen-phase/gameplay/score admission or hardware permission is introduced.

## Demonstration and checks

Baseline focused suite: 22 passed in 3.14s. Initial corrected focused suite: 22 passed in 3.05s. Original-fixture/full-archive/synthetic-movement/normal sensory tests: 37 passed in 61.12s. Baseline and corrected replay JSON preserve all 119 frame outcomes.

Corrected standalone replay: 97/119 supported rectangles; all 97 lie in the visually checked playfield bands. Frames 112–113 abstain; four additional conservative misses are reported rather than promoted as successful calibration. First six distinct original observations pass unchanged stability with **5.7483 px** jitter, using six source reads. A replay starting at original frame 96 spans the real dark/missing interval and confirms six fresh supported views after fourteen reads with **7.3970 px** jitter, within the unchanged twenty-four-attempt budget. This is software replay, not a new native/physical run or a claim that every optics/startup stage completed on the Pi.

Synthetic tests exercise changed perspective/location with a former border, continuously shifting geometry, and interruption of a five-view sequence by a miss. Original fixtures check byte/pixel provenance, competing lower edges on 4 and 18, false text rectangles on 112–113, and six genuinely distinct consecutive photographs. No controller is constructed by these tests.

Host: x86_64 Python 3.12.14, pytest 9.1.1, NumPy 2.5.3, Pillow 12.3.0, OpenCV headless 5.0.0.93, pyserial 3.5. No native Pi timing or optics qualification is inferred. Final full offline suite: **707 passed, 21 skipped in 222.75s**, exit 0; JUnit and complete final console output are retained as lossless gzip files. Final original-archive replay after the last source/test changes: **15 passed in 85.86s**, including all 119 originals and the real frame-96 tail. The earlier full-suite invocation returned zero but its console log ended before the summary; that incomplete log and exit record are preserved, and the complete JUnit-backed rerun is the qualification result. No native Pi acceptance is claimed.

## Guarded Pi software replay

Use the existing safe checkout/update procedure with the exact published correction SHA, preserving original evidence/configuration. With the existing Python environment, run without opening camera/controllers:

```bash
CHARLIE_GEOMETRY_ACCEPTANCE_ROOT=/home/five/Projects/charlie/robotron-runs/marathon-20261009-004249/game-01 /home/five/Projects/charlie/.venv/bin/python -m pytest tests/test_robotron_geometry_replay.py tests/test_ppal_settle.py tests/test_robotron_preflight.py tests/test_sensory_recording.py -q
```

Optional full-archive test fails if the supplied directory has other than 119 originals; it never reconstructs missing ones. Default offline suite always exercises the nine retained originals even without that environment variable. Actual fresh camera acquisition, preflight under changed lighting, native latency and physical gameplay remain separately unperformed. Dim or occluded borders can still legitimately fail; independently visible complete corners are required. Other similarly supported rectangles remain a visual ambiguity, not solved universally by temporal preference.

No physical gameplay, servo movement, firmware deployment or learned-policy activation occurred. ALA-2 remains open until Charlie-originated learning improves independently verified mean complete-game Robotron SCORE; this is a geometry prerequisite, not a learning/score achievement.
