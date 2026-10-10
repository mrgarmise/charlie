"""Preregistered physical score comparison over preserved episode evidence.

This adapter analyzes records; it never captures, controls, certifies a reader,
or chooses a policy. Qualification evidence must come from independent work.
"""
from dataclasses import asdict
import random
from memory.evidence import digest
from .runner import analyze

VERSION='robotron-score-comparison-v2'


def commit(journal, plan, *, conditions, sources, episode, require_certificates=True):
    plan.validate()
    if require_certificates is not True:
        raise ValueError('new protocols require certificates; preserved v1 records remain readable')
    if plan.synthetic or plan.primary.name!='official_game_score' or not plan.primary.higher_is_better:
        raise ValueError('physical official-score objective required')
    if not sources or not all(conditions.get(k) for k in ('camera','game','system','measurement')):
        raise ValueError('frozen camera/game/system/measurement conditions and learning provenance required')
    rng=random.Random(plan.seed); schedule=[]
    for pair in range(plan.pairs):
        order=['baseline','candidate'];rng.shuffle(order)
        base=len(schedule)
        schedule.extend([dict(slot=base+i,pair=pair,arm=arm,
                             policy=getattr(plan,arm)) for i,arm in enumerate(order)])
    return journal.append('event',dict(category='physical_score_protocol',plan=asdict(plan),
        conditions=conditions,schedule=schedule,require_certificates=require_certificates,
        rule='independent complete games in randomized temporal blocks; no identical game RNG claimed',
        stopping='predeclared pairs; missing/uncertain outcomes retained as inconclusive'),
        episode=episode,sources=sources,producer='existing-comparison',version=VERSION)


def evaluate(journal, protocol_id, plan, episode_records):
    protocol=journal.get(protocol_id);p=protocol.data['payload']
    if p.get('category')!='physical_score_protocol' or digest(p['plan'])!=digest(asdict(plan)):
        raise ValueError('comparison must match the exact committed plan')
    failures=[];slots={};episodes=set();sources=[protocol_id]
    for identifier in episode_records:
        record=journal.get(identifier);row=record.data['payload'];sources.append(identifier)
        if record.sequence<=protocol.sequence or record.data['episode']!=protocol.data['episode']:
            raise ValueError('prospective protocol and consolidated episode references required')
        if row.get('category')!='robotron_evaluation_episode':raise ValueError('episode evidence required')
        slot=row.get('slot');episode=row.get('source_episode')
        if type(slot) is not int or not 0<=slot<len(p['schedule']) or not episode:
            raise ValueError('scheduled slot and physical episode identity required')
        from learning.episode_identity import canonical_experience, eligible
        group=canonical_experience(journal,episode)
        if slot in slots or group in episodes:raise ValueError('repeated games are not independent trials')
        episodes.add(group);slots[slot]=None
        if not eligible(journal,row):
            failures.append(dict(slot=slot,reason='source identity association quarantined'));continue
        scheduled=p['schedule'][slot]
        if row.get('policy')!=scheduled['policy'] or row.get('conditions')!=p['conditions']:
            failures.append(dict(slot=slot,reason='policy or environmental conditions differ'));continue
        if row.get('confirmed_terminal') is not True:
            failures.append(dict(slot=slot,reason='unconfirmed complete-game boundary'));continue
        if p.get('require_certificates'):
            try:
                validate_certificates(journal,row,protocol=protocol)
            except (ValueError,KeyError,OSError) as exc:
                failures.append(dict(slot=slot,reason='Unqualified hash-bound measurement/boundary: '+str(exc)));continue
        measurements=row.get('score_observations',[])
        qualified=[m for m in measurements if m.get('qualification')=='independently_validated'
                   and m.get('validation_evidence') and m.get('artifact_sha256')
                   and m.get('timestamp') is not None and m.get('phase')=='final']
        # No source/person gets priority. Preserve disagreement; do not adjudicate.
        if not qualified or len(qualified)!=len(measurements):
            failures.append(dict(slot=slot,reason='unqualified or unknown final score evidence'));continue
        values=[m.get('value') for m in qualified]
        if any(type(v) is not int or not plan.primary.low<=v<=plan.primary.high for v in values) or len(set(values))!=1:
            failures.append(dict(slot=slot,reason='score disagreement or declared metric range exceeded'));continue
        metrics=dict(row.get('diagnostic_metrics',{}),official_game_score=values[0])
        if any(name not in metrics for name in [m.name for m in plan.guardrails]):
            failures.append(dict(slot=slot,reason='missing preregistered guardrail'));continue
        if any(not isinstance(metrics[m.name],(int,float)) or not m.low<=metrics[m.name]<=m.high for m in plan.guardrails):
            failures.append(dict(slot=slot,reason='invalid guardrail'));continue
        slots[slot]=metrics
    trials=[]
    for pair in range(plan.pairs):
        members=[s for s in p['schedule'] if s['pair']==pair]
        if all(slots.get(s['slot']) is not None for s in members):
            trials.append(dict(pair=pair,**{s['arm']:slots[s['slot']] for s in members}))
    report=analyze(plan,trials,error='uncertain or missing scheduled games' if failures or len(slots)!=len(p['schedule']) else None)
    report.update(protocol_id=protocol_id,failures=failures,
        qualification='provided independent validation references; this analyzer does not certify measurement methods',
        limitations=['randomized blocks do not restore identical Robotron randomness',
                     'diagnostic accuracy alone is not score improvement'])
    return journal.append('observation',dict(category='physical_score_comparison',report=report),
        episode=protocol.data['episode'],sources=sources,producer='existing-comparison',version=VERSION)


