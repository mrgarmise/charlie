# Startup and episode-transition audit

This audit covers published `7b4bb55` and the complete available physical archive
`body-fire-bootstrap-20261001-020552` (`dfdccde`, dirty worktree). No newer
physical developmental archive was supplied or found in the available files.
Consequently there is no claimed post-repair physical startup latency or completed
multi-game marathon. [Timestamp evidence](startup-timeline-body-fire.json) retains
original hashes, rows, transport timings and the distinction between measurements,
intervals and interpretations.

## Old START path

The recollection “if the screen does not look like gameplay, press START” is not
what this revision implements. `play_robotron.main` initializes the camera,
warms it, applies requested focus, and optionally sweeps exposure. Then:

```python
auto_start = args.arm and not args.no_start_game
if auto_start:
    controller = ArcadeController(..., protocol="positions")
    controller._command("START")
```

There is no initial visual START decision. `ArcadeController` first sends
`NEUTRAL`, then the player sends exactly one momentary `START`, both requiring an
`OK` response. Weak recognition cannot authorize initial START because recognition
is not consulted; explicit `--arm` already authorizes it even on a live game or
unknown display. Recent successful starts prove the command sequence worked on
those instruction pages, not that this decision distinguishes screens.

With `--recalibrate`, the old player then performs a two-second settle followed
by up to 24 border attempts / a 30-second search. Each saves a full PNG and runs
geometry detection. Only after that does `_wait_for_gameplay` observe sprites.
Its generic-ready path accepts three stable candidate populations; it does not
require screen-state evidence. The log label “GAMEPLAY VISUAL CANDIDATES” is not
a positive gameplay classification. Armed SELF discovery can begin regardless
of whether the watch actually demonstrated gameplay.

## Old screen model and restart weakness

The existing classifier samples saturated, bright perimeter pixels:

- Saturation >=70 and value >=90; at least 80 pixels and coverage >=.08.
- Hue concentration >=.82 and <=3 occupied hue bins yields `gameplay`.
- Concentration <=.62 and >=4 bins yields `not_gameplay`.
- Otherwise `unknown`.

This answers uniform-versus-striped border appearance. It cannot distinguish an
instruction page, title, high-score page, death, respawn, wave transition or
calibration failure. A washed-out white gameplay border can be UNKNOWN. A striped
page is NOT_GAMEPLAY, not permission to START. Geometry failure is an I/O/preflight
failure rather than a recognized visual state.

`EpisodeEndObserver` already requires eight consecutive positive NOT_GAMEPLAY
observations and at least one failed eligible control challenge; gameplay or
UNKNOWN breaks the streak, and reacquisition clears suspicion. However, the
player bypassed this observer when two eligible appearance probes failed: it
unconditionally wrote `GAME OVER`, confirmed, with rule
`established_gameplay_plus_eligible_failed_agency`. Both marathon modes trusted
any nonempty `episode_end.evidence` on a successful child exit. That shortcut
could turn identity uncertainty, a death/respawn or delayed response into a new
START. It was not exercised in the available body/fire run (challenge ineligible,
TIME LIMIT), but is directly demonstrable from the actual entry-point code.
Screen classification also used the frame from before recovery, despite recovery
possibly taking seconds.

## Actual available physical timeline

All numeric times below use the saved sensor/controller monotonic clock. They
are not wall-clock times inferred from console order.

| Boundary | Saved time / interval | Evidence and limits |
|---|---:|---|
| Exposure sweep | 8.785 s processing | Before START; last evaluated capture completed 10253.575487. Zero EV had no geometry; valid EV -1/-2 views were discarded because the old selector required an EV-zero reference. |
| START | Between 10253.575487 and 10256.762655 | Actual transmission/ACK not saved. Lower bound is last pre-START exposure capture; upper is first saved post-START calibration exposure. |
| First saved visible gameplay | 10256.762655 | `setup-attempt-000.png`, active field with reserve-player icons. Actual onset may be earlier. |
| Calibration frame span | 10256.762655–10279.978216 | 13 attempts, 23.215561 s between first/last exposures, six stable views, 6.987px jitter. This is not the entire calibration-call duration. |
| Calibration completion | Between 10280.066576 and 10282.677392 | Last setup capture completion to first startup-watch request. No explicit completion event saved. |
| First life loss | Between 10266.156234 and 10267.833658 | Visual interpretation: two reserve-player icons in attempt 6 become one in attempt 7; field population subsequently resets. Runtime did not track lives. |
| Candidate watch | Samples 1–3, exposures 10282.729192–10283.802743 | Relative watch times .3261, .8559, 1.3913 s. These rows are uncommanded and UNKNOWN SELF. |
| SELF discovery begins | Between 10283.890054 and 10284.255153 | Last watch capture completion to first discovery capture request. Exact call-start timestamp absent. |
| First FIRE-only probe | 10284.642820 | BODY STAY, FIRE E; captured actual transport. Effects remain uninterpreted. |
| First BODY probe | 10285.917010 | BODY E, FIRE N. Pulse requested 60ms; execute returned 10286.077336 (160ms total transport/hold). Second sensor endpoint 10286.419528. |
| First provisional SELF | Exposure 10288.633730, capture completed 10288.721065 | Sample 14, candidate 146. This is provisional, not certified identity. |
| Ordinary-policy timer begins | Approximately 10289.299633 | Reconstructed from controller return time minus relative step time; eight rows agree within microseconds. Not a saved phase event. |
| First ordinary action transport starts | 10289.570431 | BODY NE/FIRE NW; actual controller execution. Requested action timestamp 10289.570422; return 10289.710892. |
| Ordinary action latency after START | 32.808–35.995 s | A defensible interval because START time is missing. No exact physical latency is fabricated. |
| Ordinary actions | Eight, last starts 10294.395595 | About five seconds of ordinary BODY/FIRE action before sustained identity loss. |
| Recovery | Relative rows 12.410–21.096 s | Initial recovery consumed about 7.2 s after last action. Later rows classify gameplay then UNKNOWN; no confirmed terminal evidence. |
| End | TIME LIMIT; terminal UNKNOWN | No second START is justified. |

