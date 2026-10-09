"""Offline ALA orchestration over existing Reflection, chooser, Executive and E/E.

Serial resource scheduling permits multiple shared-evidence investigations.
Physical experiments retain their actuator interference boundary.
"""
from pathlib import Path
import json
import os
import sys
import time
import fcntl
from memory.evidence import EvidenceJournal, digest
from memory.former import Experience
from memory.learning_projects import LearningExecutive
from .datasets import ExperienceDataset, SCOPE, sha
from .capabilities import default_registry
import importlib.util
from contextlib import contextmanager


def _gameplay_lock():
    import tempfile
    return Path(tempfile.gettempdir())/f'charlie-gameplay-{os.getuid()}.lock'


@contextmanager
def gameplay_session():
    """Existing primary-resource boundary spans gaps between marathon children.

    Kernel ownership expires on process exit; no stale PID file grants authority.
    This reserves resources only and never selects an agenda or sends controls.
    """
    with _gameplay_lock().open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)
from .foundry import atomic_json


def gameplay_active():
    try:
        with _gameplay_lock().open('a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return True
            finally:fcntl.flock(lock,fcntl.LOCK_UN)
    except OSError:return True  # Ownership unavailable: fail closed.
    # No camera ownership probe. Refuse host training while a live player owns
    # time-critical work. Non-Linux callers must supply equivalent orchestration.
    proc=Path('/proc')
    if not proc.is_dir(): return True
    # scandir reads only the process directory. Path.glob recursively visits
    # each PID directory and matches its entries on every analytical pulse.
    try:
        with os.scandir(proc) as entries:
            for entry in entries:
                if not entry.name.isdigit():continue
                try:
                    with open(os.path.join(entry.path,'cmdline'),'rb') as stream:
                        args=stream.read().split(b'\0')
                    if b'experiments.ppal.play_robotron' in args:return True
                except (OSError,PermissionError):pass # exited process
    except OSError:
        return True  # Unavailable ownership information cannot admit learning.
    return False


def ingest_episode(root, dataset, gateway):
    """Reuse existing immutable import and context Reflection; no tracker pass."""
    from .retrospective import ingest
    root = Path(root)
    from .acquisition import maintain_episode_identity
    identity = maintain_episode_identity(root,dataset.journal)
    if identity['status']=='quarantined':
        return dict(episode=None,context_id=None,examples=[],ingestion_status='quarantined',identity=identity)
    marker = ingest(root, dataset)
    record = dataset.journal.get(marker['record_id'])
    reference = dataset.journal.get(record.data['payload']['context_id'])
    source_path = reference.data['payload'].get('source_journal')
    examples = []
    for path in sorted(root.glob('review-*.jpg')):
        original_hash = sha(path)
        previous = [r for r in dataset.journal.records('observation')
            if r.data['payload'].get('category') == 'experience_example'
            and r.data['payload'].get('source_episode') == marker['source_episode']
            and r.data['payload'].get('original_sha256') == original_hash
            and Path(r.data['payload'].get('original_path', '')).name == path.name
            and r.data['payload'].get('crop') is None
            and r.data['payload'].get('metadata', {}).get('review_subset')]
        if previous:
            examples.append(previous[0].id)
            continue
        examples.append(dataset.add(path, episode=marker['source_episode'],
            source=dict(journal=source_path, context_id=reference.id,
                artifact=str(path.resolve()), sha256=original_hash),
            metadata=dict(review_subset=True, identity_status='unknown',
                physical_experiment=marker['source_episode'],
                temporal_context='see original agency/action evidence',
                context_reference=reference.id)).id)
    return dict(episode=marker['source_episode'], context_id=reference.id,
                examples=examples, ingestion_status=marker['status'])


def run_plan(plan, dataset, output, *, driver=None, on_progress=None):
    """Frozen alternative comparison; final test never ranks architectures."""
    if gameplay_active(): raise RuntimeError('offline learning unavailable during active gameplay')
    from experiments.ppal.progress_supervision import supervise
    from .foundry import evaluate, discover_groups
    journal=dataset.journal
    committed=[r.data['payload']['plan'] for r in journal.records('event') if r.data['payload'].get('category')=='offline_experiment_plan' and r.data['payload']['plan']['prediction_id']==plan['prediction_id']]
    if len(committed)!=1 or committed[0]!=plan: raise ValueError('execution must match the exact committed chooser plan')
    snapshot=journal.get(plan['dataset_id']).data['payload']
    resolved=journal.resolution_for(plan['prediction_id'])
    scope=plan.get('episode',SCOPE)
    from .clock import domain
    prior_outcomes=[r for r in journal.records('observation') if r.data['payload'].get('category')=='offline_model_evaluation' and r.data['payload'].get('prediction_id')==plan['prediction_id']]
    if resolved and not prior_outcomes:
        p=resolved.data['payload']
        return dict(status='already_resolved',result=p['result'],reason=p['reason'],resolution=p,resolution_id=resolved.id,metrics={'evaluation':'not completed'})
    if not resolved and not prior_outcomes and plan.get('clock_domain') and plan['clock_domain']!=domain():
        reason='Host clock changed before evaluation; preserve checkpoints but do not invent deadline continuity'
        resolution=journal.resolve(plan['prediction_id'],sources=[],result='unresolved',reason=reason)
        return dict(status='resolved',result='unresolved',reason=reason,resolution_id=resolution.id,metrics={'clock_continuity':'UNKNOWN'})
    dataset_reference=plan['dataset_id']
    if journal.get(dataset_reference).data['episode']!=scope:
        dataset_reference=journal.append('observation',dict(category='consolidated_evidence_reference',record_id=dataset_reference,
            source_episode=journal.get(dataset_reference).data['episode'],journal=str(journal.path.resolve())),
            episode=scope,producer='existing-evidence-consolidation',version='ala-2').id
    # A committed resolution may precede a crash before proposal/shadow/export.
    # Reconcile those durable handoffs; do not rerun the final evaluation.
    output=Path(output)/plan['prediction_id']; output.mkdir(parents=True,exist_ok=True)
    training=[]
    for spec in plan['candidates']:
        identifier=digest(dict(spec=spec,dataset_digest=digest(snapshot))); candidate=output/identifier; candidate.mkdir(exist_ok=True)
        config=dict(snapshot=snapshot,spec=spec,output=str(candidate.resolve()),budget_seconds=plan['budget_seconds']/len(plan['candidates']))
        config_path=candidate/'worker.json'; atomic_json(config_path,config)
        if not (candidate/'training.json').exists():
            cmd=[sys.executable,'-m','learning.worker',str(config_path)]
            rc=(driver(cmd,candidate/'progress.json',budget=config['budget_seconds']+40) if driver else
                supervise(cmd,candidate/'progress.json',silence=30.,processing=30.,budget=config['budget_seconds']+40,on_progress=on_progress))
            if rc!=0:
                journal.append('event',dict(category='offline_experiment_deferred',prediction_id=plan['prediction_id'],returncode=rc,
                    checkpoint=str(candidate/'last.pt'),reason='worker yielded, failed or stopped; no verdict fabricated'),
                    episode=scope,sources=[plan['prediction_id']],producer='offline-orchestrator',version='ala-1')
                return dict(status='deferred',returncode=rc)
        value=json.loads((candidate/'training.json').read_text())
        if value['dataset_digest']!=digest(snapshot) or value['spec']!=spec or sha(value['checkpoint'])!=value['checkpoint_sha256']:
            raise ValueError('candidate artifact provenance changed')
        record=journal.append('event',dict(category='model_training',candidate=value,experiment_kind='offline',
            prediction_id=plan['prediction_id'],dataset_id=plan['dataset_id']),episode=scope,
            sources=[plan['prediction_id'],dataset_reference],producer='ModelFoundry',version='ala-1')
        training.append((record,value))
    record,candidate=min(training,key=lambda pair:pair[1]['validation_loss'])
    selected=journal.append('event',dict(category='model_candidate_selected',candidate_id=candidate['identifier'],
        criterion='validation loss only',alternatives=[dict(id=v['identifier'],validation_loss=v['validation_loss']) for _,v in training]),
        episode=scope,sources=[r.id for r,_ in training],producer='ModelFoundry',version='ala-1')
    prior=[r for r in journal.records('observation') if r.data['payload'].get('category')=='offline_model_evaluation' and r.data['payload'].get('prediction_id')==plan['prediction_id']]
    if len(prior)>1: raise ValueError('conflicting final evaluations; create an explicit version')
    if prior:
        outcome=prior[0]; value=outcome.data['payload']
        if value['candidate']!=candidate: raise ValueError('frozen evaluation candidate changed')
        metric=value['metrics']
    else:
        if plan.get('evaluation_mode')=='validation-only':
            control=training[0][1];extended=training[1][1]
            metric=dict(metric='matched_validation_loss',value=extended['validation_loss'],baseline=control['validation_loss'],
                improved=extended['validation_loss']<control['validation_loss'],independence_groups=[],operational=None,
                test_consulted=False,limitations=['reused validation is correlated, not independent confirmation','not eligible for deployment','no score claim'])
        else:
            metric=evaluate(snapshot,candidate)
            # A new dataset version or model does not make previously consulted
            # final evidence fresh. Preserve diagnostic measurements, but deny
            # another deployment admission on overlapping physical test groups.
            test_rows=[r for r in snapshot['examples'] if r['partition']=='test']
            current_units={r['source_episode'] for r in test_rows}
            current_hashes={r[k] for r in test_rows for k in ('original_sha256','pixel_sha256')}
            snapshots={digest(r.data['payload']):r.data['payload'] for r in journal.records('event')
                       if r.data['payload'].get('category')=='experience_dataset_snapshot'}
            reused=[]
            for earlier in journal.records('observation'):
                payload=earlier.data['payload']
                if payload.get('category')!='offline_model_evaluation' or not payload.get('metrics',{}).get('independence_groups'):continue
                historical=snapshots.get(payload.get('candidate',{}).get('dataset_digest'))
                old_rows=[r for r in historical['examples'] if r['partition']=='test'] if historical else []
                overlap=(current_units & {r['source_episode'] for r in old_rows} or
                         current_hashes & {r[k] for r in old_rows for k in ('original_sha256','pixel_sha256')} or
                         set(metric['independence_groups']) & set(payload['metrics']['independence_groups']))
                if overlap or historical is None:reused.append(earlier.id)
            metric['fresh_final_evidence']=not reused
            metric['prior_final_evaluations']=reused
            if reused:
                metric['limitations'].append('final evidence previously consulted or its isolation unverifiable; diagnostic reuse cannot admit deployment')
                if metric.get('operational'):metric['operational']=dict(metric['operational'],eligible=False)
            groups=discover_groups(snapshot,candidate,output)
            journal.append('event',dict(category='opaque_visual_groups',interpretation=groups),episode=scope,
                sources=[selected.id,dataset_reference],producer='Meditation:learned-representation',version='ala-1')
        outcome=journal.append('observation',dict(category='offline_model_evaluation',ee_episode=SCOPE,
            prediction_id=plan['prediction_id'],candidate=candidate,metrics=metric,
            experiment_kind='offline',independence_unit=plan['independence_unit'],
            semantic_finding='UNKNOWN',physical_performance='not tested'),episode=scope,
            at=time.monotonic(),sources=[selected.id,dataset_reference],producer='ModelFoundry',version='ala-1')
    forecast=journal.get(plan['prediction_id']).data
    in_horizon=forecast['at'] < outcome.data['at'] <= forecast['payload']['deadline']
    verdict=('supported' if metric['improved'] else 'contradicted') if in_horizon else 'unresolved'
    reason=('Matched training duration comparison on reused validation only; independent generalization and task utility remain UNKNOWN'
            if plan.get('evaluation_mode')=='validation-only' else 'Independent diagnostic metric compared with frozen train-only baseline; no gameplay causation inferred')
    if not in_horizon: reason='Completed outside the committed prediction horizon; diagnostic evaluation retained, forecast unresolved'
    resolution=resolved or journal.resolve(plan['prediction_id'],sources=[outcome.id] if outcome.data['at']>forecast['at'] else [],result=verdict,reason=reason)
    verdict=resolution.data['payload']['result'];reason=resolution.data['payload']['reason']
    proposal=journal.append('event',dict(category='model_deployment_proposal',candidate_id=candidate['identifier'],
        evaluation_id=outcome.id,eligible=metric['improved'] and metric.get('fresh_final_evidence',True) and plan.get('evaluation_mode')!='validation-only',target='offline-shadow',
        production=False,reason='correlated validation-only result; independent evaluation still required' if plan.get('evaluation_mode')=='validation-only' else 'previously consulted final evidence; fresh independent evaluation required' if metric.get('fresh_final_evidence') is False else 'independent diagnostic improvement' if metric['improved'] else 'candidate failed diagnostic baseline',
        limitations=metric['limitations']),episode=scope,sources=[resolution.id,outcome.id],producer='Reflection',version='ala-1')
    operational_proposal=None
    contract=metric.get('operational')
    if contract and contract['eligible'] and verdict=='supported':
        operational_proposal=journal.append('event',dict(category='model_deployment_proposal',candidate_id=candidate['identifier'],
            evaluation_id=outcome.id,eligible=True,target='ppal-semantics',production=False,contract=contract,
            reason='independently evaluated semantic admission; separate shadow test and authorization required'),
            episode=scope,sources=[resolution.id,outcome.id],producer='Reflection',version='ala-2').id
    shadow_id=None
    if operational_proposal:
        from .operational import shadow
        shadow_id=shadow(journal,operational_proposal,snapshot).id
    return dict(status='already_resolved' if resolved else 'resolved',resolution=resolution.data['payload'],result=verdict,reason=reason,resolution_id=resolution.id,
        evaluation_id=outcome.id,deployment_proposal=proposal.id,operational_proposal=operational_proposal,shadow_id=shadow_id,metrics=metric,candidate_id=candidate['identifier'])


def investigate(dataset, gateway, *, budget_seconds=60., max_jobs=2, driver=None, executive=None, on_progress=None, diagnostics_only=False, review_questions=False, deployment_authority=None, refinement_only=False):
    """Existing Executive selects portfolio; existing chooser selects method trial."""
    if gameplay_active(): raise RuntimeError('offline learning unavailable during active gameplay')
    if not 1<=max_jobs<=8 or not 1<=budget_seconds<=3600: raise ValueError('bounded offline resources required')
    from experiments.ppal.reflect_robotron import reflect_perceptual_opportunities, reflect_model_investigations, reflect_question_investigations, reflect_training_extensions
    from experiments.ppal.experiment_return import select_offline_experiment
    registry=default_registry(); executive=executive or LearningExecutive(dataset.journal,gateway)
    # Recover an interruption after Executive outcome delivery but before the
    # ordinary pause handoff. Never commission that completed prediction again.
    for identifier, project in executive.projects().items():
        history=project['experiment_history']
        if project['status']=='active' and history and history[-1].get('experiment_kind')=='offline':
            pending=[r for r in dataset.journal.records('event') if
                r.data['payload'].get('category')=='offline_experiment_plan' and
                r.data['payload']['plan'].get('project_id')==identifier and
                not any(h['prediction_id']==r.data['payload']['plan']['prediction_id'] for h in history)]
            if not pending:
                executive.transition(identifier,'paused','Recorded outcome recovered after interruption; await new evidence',
                    dataset.journal,[history[-1]['resolution_id']])
    torch_available=importlib.util.find_spec('torch') is not None
    opportunities=([] if diagnostics_only or refinement_only else reflect_perceptual_opportunities(dataset,gateway,registry))+([] if refinement_only else reflect_model_investigations(dataset,gateway,registry))
    if not diagnostics_only:opportunities+=reflect_training_extensions(dataset,gateway,registry)
    if review_questions: opportunities+=reflect_question_investigations(dataset,gateway,registry)
    if not refinement_only:
        from .meditation import reflect
        opportunities+=reflect(dataset,gateway,registry)
    for item in opportunities:
        identifier=executive.propose(item['proposal'],dataset.journal,[item['evidence_id']])
        project=executive.projects()[identifier]
        spec=dataset.journal.get(item['hypothesis_id']).data['payload']['proposal']
        from .datasets import scientific_content
        if (project['status']=='blocked' and not project['experiment_history']
                and 'Source identity quarantined' in (project.get('completion_rationale') or '')):
            from .episode_identity import eligible
            if all(eligible(dataset.journal,dataset.journal.get(i).data['payload']) for i in spec['source_evidence']):
                executive.transition(identifier,'candidate','Acquisition restored verified association; resume preserved experiment',
                    dataset.journal,[item['evidence_id']])
        if project.get('hold') and project['status'] in ('paused','blocked') and project['experiment_history'] and project.get('disposition')!='budget_exhausted' and (project['method']!='meditation-motion' or spec.get('scope',{}).get('corpus_id')) and not any(scientific_content(dataset.journal,h.get('dataset_id'))==scientific_content(dataset.journal,spec['dataset_id']) for h in executive.agenda_history(identifier)) and executive.reassessment_ready(identifier,dataset.journal,spec):
            executive.transition(identifier,'candidate','New versioned evidence permits reassessment; no independent confirmation assumed',dataset.journal,[item['evidence_id']])
    # A yielded committed experiment can resume after its precise input,
    # checkpoint or capability changes. Preserve the original prediction.
    for row in dataset.journal.category_records('event','offline_experiment_plan'):
        plan=row.data['payload']['plan'];identifier=plan.get('project_id')
        old=executive.work_states().get(identifier)
        if not old or old['status']!='blocked':continue
        progress=executive.experiment_progress(dataset.artifacts.parent/'models',plan['prediction_id'])
        dependency=executive.experiment_dependency(plan,budget_seconds,registry,torch_available)
        if old['dependency']!=dependency or old['after']!=progress:
            executive.transition(identifier,'candidate','Recorded experiment dependency/checkpoint changed; resume original work',
                dataset.journal,[row.id])
    started=time.monotonic(); results=[]; seen=set()
    for _ in range(max_jobs):
        remaining=budget_seconds-(time.monotonic()-started)
        if remaining<1: break
        available = {'model-diagnostics','meditation-motion'} | ({'evidence-review'} if review_questions else set()) | ({'cnn-reconstruction','cnn-classification','cnn-validation-extension'} if not diagnostics_only and torch_available else set())
        if refinement_only:available={'cnn-validation-extension'} if torch_available else set()
        selection=executive.select(methods=available,
            resources={'offline-slot','RGB-examples','torch','model-evaluation','context-evidence','meditation-evidence'},authorized_methods=available)
        if not selection['project']: break
        project=selection['project']; context=executive.chooser_context(project['id'])
        plan=select_offline_experiment(gateway,dataset.journal,context,budget_seconds=remaining)
        if plan is None:
            executive.transition(project['id'],'blocked','Evaluator/chooser has no justified executable investigation under current evidence',
                dataset.journal,project['tactical_hypothesis_evidence'])
            continue
        if plan['prediction_id'] in seen: break
        seen.add(plan['prediction_id'])
        commission=executive.commission(plan,dataset.journal)
        from .episode_identity import eligible
        evidence_payloads=[dataset.journal.get(i).data['payload'] for i in plan['source_evidence']]
        try:
            evidence_payloads.append(dataset.journal.get(plan['dataset_id']).data['payload'])
        except KeyError:
            pass # aggregate content key; exact contributing records checked above
        if not all(eligible(dataset.journal,p) for p in evidence_payloads):
            executive.transition(project['id'],'blocked',
                'Source identity quarantined; preserve experiment and bookmark, await verified association',
                dataset.journal,plan['source_evidence'])
            continue
        work_before=executive.experiment_progress(dataset.artifacts.parent/'models',plan['prediction_id'])
        result=registry.invoke(project['method'],resources={'RGB-examples','verified-labels','three-independent-groups','model-evaluation','context-evidence','meditation-evidence'},
            authorized={project['method']},plan=plan,dataset=dataset,output=dataset.artifacts.parent/'models',driver=driver,on_progress=on_progress)
        if result['status'] in ('resolved','already_resolved'):
            if project['id'] in executive.work_states():
                executive.account_work(project['id'],before=work_before,
                    after=digest(dict(resolution=result.get('resolution_id'))),
                    dependency=executive.experiment_dependency(plan,budget_seconds,registry,torch_available),
                    outcome='completed',sources=[plan['prediction_id']],
                    resumption_condition='Completed retained experiment; future independent evidence may justify a new version')
            if result['status']=='already_resolved':
                payload=result['resolution']; result.update(result=payload['result'],reason=payload['reason'])
            executive.record_result(project['id'],plan,result,dataset.journal,episode=SCOPE)
            gateway.assess_decision('offline:'+plan['prediction_id'],'helpful' if result['result']=='supported' else 'harmful',
                result['resolution_id'],'diagnostic prediction usefulness only; no score reward attribution')
            gateway.remember(Experience(kind='outcome',summary='Offline '+project['method']+' experiment: '+result['result'],
                source='learning:foundry-resolution',subject=project['id'],goal=project['goal'],
                outcome=json.dumps(result.get('metrics',{})),significant=True,
                tags=('offline','diagnostic','uncertain'),evidence=result['resolution_id']))
        if result['status'] in ('resolved','already_resolved') and result.get('evaluation_id') and project['method'] not in ('model-diagnostics','evidence-review','meditation-motion'):
            from experiments.ppal.reflect_robotron import reflect_model_outcome
            result['reflection']=reflect_model_outcome(dataset.journal,plan,result,gateway)
            from .deployment import CapabilityDeployment
            result['deployment']=CapabilityDeployment(dataset.journal).apply_authority(result,deployment_authority,dataset.artifacts.parent/'semantic-activation.json')
        elif result['status'] in ('resolved','already_resolved'):
            from experiments.ppal.reflect_robotron import reflect_retrieval_outcome
            result['reflection']=reflect_retrieval_outcome(dataset.journal,plan,result,gateway)
        results.append(dict(project_id=project['id'],selection=selection,commission=commission,plan=plan,result=result))
        if result['status']=='deferred':
            result['developmental_progress']=executive.account_work(project['id'],before=work_before,
                after=executive.experiment_progress(dataset.artifacts.parent/'models',plan['prediction_id']),
                dependency=executive.experiment_dependency(plan,budget_seconds,registry,torch_available),outcome='yielded',sources=[plan['prediction_id']],
                resumption_condition='Resume same prediction when its retained checkpoint, qualified dataset or capability/resource budget changes')
            break
        # Serial offline jobs can serve additional projects; no second physical
        # actuator experiment is smuggled into the ordinary action hook.
        executive.transition(project['id'],'paused','Offline result awaits independent new evidence; preserve questions',
            dataset.journal,[result['resolution_id']])
    report=dict(schema='ala-1-cycle-v1',opportunities=opportunities,results=results,projects=executive.projects(),
        capabilities=registry.describe(),elapsed=time.monotonic()-started,
        autonomy='bounded rule-based evidence-to-experiment control, not general intelligence',
        physical_gameplay_improvement='not demonstrated')
    report['resources']=dict(torch_available=torch_available,
        unavailable_methods=[] if torch_available else ['cnn-reconstruction','cnn-classification','cnn-validation-extension'],
        inference='portable NumPy classifier available only with verified export and separate deployment authority')
    atomic_json(dataset.artifacts.parent/'ala-report.json',report)
    lines=['ALA-1 offline learning report','',report['autonomy'],'']
    for item in results:
        result=item['result']
        lines.extend([f"Project {item['project_id'][:12]}: {item['selection']['project']['goal']}",
            'Selection: '+item['plan']['reason'],
            f"Prediction {item['plan']['prediction_id'][:12]}: {item['plan']['expected']}",
            'Resolution: '+result.get('result',result['status']),
            'Diagnostic metrics: '+json.dumps(result.get('metrics',{})),
            'Next: '+(report['projects'][item['project_id']].get('completion_rationale') or 'Resume the checkpointed investigation; prediction unresolved'),
            'Physical task improvement: UNKNOWN',''])
    if not results: lines.append('No justified executable experiment under current evidence and resources.')
    if not torch_available:lines.append('Torch unavailable: CNN training/refinement deferred; metadata diagnostics remain available. No learned model activated.')
    (dataset.artifacts.parent/'ala-report.md').write_text('\n'.join(lines)+'\n')
    return report


def main():
    import argparse
    from memory.gateway import MemoryGateway
    from memory.evaluator import MemoryEvaluator
    from memory.store import JsonlStore
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('episodes',nargs='*',type=Path); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--budget-seconds',type=float,default=60.); parser.add_argument('--max-jobs',type=int,default=2)
    parser.add_argument('--episode-root',type=Path,action='append',default=[])
    parser.add_argument('--ingest-only',action='store_true')
    parser.add_argument('--diagnostics-only',action='store_true',help='retrieve existing failed-model evidence without opening pixel/model artifacts')
    parser.add_argument('--review-questions',action='store_true',help='also investigate unresolved questions by retrieving frozen experience references')
    parser.add_argument('--refinement-only',action='store_true',help='only evidence-generated training interventions; never reopen the final test')
    parser.add_argument('--deployment-authority',type=Path,help='pre-existing external bounded deployment authorization; not generated by learning')
    parser.add_argument('--resolve-artifacts',type=Path,help='explicit directory of original content-hashed pixels after relocation; histories remain immutable')
    args=parser.parse_args()
    if gameplay_active(): parser.error('offline only: active player detected')
    args.output.mkdir(parents=True,exist_ok=True)
    with (args.output/'offline.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: parser.error('another offline worker owns these resources')
        journal=EvidenceJournal(args.output/'learning-evidence.sqlite3'); dataset=ExperienceDataset(journal,args.output/'pixels')
        gateway=MemoryGateway(store=JsonlStore(args.output/'memory.jsonl'),
                              evaluator=MemoryEvaluator(args.output/'evaluator.sqlite3'))
        try:
            if args.resolve_artifacts:dataset.locate_artifacts(args.resolve_artifacts)
            from .retrospective import discover_episodes
            for episode in args.episodes+discover_episodes(args.episode_root): ingest_episode(episode,dataset,gateway)
            if not args.ingest_only:
                report=investigate(dataset,gateway,budget_seconds=args.budget_seconds,max_jobs=args.max_jobs,
                    executive=LearningExecutive(journal,gateway),diagnostics_only=args.diagnostics_only,
                    review_questions=args.review_questions,
                    deployment_authority=json.loads(args.deployment_authority.read_text()) if args.deployment_authority else None,
                    refinement_only=args.refinement_only)
                print(json.dumps({k:report[k] for k in ('elapsed','autonomy','physical_gameplay_improvement')}))
        finally: journal.close()

if __name__=='__main__': main()


def postgame_learning(root, source_journal, episode, context, gateway, executive, output, *, budget_seconds=60., on_progress=None, deployment_authority=None):
    """Optional existing between-game hook; reuse already computed context."""
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    with (output/'offline.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        journal=EvidenceJournal(output/'learning-evidence.sqlite3')
        dataset=ExperienceDataset(journal,output/'pixels')
        try:
            if (Path(root)/'report.json').is_file():
                imported = ingest_episode(root, dataset, gateway)
                if imported['episode'] != episode:
                    raise ValueError('postgame source episode identity mismatch')
                if on_progress: on_progress()
            else:
                # Existing unfinished postgame contexts retain their original
                # journal identity; no fabricated finalized episode is imported.
                reference=journal.append('observation',dict(category='learning_context_reference',context=context,
                    source_journal=str(source_journal.path.resolve()),source_id=context['evidence_id'],source_episode=episode),
                    episode=SCOPE,producer='existing-evidence-consolidation',version='ala-1')
                for path in sorted(Path(root).glob('review-*.jpg')):
                    dataset.add(path,episode=episode,source=dict(journal=str(source_journal.path.resolve()),
                        context_id=context['evidence_id'],artifact=str(path.resolve()),sha256=sha(path)),
                        metadata=dict(review_subset=True,identity_status='unknown',physical_experiment=episode,
                            temporal_context='see original agency/action evidence',context_reference=reference.id))
                    if on_progress: on_progress()
            return investigate(dataset,gateway,budget_seconds=budget_seconds,executive=executive,on_progress=on_progress,deployment_authority=deployment_authority)
        finally: journal.close()
