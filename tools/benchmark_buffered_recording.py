#!/usr/bin/env python3
"""Integrated recording/PPAL cost; software by default, optional camera-only Pi.

Never constructs a controller, changes policy, commands motion or starts a game.
"""
import argparse
import hashlib
import importlib.util
import json
import platform
import os
import resource
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from benchmark_tactical_feedback import distribution,counters
from experiments.ppal.progress_evidence import CaptureEvidence,DurableRows
from experiments.ppal.progress_supervision import ObservationFailure
from experiments.ppal.observation_camera import ObservedCamera
from experiments.ppal.models import WorldState,Position,Object
from experiments.ppal.forebrain import Forebrain
from experiments.ppal.hindbrain import Hindbrain
from memory.evidence import EvidenceJournal
from PIL import Image

BASELINE='70e5b714f0d2ddad72fc2f4792032fd22f99963e'


def load_baseline(directory):
    source=subprocess.check_output(['git','show',BASELINE+':experiments/ppal/progress_evidence.py'])
    path=directory/'frozen_baseline.py';path.write_bytes(source)
    spec=importlib.util.spec_from_file_location('experiments.ppal._recording_baseline',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.CaptureEvidence,module.DurableRows,hashlib.sha256(source).hexdigest()


def run_case(args,name,recorder_type,rows_type,*,burst=False,slow_ms=0):
    directory=args.output.with_suffix('')/name;directory.mkdir(parents=True,exist_ok=False)
    if args.native_camera:
        from experiments.ppal.eyes.sources import PiCameraSource
        raw=PiCameraSource();camera_kind='native Pi camera; tactical states remain software fixtures'
    else:
        image=Image.open(args.source);image.load()
        class SoftwareCamera:
            def read(self):return image.copy()
            def close(self):pass
        raw=SoftwareCamera();camera_kind='repeated authentic failed-start pixels; simulated acquisition'
    camera=ObservedCamera(raw,require_fresh=args.native_camera)
    recorder=recorder_type(directory,'benchmark-not-independent-game',dict(simulated_tactics=True))
    recorder.ready();camera.recorder=recorder
    costs=[];encode=[];original=recorder._capture
    def instrument(*item):
        began=time.perf_counter_ns()
        if slow_ms:time.sleep(slow_ms/1000)
        try:return original(*item)
        finally:costs.append(time.perf_counter_ns()-began)
    recorder._capture=instrument
    # PIL encoder timing is measured on the writer, never on the decision caller.
    save=Image.Image.save
    def timed_save(*a,**k):
        began=time.perf_counter_ns()
        try:return save(*a,**k)
        finally:encode.append(time.perf_counter_ns()-began)
    Image.Image.save=timed_save
    forebrain=Forebrain();brain=Hindbrain(tactical_learning=True)
    rows=rows_type(directory/'steps.jsonl')
    if hasattr(rows,'recorder'):rows.recorder=recorder
    acquisitions=[];decisions=[];fast=[];pause=0;previous=None;first_timestamp=None;last_timestamp=None;capture_metadata=None
    cpu=time.process_time();began=time.perf_counter();before=counters();failure=None
    try:
        for tick in range(args.samples):
            if not burst:
                due=began+tick/args.hz
                time.sleep(max(0.,due-time.perf_counter()))
            start=time.perf_counter_ns();acquired=start
            try:camera.read()
            except ObservationFailure:
                acquisitions.append(time.perf_counter_ns()-acquired);pause+=1
                recorder.flush() # no commands; explicitly pause acquisition
                previous=None
                continue
            acquisitions.append(time.perf_counter_ns()-acquired)
            if first_timestamp is None:first_timestamp=camera.timestamp
            last_timestamp=camera.timestamp;capture_metadata=camera.capture
            if previous:
                recorder.event('tactical_outcome',dict(prediction_id=previous,eligible=False,
                    resolved_result='unresolved',reason='synthetic states cannot qualify camera causation'),at=time.monotonic())
            # Frozen software geometry is deliberately not inferred from replay/native pixels.
            w=WorldState(tick,Position(50,50),(Object('rescue',Position(85,50)),),())
            decision_start=time.perf_counter_ns();goal=forebrain.update(w);intent,action=brain.decide(w,goal)
            decisions.append(time.perf_counter_ns()-decision_start)
            previous=recorder.event('tactical_prediction',dict(question='software option timing',
                action={'move':action.move,'fire':action.fire},simulated_world=True),at=time.monotonic())
            recorder.event('tactical_execution',dict(prediction_id=previous,controller_emitted=False),at=time.monotonic())
            rows.append(dict(tick=tick,prediction_id=previous,observed_at=camera.timestamp))
            fast.append(time.perf_counter_ns()-start)
    except Exception as exc:failure=f'{type(exc).__name__}: {exc}'
    finally:
        camera.close()
        try:recorder.close()
        except Exception as exc:failure=f'{failure or ""}; {type(exc).__name__}: {exc}'
        Image.Image.save=save
    elapsed=time.perf_counter()-began;cpu_used=time.process_time()-cpu;after=counters()
    utilization={}
    for core,a in before.items():
        delta=[x-y for x,y in zip(after[core],a)];total=sum(delta[:8])
        utilization[core]=(100*(total-delta[3]-delta[4])/total) if total else None
    journal=EvidenceJournal(directory/'session-evidence.sqlite3',read_only=True);journal.verify()
    captures=len(journal.category_records('observation','camera_capture'));journal.close()
    dist=lambda r:distribution(r) if r else None
    return dict(case=name,camera=camera_kind,wall_seconds=elapsed,cpu_seconds=cpu_used,
        peak_process_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        system_core_busy_percent=utilization,acquisition_including_snapshot=dist(acquisitions),
        tactical=dist(decisions),decision_path_including_record_enqueue=dist(fast),
        writer_frame_service=dist(costs),encoding=dist(encode),completed_frames=captures,
        sustained_completed_frames_per_second=captures/elapsed,acquisition_pauses=pause,
        pipeline=recorder.telemetry() if hasattr(recorder,'telemetry') else {'frame_capacity':4,'legacy_prediction_wait':True},
        exposure=dict(first_timestamp=first_timestamp,last_timestamp=last_timestamp,latest_capture_metadata=capture_metadata),
        failure=failure,controller_commands=0,independently_qualified_findings=0)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--source',type=Path,default=Path('tests/fixtures/robotron-failed-start-031501/start-decision-000.png'))
    p.add_argument('--samples',type=int,default=20);p.add_argument('--hz',type=float,default=10)
    p.add_argument('--slow-write-ms',type=float,default=100);p.add_argument('--native-camera',action='store_true')
    a=p.parse_args()
    if not 2<=a.samples<=120 or not 1<=a.hz<=60 or not 0<=a.slow_write_ms<=500:p.error('bounded samples/rate/storage delay required')
    model=Path('/proc/device-tree/model').read_text().strip('\x00') if Path('/proc/device-tree/model').exists() else None
    if a.native_camera and (platform.machine()!='aarch64' or not model or 'Raspberry Pi 5' not in model):
        p.error('native camera benchmark requires verified aarch64 Raspberry Pi 5 hardware')
    root=a.output.with_suffix('');root.mkdir(parents=True,exist_ok=False)
    old,old_rows,old_sha=load_baseline(root)
    result=dict(schema='charlie-buffered-benchmark-v1',revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        dirty_worktree=bool(subprocess.check_output(['git','status','--porcelain'],text=True)),
        environment=dict(python=sys.version,machine=platform.machine(),platform=platform.platform(),
            hardware_model=model,logical_cpus=os.cpu_count(),
            meminfo=Path('/proc/meminfo').read_text() if Path('/proc/meminfo').exists() else None),
        baseline_revision=BASELINE,baseline_module_sha256=old_sha,
        source_sha256=hashlib.sha256(a.source.read_bytes()).hexdigest() if not a.native_camera else None,
        code_sha256={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in
            map(Path,['experiments/ppal/progress_evidence.py','memory/evidence.py','memory/episode_identity.py',__file__])},
        cases=[run_case(a,'baseline-normal',old,old_rows),run_case(a,'buffered-normal',CaptureEvidence,DurableRows),
               run_case(a,'buffered-burst',CaptureEvidence,DurableRows,burst=True),
               run_case(a,'buffered-slow-storage',CaptureEvidence,DurableRows,slow_ms=a.slow_write_ms)],
        limitations='No physical gameplay; tactical states controlled fixtures even with native camera. CPU counters include OS load; RSS cumulative high water. No inference/transport or complete-game score qualification.')
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
