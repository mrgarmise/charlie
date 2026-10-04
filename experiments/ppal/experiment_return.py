"""Narrow existing-memory -> actuator experiment adapter, not a Learning Executive."""
from __future__ import annotations

import json
from math import hypot, isfinite
from pathlib import Path
import time

from memory.evidence import ArtifactReader, EvidenceJournal, read_artifact
from memory.former import Experience
from .hindbrain import MOVE_VECTORS, distance_to_segment
from .models import Action, Position
from .hands import AXES
from .reflect_robotron import ACTUATOR_HYPOTHESIS_MARKER


def select_experiment(gateway, journal, game_path, *, horizon_seconds, project_context=None):
    """Use local evaluated memories; remote prose is never executable control."""
    choices=[]
    memories = (gateway.evaluator.for_evidence(project_context.get('hypothesis_evidence', []))
                if project_context is not None else gateway.evaluator.recent(100))
    for row in memories:
        if (row['status'] != 'promoted' or row.get('source')!='ppal:actuator-response-reflection'
                or not row['text'].startswith(ACTUATOR_HYPOTHESIS_MARKER)):
            continue
        try:
            spec,_=json.JSONDecoder().raw_decode(row['text'][len(ACTUATOR_HYPOTHESIS_MARKER):])
        except (ValueError,TypeError):
            continue
        if project_context is not None and (
                project_context.get('method') != 'actuator-response'
                or project_context.get('scope') != {'body': spec.get('body')}
                or project_context.get('expected') != spec.get('expected')
                or row.get('evidence') not in project_context.get('hypothesis_evidence', [])):
            continue
        if (spec.get('schema')=='charlie-actuator-test-v2' and spec.get('body') in AXES and spec.get('body')!='NONE'
                and spec.get('fire') in AXES and spec.get('fire')!='STAY' and isinstance(spec.get('expected'),str)
                and spec.get('evidence_windows',0)>=2 and len(spec.get('source_fire_settings',[]))>=2
                and len(spec.get('source_evidence',[]))>=2 and len(spec.get('proposal_rank',[]))==4):
            choices.append((row,spec))
    if not choices:
        return None
    all_choices = choices
    coverage_reason = None
    if project_context:
        # Tactical coverage of the declared criterion; Executive picks no setting.
        history = project_context.get('experiment_history', [])
        settled = {h['condition']['fire'] for h in history if h['result'] != 'unresolved'}
        tried = {h['condition']['fire'] for h in history}
        novel = [choice for choice in choices if choice[1]['fire'] not in tried]
        if len(settled) < project_context['criteria']['min_conditions'] and novel:
            choices = novel
            coverage_reason = 'chooser explores unattempted conditions until project coverage criterion is met; Evaluator ranking within that set'
    # Existing Evaluator priority first; explicit evidence rank resolves ties.
    row,spec=max(choices,key=lambda x:(x[0]['priority'],*x[1]['proposal_rank']))
    scope='planned-episode:'+str(Path(game_path).resolve())
    at=time.monotonic()
    recalled_payload = dict(category='evaluated_memory_recalled',
        memory_id=row['id'],proposal=spec,intended_game=str(game_path))
    if project_context:
        recalled_payload['project_context'] = project_context
    recalled=journal.append('observation',recalled_payload,episode=scope,at=at,
        producer='MemoryEvaluator',version='1')
    at=time.monotonic()
    prediction=journal.predict(dict(condition='one eligible normal action under provisional or confirmed SELF',
        expected_agency_reason=spec['expected'],body=spec['body'],fire=spec['fire'],
        physical_identity='same within-episode track; cross-episode ID not inherited',
        uncertainty='tentative BODY relationship; FIRE independence unestablished'),
        episode=scope,at=at,deadline=at+horizon_seconds,sources=(recalled.id,),
        producer='existing-memory-actuator-test',version='1',mode='live_prospective')
    decision_id='experiment:'+prediction.id
    plan = dict(schema='charlie-actuator-plan-v1',prediction_id=prediction.id,
        prediction_at=at,deadline=prediction.data['payload']['deadline'],memory_id=row['id'],
        decision_id=decision_id,scope=scope,body=spec['body'],fire=spec['fire'],
        max_actions=1,intended_game=str(Path(game_path).resolve()),source_episode=spec['source_episode'],
        source_evidence=spec['source_evidence'],
        expected=spec['expected'],alternatives=[dict(memory_id=r['id'],evaluator_priority=r['priority'],
            body=s['body'],fire=s['fire'],expected=s['expected'],proposal_rank=s['proposal_rank']) for r,s in all_choices],
        reason='Evaluator priority then evidence-based proposal rank: untested binding, modal-response support, window count, observed setting frequency')
    if project_context:
        plan['project_id'] = project_context['project_id']
        plan['project_objective'] = project_context['objective']
        plan['project_coverage_reason'] = coverage_reason
    return plan


