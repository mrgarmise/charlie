"""Benchmark the existing unarmed main.py; no developmental agenda selection.

Use the same input root, turn budget and initially absent output directory for
baseline/candidate. Profiling overhead is reported and must not be mixed with
unprofiled latency claims. State is retained, never deleted by this tool.
"""
import argparse
import cProfile
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import runpy
import sys
import time


def cpu_counters():
    try:
        return {r[0]:list(map(int,r[1:])) for line in Path('/proc/stat').read_text().splitlines()
            if (r:=line.split()) and r[0].startswith('cpu') and r[0]!='cpu'}
    except OSError:return {}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--episode-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--turns',type=int,default=1)
    p.add_argument('--budget',type=float,default=10.)
    p.add_argument('--profile',action='store_true')
    args=p.parse_args()
    args.repo=args.repo.resolve();args.output=args.output.resolve();args.episode_root=args.episode_root.resolve()
    os.chdir(args.repo);sys.path.insert(0,str(args.repo))
    from learning.retrospective import inventory
    from memory.evidence import EvidenceJournal,digest
    if args.output.exists():raise ValueError('new output directory required; preserve every prior benchmark')
    args.output.mkdir(parents=True)
    before=inventory(args.episode_root);start_cpu=cpu_counters()
    usage=resource.getrusage(resource.RUSAGE_SELF);wall=time.monotonic();cpu=time.process_time()
    prof=cProfile.Profile() if args.profile else None
    sys.argv=['main.py','--offline','--learning-state',str(args.output/'state'),
        '--episode-root',str(args.episode_root),'--learning-turns',str(args.turns),
        '--learning-budget',str(args.budget),'--learning-interval','.05']
    # Execute the selected revision's real entry point, not imported adapters
    # from another checkout. The outer CLI must use that checkout's PYTHONPATH.
    os.chdir(args.repo);sys.path.insert(0,str(args.repo))
    error=None
    if prof:prof.enable()
    try:runpy.run_path(str(args.repo/'main.py'),run_name='__main__')
    except BaseException as exc:error=repr(exc);raise
    finally:
        elapsed=time.monotonic()-wall;cpu_time=time.process_time()-cpu
        if prof:prof.disable();prof.dump_stats(str(args.output/'normal.prof'))
        end_cpu=cpu_counters();u=resource.getrusage(resource.RUSAGE_SELF)
        per_core={}
        for core,values in start_cpu.items():
            delta=[b-a for a,b in zip(values,end_cpu.get(core,values))];total=sum(delta[:8])
            per_core[core]=(100*(total-delta[3]-delta[4])/total if total else None)
        records=[];state=args.output/'state';iterations=0;results=[];cursors=[];checkpoints={};consistent=True
        if (state/'learning-evidence.sqlite3').exists():
            journal=EvidenceJournal(state/'learning-evidence.sqlite3',read_only=True)
            try:records=journal.records()
            finally:journal.close()
        for path in state.glob('meditations/*/checkpoint.json'):
            d=json.loads(path.read_text());r=d.get('reconstruction',{})
            checkpoints[path.parent.name]=d
            iterations+=len(d['history'])
            cursors.append(dict(context_id=path.parent.name,iterations=len(d['history']),
                completed_left_tracks=r.get('left',0),neighbor=r.get('neighbor',0),
                retained_candidates=len(r.get('candidates',[]))))
        for path in state.glob('meditations/**/result.json'):
            d=json.loads(path.read_text());results.append(digest({k:d.get(k) for k in
                ('status','source_episode','source_sha256','tracks','history','merges','quality')}))
            if d.get('status')=='completed':
                c=checkpoints.get(path.parent.name)
                consistent &= c is not None and all(c.get(k)==d.get(k) for k in ('source_sha256','tracks','history','merges'))
        import subprocess
        revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        report=dict(schema='normal-development-benchmark-v1',code_revision=revision,
            dirty_worktree=bool(subprocess.check_output(['git','status','--porcelain'],text=True)),
            environment=dict(machine=platform.machine(),python=platform.python_version(),
                platform=platform.platform(),affinity=sorted(os.sched_getaffinity(0)),
                cpu_quota=Path('/sys/fs/cgroup/cpu.max').read_text().strip() if Path('/sys/fs/cgroup/cpu.max').exists() else None,
                memory_limit=Path('/sys/fs/cgroup/memory.max').read_text().strip() if Path('/sys/fs/cgroup/memory.max').exists() else None),
            profiled=bool(prof),wall_seconds=elapsed,cpu_seconds=cpu_time,
            user_seconds=u.ru_utime-usage.ru_utime,system_seconds=u.ru_stime-usage.ru_stime,
            peak_rss_bytes=u.ru_maxrss*1024,input_blocks=u.ru_inblock-usage.ru_inblock,
            output_blocks=u.ru_oublock-usage.ru_oublock,per_core_system_busy_percent=per_core,
            per_core_interpretation='Whole-system counters; not exclusive attribution to Charlie',
            completed_analytical_stages=iterations,meditation_cursors=cursors,
            checkpoint_result_consistent=consistent,
            scientific_result_digests=results,independently_qualified_findings=sum(
                r.data['payload'].get('category')=='meditation_candidate_evaluation' and
                r.data['payload'].get('result',{}).get('metrics',{}).get('fresh_final_evidence') is True
                for r in records),original_evidence_inventory=before,
            evidence_unchanged=before==inventory(args.episode_root),error=error,
            physical_authorization=False,physical_score_improvement='UNKNOWN')
        (args.output/'benchmark.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
