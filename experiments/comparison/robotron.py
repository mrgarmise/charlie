"""Preregistered physical score comparison over preserved episode evidence.

This adapter analyzes records; it never captures, controls, certifies a reader,
or chooses a policy. Qualification evidence must come from independent work.
"""
from dataclasses import asdict
import random
from memory.evidence import digest
from .runner import analyze

VERSION='robotron-score-comparison-v1'


def commit(journal, plan, *, conditions, sources, episode):
    plan.validate()
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
        conditions=conditions,schedule=schedule,
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
        if slot in slots or episode in episodes:raise ValueError('repeated games are not independent trials')
        episodes.add(episode);slots[slot]=None
        scheduled=p['schedule'][slot]
        if row.get('policy')!=scheduled['policy'] or row.get('conditions')!=p['conditions']:
            failures.append(dict(slot=slot,reason='policy or environmental conditions differ'));continue
        if row.get('confirmed_terminal') is not True:
            failures.append(dict(slot=slot,reason='unconfirmed complete-game boundary'));continue
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