def validate_plan(plan, output):
    if (plan.get('schema')!='charlie-actuator-plan-v1' or plan.get('body') not in AXES or plan.get('body')=='NONE'
            or plan.get('fire') not in AXES or plan.get('fire')=='STAY' or not isinstance(plan.get('expected'),str) or plan.get('max_actions')!=1
            or plan.get('intended_game')!=str(Path(output).resolve())
            or not plan.get('prediction_id') or not plan.get('memory_id')
            or not isinstance(plan.get('deadline'),(int,float))
            or not isfinite(plan['deadline']) or not isinstance(plan.get('prediction_at'),(int,float))
            or not isfinite(plan['prediction_at']) or plan['deadline']<=plan['prediction_at']):
        raise ValueError('invalid or wrong-episode experiment plan')
    return plan


def experimental_action(plan, world, intent, baseline, snapshot, *, now):
    """One constrained opt-in override. Does not alter agency or baseline policy."""
    if now>plan['deadline']:
        return None,'prediction horizon expired'
    if snapshot.get('identity_status') not in ('confirmed','provisional'):
        return None,'SELF UNKNOWN'
    if intent.kind in ('evade','clear'):
        return None,'existing immediate-response policy has priority'
    if (baseline.move,baseline.fire)==(plan['body'],plan['fire']):
        return None,'baseline already identical; no experimental action difference'
    dx,dy=MOVE_VECTORS.get(plan['body'],(0,0));length=hypot(dx,dy) or 1.
    end=Position(world.player.x+8*dx/length,world.player.y+8*dy/length)
    if not (4<=end.x<=96 and 4<=end.y<=96):
        return None,'existing arena bounds'
    if any(distance_to_segment(o.position,world.player,end)<4 for o in (*world.threats,*world.unresolved)):
        return None,'occupied route; no eligible experiment slot'
    return Action(plan['body'],plan['fire'],'evidence-backed actuator experiment'),None


