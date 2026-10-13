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
    if plan.get('predicate') == 'capture_horizon_supported':
        # Independently reconstruct availability from hash-bound originals.
        # The service report is evidence to inspect, not its own ground truth.
        from .archive_audit import audit
        from .episode_identity import eligible, canonical_experience
        results = []; episodes = set(); unavailable=[]
        for identifier in plan['source_evidence']:
            p = journal.get(identifier).data['payload']
            if p.get('category') != 'observation_qualification':
                raise ValueError('capture qualification reference required')
            saved = p['report']
            from pathlib import Path
            root=Path(saved['source_root'])
            # Original audit paths survive restoration. Resolve a verified copy
            # through acquisition's immutable association, never by filename.
            from .episode_identity import bindings, _events
            from memory.episode_identity import inspect_capture
            bound=None
            for candidate in bindings(journal):
                if candidate['manifest_id']!=saved.get('manifest_id'):continue
                for location in _events(journal,'episode_identity_location'):
                    loc=location.data['payload'];copy=Path(loc['source_root'])
                    if loc['status']!='verified' or loc['manifest_id']!=candidate['manifest_id'] or not copy.is_dir():continue
                    try:
                        if inspect_capture(copy)['manifest_id']!=candidate['manifest_id']:continue
                    except (ValueError,OSError):continue
                    root=copy;bound=candidate;break
                if bound:break
            if not eligible(journal,p) or not root.is_dir():
                unavailable.append(dict(reference=identifier,reason='Original audit location unavailable or quarantined; retained finding is not erased'))
                continue
            actual = audit(root,identity=bound)
            # Historical reports did not contain the new identity fields.
            if any(actual.get(k)!=v for k,v in saved.items() if k not in ('schema','source_root','game_relative')):
                from .acquisition import maintain_episode_identity
                maintain_episode_identity(root/saved.get('game_relative','.'),journal)
                raise ValueError('qualified archive or measurement changed; excluded from retrieval')
            episodes.add(canonical_experience(journal,actual['source_episode']))
            results.append(actual)
        known = bool(results) and not unavailable and not any(r['binding_issues'] or any(r['torn_lines'].values()) for r in results)
        supported = all(len(r['cadence']['compatible_pairs']) > 0 for r in results) if known else None
        return dict(capture_horizon_supported=supported,distinct_source_episodes=len(episodes),
            compatible_pairs=sum(len(r['cadence']['compatible_pairs']) for r in results),
            qualified_identities=0,fresh_final_evidence=False,
            unavailable_references=unavailable,
            finding='Independent capture-availability audit; no motion accuracy or score evaluation',
            missing_evidence=sorted({reason for r in results for reason in r['reasons']} | {u['reason'] for u in unavailable}))
    from .episode_identity import canonical_experience, eligible
    episodes=set(); matching=[]
    for identifier in plan['source_evidence']:
        record=journal.get(identifier);p=record.data['payload']
        if p.get('category')!='learning_context_reference':raise ValueError('context reference required')
        if any(q.get('category')==plan['question_category'] for q in p['context'].get('questions',[])):
            # Missing source identity cannot count as independent recurrence.
            if p.get('source_episode') and eligible(journal,p):episodes.add(canonical_experience(journal,p['source_episode']))
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
    def retrieve():
        try:
            return retrieve_questions(journal,plan) if plan['method']=='evidence-review' else measurements(journal,plan['evaluation_id'])
        except (ValueError,OSError) as exc:
            # A sealed retrieval cannot certify inconsistent bytes. Preserve the
            # finding as inconclusive, freeing unrelated portfolio work.
            return {plan['predicate']:None,'evidence_integrity_conflict':str(exc),
                'independent_measurements':0,'physical_score_improvement':'UNKNOWN'}
    observed = prior[0] if prior else journal.append('observation',
        dict(category='model_diagnostic_retrieval', prediction_id=plan['prediction_id'],
             ee_episode=SCOPE,
             measurements=retrieve(),
             interpretation='compatible signatures do not establish cause'),
        episode=plan['episode'], at=time.monotonic(), sources=[plan['prediction_id'], *references],
        producer='CapabilityRegistry:'+plan['method'], version='ala-2')
    value = observed.data['payload']['measurements'][plan['predicate']]
    forecast = journal.get(plan['prediction_id']).data
    timely = forecast['at'] < observed.data['at'] <= forecast['payload']['deadline']
    result = 'unresolved' if value is None or not timely else 'supported' if value else 'contradicted'
    reason = ('Reconstructed hash-bound capture timing; frozen-horizon availability only, identities and performance remain unqualified'
              if plan.get('predicate')=='capture_horizon_supported' else
              'Retrieved frozen experience references; question recurrence only, causal explanation remains tentative'
              if plan['method']=='evidence-review' else
              'Retrieved frozen training history; diagnostic signature only, causal explanation remains tentative')
    resolution = journal.resolve(plan['prediction_id'], sources=[observed.id], result=result, reason=reason)
    return dict(status='resolved', result=result, reason=reason, resolution_id=resolution.id,
                evaluation_id=observed.id, metrics=observed.data['payload']['measurements'])