The first-life icon decrement precedes the first ordinary action by at least
21.74 seconds. Alex's observation of standing through a first life is therefore
supported by saved imagery in this available run. The exact instant of death,
or the identity/state of every subsequent respawn, was not measured.

The dominant startup delay is post-START geometry acquisition: 23.2 seconds of
frame span plus settling and final processing, versus roughly 1.6 seconds of
candidate watch and 4.9 seconds from discovery's first capture completion to the
ordinary-policy clock. Setup capture calls sum to 1.734 seconds across 13 frames;
the long gaps contain detector work, PNG encoding, sleeps and other processing.
Those components were not timed separately, so their exact historical shares
are unknown. The first BODY transport consumed 160ms including a 60ms hold;
controller/display response is not a supported explanation for the 23-second
geometry delay. Exact display onset is still unmeasured; the existing two-fresh-
endpoint agency protocol is unchanged.

## Narrow repair: actual new path

1. Warm camera, set requested focus, run existing exposure preflight. When zero
   EV has no geometry but dimmer measured views do, use the least dim valid view
   as the existing comparison reference. The recorded body/fire sweep now selects
   EV -2 against measured EV -1 instead of restoring unreadable EV 0. This is an
   offline recorded-sweep check, not a new physical camera measurement. RGB and
   automatic white balance handling remain intact.
2. Complete existing `prepare` **before any controller is constructed or START
   sent**, using `require_uniform_border=False`. Its existing geometry-only
   option accepts attract-style color differences; the same six-view/jitter checks
   remain. Missing geometry stops with a partial report and zero START commands.
3. Extend the existing screen classifier, not a parallel classifier. Three fresh
   consecutive recognized instruction-page observations authorize one START.
   Three positive gameplay observations attach to the current game without START.
   Terminal-style pages alone, transitions and UNKNOWN do not authorize initial
   START. The bounded decision watch stops if no supported decision emerges.
4. Preserve the exact successful transport sequence: controller-constructor
   NEUTRAL/OK, then one START/OK. `--no-start-game` explicitly bypasses initial
   START, but still requires a positive gameplay-entry watch before discovery.
   No repeated START/retry loop is introduced.
5. Require three positive gameplay phase observations plus existing generic
   candidate readiness before SELF discovery. A title/attract page containing
   moving shapes can no longer pass merely because its sprite candidates persist.
6. Run the unchanged BODY/FIRE discovery and provisional SELF criteria. Enable
   ordinary policy and the unchanged one-action experiment hook when eligible.
   The requested gameplay timer still begins after discovery and includes recovery;
   it is not a 20-second budget measured from START. Startup has the existing
   separate developmental child timeout.
7. Remove the failed-probe terminal shortcut. Classify the latest already observed
   recovery frame. Only positively recognized pregame/terminal pages can advance
   terminal suspicion; a merely striped unrecognized page remains uncertain.
   `safe_to_restart` now validates GAME OVER result, known independent-evidence
   rule, eight-frame streak, failed agency, and a positive recognized page.
8. Apply the existing deadline to recovery frame collection and legacy control
   challenges. An incomplete deadline-truncated challenge is inconclusive; no new
   work/probe is scheduled after expiry. An already-running camera/transport call
   may still finish after expiry; this is not a hard real-time cancellation claim.

## Recognition evidence and boundaries