def resolve_experiment(root, episode_journal, episode, commitment_journal, plan, gateway):
    report=json.loads((Path(root)/'report.json').read_text())
    read_verified=ArtifactReader(root)
    attempts=[s for s in report.get('steps',[]) if (s.get('experiment') or {}).get('prediction_id')==plan['prediction_id']]
    result='unresolved';reason='experiment not executed';source_ids=[];matching=None;observed=None
    if attempts:
        step=attempts[0];context=step['experiment'];track_id=context['track_id']
        reason='no trustworthy same-ID response window'
        for record in episode_journal.records('observation'):
            data=record.data
            if data['episode']!=episode or data['payload'].get('category')!='agency_tracking_observation':continue
            row=read_verified(data['payload']['artifact']);window=row.get('response_window') or {}
            control=row.get('control_execution') or {}
            if (window.get('endpoint')!=2 or window.get('origin_at')!=context['origin_at']
                    or window.get('move')!=plan['body']):continue
            matching=record
            evidence=next((e for e in row.get('evidence',[]) if e.get('track_id')==track_id),None)
            observed=evidence
            at=data['at']
            if (at is None or at<=plan['prediction_at'] or at>plan['deadline']
                    or control.get('started_at',-1)<=plan['prediction_at']
                    or control.get('move')!=plan['body'] or control.get('fire')!=plan['fire']
                    or row.get('global_motion') or not evidence
                    or any(e.get('track_id')==track_id and e.get('kind') in ('ambiguous','created')
                           for e in row.get('tracking',{}).get('events',[]))):
                reason='timing, transport, track or motion evidence inadequate';break
            if evidence['reason']==plan['expected']:
                result='supported';reason='existing AgencyTracker matched the evidence-derived modal response'
            elif isinstance(evidence.get('reason'),str):
                result='contradicted';reason='existing AgencyTracker reported a different measured response from the evidence-derived expectation'
            else:
                reason='agency evidence did not settle requested measurable response'
            outcome=commitment_journal.append('observation',dict(category='experiment_outcome',
                canonical_evidence=record.id,ee_episode=episode,artifact=data['payload']['artifact'],
                candidate_track_id=track_id,identity_status=row.get('identity_status'),agency_evidence=evidence),
                episode=plan['scope'],at=at,producer='AgencyTracker-report-adapter',version='1')
            source_ids.append(outcome.id)
            break
    resolution=commitment_journal.resolution_for(plan['prediction_id'])
    if resolution:
        payload=resolution.data['payload']
        if payload['result']!=result or payload['reason']!=reason or resolution.data['sources'] != [plan['prediction_id'],*source_ids]:
            raise ValueError('new interpretation conflicts with committed experiment resolution')
    else:
        resolution=commitment_journal.resolve(plan['prediction_id'],sources=source_ids,result=result,reason=reason)
    before=next((r for r in gateway.evaluator.recent(100) if r['id']==plan['memory_id']),{})
    change='no usefulness credit for unresolved evidence'
    if result!='unresolved':
        gateway.record_decision(plan['decision_id'],'ppal:actuator-response-test',[plan['memory_id']])
        gateway.assess_decision(plan['decision_id'],'helpful' if result=='supported' else 'harmful',
            resolution.id,'Diagnostic comparison: evidence-derived expected agency response versus measured AgencyTracker verdict; no score or strategy benefit claimed',weight=.5)
        change='existing Evaluator received diagnostic predictive-usefulness feedback'
    gateway.remember(Experience(kind='observation',summary=f"Actuator experiment {plan['prediction_id']} was {result}: {reason}",
        source='ppal:actuator-experiment-resolution',subject='actuator response',confidence=1.,significant=True,
        evidence=resolution.id,tags=('experiment-resolution','diagnostic',result)))
    after=next((r for r in gateway.evaluator.recent(100) if r['id']==plan['memory_id']),{})
    return dict(prediction_id=plan['prediction_id'],result=result,reason=reason,
        resolution_id=resolution.id,memory_id=plan['memory_id'],belief_change=change,
        outcome_evidence_ids=source_ids,canonical_response_evidence=matching.id if matching else None,observed_agency_evidence=observed,
        memory_evaluation_before={k:before.get(k) for k in ('status','priority')},
        memory_evaluation_after={k:after.get(k) for k in ('status','priority')},
        hypothesis_status='tentative; no physical identity or game-rule certification',
        attempted=bool(attempts),score_attribution=None)


