"""Agency-first scheduling and measured hot-path costs; never selects tactics."""
from collections import defaultdict, deque
from contextlib import contextmanager
import math
import time


class AgencyScreen:
    """Skip terminal templates only with supported SELF and stable scene evidence.

    This path cannot grant START permission or establish a terminal boundary.
    A scene change or loss of supported SELF immediately restores investigation.
    """
    def __init__(self,classifier,supported):
        self.classifier=classifier;self.supported=supported
        self.active=False;self.reference=None;self.full_calls=0;self.fast_calls=0

    @staticmethod
    def signature(frame):
        import numpy as np
        return np.asarray(frame.convert('RGB').resize((32,24)),dtype='float32')/255.

    def __call__(self,frame):
        import numpy as np
        signature=self.signature(frame)
        stable=(self.reference is not None and float(np.mean(np.abs(signature-self.reference)))<.16)
        # Even stable attract imagery has no fast path without independently
        # supported SELF. A large transition always receives the full classifier.
        if self.active and self.supported() and stable:
            self.fast_calls+=1
            self.reference=signature
            return dict(state='gameplay',phase='gameplay',reason='supported_SELF_and_stable_scene',
                        terminal_investigation=False,restart_permission=False)
        self.full_calls+=1
        result=self.classifier(frame)
        if result.get('phase')=='gameplay':
            self.reference=signature
        else:
            self.reference=None
            if result.get('phase') in ('terminal','title','startable'):self.active=False
        return result


class CycleMetrics:
    """Bounded samples; sustained counts include only fresh supported decisions."""
    def __init__(self,capacity=2048):
        self.stages=defaultdict(lambda:deque(maxlen=capacity));self.ages=deque(maxlen=capacity)
        self.first=None;self.last=None;self.count=0;self.last_observation=None
        self.feedback=deque(maxlen=capacity);self.feedback_unresolved=0
        self.previous_track=None;self.identity_changes=0;self.interruptions=deque(maxlen=capacity)

    @contextmanager
    def measure(self,name):
        started=time.perf_counter()
        try:yield
        finally:self.stages[name].append(time.perf_counter()-started)

    def decision(self,observation,exposure_at,*,supported,track_id=None):
        now=time.monotonic()
        if not supported or observation is None or observation==self.last_observation:return False
        if not isinstance(exposure_at,(int,float)) or not math.isfinite(exposure_at) or exposure_at>now or now-exposure_at>.25:return False
        self.last_observation=observation;self.count+=1;self.ages.append(now-exposure_at)
        if self.first is None:self.first=now
        if self.last is not None:self.interruptions.append(now-self.last)
        self.last=now
        if self.previous_track is not None and track_id!=self.previous_track:self.identity_changes+=1
        self.previous_track=track_id
        return True

    @staticmethod
    def distribution(values):
        values=sorted(values)
        if not values:return dict(samples=0,median=None,p95=None,worst=None)
        return dict(samples=len(values),median=values[len(values)//2],
                    p95=values[min(len(values)-1,math.ceil(.95*len(values))-1)],worst=values[-1])

    def report(self,*,stream=None,screen=None,recording=None):
        import resource
        thermal=None
        try:
            from pathlib import Path
            thermal=float(Path('/sys/class/thermal/thermal_zone0/temp').read_text())/1000
        except (OSError,ValueError):pass
        usage=resource.getrusage(resource.RUSAGE_SELF)
        return dict(schema='charlie-gameplay-performance-v1',meaningful_updates=self.count,
            meaningful_definition='one distinct exposure at most 250ms old with supported SELF used for an existing Forebrain/Hindbrain decision',
            sustained_hz=(self.count-1)/(self.last-self.first) if self.count>1 and self.last>self.first else None,
            sample_retention='last 2048 samples; sustained counter spans the whole run',
            camera_to_decision_seconds=self.distribution(self.ages),interruptions_seconds=self.distribution(self.interruptions),
            stage_seconds={k:self.distribution(v) for k,v in self.stages.items()},
            controller_visual_feedback_seconds=self.distribution(self.feedback),
            feedback_status='only independently resolved command-to-visual attribution may populate this metric; otherwise unmeasured',
            self_identity_changes=self.identity_changes,stream=stream.stats() if stream else None,
            full_screen_calls=screen.full_calls if screen else None,fast_screen_calls=screen.fast_calls if screen else None,
            recording=recording,process_cpu_seconds=usage.ru_utime+usage.ru_stime,
            maximum_rss_kib=usage.ru_maxrss,temperature_c=thermal,
            native_target_hz=[8,12],native_target_qualification='requires authentic sustained native run; host replay is not acceptance')
