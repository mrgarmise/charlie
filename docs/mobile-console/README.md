# Mobile Body operation

Status: implementation under draft PR #16. This checkout is not a physically
qualified release. Software tests use fake wire transports and synthetic pixels.
The existing safety/evidence admission, durable uncertainty marker and independent
cutoff requirements remain mandatory. No firmware flash is part of setup.

## Startup and private access

Use a separate reviewed checkout and preserve the running application's source,
configuration, PIDs, notebooks and device owners. Do not run two Charlie hardware
applications. Add `--mobile-dashboard` to the selected existing application start;
its camera feeder and executor remain owners. The server is the existing dashboard
adapter, loopback port 8768. When `--abilities-dashboard` is also selected, both
pages share that server and existing operator token; otherwise configure the
separate monitoring token. A missing drive token produces a read-only console.

Generate credentials outside shell history (do not paste literal tokens into a
command line). For example, in an interactive shell:

```bash
read -rsp 'Monitoring token (32+ characters): ' CHARLIE_MONITOR_TOKEN; echo
export CHARLIE_MONITOR_TOKEN
# Optional, only after the existing native readiness/qualification gates pass:
read -rsp 'Separate drive token (32+ characters): ' CHARLIE_DRIVE_TOKEN; echo
export CHARLIE_DRIVE_TOKEN
```

Keep credentials out of Git, URLs, logs, hosted assets and screenshots. Changing a
token requires stopping/restarting this application; it revokes browser sessions.
The service binds only loopback. Use the established private SSH tunnel:

```bash
ssh -N -L 8768:127.0.0.1:8768 five@charlie.local
```

Open `http://127.0.0.1:8768/mobile` on the tunnel host. On a phone use a reviewed
private tunnel/HTTPS path with authentication; `127.0.0.1` means that phone, not
Charlie. Do not bind this service to the public network. The server validates
exact Host and Origin. A private HTTPS reverse proxy must rewrite Host to the
loopback address and use the configured exact HTTPS origin; configure/review TLS
and operator routing before using it. Hosted HTTPS-to-loopback requests may be
blocked by the browser; the same-origin local page remains available.

Examples below are preparation commands, not evidence they ran here. When
hardware is disconnected/unqualified, an offline monitoring service can coexist
with the normal offline Learning Executive:

```bash
python main.py --offline --mobile-dashboard --learning-state /path/to/existing/reviewed/state
```

For an independently authorized stationary camera-only/native monitoring window:

```bash
python main.py --hardware --mobile-dashboard \
  --learning-state /path/to/reviewed/state \
  --mobile-hardware-id VERIFIED_DEVICE --mobile-zone REVIEWED_ZONE \
  --actuator-safety-feed /path/to/independent-measured-feed.json
```

This starts the existing ELEGOO feeder, qualified executor/telemetry facade and
normal background developmental lifecycle. Neither the executor nor telemetry
opens the command transport until independent admission permits it. Merely
supplying IDs/a feed path does not qualify any device or grant motion.

For existing object recognition on the ELEGOO feed, append the console to that
normal mode, keeping display opt-in explicit:

```bash
python main.py --hardware --object-recognition --camera-source elegoo \
  --object-label-display off --mobile-dashboard \
  --object-model-manifest /path/to/existing/hash-bound/mobile-models.json \
  --learning-state /path/to/reviewed/state
```

Existing `--pet-abilities` / `--pet-follow` / `--primary-vision` modes can also
attach `--mobile-dashboard`. Manual chassis authority preempts both source-bound
face requests and pet executor dispatch. It does not stop the Learning Executive
or replace attention selection. Independent safety STOP remains authoritative.
Dedicated face-trial instrumentation remains its own bounded acceptance workflow;
that special entry does not currently attach the web service.

## Controls and freshness

Connect with monitoring credentials; optionally supply the separate drive token.
Tokens remain in page memory. Take control only when qualified admission is
available. Browser ownership expires 400 ms after its last accepted heartbeat/
command. A dedicated worker checks every 25 ms; these are software settings,
not measured physical STOP guarantees. Device-local timed pulses remain at most
100 ms here and require the qualified envelope; the executor/driver may reduce
or reject them. HTTP/CPU/native timing must be measured before acceptance.

Hold WASD/arrows or a touch direction. Release/key-up/pointer cancellation issues
STOP. Focus loss, page hiding, navigation and disconnect revoke control and issue
STOP; failed delivery relies on the watchdog and independently qualified local
expiry/cutoff. Emergency STOP needs the drive token but no lease and latches the
executor until independent restart/requalification. A STOP ACK is never presented
as physical stopping. Reopening the page cannot clear hardware uncertainty.