def select_offline_experiment(gateway, journal, project_context, *, budget_seconds):
    """Offline method extension of the existing Evaluator-first tactical chooser."""
    from learning.datasets import SCOPE
    from memory.evidence import digest
    if project_context['method'] in ('model-diagnostics','evidence-review','meditation-motion'):
        return select_diagnostic_experiment(gateway,journal,project_context,budget_seconds=budget_seconds)
    if project_context['method'] not in ('cnn-reconstruction','cnn-classification','cnn-validation-extension'): return None
    choices=[]
    for row in gateway.evaluator.for_evidence(project_context['hypothesis_evidence']):
        if row['status']!='promoted' or row.get('source')!='ppal:perceptual-reflection': continue
        try: spec=json.JSONDecoder().raw_decode(row['text'][len('Perceptual experiment hypothesis: '):])[0]
        except (ValueError,TypeError): continue
        if spec.get('method')==project_context['method'] and spec.get('scope')==project_context['scope'] and spec.get('expected')==project_context['expected']:
            choices.append((row,spec))
    if not choices: return None
    attempted={h.get('dataset_id') for h in project_context['experiment_history']}
    fresh=[choice for choice in choices if choice[1]['dataset_id'] not in attempted]
    row,spec=max(fresh or choices,key=lambda pair:(pair[0]['priority'],*pair[1]['rank']))
    snapshot=journal.get(spec['dataset_id']).data['payload']
    # Fixed bounded component vocabulary, not a finished classifier. Candidate
    # alternatives are generated from input shape/coverage and resource budget.
    size=32
    epochs=min(100,max(8,int(budget_seconds)))
    candidates=[dict(family='small-cnn',objective=snapshot['objective'],channels=channels,kernel=3,
        activation='relu',size=size,epochs=epochs,lr=lr,seed=0,patience=10)
        for channels,lr in [([4],.01),([8,16],.003)]]
    validation_only=spec['method']=='cnn-validation-extension'
    if validation_only:
        original=journal.get(spec['evaluation_id']).data['payload']['candidate']['spec']
        if original['epochs']>=100:return None
        candidates=[dict(original),dict(original,epochs=min(100,2*original['epochs']))]
    key=digest(dict(project_id=project_context['project_id'],dataset=spec['dataset_id'],method=spec['method']))
    prior=[r for r in journal.records('event') if r.data['payload'].get('category')=='offline_experiment_plan' and r.data['payload'].get('key')==key]
    if prior: return prior[0].data['payload']['plan']
    from learning.clock import domain
    clock_domain=domain(); scope=SCOPE+':'+clock_domain
    recalled=journal.append('observation',dict(category='evaluated_memory_recalled',proposal=spec,memory_id=row['id'],project_context=project_context),
        episode=scope,producer='MemoryEvaluator',version='ala-1')
    at=time.monotonic()
    prediction=journal.predict(dict(expected=spec['expected'],dataset=spec['dataset_id'],
        metric='matched_validation_loss' if validation_only else 'balanced_accuracy' if snapshot['objective']=='classification' else 'reconstruction_mse',
        uncertainty='diagnostic expectation, no semantic or score claim'),episode=scope,at=at,
        deadline=at+budget_seconds+60,sources=[recalled.id],producer='existing-memory-offline-test',version='ala-1',mode='live_prospective')
    plan=dict(project_id=project_context['project_id'],prediction_id=prediction.id,memory_id=row['id'],
        dataset_id=spec['dataset_id'],expected=spec['expected'],condition=dict(spec['scope'],dataset_id=spec['dataset_id']),candidates=candidates,
        budget_seconds=budget_seconds,experiment_kind='offline',episode=scope,clock_domain=clock_domain,
        independence_unit=digest(sorted({r['independence_group'] for r in snapshot['examples'] if r['partition']=='test'})),
        evidence_groups=sorted({r['source_episode'] for r in snapshot['examples'] if r['partition']=='test'}),
        source_evidence=spec['source_evidence'],alternatives=[dict(memory_id=r['id'],evaluator_priority=r['priority'],rank=s['rank']) for r,s in choices],
        method_alternatives=spec['alternatives'],evaluation_mode='validation-only' if validation_only else 'independent-test',
        reason='existing Evaluator priority; matched duration alternatives from retrieved history' if validation_only else 'existing Evaluator priority, then independent coverage; architecture comparison on validation only')
    journal.append('event',dict(category='offline_experiment_plan',key=key,plan=plan),episode=scope,
        sources=[prediction.id],producer='existing-chooser',version='ala-1')
    gateway.record_decision('offline:'+prediction.id,'diagnostic-generalization',[row['id']])
    return plan


