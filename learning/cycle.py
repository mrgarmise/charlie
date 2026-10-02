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
from .foundry import atomic_json


def gameplay_active():
    # No camera ownership probe. Refuse host training while a live player owns
    # time-critical work. Non-Linux callers must supply equivalent orchestration.
    proc=Path('/proc')
    if not proc.is_dir(): return True
    for path in proc.glob('[0-9]*/cmdline'):
        try:
            args=path.read_bytes().split(b'\0')
            if b'experiments.ppal.play_robotron' in args: return True
        except (OSError,PermissionError): pass
    return False


def ingest_episode(root, dataset, gateway):
    """Reuse existing immutable import and context Reflection; no tracker pass."""
    from experiments.ppal.episode_evidence import import_episode
    from experiments.ppal.reflect_robotron import reflect_episode_context
    root=Path(root)
    source=EvidenceJournal(dataset.artifacts.parent/('import-'+digest(str(root.resolve()))[:16]+'.sqlite3'))
    try:
        episode=import_episode(root,source)
        context=reflect_episode_context(root,source,episode,gateway)
        reference=dataset.journal.append('observation',dict(category='learning_context_reference',
            context=context,source_journal=str(source.path.resolve()),source_id=context['evidence_id'],
            source_episode=episode,source_sha256=sha(root/'report.json') if (root/'report.json').exists() else None),
            episode=SCOPE,producer='existing-evidence-consolidation',version='ala-1')
        # Existing saved review frames are a deliberately selected, biased subset.
        # This dataset contains all of that subset, never fictional capture frames.
        examples=[]
        for path in sorted(root.glob('review-*.jpg')):
            examples.append(dataset.add(path,episode=episode,source=dict(journal=str(source.path.resolve()),
                context_id=context['evidence_id'],artifact=str(path.resolve()),sha256=sha(path)),
                metadata=dict(review_subset=True,identity_status='unknown',
                    physical_experiment=episode,temporal_context='see original agency/action evidence',
                    context_reference=reference.id)).id)
        return dict(episode=episode,context_id=reference.id,examples=examples)
    finally: source.close()


