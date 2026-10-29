"""Local operator inspection/review; uses the normal application's notebook."""
import argparse
import fcntl
import json
from pathlib import Path
from memory.evidence import EvidenceJournal
from .service import ModelLearningService
from .robotron import import_fixtures
from .adapters import get_adapter


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state',type=Path,required=True,help='same --learning-state as main.py; stop application before writes')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('status')
    sub.add_parser('baseline')
    sub.add_parser('coverage')
    gallery=sub.add_parser('review-gallery');gallery.add_argument('output',type=Path)
    reviews=sub.add_parser('review-import');reviews.add_argument('packet',type=Path)
    sub.add_parser('import-fixtures')
    label=sub.add_parser('label');label.add_argument('observation_id');label.add_argument('label',choices=get_adapter().labels)
    label.add_argument('--reviewer',required=True);label.add_argument('--reason',required=True);label.add_argument('--supersedes')
    split=sub.add_parser('partition');split.add_argument('session');split.add_argument('partition',choices=['train','validation','test']);split.add_argument('--reviewer',required=True)
    intake=sub.add_parser('ingest');intake.add_argument('manifest',type=Path,help='local JSON with source frame path, session, provenance, authentic, calibration and optional partition')
    args=p.parse_args(argv);args.state.mkdir(parents=True,exist_ok=True)
    with (args.state/'offline.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        journal=EvidenceJournal(args.state/'learning-evidence.sqlite3')
        try:
            service=ModelLearningService(journal,args.state/'model-learning')
            if args.command in ('review-gallery','review-import','coverage'):
                from .review import export_gallery, import_reviews, coverage
                from learning.resources import DevelopmentResources, ResourceGuard
                guard=ResourceGuard()
                if args.command=='review-gallery':
                    DevelopmentResources().apply();guard.check(force=True)
                result = export_gallery(service.data,args.output,on_progress=guard.check) if args.command=='review-gallery' else import_reviews(service.data,args.packet) if args.command=='review-import' else coverage(service.data)
                print(json.dumps(result,indent=2)); return
            if args.command=='import-fixtures': import_fixtures(service.data,Path(__file__).resolve().parents[2])
            if args.command=='label': service.data.label(args.observation_id,args.label,reviewer=args.reviewer,reason=args.reason,supersedes=args.supersedes)
            if args.command=='partition': service.data.partition(args.session,args.partition,reviewer=args.reviewer)
            if args.command=='ingest':
                manifest=json.loads(args.manifest.read_text())
                if not isinstance(manifest,list) or len(manifest)>256: raise ValueError('bounded 256-observation intake required')
                for row in manifest:
                    service.data.add(row['path'],session=row['session'],provenance=row['provenance'],authentic=row['authentic'],
                        calibration=row.get('calibration'),partition=row.get('partition'))
            if args.command=='baseline':
                import time, platform
                from learning.resources import DevelopmentResources, ResourceGuard
                DevelopmentResources().apply()
                guard=ResourceGuard();guard.check(force=True)
                from .robotron import frame,incumbent
                from .evaluation import metrics
                rows=service.data.rows();predictions=[];truth=[];latency=[];observations=[]
                for row in rows:
                    guard.check()
                    start=time.perf_counter();prediction=incumbent(frame(row));latency.append((time.perf_counter()-start)*1000)
                    observations.append(dict(observation_id=row['observation_id'],sha256=row['sha256'],provenance=row['provenance'],
                        session=row['session'],label=row['label'],incumbent=prediction))
                    if row['label'] is not None:truth.append(row['label']);predictions.append(prediction)
                report=dict(schema='model-learning-baseline-v1',counts=service.data.inspect()['counts'],
                    incumbent=metrics(truth,predictions),observations=observations,
                    latency_ms_including_image_load=latency,resources=guard.sample,hardware=dict(runtime='CPU only',architecture=platform.machine(),system=platform.system()),candidate=None,
                    independence='descriptive replay of retained labels; NOT an independent accuracy estimate',
                    transitions='not measured',unknown_recall='see incumbent metrics' if 'unknown' in truth else 'not measured: no reviewed unknown labels',status=service.data.inspect()['status'])
                print(json.dumps(report,indent=2))
            else: print(json.dumps(service.status(),indent=2))
        finally:journal.close()

if __name__=='__main__': main()