`config/robotron/screen-labels` contains small masks cropped from the recorded
normalized instruction and Heroes headings, with original frame/calibration
hashes and crop provenance. Local grayscale contrast supplies shape evidence;
hue is not a label requirement. All original camera frames remain RGB.

The model adds an explicit `phase` while retaining existing border diagnostics:

| Phase | Positive evidence | Initial START? | Episode meaning |
|---|---|---|---|
| gameplay | Complete luminous border contrast on four sides plus small interior regions; no recognized instruction/Heroes heading | No; attach after three observations | Visual gameplay hypothesis, not certified SELF or life count |
| startable | Recorded ROBOTRON: 2084 instruction heading, similarity >=.74 and margin >=.08 against Heroes heading | One START after three observations and explicit arm | Recognized instruction/pregame page; alone does not prove previous game ended |
| terminal | Both ROBOTRON HEROES and ALL TIME HEROES headings, similarity >=.78 each | No initial START on this page alone | Terminal-style display; episode context and existing independent evidence still required |
| transition | Complete border but insufficient active field evidence | No | Empty/intermission-like view; no claimed transition subtype |
| unknown | Missing/ambiguous geometry/labels, contradictory label evidence, unrecognized striped page | No | Stop/observe; no fabricated semantic fact |

Similarities are not calibrated probabilities. No general text OCR, GAME OVER
word detector, arbitrary title-page recognizer, death/respawn classifier or life
tracker was added. Attract demonstration screens lacking the recognized heading
are not assumed startable. Some unsupported screens can still remain UNKNOWN;
passing this corpus is not proof of universal recognition.

Checks against original full-camera frames from three runs recognize all six
EV-zero/EV-minus-two instruction views, four live gameplay views (including white
washed-out borders), and the single Heroes view. Fresh geometry-only location
also recognizes 10/12 exposure images as usable pregame; the other two remain
geometry failures rather than silently authorizing START. Full-camera RGB JPEG
regression fixtures are explicitly marked derived copies, with original hashes;
a held-out instruction page checks that recognition is not exact-pixel matching.

## Timing instrumentation and reuse

The previously unused `RobotronSessionManager` and existing `GameDiary` now record
CAMERA_READY, STARTING, WAITING_FOR_GAMEPLAY, ACQUIRING, PLAYING, REACQUIRING and
STOPPED. `events.jsonl`, `session_transitions`, and `session_timing` are preserved
in the normal report/E/E import. Agency rows carry `session_phase` without another
tracking/association pass. Startup and recovery cannot be silently counted as
ordinary action rows.

Saved boundaries include exposure/calibration start and finish; positive START
decision and its image/similarity evidence; START write-start/write-completion/ACK;
first visually classified gameplay and three-observation confirmation; first BODY
probe transport; first provisional/confirmed SELF sensor and record time; timer
start/deadline; first ordinary action's transport; and stop. New reports calculate
latency from first ordinary controller execution minus START local write completion.
Local transmission/ACK are not remote execution or TV rendering timestamps.
Calibration attempts now separately time capture, detector and frame encoding.
There is no attempt to retrofit these missing timestamps into historical evidence.

## Marathon readiness

Both old and developmental marathon modes share `safe_to_restart`. Initial START
is separately governed by the player's positive pregame decision. Between games,
processing/learning occurs with camera/controller closed; no new START follows
TIME LIMIT, SELF loss, death/respawn uncertainty, calibration/recognition failure,
interrupt, missing report or nonzero child exit. Developmental early stop writes
`session.json`, preserves completed/partial episode evidence, resolves a pending
experiment as unresolved when evidence is inadequate, and releases controls.
Starting a new process later is a new explicit operator request, not permission
inherited from an uncertain earlier screen.

The corrected software has regression coverage for multiple synthetic games,
but **is not yet validated for multiple physical games**. The available physical
run ends TIME LIMIT/UNKNOWN, so it cannot authorize a second game. Do not extend
the developmental marathon acceptance claim until the newer archive is available
and an actual confirmed-terminal transition/restart is demonstrated. Exact
post-repair physical first-action latency likewise awaits new phase evidence.

Proposal generation/ranking, selected experiment, AgencyTracker, provisional
SELF criteria, tracker association and passive score code are unchanged. The
user's local `experiments/ppal/run_camera.py` was not modified.

Final complete suite: **350 passed in 23.75 seconds**. Entry-point tests verify
pre-START calibration ordering (including a simulated 20-second geometry delay),
one START on recognized pregame, no START when attaching to gameplay, exact new
transport-based latency arithmetic, neutral release on errors, unchanged
provisional embodiment/experiment behavior, and failed probes remaining
nonterminal. Recorded-frame tests cover supported pregame/gameplay/Heroes
recognition and fresh pregame geometry. Deadline and restart tests cover UNKNOWN,
transitions, partial probes, old unsafe evidence rules and unverified early stops.
