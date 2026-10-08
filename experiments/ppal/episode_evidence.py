"""Offline adapter: preserved PPAL artifacts -> generic evidence -> replay tests.

No live imports this module. No camera, controller or second tracker is opened.
Original logs remain canonical; the notebook indexes hashed JSON locations.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from math import hypot
from pathlib import Path
import time

from memory.evidence import EvidenceJournal, digest, read_artifact
from .predict_robotron import predict_next

ADAPTER = 'robotron-artifact-adapter-v1'


def _external_observations(root,journal,episode,start_id,provenance):
    """Acquisition overlays can arrive after capture import without new gameplay."""
    path=root/'external-observations.json'
    if not path.is_file():return
    reference=dict(path=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    for index,row in enumerate(json.loads(path.read_text())):
        if not isinstance(row,dict) or not row.get('source') or 'value' not in row:
            raise ValueError('external observation needs source and value')
        journal.append('observation',dict(category='external_observation',
            artifact={**reference,'pointer':[index]},epistemic_status='subsystem report, not environmental truth'),
            episode=episode,at=row.get('timestamp'),sources=[start_id],producer=ADAPTER,version='1',provenance=provenance)


def _session_history(root,journal,episode,start_id,refs):
    """Retain live prospective records exactly once, never replay as experience."""
    name='session-evidence.sqlite3'
    if name not in refs:return
    source=EvidenceJournal(root/name,read_only=True)
    try:
        rows=source.records()
        journal.merge_from(source)
        journal.append('event',dict(category='recording_history_retained',artifact=refs[name],
            original_record_ids=[r.id for r in rows],
            interpretation='original recording history; not additional independent gameplay'),
            episode=episode,sources=[start_id],producer=ADAPTER,version='1')
    finally:source.close()


def import_episode(root, journal, *, identity=None):
    root = Path(root)
    report_path = root / 'report.json'
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    provenance = report.get('provenance', {})
    from learning.acquisition import maintain_episode_identity
    from memory.episode_identity import IdentityIntegrityError
    identity = identity or maintain_episode_identity(root,journal)
    if identity['status']=='quarantined':
        raise IdentityIntegrityError(identity['reason'])
    refs = {name:dict(path=name,sha256=value) for name,value in identity['artifacts'].items()}
    episode = identity['source_episode']
    # Acquisition preserves every package independently. The content adapter
    # observes shared experience once; copies are not another observation.
    complete = [r for r in journal.records('event') if r.data['payload'].get('category')=='episode_import_complete'
                and r.data['episode']==episode]
    if complete:
        start=next(r for r in journal.records('episode') if r.data['episode']==episode)
        _external_observations(root,journal,episode,start.id,provenance)
        _session_history(root,journal,episode,start.id,refs)
        return episode
    start = journal.append('episode', dict(artifacts=refs, capture_id=identity['capture_id'], manifest_id=identity['manifest_id'],
                           content_id=identity['content_id'], experience_id=identity['experience_id'],
                           observation_id=identity['observation_id'], independent_gameplay=identity['independent_gameplay'],
                           outcome=report.get('result'),
                           completeness='report_present' if report_path.exists() else 'partial; boundary unknown',
                           configuration={k:report.get(k) for k in ('armed','seconds','pulse_ms','bootstrap_body_fire')},
                           wall_time=None, wall_time_status='not recorded; filename is not a clock anchor'),
                           episode=episode, producer=ADAPTER, version='1', provenance=provenance)
    def add(category, ref, at=None, subsystem=None):
        return journal.append('observation', dict(category=category, artifact=ref,
                              epistemic_status='subsystem report, not environmental truth'),
                              episode=episode, at=at, sources=(start.id,), producer=subsystem or ADAPTER,
                              version='1', provenance=provenance)
    # Partial runs without agency/score remain first-class episodes.
    if 'report.json' in refs:
        add('session_report', refs['report.json'])
    executions = set()
    for name, category in (('agency.jsonl','agency_tracking_observation'), ('score.jsonl','score_observation'),
                           ('events.jsonl','session_event_observation'), ('steps.jsonl','partial_planning_observation')):
        if name not in refs:
            continue
        if name == 'steps.jsonl' and report_path.exists():
            continue  # completed report already references those same steps
        for line, text in enumerate((root/name).read_text().splitlines(), 1):
            if not text.strip():
                continue
            try:
                row = json.loads(text)
            except ValueError:
                # A killed writer may leave a torn final line. It remains in the
                # hashed artifact; do not reinterpret it as an observation.
                add('unreadable_artifact_line', {**refs[name], 'line':line})
                continue
            at = row.get('capture_timestamp', row.get('timestamp'))
            if name == 'events.jsonl':
                at = row.get('at', at)  # Existing diary's explicit monotonic phase timestamps.
            # Legacy relative t is NOT interchangeable with sensor monotonic time.
            ref = {**refs[name], 'line':line}
            with journal.batch():
                add(category, ref, at=at, subsystem=name.removesuffix('.jsonl'))
                execution = row.get('control_execution') if name=='agency.jsonl' else None
                if execution and digest(execution) not in executions:
                    executions.add(digest(execution))
                    add('action_transport_report',{**ref,'pointer':['control_execution']},
                        at=execution.get('started_at'),subsystem='controller')
    for index, step in enumerate(report.get('steps', [])):
        ref = {**refs['report.json'], 'pointer':['steps', index]}
        add('planning_observation', ref, step.get('observed_at',step.get('capture_timestamp')))
        if 'action' in step:
            add('action_issued', ref, step.get('action_timestamp'))
        if 'shadow' in step:
            add('reported_forecast', {**ref,'pointer':ref['pointer']+['shadow']}, step.get('observed_at'))
    _external_observations(root,journal,episode,start.id,provenance)
    _session_history(root,journal,episode,start.id,refs)
    # Index preflight/failure context without inventing transition timestamps.
    for field in ('startup_watch','exposure_preflight','episode_end','calibration','acquisition',
                  'sensory_preflight','exploratory_startup','session_evidence'):
        if field in report:
            add('session_'+field,{**refs['report.json'],'pointer':[field]})
    journal.append('event',dict(category='episode_import_complete',content_id=identity['content_id']),
        episode=episode,sources=[start.id],producer=ADAPTER,version='2')
    return episode


def derive_episode(root, journal, episode, *, window=3, tolerance=2.0):
    """Re-derive from immutable references; forecasts explicitly made in replay.

    A second run/version appends its interpretations, preserving older ones.
    Model receives past points only; no outcome participates in prediction.
    """
    if window < 2 or tolerance <= 0:
        raise ValueError('window>=2 and positive tolerance required')
    version = f'cv-window-{window}-tolerance-{tolerance:g}-v1'
    completed = [r for r in journal.records('derivation_complete') if r.data['episode']==episode and r.data['version']==version]
    if completed:
        return [r for r in journal.records() if r.data['version']==version and r.data['kind'] in ('event','resolution_reference')]
    from memory.evidence import ArtifactReader
    read_verified = ArtifactReader(root)
    history = {}
    previous_agency = None
    previous_score = None
    derivations = []
    for record in journal.records('observation'):
        doc = record.data
        if doc['episode'] != episode:
            continue
        payload = doc['payload']
        if payload['category'] not in ('agency_tracking_observation','score_observation'):
            continue
        row = read_verified(payload['artifact'])
        if payload['category'] == 'score_observation':
            if previous_score:
                changes = {channel:row.get(channel,{}).get('delta') for channel in ('p1','p2')
                           if row.get(channel,{}).get('changed') is True}
                if changes:
                    derivations.append(journal.append('event', dict(category='accepted_score_changed',
                        channels=changes, self_score=row.get('self_score'), self_delta=row.get('self_delta'),
                        attribution='unknown; temporal adjacency is not causation'), episode=episode,
                        at=doc['at'], sources=(previous_score.id,record.id), producer=ADAPTER, version=version))
            previous_score = record
            continue
        track = row.get('tracking')
        if not track:
            continue
        with journal.batch():
            for event in track.get('events',[]):
                # 'created' means tracker allocation, not confirmed physical birth.
                if event.get('kind') in ('created','missed','finished'):
                    derivations.append(journal.append('event', dict(category='tracker_'+event['kind'],
                        report=event, physical_birth_death='unknown'), episode=episode, at=doc['at'],
                        sources=(record.id,), producer='SpriteTracker-report-adapter', version=version))
            if previous_agency:
                old = read_verified(previous_agency.data['payload']['artifact'])
                before = old.get('identity_status', 'confirmed' if old.get('self_track_id') is not None else 'unknown')
                after = row.get('identity_status', 'confirmed' if row.get('self_track_id') is not None else 'unknown')
                if before != after or old.get('self_track_id') != row.get('self_track_id'):
                    derivations.append(journal.append('event', dict(category='self_belief_changed',
                        before=dict(status=before,track_id=old.get('controlled_track_id',old.get('self_track_id'))),
                        after=dict(status=after,track_id=row.get('controlled_track_id',row.get('self_track_id'))),
                        confidence=row.get('confidence'), status='belief, not certified physical identity'),
                        episode=episode, at=doc['at'], sources=(previous_agency.id,record.id),
                        producer='AgencyTracker-report-adapter', version=version))
            previous_agency = record
            for d in track.get('detections',[]):
                history.setdefault(d['track_id'], []).append((record,dict(tick=row['sample'],center=d['center'])))
    # One ordered replay notebook, not one tracker/association per object.
    replay_path = journal.path.with_name(journal.path.stem + f'.{version}.replay.sqlite3')
    replay = EvidenceJournal(replay_path, on_progress=journal.on_progress)
    def predict_once(expected, **args):
        return replay.existing_prediction(expected, **args) or replay.predict(expected, **args)
    def resolve_once(identifier, **args):
        existing = replay.resolution_for(identifier)
        if existing:
            payload = existing.data['payload']
            if (any(payload[k] != args.get(k) for k in ('result','reason','error'))
                    or existing.data['sources'] != [identifier,*args.get('sources',())]):
                raise ValueError('resumption conflicts with committed resolution; use a new interpretation version')
            return existing
        return replay.resolve(identifier, **args)
    pending = {}
    past = {}
    by_record = {}
    for identifier, points in history.items():
        for source, point in points:
            by_record.setdefault(source.sequence, (source, {}))[1][identifier] = point
    try:
        for source, points in sorted(by_record.values(), key=lambda pair: pair[0].sequence):
            at = source.data['at']
            if at is None:
                continue
            with journal.batch(), replay.batch():
                observation = replay.append('observation',dict(canonical_evidence=source.id,
                    artifact=source.data['payload']['artifact']), episode=episode,at=at,
                    producer='canonical-evidence-reference',version='1')
                sample = next(iter(points.values()))['tick']
                for identifier, prediction in list(pending.items()):
                    point = points.get(identifier)
                    expected = prediction.data['payload']['expected']
                    timely = at<=prediction.data['payload']['deadline'] and sample==expected['target_sample']
                    error = hypot(point['center'][0]-expected['center'][0],point['center'][1]-expected['center'][1]) if point else None
                    resolution = resolve_once(prediction.id,sources=(observation.id,),
                        result=('supported' if error<=tolerance else 'contradicted') if point and timely else 'unresolved',
                        reason='same tracker ID at predicted sample within horizon' if point and timely else 'same ID not observed at predicted sample within horizon',
                        error=error if point and timely else None)
                    derivations.append(journal.append('resolution_reference',dict(**resolution.data['payload'],
                        replay_artifact=replay_path.name, replay_resolution_id=resolution.id),
                        episode=episode,at=at,sources=(source.id,),producer='predict_robotron.predict_next',version=version))
                    del pending[identifier]
                for identifier, point in points.items():
                    past.setdefault(identifier,[]).append(point)
                    if identifier in pending or len(past[identifier])<2:
                        continue
                    expected = predict_next(past[identifier],point['tick']+1,window=window)
                    pending[identifier] = predict_once(dict(track_id=identifier,center=list(expected),
                        target_sample=point['tick']+1,tolerance=tolerance,units='normalized_board_percent',
                        condition='same ID in next agency sample within one second'),
                        episode=episode,at=at,deadline=at+1.0,sources=(observation.id,),
                        producer='predict_robotron.predict_next',version=version)
        for prediction in pending.values():
            resolution = resolve_once(prediction.id,sources=(),result='unresolved',reason='episode ended without outcome')
            derivations.append(journal.append('resolution_reference',dict(**resolution.data['payload'],
                replay_artifact=replay_path.name,replay_resolution_id=resolution.id),episode=episode,
                producer='predict_robotron.predict_next',version=version))
        journal.append('derivation_complete',dict(replay_artifact=replay_path.name,
            replay_sha256=hashlib.sha256(replay_path.read_bytes()).hexdigest()),episode=episode,
            producer=ADAPTER,version=version)
    finally:
        replay.close()
    return derivations


def summarize(journal, episode):
    rows = [r for r in journal.records() if r.data['episode']==episode]
    return dict(schema='charlie-evidence-summary-v1',episode=episode,
                records=dict(Counter(r.data['kind'] for r in rows)),
                resolutions=dict(Counter(r.data['payload']['result'] for r in rows if r.data['kind']=='resolution_reference')),
                prediction_status='replay prospective; historical live forecasts are reported observations only',
                gameplay_overhead_seconds=0.0, integration='offline only; no live imports')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('episode',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--window',type=int,default=3)
    parser.add_argument('--tolerance',type=float,default=2.0)
    parser.add_argument('--reflect',action='store_true',help='consolidate diagnostics through existing MemoryGateway/MARM outbox')
    args=parser.parse_args()
    if args.output.resolve().is_relative_to(args.episode.resolve()):
        parser.error('keep derived output outside the original episode directory')
    args.output.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter()
    journal=EvidenceJournal(args.output/'evidence.sqlite3')
    try:
        episode=import_episode(args.episode,journal)
        derive_episode(args.episode,journal,episode,window=args.window,tolerance=args.tolerance)
        result=summarize(journal,episode)
        result['offline_processing_seconds']=time.perf_counter()-start
        if args.reflect:
            from memory.gateway import MemoryGateway
            from .reflect_robotron import reflect_evidence
            result['reflection']=reflect_evidence(journal,episode,MemoryGateway())
        (args.output/'evidence-summary.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
    finally:
        journal.close()


if __name__=='__main__':
    main()
