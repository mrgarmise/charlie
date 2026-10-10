# Deferred Robotron score review

Parent verified before implementation: `177b0b2d52c198d24e403da3142df755c48877fc`.
This extends ScoreObserver, the existing marathon diary and score inspector. No
physical gameplay, motion, firmware or policy activation is authorized or performed.
ALA-2 remains open; no score improvement is claimed.

Milestone A records every marathon child attempt before execution and appends its
outcome afterward. Missing reports/images and interrupted children remain durable
records. Selected score photographs retain source timestamp, camera observation ID,
source-log hash and original PNG hash. The original prediction is immutable.
Photographs observed in a reported terminal sequence are distinguished from other
score photographs; reported boundaries are not independent game qualification.

Offline validation:
`python -m pytest -q tests/test_score_review_queue.py tests/test_marathon_deferred.py tests/test_marathon_robotron.py tests/test_score_human_review.py tests/test_score_observer.py`.
The 30-game fixture collects 30 attempts and 29 proposals without human review;
the missing photograph remains a record. Fixtures are not physical games. Test
transcripts and JUnit are retained alongside this report. Native Pi validation
and real unattended-marathon acceptance remain outstanding.