def run_plan(plan, dataset, output, *, driver=None):
    """Frozen alternative comparison; final test never ranks architectures."""
    from experiments.ppal.progress_supervision import supervise
    from .foundry import evaluate
    journal=dataset.journal; snapshot=journal.get(plan['dataset_id']).data['payload']
    resolved=journal.resolution_for(plan['prediction_id'])
    if resolved:
        return dict(status='already_resolved',resolution=resolved.data['payload'],resolution_id=resolved.id)
    output=Path(output)/plan['prediction_id']; output.mkdir(parents=True,exist_ok=True)
    training=[]
    for spec in plan['candidates']:
        identifier=digest(dict(spec=spec,dataset_digest=digest(snapshot))); candidate=output/identifier; candidate.mkdir(exist_ok=True)
        config=dict(snapshot=snapshot,spec=spec,output=str(candidate.resolve()),budget_seconds=plan['budget_seconds']/len(plan['candidates']))
        config_path=candidate/'worker.json'; atomic_json(config_path,config)
        if not (candidate/'training.json').exists():
            cmd=[sys.executable,'-m','learning.worker',str(config_path)]
            rc=(driver(cmd,candidate/'progress.json',budget=config['budget_seconds']+40) if driver else
                supervise(cmd,candidate/'progress.json',silence=30.,processing=30.,budget=config['budget_seconds']+40))
            if rc!=0:
                journal.append('event',dict(category='offline_experiment_deferred',prediction_id=plan['prediction_id'],returncode=rc,
                    checkpoint=str(candidate/'last.pt'),reason='worker yielded, failed or stopped; no verdict fabricated'),
                    episode=SCOPE,sources=[plan['prediction_id']],producer='offline-orchestrator',version='ala-1')
                return dict(status='deferred',returncode=rc)
        value=json.loads((candidate/'training.json').read_text())
        if value['dataset_digest']!=digest(snapshot) or value['spec']!=spec or sha(value['checkpoint'])!=value['checkpoint_sha256']:
            raise ValueError('candidate artifact provenance changed')
        record=journal.append('event',dict(category='model_training',candidate=value,experiment_kind='offline',
            prediction_id=plan['prediction_id'],dataset_id=plan['dataset_id']),episode=SCOPE,
            sources=[plan['prediction_id'],plan['dataset_id']],producer='ModelFoundry',version='ala-1')
        training.append((record,value))
    record,candidate=min(training,key=lambda pair:pair[1]['validation_loss'])
    selected=journal.append('event',dict(category='model_candidate_selected',candidate_id=candidate['identifier'],
        criterion='validation loss only',alternatives=[dict(id=v['identifier'],validation_loss=v['validation_loss']) for _,v in training]),
        episode=SCOPE,sources=[r.id for r,_ in training],producer='ModelFoundry',version='ala-1')
    metric=evaluate(snapshot,candidate)
    outcome=journal.append('observation',dict(category='offline_model_evaluation',ee_episode=SCOPE,
        prediction_id=plan['prediction_id'],candidate=candidate,metrics=metric,
        experiment_kind='offline',independence_unit=plan['independence_unit'],
        semantic_finding='UNKNOWN',physical_performance='not tested'),episode=SCOPE,
        at=time.monotonic(),sources=[selected.id,plan['dataset_id']],producer='ModelFoundry',version='ala-1')
    forecast=journal.get(plan['prediction_id']).data
    in_horizon=forecast['at'] < outcome.data['at'] <= forecast['payload']['deadline']
    verdict=('supported' if metric['improved'] else 'contradicted') if in_horizon else 'unresolved'
    reason='Independent diagnostic metric compared with frozen train-only baseline; no gameplay causation inferred'
    if not in_horizon: reason='Completed outside the committed prediction horizon; diagnostic evaluation retained, forecast unresolved'
    resolution=journal.resolve(plan['prediction_id'],sources=[outcome.id] if outcome.data['at']>forecast['at'] else [],result=verdict,reason=reason)
    proposal=journal.append('event',dict(category='model_deployment_proposal',candidate_id=candidate['identifier'],
        evaluation_id=outcome.id,eligible=metric['improved'],target='offline-shadow',
        production=False,reason='independent diagnostic improvement' if metric['improved'] else 'candidate failed diagnostic baseline',
        limitations=metric['limitations']),episode=SCOPE,sources=[resolution.id,outcome.id],producer='Reflection',version='ala-1')
    return dict(status='resolved',result=verdict,reason=reason,resolution_id=resolution.id,
        evaluation_id=outcome.id,deployment_proposal=proposal.id,metrics=metric,candidate_id=candidate['identifier'])