Diagonal controls alternate separately admitted turn/travel pulses. They do not
send an unqualified differential-wheel packet. Existing pivot-only qualifications
remain pivot-only; forward/reverse need three witnessed envelope/braking trials
per added direction plus the original stopping/loss/preemption/cutoff stages.
Speed is capped at PWM35 and independently admitted limits. Manual request identities are minted inside the gateway from its boot, opaque
lease epoch and strictly increasing sequence. Its replay memory stays bounded
without the autonomous path’s existing 256-request lifetime cap. Old owner/boot/
sequence combinations cannot rearm or replay; the autonomous replay guard remains
unchanged.

Camera display uses one independent subscription and cached lossless PNG encoding
(the existing passive publisher's baseline format). No camera or model opens in
HTTP handlers. The browser continuously fetches latest frames without a configured
FPS target, automatically retries outages, and hides stale frames after 500 ms.
It reports unique displayed FPS, subscription FPS/drop count, Pi receipt age and
HTTP/decode interval. Exposure latency stays unknown for ELEGOO MJPEG. These are
different measurements; receipt time is not sensor exposure time.

Ultrasonic is published by existing ElegooTelemetry through StimulusBus using the
same qualified transport schedule. Dashboard centimeters are converted from the
existing meter value; timestamp age, observed sample frequency, validity and
fault counters are shown. Values older than 500 ms or faulted are unavailable.
The scalar is neither target-associated distance nor proof of obstacle clearance.
Other shared ELEGOO modalities are discovered dynamically. Unsupported sensors
stay listed as deferred; physical presence is not inferred from a car model.

Object overlays consume existing recognition/pet results on the shared bus,
without a second detector. Source, generation, frame ID and geometry must match
exactly; otherwise results are stale/unavailable. The existing attention packet
and learning evidence flow are unchanged. Detection cadence may be lower than video cadence. With overlays enabled, the
transport selects the exact retained decision frame (still within the freshness
budget); it never attaches old boxes to newer pixels. If that frame has expired
or left bounded history, overlays disappear. Disable overlays for the latest
camera frames. At most 24 boxes and a bounded metadata header are delivered. The overlay switch changes display only, not model ownership.
Screenshot downloads save the displayed camera/overlays locally and include the
source frame ID in the filename. They are not journaled evidence or a physical
qualification receipt. Existing recognition evidence retention remains available
through its normal pipeline; web evidence bookmarking is deferred.

## Hosted dashboard integration

The same mobile.js mount function and mobile.css are ready for the existing
Sites source. Use the Sites skill source helper to open project
`appgprj_6ad39fb624888191ae560b8058e856a7`; preserve its custom owner audience,
all existing pages/data, and current navigation. Add a dedicated Mobile Body nav
item, load `ui/mobile.js` and `ui/mobile.css` as local versioned assets, and call
`mountCharlieMobile(routeRoot)` for that route. Call `stopCharlieMobile()` on
route teardown. Keep the existing Abilities route. The only live endpoint is the
reviewed Pi backend entered by the operator; never include bearer credentials in
hosting source or proxy motor commands through a public Site.

Hosted navigation/publication remains pending because this session could not open
the actual Sites source (no Node/DNS/network). The prepared mount is used by the
existing local dashboard adapter now. Do not claim the hosted dashboard was
updated until its source has been independently tested, packaged and published.

## Rollback

Stop only this reviewed process using its documented operator STOP and independent
physical cutoff. Preserve its receipts and durable uncertainty marker. Return to
the previously preserved qualified checkout/startup configuration; do not reset
another worktree, delete motion incident records, revoke unrelated learning state
or flash firmware. Revert feature commits for software rollback. Monitoring can
remain available with no drive credential or executor.

A non-installed user-unit template is provided at
`setup/charlie-mobile-console.service.example`. Its default is offline monitoring
with the existing Executive and `Restart=no`; it never enables hardware or firmware
maintenance by itself. Review paths, the existing application service and state,
then use the established user-service deployment procedure. The private
`~/.config/charlie/mobile-console.env` must be mode 0600 and contain the reviewed
monitoring credential plus an optional distinct drive credential. Do not run this
unit alongside another physical Charlie application. SIGINT allows context cleanup;
process loss still requires the independently measured device-local expiry/cutoff.
