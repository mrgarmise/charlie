"""Bounded retrieval of existing model evidence; no new test-set evaluation.

Predictions concern prospective retrieval outcomes, not the historical failure.
A compatible diagnostic is not proof of its causal explanation.
"""
import math
import time
from memory.evidence import digest
from .datasets import SCOPE


def measurements(journal, evaluation_id):
    evaluation = journal.get(evaluation_id)
    p = evaluation.data['payload']
    if p.get('category') != 'offline_model_evaluation':
        raise ValueError('model evaluation evidence required')
    candidate = p['candidate']
    history = candidate.get('history', [])
    valid = [h for h in history if all(isinstance(h.get(k), (int, float))
             and math.isfinite(h[k]) for k in ('train_loss', 'validation_loss'))]
    if len(valid) != len(history): raise ValueError('invalid training history')
    best = min(valid, key=lambda h: h['validation_loss']) if valid else None
    # Training loss is measured before the optimizer step; validation afterward.
    # This is a diagnostic signature, not a precise generalization-error estimate.
    gap = best['validation_loss'] > best['train_loss'] if best else None
    unfinished = (history[-1]['validation_loss'] < history[-2]['validation_loss']
                  and len(history) == candidate['spec']['epochs']) if len(history) >= 2 else None
    return dict(validation_exceeds_training=gap, improving_at_budget=unfinished,
                epochs_observed=len(history), best_epoch=best.get('epoch') if best else None,
                evaluation_id=evaluation.id, historical_test_reused=False)


def retrieve_questions(journal, plan):
    episodes=set(); matching=[]
    for identifier in plan['source_evidence']:
        record=journal.get(identifier);p=record.data['payload']
        if p.get('category')!='learning_context_reference':raise ValueError('context reference required')
        if any(q.get('category')==plan['question_category'] for q in p['context'].get('questions',[])):
            # Missing source identity cannot count as independent recurrence.
            if p.get('source_episode'):episodes.add(p['source_episode'])
            matching.append(identifier)
    known=all(journal.get(i).data['payload'].get('source_episode') for i in matching)
    return dict(recurrent_context_gap=len(episodes)>1 if known else None,
                isolated_context_gap=len(episodes)==1 if known else None,
                distinct_source_episodes=len(episodes),matching_references=matching,
                finding='recurrence of reported questions, not verification of the proposed cause')


def execute(plan, dataset, output=None, **unused):
    from .cycle import gameplay_active
    if gameplay_active(): raise RuntimeError('offline diagnostic unavailable during gameplay')
    journal = dataset.journal
    committed = [r.data['payload']['plan'] for r in journal.records('event')
                 if r.data['payload'].get('category') == 'offline_experiment_plan'
                 and r.data['payload']['plan']['prediction_id'] == plan['prediction_id']]
    if committed != [plan]: raise ValueError('execution must match the exact committed chooser plan')
    previous = journal.resolution_for(plan['prediction_id'])
    if previous:
        return dict(status='already_resolved', result=previous.data['payload']['result'],
                    reason=previous.data['payload']['reason'], resolution=previous.data['payload'],
                    resolution_id=previous.id)
    from .clock import domain
    if plan['clock_domain'] != domain():
        reason='Host clock domain changed before retrieval; prior prospective horizon cannot be established'
        resolution=journal.resolve(plan['prediction_id'],sources=[],result='unresolved',reason=reason)
        return dict(status='resolved',result='unresolved',reason=reason,resolution_id=resolution.id,
                    metrics={'clock_continuity':'UNKNOWN'})
    # Recovery reuses the committed retrieval rather than generating a later result.
    prior = [r for r in journal.records('observation')
             if r.data['payload'].get('category') == 'model_diagnostic_retrieval'
             and r.data['payload'].get('prediction_id') == plan['prediction_id']]
    if len(prior) > 1: raise ValueError('conflicting diagnostic outcomes')
    references=[journal.append('observation',dict(category='consolidated_evidence_reference',
        record_id=i,source_episode=journal.get(i).data['episode'],journal=str(journal.path.resolve())),
        episode=plan['episode'],producer='existing-evidence-consolidation',version='ala-2').id for i in plan['source_evidence']]
    observed = prior[0] if prior else journal.append('observation',
        dict(category='model_diagnostic_retrieval', prediction_id=plan['prediction_id'],
             ee_episode=SCOPE,
             measurements=(retrieve_questions(journal,plan) if plan['method']=='evidence-review' else measurements(journal, plan['evaluation_id'])),
             interpretation='compatible signatures do not establish cause'),
        episode=plan['episode'], at=time.monotonic(), sources=[plan['prediction_id'], *references],
        producer='CapabilityRegistry:'+plan['method'], version='ala-2')
    value = observed.data['payload']['measurements'][plan['predicate']]
    forecast = journal.get(plan['prediction_id']).data
    timely = forecast['at'] < observed.data['at'] <= forecast['payload']['deadline']
    result = 'unresolved' if value is None or not timely else 'supported' if value else 'contradicted'
    reason = ('Retrieved frozen experience references; question recurrence only, causal explanation remains tentative'
              if plan['method']=='evidence-review' else
              'Retrieved frozen training history; diagnostic signature only, causal explanation remains tentative')
    resolution = journal.resolve(plan['prediction_id'], sources=[observed.id], result=result, reason=reason)
    return dict(status='resolved', result=result, reason=reason, resolution_id=resolution.id,
                evaluation_id=observed.id, metrics=observed.data['payload']['measurements'])
