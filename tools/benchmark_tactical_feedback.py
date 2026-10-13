#!/usr/bin/env python3
"""Host/Pi software benchmark. No camera, controller or deployment is opened."""
import argparse
import hashlib
import json
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from experiments.ppal.models import WorldState,Position,Object
from experiments.ppal.forebrain import Forebrain
from experiments.ppal.hindbrain import Hindbrain


def counters():
    try:
        return {r.split()[0]:[int(x) for x in r.split()[1:]] for r in Path('/proc/stat').read_text().splitlines() if r.startswith('cpu')}
    except OSError:return {}


def distribution(rows):
    ordered=sorted(rows)
    return dict(samples=len(rows),median_ns=statistics.median(rows),p95_ns=ordered[int(.95*(len(rows)-1))],
                p99_ns=ordered[int(.99*(len(rows)-1))],max_ns=max(rows))


def measure(fn):
    start=counters();wall=time.perf_counter();cpu=time.process_time()
    result=fn()
    elapsed=time.perf_counter()-wall;used=time.process_time()-cpu;end=counters()
    utilization={}
    for core,before in start.items():
        delta=[a-b for a,b in zip(end[core],before)];total=sum(delta[:8])
        utilization[core]=100*(total-delta[3]-delta[4])/total if total else None
    return dict(wall_seconds=elapsed,cpu_seconds=used,process_cpu_percent=100*used/elapsed,
                system_core_busy_percent=utilization,peak_process_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                result=result)


def run_decisions(enabled,n):
    forebrain=Forebrain();brain=Hindbrain(tactical_learning=enabled);samples=[];contradictions=0;revisions=0
    for tick in range(n):
        # Frozen controlled software geometry; this is not an independent game.
        w=WorldState(tick,Position(50,50),(Object('rescue',Position(85,50)),),())
        began=time.perf_counter_ns()
        if enabled and tick:
            r=brain.tactical_feedback(w,timestamp=tick*.2,track_id='simulated-self',identity_status='confirmed',
                response_window=dict(endpoint=2,origin_at=(tick-1)*.2,move=previous.move))
            contradictions+=r['result']=='contradicted'
        goal=forebrain.update(w);intent,action=brain.decide(w,goal)
        if enabled:
            brain.executed_tactic(w,action,timestamp=tick*.2,track_id='simulated-self',prediction_id=f'fixture-{tick}')
            revisions+=intent.kind=='investigate'
        samples.append(time.perf_counter_ns()-began);previous=action
    return dict(latency=distribution(samples),eligible_simulated_response_windows=contradictions,
                tactical_revisions=revisions,independently_qualified_findings=0,controller_commands=0)


def run_recording(source,n):
    from PIL import Image
    from experiments.ppal.progress_evidence import CaptureEvidence
    from memory.evidence import EvidenceJournal
    image=Image.open(source);image.load();rows=[]
    original=hashlib.sha256(source.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);recorder=CaptureEvidence(root,'recording-benchmark-not-a-game',
            dict(simulated=True,source_sha256=original))
        for index in range(n):
            began=time.perf_counter_ns()
            recorder.capture(image,dict(timestamp=time.monotonic(),simulated_repeated_pixels=True))
            recorder.flush();rows.append(time.perf_counter_ns()-began)
        recorder.close()
        journal=EvidenceJournal(root/'session-evidence.sqlite3',read_only=True);journal.verify()
        count=len(journal.records('observation'));journal.close()
        restarted=CaptureEvidence(root,'recording-benchmark-not-a-game',dict(simulated=True))
        before=restarted.count;restarted.close()
    assert hashlib.sha256(source.read_bytes()).hexdigest()==original and before==count==n
    return dict(latency=distribution(rows),source_sha256=original,retained_frames=count,
                restart_next_index=before+1,original_unchanged=True,independent_experiences=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples',type=int,default=10000)
    parser.add_argument('--capture-samples',type=int,default=20)
    parser.add_argument('--capture',type=Path,default=Path('tests/fixtures/robotron-failed-start-031501/start-decision-000.png'))
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if not 10<=args.samples<=100000 or not 1<=args.capture_samples<=100:parser.error('bounded sample counts required')
    result=dict(schema='charlie-tactical-benchmark-v1',environment=dict(machine=platform.machine(),
        platform=platform.platform(),python=sys.version,revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        dirty_worktree=bool(subprocess.check_output(['git','status','--porcelain'],text=True))),
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path('experiments/ppal/hindbrain.py'),Path('experiments/ppal/forebrain.py'),Path('experiments/ppal/progress_evidence.py'),Path(__file__).relative_to(Path.cwd()) if Path(__file__).is_absolute() else Path(__file__)]},
        provenance='controlled software WorldStates; repeated original failed-start pixels for storage cost only',
        baseline=measure(lambda:run_decisions(False,args.samples)),
        tactical=measure(lambda:run_decisions(True,args.samples)),
        recording=measure(lambda:run_recording(args.capture,args.capture_samples)),
        limitations='System core counters include unrelated load; RSS is cumulative process high water. No Pi, physical gameplay, causal or score qualification implied.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