def investigate(dataset, gateway, *, budget_seconds=60., max_jobs=2, driver=None, executive=None):
    """Existing Executive selects portfolio; existing chooser selects method trial."""
    if gameplay_active(): raise RuntimeError('offline learning unavailable during active gameplay')
    if not 1<=max_jobs<=8 or not 1<=budget_seconds<=3600: raise ValueError('bounded offline resources required')
    from experiments.ppal.reflect_robotron import reflect_perceptual_opportunities
    from experiments.ppal.experiment_return import select_offline_experiment
    registry=default_registry(); executive=executive or LearningExecutive(dataset.journal,gateway)
    opportunities=reflect_perceptual_opportunities(dataset,gateway,registry)
    for item in opportunities:
        identifier=executive.propose(item['proposal'],dataset.journal,[item['evidence_id']])
        project=executive.projects()[identifier]
        spec=dataset.journal.get(item['hypothesis_id']).data['payload']['proposal']
        if project.get('hold') and project['status']=='paused' and project.get('disposition')!='budget_exhausted' and not any(h.get('dataset_id')==spec['dataset_id'] for h in project['experiment_history']):
            executive.transition(identifier,'candidate','New versioned evidence permits reassessment; no independent confirmation assumed',dataset.journal,[item['evidence_id']])
    started=time.monotonic(); results=[]; seen=set()
    for _ in range(max_jobs):
        remaining=budget_seconds-(time.monotonic()-started)
        if remaining<1: break
        selection=executive.select(methods={'cnn-reconstruction','cnn-classification'},
            resources={'offline-slot','RGB-examples','torch'},authorized_methods={'cnn-reconstruction','cnn-classification'})
        if not selection['project']: break
        project=selection['project']; context=executive.chooser_context(project['id'])
        plan=select_offline_experiment(gateway,dataset.journal,context,budget_seconds=remaining)
        if plan is None or plan['prediction_id'] in seen: break
        seen.add(plan['prediction_id'])
        result=run_plan(plan,dataset,dataset.artifacts.parent/'models',driver=driver)
        if result['status'] in ('resolved','already_resolved'):
            if result['status']=='already_resolved':
                payload=result['resolution']; result.update(result=payload['result'],reason=payload['reason'])
            executive.record_result(project['id'],plan,result,dataset.journal,episode=SCOPE)
            gateway.assess_decision('offline:'+plan['prediction_id'],'helpful' if result['result']=='supported' else 'harmful',
                result['resolution_id'],'diagnostic prediction usefulness only; no score reward attribution')
            gateway.remember(Experience(kind='outcome',summary='Offline model experiment: '+result['result'],
                source='learning:foundry-resolution',subject=project['id'],goal=project['goal'],
                outcome=json.dumps(result.get('metrics',{})),significant=True,
                tags=('offline','diagnostic','uncertain'),evidence=result['resolution_id']))
        results.append(dict(project_id=project['id'],selection=selection,plan=plan,result=result))
        if result['status']=='deferred': break
        # Serial offline jobs can serve additional projects; no second physical
        # actuator experiment is smuggled into the ordinary action hook.
        executive.transition(project['id'],'paused','Offline result awaits independent new evidence; preserve questions',
            dataset.journal,[result['resolution_id']])
    report=dict(schema='ala-1-cycle-v1',opportunities=opportunities,results=results,projects=executive.projects(),
        capabilities=registry.describe(),elapsed=time.monotonic()-started,
        autonomy='bounded rule-based evidence-to-experiment control, not general intelligence',
        physical_gameplay_improvement='not demonstrated')
    atomic_json(dataset.artifacts.parent/'ala-report.json',report)
    return report


def main():
    import argparse
    from memory.gateway import MemoryGateway
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('episodes',nargs='*',type=Path); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--budget-seconds',type=float,default=60.); parser.add_argument('--max-jobs',type=int,default=2)
    parser.add_argument('--ingest-only',action='store_true'); args=parser.parse_args()
    if gameplay_active(): parser.error('offline only: active player detected')
    args.output.mkdir(parents=True,exist_ok=True)
    with (args.output/'offline.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: parser.error('another offline worker owns these resources')
        journal=EvidenceJournal(args.output/'learning-evidence.sqlite3'); dataset=ExperienceDataset(journal,args.output/'pixels')
        gateway=MemoryGateway()
        try:
            for episode in args.episodes: ingest_episode(episode,dataset,gateway)
            if not args.ingest_only:
                project_journal=EvidenceJournal(gateway.evaluator.path.with_name('learning-project-evidence.sqlite3'))
                try: report=investigate(dataset,gateway,budget_seconds=args.budget_seconds,max_jobs=args.max_jobs,executive=LearningExecutive(project_journal,gateway))
                finally: project_journal.close()
                print(json.dumps({k:report[k] for k in ('elapsed','autonomy','physical_gameplay_improvement')}))
        finally: journal.close()

if __name__=='__main__': main()
