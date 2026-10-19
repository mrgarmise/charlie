"""Pin real exposures around synchronous transport; the sole producer keeps reading."""
import time


def capture_window(source,controller,action,duration_ms,deadline=None,should_stop=None,*,post_seconds=.25):
    if not 30<=duration_ms<=400:raise ValueError('firing duration must be explicitly bounded at 30..400 ms')
    if not 0<post_seconds<=.35:raise ValueError('post-fire window must be bounded')
    def stopped():return should_stop is not None and should_stop()
    if stopped() or (deadline is not None and time.monotonic()+duration_ms/1000+post_seconds>=deadline):
        raise InterruptedError('insufficient existing acquisition budget; no FIRE sent')
    stream=source.stream
    baseline=stream.begin_window()
    submitted=time.monotonic()
    try:
        controller.execute(action,duration_ms,cancel_event=stream.failed,deadline=deadline)
        execution=dict(controller.last_execution or {})
        until=min(time.monotonic()+post_seconds,deadline if deadline is not None else float('inf'))
        last=baseline.sequence
        while time.monotonic()<until and not stopped():
            try:packet=stream.latest(after=last,timeout=max(.001,min(1.,until-time.monotonic())))
            except TimeoutError:
                if time.monotonic()>=until:break
                raise
            last=packet.sequence
        packets=stream.end_window()
        if stopped():raise InterruptedError('shot observation cancelled')
        return execution,packets,dict(schema='pinned-shot-window-v1',submitted_at=submitted,
            baseline_at=baseline.at,completed_at=time.monotonic(),frames=len(packets),
            first_exposure_at=packets[0].at,last_exposure_at=packets[-1].at,
            controller_execution=execution,stream=stream.stats(),
            latency='acknowledgment is transport evidence, not display response time')
    except BaseException:
        with stream.condition:stream.pin=None
        controller.close() # neutral/disconnect; never qualify partial evidence
        raise
