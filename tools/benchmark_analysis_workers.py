"""Bounded pure-worker admissibility experiment, not normal learning orchestration.

Only candidate-link arithmetic is performed; no journal, agenda, camera,
controller, candidate generation, independent qualification or policy access.
Use its measured cost to decide whether worker integration is justified.
"""
import argparse
from bisect import bisect_right
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
import os
from pathlib import Path
import resource
import time
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from experiments.ppal.meditate_robotron import predicted_link,_prepare
from learning.datasets import sha
from memory.evidence import digest


def initialize(tracks):
    global _tracks,_prepared
    _tracks=tracks;_prepared=[_prepare(t,3) for t in tracks]
    resource.setrlimit(resource.RLIMIT_CPU,(60,61))


def score(chunk):
    return [(i,j,predicted_link(_tracks[i],_tracks[j],prepared=(_prepared[i],_prepared[j]))) for i,j in chunk]


def run(tracks,workers):
    onsets=sorted((int(t['first_tick']),j) for j,t in enumerate(tracks));times=[a for a,j in onsets]
    pairs=[]
    for i,t in enumerate(tracks):
        end=int(t['last_tick'])
        pairs.extend((i,j) for j in sorted(j for _,j in onsets[bisect_right(times,end):bisect_right(times,end+5)]) if i!=j)
    chunks=[pairs[i:i+256] for i in range(0,len(pairs),256)]
    started=time.monotonic();cpu=time.process_time();children=resource.getrusage(resource.RUSAGE_CHILDREN)
    results=[]
    if workers==1:
        initialize(tracks)
        for chunk in chunks:results.extend(score(chunk))
    else:
        with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn'),initializer=initialize,initargs=(tracks,)) as pool:
            # At most one batch per worker in flight, including result buffers.
            for i in range(0,len(chunks),workers):
                futures=[pool.submit(score,c) for c in chunks[i:i+workers]]
                for future in futures:results.extend(future.result(timeout=60))
    used=resource.getrusage(resource.RUSAGE_CHILDREN)
    return dict(workers=workers,wall_seconds=time.monotonic()-started,
        cpu_seconds=time.process_time()-cpu+used.ru_utime+used.ru_stime-children.ru_utime-children.ru_stime,
        self_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        maximum_child_peak_rss_bytes=used.ru_maxrss*1024 if workers>1 else None,
        completed_pairs=len(results),result_digest=digest(results),source_mutated=False,
        qualification='Unverified preserved-track arithmetic; no independent findings')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('tracks',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():raise ValueError('preserve previous worker benchmarks')
    allowed=sorted(os.sched_getaffinity(0));os.sched_setaffinity(0,allowed[-2:])
    os.nice(10)
    before=sha(args.tracks);tracks=json.loads(args.tracks.read_text())['tracks']
    result=[run(tracks,n) for _ in range(3) for n in (1,2)]
    assert sha(args.tracks)==before
    assert len({r['result_digest'] for r in result})==1
    args.output.write_text(json.dumps(dict(source_sha256=before,results=result,
        physical_authorization=False,independently_qualified_findings=0),indent=2))


if __name__=='__main__':main()
