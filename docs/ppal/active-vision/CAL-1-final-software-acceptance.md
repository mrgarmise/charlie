# CAL-1 recovered integrated software release

The interrupted workspace was recovered in full; reconstruction was unnecessary. Remote parent was independently observed at `f5bc3955bfacddca3445eb218fbff2d51de0caba`. The first tested checkpoint was published immediately as `b1e72c888ecbc17c1a4748864ea6895c47dc1ddc`; further tested corrections were published as `ec0cd2ac82c961e4692e6c1dcf32b7b3b8baa774`. This report belongs to the final containing commit on `feature/active-vision`. ALA-2 was not modified.

## Acceptance actually executed

| Check | Outcome |
| --- | --- |
| Final CAL-1 / Active Vision / normal-application focused suite | 238 passed, 0 skipped, 39.81 s |
| Final broader available suite | 687 passed, 19 skipped, 72.11 s |
| Compilation, indentation and whitespace | Passed |
| Pinned deployment dry-run | Passed without opening hardware or changing services/git |

The 19 skips are existing Torch-dependent ALA cases; Torch is unavailable in the host environment. Raw compressed JUnit reports for prior, intermediate and final attempts are preserved in `recovery-20261004/`; their hashes, environment, source hashes and failed-attempt explanation are in `validation-cal1-final-software.json`. An initial test-fixture transport binding error and obsolete runpy invocation were corrected; their failed reports remain visible. These are host tests with simulated IO, not native or physical proof.

## Integrated behavior retained

The normal Pi application owns one camera and RP2040 link. The existing Learning Executive selects calibration work. The shared raw-frame path selects experiments, evaluates distributed background response, records immutable captures and bookmarks, advances repeated sessions, and creates candidates. The Pico independently consumes GP10 only for unqualified extensions; qualified increments and exact supported retreats use their existing scoped authorities. Calibration completion can return to qualified normal tracking, digital framing, bounded camera correction and finite reacquisition. No alternative camera manager, learning scheduler or PWM controller was introduced. Existing firmware behaviors/display/heartbeat/watchdog/protocol and Robotron interfaces remain covered.

This session additionally corrected reference-pixel scaling between camera resolutions; preservation of the commissioning powered-start review in candidate profiles; STOP on unavailable camera/telemetry and on retained-session closure persistence failure; and cleanup of transport/camera on normal application initialization failure. Simulated candidates remain inadmissible for physical qualification. Powered-start review remains a required external physical-evidence input; no review was fabricated.

## Deployment package acceptance

`tools.update_charlie --cal1-release FULL_SHA` stages a pinned detached release, validates dependencies, preserves installed wiring/configuration and the entire Pico file snapshot, uploads dependencies before `main.py`, verifies hashes, and launches the normal service with motion authorization forced off. Existing support libraries, profiles, quarantine/running markers and commissioning evidence remain intact. Failure tests cover missing STOP acknowledgment, snapshot failure, missing configuration and partial upload, both with the original service running and stopped. Rollback restores original application bytes, removes only newly transferred application files, restores the previous service configuration, and restarts only a previously running service. A failed integrity check leaves the service stopped. Streaming Pico hashing avoids loading an entire evidence file into memory.

`--dry-run` is non-mutating. The packaged release includes an exact source revision and file-hash manifest. Its deployment instructions are a later authorized procedure, not an instruction to deploy in this mission. Application-source updates do not replace the MicroPython runtime. No Pi, Pico, service, servo, installed firmware or gameplay was accessed here.

## Remaining acceptance

Integrated host-software acceptance passes. Native Pi/MicroPython execution remains unobserved. CAL-1 remains physically unqualified: the reported jerky initial energization requires the specific powered-start pulse/pose/smoothness review; actual camera settling, combined-axis clearance, persistence/watchdog and independent envelope qualification still need their previously required physical evidence. No comprehensive physical preflight was performed or substituted for implementation. No physical profile was created, activated or deployed.

The next action can be code-only native staging of this exact release using the focused suite above. Firmware deployment and physical commissioning require separate explicit authorization. Use the package's `RELEASE.json` and `DEPLOYMENT.md` for its pinned revision.