def select_diagnostic_experiment(gateway,journal,context,*,budget_seconds):
    """Evaluator-first retrieval experiments, without examining their outcomes."""
    from learning.datasets import SCOPE
    from memory.evidence import digest
    from learning.clock import domain
    clock=domain(); scope=SCOPE+':'+clock
    choices=[]
    attempted={h['prediction_id'] for h in context['experiment_history']}
    for row in gateway.evaluator.for_evidence(context['hypothesis_evidence']):
        if row['status']!='promoted' or row.get('source')!='ppal:perceptual-reflection': continue
        try: spec=json.JSONDecoder().raw_decode(row['text'][len('Perceptual experiment hypothesis: '):])[0]
        except (ValueError,TypeError): continue
        if spec.get('method')==context['method'] and spec.get('scope') in context.get('agenda_scopes',[context['scope']]) and spec.get('expected')==context['expected']:
            choices.append((row,spec))
    if not choices:return None
    used={h.get('dataset_id') for h in context['experiment_history']}
    fresh=[pair for pair in choices if pair[1].get('dataset_id') not in used]
    row,spec=max(fresh or choices,key=lambda pair:(pair[0]['priority'],*pair[1]['rank']))
    key=digest(dict(project_id=context['project_id'],scope=spec['scope'],method=spec['method'],sources=spec['source_evidence']))
    prior=[r for r in journal.records('event') if r.data['payload'].get('category')=='offline_experiment_plan' and r.data['payload'].get('key')==key]
    if prior:
        plan=prior[0].data['payload']['plan']
        return None if plan['prediction_id'] in attempted else plan
    recalled=journal.append('observation',dict(category='evaluated_memory_recalled',proposal=spec,memory_id=row['id'],project_context=context),
        episode=scope,producer='MemoryEvaluator',version='ala-2',
        provenance={'clock_domain':clock,'historical_source_ids':spec['source_evidence']})
    at=time.monotonic()
    prediction=journal.predict(dict(expected=spec['expected'],predicate=spec['predicate'],
        interpretation='prospective retrieval; historical causal explanation remains tentative'),episode=scope,at=at,
        deadline=at+budget_seconds+60,sources=[recalled.id],producer='existing-memory-offline-test',version='ala-2',mode='live_prospective')
    plan=dict(project_id=context['project_id'],prediction_id=prediction.id,memory_id=row['id'],method=spec['method'],
        episode=scope,clock_domain=clock,
        evaluation_id=spec.get('evaluation_id'),predicate=spec['predicate'],dataset_id=spec.get('dataset_id'),expected=spec['expected'],
        question_category=spec.get('question_category'),
        condition=spec['scope'],budget_seconds=budget_seconds,experiment_kind='offline',
        independence_unit=spec['independence_unit'],evidence_groups=spec['evidence_groups'],source_evidence=spec['source_evidence'],
        competing_explanations=spec['alternatives'],alternatives=[dict(memory_id=r['id'],evaluator_priority=r['priority'],rank=s['rank']) for r,s in choices],
        reason='Existing Evaluator priority; retrieve discriminating evidence before expensive new fitting',
        stopping='one committed retrieval; no automatic retest or production deployment')
    journal.append('event',dict(category='offline_experiment_plan',key=key,plan=plan),episode=scope,
        sources=[prediction.id],producer='existing-chooser',version='ala-2')
    gateway.record_decision('offline:'+prediction.id,'model-diagnostic',[row['id']])
    return plan
