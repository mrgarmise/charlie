> Later live-run analysis and repairs: [tracking-score-232827-analysis.md](tracking-score-232827-analysis.md).

# Separate diagnoses of the two agency Pi runs

The first-run report is historical. Timing repair here is justified by the
second run's measured movement/neutral phase pattern, not by missing timing
metadata in the first run.

| Run | Code | Observed result | Interpretation |
| --- | --- | --- | --- |
| play-20260930-024128 | a70149c | No SELF acquisition; zero normal policy ticks; fragmented IDs and blue background admitted as a huge region | Motivated local-contrast detection, motion-aware global association, explicit ambiguity, shared tracker and complete replay inputs in a7a5ab2 |
| tracking-repair-20260930-034659 | a7a5ab2 | No SELF acquisition; zero normal policy ticks; replay matches 20 samples/591 detections/173 created IDs | Repaired assignment is reproducible; the likely center player retains ID 96 across all probe observations, but response is systematically attributed to the following neutral interval |

## What the repaired second run actually demonstrates

The normalized originals show a center sprite consistent with the player; this
is a visually supported hypothesis, not appearance-based admission to SELF.
Generic detections retain ID 96 throughout samples 8–20. No second association
or class filter was used to identify this history.

| Command sample | ID 96 movement there | Following neutral sample | ID 96 displacement in neutral |
| --- | --- | --- | --- |
| 9: east | (0, 0) | 10 | (+1.09375, +0.20833) |
| 11: west | (-0.07813, 0) | 12 | (-1.09375, -0.20833) |
| 13: south | (0, 0) | 14 | (0, +2.08333) |
| 15: north | (0, 0) | 16 | (+0.07813, -2.39583) |
| 17: east | (0, -0.10417) | 18 | (+1.48438, +0.10417) |
| 19: west | (+0.07813, 0) | 20 | (-1.56250, -0.10417) |

With original labels, this track earns zero signed hits and 12 contradictions.
An offline counterfactual using the preceding observation's command, over ALL
recorded generic positions, yields ID 96 with six hits, five stops, four
directions, reversal, confidence 1.0 and SELF acquisition under unchanged gates.
This strongly isolates control/capture phase as a present limiting factor. It
does not prove camera buffering is the entire delay, or that every tracked sprite
has correct identity. No counterfactual command shift is used in live code.

The provided official full-game observation was 1200 points, after the runner
had failed. There were movement probes, but no normal policy actions or score
reader in this run. Those points cannot be credited to the normal planner.
`pytest` was missing on Pi, so its full-suite command did not execute.

## Narrow repair now included with passive score integration

Armed Robotron camera reads use `capture_request(flush=True)`, which asks
Picamera2 for an exposure beginning after the request, instead of retrieving a
cached pre-command image. Pixels and metadata come from the same request; copied
pixels remain valid after its buffer is released in a finally block. This changes
only armed capture behavior; ordinary camera/preview and `run_camera.py` are
untouched. Unsupported Picamera2 flush APIs fail explicitly with neutral controls
rather than silently claim fresh observations.

The Raspberry Pi Picamera2 manual, sections 6.4 and 6.4.1, documents request
release, SensorTimestamp minus ExposureTime for first-pixel exposure onset, and
the flush guarantee:
https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf

A capture wrapper independent of HUD scoring retains raw pixels, request/read
completion, sensor timestamp, exposure time, first-pixel exposure estimate,
frame duration and actual lens position. This exposure timestamp feeds generic
tracking and score evidence. Controller telemetry records host send/ack times,
controls-ready time, pulse end and neutral acknowledgements. Host acknowledgement
is NOT a measurement of game input onset. No arbitrary sleep, score condition,
identity confidence reduction or new association pass is introduced.

Score remains an independent best-effort worker submitted AFTER the generic
tracking observation. Score errors/dropouts do not gate any control decision.
Queue/copy cost and reader cost remain separately logged. HUD processing does
consume CPU and memory; assess measured Pi cadence rather than assume zero cost.

## What remains and what is not yet proven

- Fresh captures eliminate the demonstrated cached-frame mechanism in a
  deterministic camera/agency regression, but have NOT yet been validated on the
  physical Pi. Emulator/controller/display delay may remain. Exposure and ACK
  evidence in the next run distinguish that possibility; do not hardcode a lag
  or lower SELF gates if it does.
- Early startup still produced 148 detections in one frame and created 127 IDs.
  Subsequent association briefly took 0.35–0.71 seconds on Pi. Once probes began,
  tracker association took about 2.3–6.4 ms. Startup-animation clutter and its
  cost remain unresolved; the generic tracker implementation is preserved.
- Exact replay proves reproducibility, not physical correctness of all IDs.
  Stable early-level population, actual SELF acquisition/maintenance, normal
  movement/firing and respawn remain the next live experiment's questions.
- Real raw-HUD validation remains 3/14: 8400, 8400 and 9500 accepted visually;
  the other eleven return UNKNOWN. P2 is None on all labeled single-player
  frames. Hue is not used; dim geometry/threshold robustness remains limited.
  Digit 7 has no real camera exemplar and retains inferred confidence.
- Full suite after this repair: 276 tests pass. Tests cover cached-vs-fresh
  agency endpoints, camera-buffer release on success/failure, raw RGB copies,
  the actual second-run phase counterfactual, score failure/drop isolation,
  armed cleanup/respawn and transport behavior. Second-run exact replay remains
  assignments_match=true with the unchanged SpriteTracker.

For the guarded 20-second Pi command and full archive instructions, use
[score-tracking-integration.md](score-tracking-integration.md). Local modifications
must survive fast-forward; never reset them. Gameplay duration starts after SELF
acquisition, so startup and probes add time to the 20-second policy window.
