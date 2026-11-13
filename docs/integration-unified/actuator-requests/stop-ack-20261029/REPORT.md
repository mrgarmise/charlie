# Bounded native STOP acknowledgment timing correction

Existing draft PR #13; parent published
`95a7cd583ea8a6a568bdfb274de21638bc1c604c`, corresponding local
`7707c53a397d61971b47bda59471f82d679e958d`. The broad face-trial preparation
worktree is preserved separately. This increment changes **one runtime line**
in the existing `ElegooMobileBase.stop_verified()` path: its response wait is
150 ms instead of 50 ms. No other deadline, motor packet or controller changes.

The operator supplied this installed-controller stationary result on October 29:

```text
Command: {"N":1,"H":"stopcheck1","D1":0,"D2":0,"D3":0}
Result: {"ok":True,"response":"{stopcheck1_ok}","value":"ok"}
Measured host elapsed: 0.085 seconds
Two preceding supervised N2 trials returned STOP TimeoutError at 0.050 seconds.
```

This is an operator-provided chat receipt, preserved as reported, not an
independently collected raw trace/video. It demonstrates that the previous
50 ms response window can reject a legitimate 85 ms reply. The initial 150 ms
window is the operator-requested bounded correction, not a measured latency
percentile or guarantee for every transaction. Replies outside that window
remain failures. The prior N2/T200 receipt reported tagged completion at 292 ms
and failed backup STOP; it remains partial evidence and does not qualify local
expiry or physical stopping.

The preserved manufacturer source dispatches N1/D3=0 to
`ApplicationFunctionSet_SmartRobotCarMotionControl(stop_it, 0)`. Classic parser
ACK ordering and installed bridge/firmware qualifications remain unchanged.
A successful tagged ACK establishes a reply, **not observed motor or servo rest**.
No firmware was modified or flashed and no connection, query or motor operation
was performed while preparing this correction.

Immediate STOP dispatch is unchanged: the extra time is response observation
**after** the existing send, never a pre-dispatch delay. There is still exactly
one write, no automatic retry/reconnect, exact tagged reply matching, unchanged
concurrent STOP admission/priority, independent authority, and uncertainty
latching/persistence/rollback. Physical stopping remains unknown in every driver
receipt. A later unmatched ACK cannot repair a timed-out result or clear an
executor incident. N2/T bounds, completion timing, lease/cancellation/safety and
all physical qualification thresholds are unchanged. The runtime hash changes;
older runtime-bound motion grants cannot be reused.

Deterministic fake-peer tests cover 85/149 ms replies, a 151 ms late reply,
untagged/wrong-ID/error replies, immediate send before wait, exactly one write,
no reconnect and no physical claim. Existing timed-pulse/executor/authority,
STOP/preemption, persistent uncertainty and ultrasonic regressions are rerun;
independent full CI is reported with the exact published commit on PR #13.
Software tests do not establish native physical face-following acceptance.
