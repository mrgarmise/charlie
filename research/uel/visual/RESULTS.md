# Offline qualification evidence

The front-left knee marker revealed a deliberately injected 60 ms command delay on the simulated FNK0050. Fitting used an isolated pulse train, then froze the candidate. Validation used sinusoidal and reversal motions at three different seeds each. An analytic pan/tilt rig ran through the same selector and estimator. The baseline, data split and rejection rules are specified in PLAN.md. Numerical evidence and runnable fixtures are in evidence/.

| Held-out comparison | FNK0050 knee | Two-axis tip |
|---|---:|---:|
| Unchanged model, mean trajectory RMS error (px) | 4.991 | 70.590 |
| Uniform single random parameter candidate (px) | 2.643 | 35.867 |
| Existing UEL linear response estimator, same commands and camera samples (pooled RMS px) | 13.099 | 27.534 |
| Fitted delay model, mean trajectory RMS (px) | 0.227 | 0.206 |
| 95% bootstrap interval over six held-out trajectories (px) | 0.217–0.236 | 0.202–0.210 |
| Candidate interval coverage, nominal 95% | 100% | 100% |
| Fixed-model mean trajectory deviation, evaluator-only 3D truth | 0.764 mm | 53.904 mm |
| Fixed-model mean link orientation error | 0.606° | 31.706° |
| Fitted-model 3D and orientation deviation | 0 mm, below 0.000001° | 0 mm, below 0.000001° |

The planted delay was the only dynamic difference between the generator and the candidate family. Consequently, recovery reproduces its deterministic 3D trajectory exactly. Pixel residuals remain because the estimator tracks noisy rasterized frames. The acceleration, mass, geometry, contact and servo mapping of the real dog remain unknown. A close-up camera was centered on the simulated joint after an initial fixture missed the dog marker and the observability gate correctly stopped fitting. The wide annotated video uses a distinct camera profile. No pass threshold was relaxed.

## Independent tests by stage

| Stage | Executed check | Observed result |
|---|---|---|
| A | Invalid units and permissions, untrusted command names, transport import check, type and schema checks | Physical mock denies all calls. Imported hypotheses remain inert. Schema examples validated. |
| B | Decode only image pixels, drop samples, hide markers, replay stored files, detect corrupt hashes, rerun partial-session logic | 512 frames per body. 464/464 visible, delivered markers recovered. No marker reported on 32 occluded frames. 16 simulated drops. Four keyframes retained per trajectory. |
| C | Calibrate from twelve rasterized boards; independently check metric correspondences, swapped cameras, degeneracy, missing calibration, affine clocks and uncertainty | 0.0432 px calibration RMS. Recovered focal lengths 603.29 and 603.21 px against known 600 px. Dog fixture horizontal FOV 5.23°, scale 0.1555–0.1556 mm/px. Rig 25.75°, 0.802–0.857 mm/px. Median noisy stereo error against known metric truth 0.509 mm dog and 2.965 mm rig. |
| D | One bounded delay grid, six held-out trajectories, stationary non-identifiability control, all five planted values at three new seeds | Informed selection recovered 15/15 delays per body (Wilson 95% interval 79.6–100%). Random questions recovered 10/15 each. The stationary control retained all five candidates. All six held-out fitted errors improved in each body. |
| E | Randomized dog ensemble, four OOD seeds × fitted delay and two neighboring delays. Vary mass/inertia, friction, rate and starting attitude. Keep every rejection | Stand, squat, isolated leg excursion and step-in-place passed 12/12 each. Modest disturbance release passed 12/12. Tripod, default forward walk and unstable-start challenge passed 0/12. The existing optimized gait advanced in 1/12. These are 2-second rollouts. |
| F | Same UEL question chooser, journal, robust estimator, non-identifiability control and validation on second body; CPU detector and optional accelerator output contract | Both bodies recovered 3 ticks. Hailo mock returned the same feature schema. No accessible Hailo device or licensed quadruped HEF for a native A/B comparison. |
| G | CLI demo, recording ingestion, comparison, simulation-only skill export and replay, calibration API, saved overlay, static HTML, review-only proposal | Headless run produced immutable candidate and qualification IDs. Replaying a selected rollout reproduced its recorded result. The proposed physical experiment has an empty command timeline. |

For the 464/464 tracking result, the Wilson 95% interval is 99.18–100%. The occlusion control is a small deterministic challenge. Both cameras use synthetic known clocks in the main benchmark, giving zero induced alignment error and drift. Clock tests independently compensate a 200 ms offset, reject excessive drift/skew and leave unmatched drops unpaired. These figures do not measure actual exposure timing, real autofocus, rolling shutter or camera-to-servo synchronization. Synthetic error intervals are conditional on the fixtures and the chosen motion families.

Dog detector localization RMS was 0.224 px, and rig localization RMS was 0.202 px. Tracking confidence is a fixture-specific isotropic pixel uncertainty; 100% predictive coverage means it was conservative on these samples. Silhouette centroids have a larger assigned uncertainty and cannot qualify a precision joint fit. Hailo-on/off power, native temperatures, exposures, Mint and Pi performance remain unmeasured. Host CPU throughput, latency, peak process RSS and wall time are directly recorded in dog.json and rig.json. Detector throughput excludes simulation, disk and capture. Session databases occupied 729,088 and 548,864 bytes, respectively, including 111,943 and 38,182 compressed keyframe bytes.

## Regression evidence and handoff

- UEL regression including visual stages: 42 passed. Dog Gym and UEL integration: 15 passed. Charlie unified contracts: 134 passed. These overlap parts of the broader suite.
- Broader Charlie tests and UEL run during implementation: 2,556 passed, 29 skipped, 5 failed. All five failures reproduced on unchanged cf0842e. The firmware recovery test passed after fetching its historical Git object. Four browser tests remain unverified: the expected Playwright browser was unavailable and system Chromium could not create its process socket in the sandbox. No runtime changes were made to mask those failures. Machine-readable summaries are in evidence/tests.json.
- Initial contract test failed before implementation. Calibration and stereo tests exposed two array-shape defects under OpenCV 5. The dog sequence exposed a non-contiguous OpenCV drawing input. Fixed and retested. Existing simulator and original training evidence are preserved.
- Charlie branch research/visual-twin stacks on draft #42. The dog companion is [draft #4](https://github.com/mrgarmise/dog/pull/4) at 59ae65fbe1b12f0e36a9122cfc2ad5c9ba71e149. Review the pair together. Rollback selects the prior content ID or original research branch. Nothing was installed in Charlie's approved runtime.

The first proposed separately authorized observation is a fixed external camera looking at a measured board beside the stationary, unpowered dog. It can test scale, visibility and exposure stability before any request for a powered probe.
