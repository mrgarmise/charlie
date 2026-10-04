"""Read-only qualification of preserved captures; no labels, fitting or hardware.

Availability and provenance are measured here. Tracker beliefs, predictions and
retained scores never qualify identities, physical effects or complete games.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics
from PIL import Image
from memory.evidence import EvidenceJournal, digest
from .datasets import SCOPE, sha
from .retrospective import inventory, _rows

VERSION = 'robotron-preserved-archive-audit-v2'


def capture_bindings(root, report, agency, scores):
    """Only explicit saved references bind pixels to sample/exposure time.

    Legacy final score images have no row reference. Their score-summary
    retention declaration binds the final processed sample; filename similarity
    alone cannot establish that relationship.
    """
    root = Path(root)
    rows = []; issues = []
    def add(name, row, kind, basis):
        if not isinstance(name, str): return
        p = (root/name).resolve()
        if not p.is_relative_to(root.resolve()):
            issues.append(dict(path=name, reason='capture reference escapes source')); return
        at = row.get('capture_timestamp', row.get('timestamp'))
        if type(at) not in (int, float) or not math.isfinite(at) or at < 0:
            issues.append(dict(path=name, reason='missing finite exposure timestamp')); return
        if not p.is_file():
            issues.append(dict(path=name, reason='referenced capture missing')); return
        with Image.open(p) as im: size = list(im.size)
        rows.append(dict(path=name, sha256=sha(p), sample=row.get('sample'),
            timestamp=at, kind=kind, dimensions=size, binding=basis,
            identity_status='unqualified'))
    for row in agency:
        add(row.get('raw_frame'), row, 'playfield', 'agency row raw_frame')
    for row in scores:
        add(row.get('raw_frame'), row, 'camera-hud', 'score row raw_frame')
    if scores:
        last = scores[-1]
        name = 'score-raw-%04d.png' % last['sample'] if type(last.get('sample')) is int else None
        summary = report.get('score_summary', {})
        retained=summary.get('raw_frames', [])
        if (name and retained and retained[-1]==name and summary.get('worker_finished') is True
                and not any(r['path'] == name for r in rows)):
            add(name, last, 'camera-hud', 'closed worker final-sample retention declaration')
    seen = {}; conflicts = []
    for row in rows:
        key = (row['kind'], row['sample'])
        if key in seen and (seen[key]['sha256'],seen[key]['timestamp']) != (row['sha256'],row['timestamp']):
            conflicts.append(dict(kind=key[0], sample=key[1], reason='conflicting sample bindings'))
        seen[key] = row
    for kind in ('playfield','camera-hud'):
        sequence=[r for r in rows if r['kind']==kind]
        if any(b['timestamp']<=a['timestamp'] for a,b in zip(sequence,sequence[1:])):
            conflicts.append(dict(kind=kind,reason='capture timestamps are not strictly increasing'))
    return rows, issues+conflicts


def cadence(bindings):
    """Frozen motion evaluation needs observed 150ms horizons, never interpolation."""
    rows = sorted((r for r in bindings if r['kind']=='playfield'), key=lambda r:r['timestamp'])
    intervals = [b['timestamp']-a['timestamp'] for a,b in zip(rows,rows[1:])]
    # The frozen evaluator skips the first pair: velocity needs a preceding
    # exposure. A single first-pair horizon is not an executable measurement.
    pairs = [dict(before=a['path'],after=b['path'],seconds=b['timestamp']-a['timestamp'])
             for i,(a,b) in enumerate(zip(rows,rows[1:]))
             if i>=1 and abs(b['timestamp']-a['timestamp']-.15)<=.025]
    return dict(captures=len(rows), adjacent_pairs=len(intervals),
        median_seconds=statistics.median(intervals) if intervals else None,
        minimum_seconds=min(intervals,default=None),maximum_seconds=max(intervals,default=None),
        frozen_horizon_seconds=.15,tolerance_seconds=.025,compatible_pairs=pairs,
        qualification='timing availability only; identities remain unqualified')


def audit(root):
    root = Path(root).resolve()
    game = root/'game-01' if (root/'game-01').is_dir() else root
    before = inventory(root)
    report = json.loads((game/'report.json').read_text()) if (game/'report.json').is_file() else {}
    episode = 'episode:'+sha(game/'report.json') if (game/'report.json').is_file() else 'partial-episode:'+digest(before)
    history = json.loads((Path(__file__).resolve().parents[1]/'docs/ppal/ala-1-demonstration.json').read_text())['snapshot_split']
    prior = history.get(episode, 'unknown')
    agency, agency_torn = _rows(game,'agency.jsonl'); scores, score_torn = _rows(game,'score.jsonl')
    bindings, issues = capture_bindings(game,report,agency,scores)
    timing = cadence(bindings)
    medpath = game.parent/(game.name+'-evidence')/'meditation.json'
    med = json.loads(medpath.read_text()) if medpath.exists() else None
    journals = []
    for path in sorted(root.rglob('*.sqlite3')):
        journal = EvidenceJournal(path,read_only=True)
        try: journals.append(dict(path=str(path.relative_to(root)),records=len(journal.records()),verified=True))
        finally: journal.close()
    executions = {digest(r['control_execution']):r['control_execution'] for r in agency if r.get('control_execution')}
    windows = []
    for a,b in zip(agency,agency[1:]):
        names = (a.get('raw_frame'),b.get('raw_frame'))
        if all(n and (game/n).is_file() for n in names) and b.get('control_execution'):
            windows.append(dict(before=names[0],after=names[1],
                before_timestamp=a.get('capture_timestamp'),after_timestamp=b.get('capture_timestamp'),
                execution_digest=digest(b['control_execution']),
                physical_effect='UNKNOWN',identity='unqualified'))
    final = scores[-1] if scores else None
    reasons = ['Independent identity/role/trajectory annotations are not supplied',
        'Controller transport is not proof of physical effects',
        'Start/termination captures do not independently certify a complete-game boundary',
        'Retained scores are historical reader state, not fresh score observations']
    if not timing['compatible_pairs']: reasons.append('No preserved playfield pairs match frozen 150ms +/-25ms motion evaluation')
    if prior != 'unknown': reasons.append('Published prior partition use excludes fresh final admission')
    if inventory(root)!=before: raise ValueError('archive changed during read-only audit')
    return dict(schema=VERSION,source_root=str(root),game_relative=str(game.relative_to(root)),
        source_episode=episode,inventory=before,inventory_digest=digest(before),
        preserved_bytes_unchanged=True,prior_partition=prior,final_already_consulted=prior=='test',
        journals=journals,learning_mode=report.get('learning_mode'),result=report.get('result'),
        recorded_score=report.get('score'),last_score_observation=final,score_rows=len(scores),
        terminal=report.get('episode_end'),
        meditation_artifact_sha256=sha(medpath) if med else None,
        preserved_meditation_quality=med.get('quality') if med else None,
        capture_bindings=bindings,binding_issues=issues,cadence=timing,
        action_response_review_windows=windows,
        score_status_counts=dict(Counter(r.get('p1',{}).get('status','unknown') for r in scores)),
        score_current_observations=sum(r.get('p1',{}).get('observed_score') is not None for r in scores),
        score_retained_without_observation=sum(r.get('p1',{}).get('score') is not None and r.get('p1',{}).get('observed_score') is None for r in scores),
        torn_lines={'agency.jsonl':agency_torn,'score.jsonl':score_torn},
        admissibility=dict(diagnostic=True,unlabeled_training=True,
            independently_verified_training=False,fresh_final_evaluation=False,
            complete_game_score=False,physical_score_improvement=False),reasons=reasons,
        required_new_evidence=['Independent persistent player/object identities and board coordinates',
            'At least one validation and three distinct unconsulted final motion episodes with observed 150ms +/-25ms pairs',
            'Synchronized start/terminal/HUD captures with independently qualified score channel and score reader',
            'Candidate-specific native Pi cadence/ownership/reacquisition/recovery/rollback qualification'],
        recoverable_existing=['Hash/timestamp-bound early playfield captures and recorded command windows for independent annotation',
            'Retained final camera HUD capture for score/phase review; no terminal claim',
            'Historical score proposals, abstentions and conflicts for segregated reader qualification'])


def ingest(journal, report):
    """Publish new measurement availability, never another historical experience."""
    if report.get('schema')!=VERSION: raise ValueError('qualification report required')
    stable = {k:v for k,v in report.items() if k!='source_root'}
    key = digest(stable)
    prior = [r for r in journal.records('observation') if r.data['payload'].get('category')=='observation_qualification'
             and r.data['payload'].get('qualification_key')==key]
    if prior: return prior[0]
    return journal.append('observation',dict(category='observation_qualification',qualification_key=key,
        source_episode=report['source_episode'],report=report,new_physical_experience=False),
        episode=SCOPE,producer='archive-measurement-service',version=VERSION)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); result=audit(args.episode)
    if args.output.resolve().is_relative_to(args.episode.resolve()):
        parser.error('output must be outside original evidence')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream: json.dump(result,stream,indent=2);stream.write('\n')


if __name__=='__main__': main()