def validate_certificates(journal,row,*,protocol=None):
    """Resolve independent certificates; strings and held HUD values cannot pass.

    External qualification remains an independent prerequisite. Here we verify
    exact artifacts and consistency, rather than certifying a reader ourselves.
    """
    from learning.datasets import sha
    import math
    def certificate(identifier,category):
        record=journal.get(identifier);p=record.data['payload']
        if (record.data['producer']!='independent-physical-measurement'
                or p.get('category')!=category or p.get('status')!='verified'
                or p.get('source_episode')!=row['source_episode']):
            raise ValueError('independent episode-bound certificate required')
        if protocol is not None and (record.sequence<=protocol.sequence or record.data['episode']!=protocol.data['episode']):
            raise ValueError('prospective consolidated certificate required')
        proof=p.get('qualification_artifact',{})
        if not proof.get('path') or sha(proof['path'])!=proof.get('sha256'):
            raise ValueError('qualification proof missing or changed')
        return p
    boundary=certificate(row['boundary_certificate'],'complete_game_boundary')
    if protocol is not None and (boundary.get('protocol_id')!=protocol.id or boundary.get('slot')!=row['slot']
                                or boundary.get('policy')!=row['policy']):
        raise ValueError('boundary must bind the preregistered slot and frozen policy')
    report=boundary.get('source_report',{})
    from learning.episode_identity import qualified_reference
    qualified_reference(journal,row['source_episode'],report,capture_root=boundary.get('source_capture_root'))
    if boundary.get('complete_game') is not True or boundary.get('end_reason') not in ('GAME OVER','terminal'):
        raise ValueError('complete GAME OVER boundary required')
    start=boundary.get('start_frame',{})
    if (boundary.get('start_state')!='new_game' or not start.get('path')
            or sha(start['path'])!=start.get('sha256') or not isinstance(start.get('timestamp'),(int,float))
            or not math.isfinite(start['timestamp'])):
        raise ValueError('independently qualified new-game start capture required')
    frames=boundary.get('terminal_frames',[])
    if len(frames)<2: raise ValueError('persistent terminal observations required')
    times=[];captures=set()
    for frame in frames:
        t=frame['timestamp'];h=frame['sha256']
        if not isinstance(t,(int,float)) or not math.isfinite(t) or sha(frame['path'])!=h:
            raise ValueError('finite, unchanged terminal captures required')
        times.append(t);captures.add((h,t))
    if times!=sorted(set(times)): raise ValueError('increasing terminal capture timestamps required')
    if start['timestamp']>=times[0]:raise ValueError('new-game start must precede terminal captures')
    measurements=row.get('score_observations',[])
    if not measurements: raise ValueError('final score missing')
    for m in measurements:
        c=certificate(m['validation_evidence'],'official_score_measurement')
        if c.get('human_annotation_id'):
            annotation=journal.get(c['human_annotation_id']);a=annotation.data['payload']
            proposal=journal.get(a['proposal_id']);review=proposal.data['payload']
            if (a.get('category')!='score_human_annotation' or a.get('independence_attested') is not True
                or a.get('synthetic') or a.get('verdict')=='unreadable' or a.get('value')!=m.get('value')
                or a.get('artifact_sha256')!=m.get('artifact_sha256') or a.get('timestamp')!=m.get('timestamp')
                or a.get('source_episode')!=row['source_episode'] or review.get('synthetic')
                or sha(review['artifact']['path'])!=m.get('artifact_sha256')):
                raise ValueError('auditable independent human annotation must match original final score')
            annotations=journal.category_records('observation','score_human_annotation')
            superseded={r.data['payload'].get('supersedes') for r in annotations}
            if annotation.id in superseded:raise ValueError('score certificate references superseded annotation')
            statuses=[r.data['payload'] for r in journal.category_records('observation','score_review_status')
                if r.data['payload'].get('proposal_id')==proposal.id]
            if statuses and statuses[-1]['status'] not in ('confirmed','corrected'):
                raise ValueError('score review remains unresolved')
            peers=[r.data['payload']['value'] for r in annotations if r.id not in superseded
                   and r.data['payload'].get('proposal_id')==proposal.id and r.data['payload'].get('independence_attested')]
            if len(set(peers))!=1:raise ValueError('human score annotation disagreement remains unresolved')
        if (c.get('value')!=m.get('value') or c.get('timestamp')!=m.get('timestamp')
                or c.get('phase')!='final' or c.get('artifact_sha256')!=m.get('artifact_sha256')
                or c.get('boundary_certificate')!=row['boundary_certificate']
                or (m.get('artifact_sha256'),m.get('timestamp')) not in captures):
            raise ValueError('score must bind the same validated terminal capture and boundary')
