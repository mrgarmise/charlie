"""Executive-owned model investigation, retained in Charlie's existing notebook."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from memory.evidence import digest
from memory.former import Experience
from .contracts import LearningNeed,TrainingProposal,ModelCandidate,QualificationDecision,document
from .data import DatasetStore,sha,SCOPE
from .robotron import frame,incumbent,predict
from .evaluation import evaluate
from learning.foundry import atomic_json


class ModelLearningService:
    def __init__(self,journal,root,*,wall_seconds=10.,allow_synthetic=False,qualification_gates=None):
        self.journal=journal;self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.data=DatasetStore(journal,self.root/'observations')
        self.wall_seconds=wall_seconds;self.allow_synthetic=allow_synthetic
        # Policy is supplied by the human/application, never by the candidate.
        from .qualification import gates
        self.gates=gates(qualification_gates)
        self.human=None
        import importlib.util
        if importlib.util.find_spec("memory.human_interaction") is not None:
            from memory.human_interaction import HumanInteractionGateway
            from .human import ModelHumanGateway
            self.human=ModelHumanGateway(self,HumanInteractionGateway(journal))

    def gaps(self, on_progress=None):
        """Durable uncertainty/errors only, including incumbent unknown observations."""
        result=[]
        incumbent_sha=sha(Path(__file__).resolve().parents[2]/'experiments/ppal/robotron_screen_state.py')
        cached={r.data['payload']['observation_id']:r.data['payload']['label'] for r in self.data.events('model_incumbent')
                if r.data['payload'].get('implementation_sha256')==incumbent_sha}
        for row in self.data.rows():
            if row['task']!='robotron.screen_state': continue
            if on_progress:on_progress()
            phase=cached.get(row['observation_id'])
            if phase is None:
                phase=incumbent(frame(row))
                self.data.append('model_incumbent',dict(observation_id=row['observation_id'],label=phase,adapter='existing-screen-state-v1',implementation_sha256=incumbent_sha),sources=[row['observation_id']])
            if phase=='unknown' or (row['label'] is not None and phase!=row['label']): result.append(row['observation_id'])
        # Registered shadow uncertainty is eligible evidence, never action authority.
        for row in self.data.events('model_shadow'):
            if row.data['payload']['prediction']['label']=='unknown': result.append(row.data['payload']['observation_id'])
        return list(dict.fromkeys(result))[-256:]

    def status(self):
        report=self.data.inspect(allow_synthetic=self.allow_synthetic)
        return dict(schema=SCOPE,data={k:v for k,v in report.items() if k!='rows'},review_queue=self.data.review_queue(),
            needs=[dict(id=r.id,**r.data['payload']) for r in self.data.events('model_need')],
            candidates=[dict(id=r.id,**r.data['payload']) for r in self.data.events('model_candidate')],
            decisions=[dict(id=r.id,**r.data['payload']) for r in self.data.events('model_qualification')],
            activation=self.active(),mode='shadow by default',physical_authorization=False)

    def consider(self,executive,*,on_progress=None):
        """Called by the existing Executive. Selection competes in its portfolio."""
        if executive.journal is not self.journal: raise ValueError('single Executive notebook required')
        from learning.cycle import gameplay_active
        if gameplay_active(): return dict(status='DEFERRED',reason='primary gameplay owner')
        sources=self.gaps(on_progress)
        if not sources: return dict(status='NO_NEED',reason='no durable perception gap')
        need=LearningNeed('robotron.screen_state','incumbent unknown or disagrees with attributed evidence',tuple(sources))
        key=digest(document(need))
        rec=next((r for r in self.data.events('model_need') if r.data['payload']['need_key']==key),None)
        rec=rec or self.data.append('model_need',dict(need=document(need),need_key=key),sources=sources,producer='Reflection')
        report=self.data.inspect(allow_synthetic=self.allow_synthetic)
        signature=digest(dict(rows=report['rows'],budget=self.wall_seconds))
        prior=next((r for r in reversed(self.data.events('model_turn')) if r.data['payload']['need_id']==rec.id),None)
        if prior and prior.data['payload']['signature']==signature:
            if self.human:
                self.human.dispatch();self.human.receive()
            return prior.data['payload']['result']
        from memory.learning_projects import reflect_project_opportunities
        reflected=reflect_project_opportunities(self.journal,SCOPE,[dict(method='perception-model-learning',
            scope=dict(task=need.task,need_id=rec.id),expected='independent screen-state diagnostic improvement',
            conditions=[dict(partition='validation'),dict(partition='test')],observed_conditions=[dict(partition='validation')],
            evidence_ids=[rec.id],requires=['offline-slot'])])[0]
        project_id=executive.propose(reflected['proposal'],self.journal,[reflected['evidence_id']])
        # A dataset change may reopen a held evidence request, but never repeat a
        # completed training trial. One candidate per need; new need needs new errors.
        project=executive.projects()[project_id]
        if project.get('hold'):
            executive._event(dict(op='assessment',project_id=project_id,changes=dict(status='candidate',hold=False)))
        import importlib.util
        methods={'perception-model-learning','model-diagnostics','meditation-motion','evidence-review'}
        resources={'offline-slot','RGB-examples','model-evaluation','context-evidence','meditation-evidence'}
        if importlib.util.find_spec('torch') is not None:
            methods|={'cnn-reconstruction','cnn-classification','cnn-validation-extension'}
            resources.add('torch')
        choice=executive.select(methods=methods,resources=resources,
            authorized_methods=methods,inspect=True)
        if not choice['project'] or choice['project']['id']!=project_id:
            return dict(status='DEFERRED',reason='Executive selected another project',alternatives=choice['alternatives'])
        selection=executive._event(dict(op='selected',project_id=project_id,input_signature=signature,alternatives=choice['alternatives'],
            interrupted_projects=[],reason='evidenced perception gap; bounded offline alternative chosen'))
        if report['status']!='READY':
            from .questions import review_requests
            review_requests(self)
            result=dict(status='NEEDS_LABELS',reason=report['issues'],review_queue=self.data.review_queue())
        else:
            snapshot=self.data.freeze(allow_synthetic=self.allow_synthetic)
            result=self.train(rec.id,snapshot.id,selection_id=selection.id,on_progress=on_progress)
        event=self.data.append('model_turn',dict(need_id=rec.id,project_id=project_id,signature=signature,result=result),sources=[rec.id],producer='LearningExecutive')
        executive._event(dict(op='assessment',project_id=project_id,changes=dict(status='paused',hold=True,
            next_direction='Await changed labels/data or new error evidence',completion_rationale=result['status'])))
        executive.gateway.remember(Experience(kind='outcome',source='model-learning:diagnostic',
            summary='Perception learning: '+result['status'],goal=need.desired_outcome,outcome=str(result),subject=need.task,
            significant=True,evidence=str(self.journal.path.resolve())+'#'+event.id,tags=('model-learning','diagnostic')))
        if self.human:
            self.human.dispatch();self.human.receive()
        atomic_json(self.root/'status.json',self.status())
        return result

    def train(self,need_id,dataset_id,*,selection_id=None,on_progress=None):
        need=self.journal.get(need_id)
        if need.data['payload'].get('category')!='model_need': raise ValueError('persisted need required')
        projects=[r for r in self.journal.records('event') if r.data['producer']=='LearningExecutive' and r.data['payload'].get('op')=='selected']
        selected=projects[-1].data['payload']['project_id'] if projects else None
        proposals=[r.data['payload']['project'] for r in self.journal.records('event') if r.data['payload'].get('op')=='proposed']
        if not selection_id or not projects or projects[-1].id!=selection_id:
            raise ValueError('Executive selection for this need required')
        if not any(p['id']==selected and p['method']=='perception-model-learning' and p['scope'].get('need_id')==need_id for p in proposals):
            raise ValueError('Executive selection for this need required')
        snapshot_record=self.journal.get(dataset_id)
        snapshot=snapshot_record.data['payload']['dataset']
        # Current immutable bytes and split ownership are independently rechecked.
        frozen=self.data.freeze(allow_synthetic=self.allow_synthetic)
        if frozen.id!=dataset_id: raise ValueError('frozen dataset differs from current reviewed evidence')
        prior=[r for r in self.data.events('model_proposal') if r.data['payload']['need_id']==need_id]
        if not prior and any(r.data['payload']['proposal']['dataset_id']==dataset_id for r in self.data.events('model_proposal')):
            return dict(status='DEFERRED',reason='same reviewed corpus already attempted; no model proliferation')
        proposal=TrainingProposal(need_id,dataset_id,wall_seconds=self.wall_seconds)
        prop=prior[0] if prior else self.data.append('model_proposal',dict(proposal=document(proposal),need_id=need_id,executive_selection_id=selection_id),sources=[need_id,dataset_id],producer='LearningExecutive')
        if prop.data['payload']['proposal']!=document(proposal):
            return dict(status='DEFERRED',reason='proposal budget/dataset version changed; explicit new evidenced need required')
        try:
            retained=next((r for r in self.data.events('model_candidate') if r.data['payload']['candidate']['proposal_id']==prop.id),None)
            receipt=self.root/'receipts'/(digest(asdict(proposal))+'.json')
            if retained:
                record=retained;candidate=retained.data['payload']['candidate']
                artifact=Path(self.candidate(record.id)['artifact'])
            else:
                if prior and not receipt.exists():
                    return dict(status='DEFERRED',reason='interrupted worker has no completed receipt; budget consumed, no automatic retraining')
                artifact=self._worker(proposal,snapshot_record,on_progress)
                candidate=document(ModelCandidate(str(artifact),sha(artifact),dataset_id,prop.id,tuple(snapshot['labels']),implementation_sha256=sha(Path(__file__).with_name('robotron.py'))))
                record=self.data.append('model_candidate',dict(candidate=candidate,training_metadata=dict(algorithm=proposal.algorithm,
                    limits=asdict(proposal),dataset_digest=snapshot_record.data['payload']['dataset_digest'],
                    trainer_sha256=sha(Path(__file__).with_name('worker.py')),operator='Executive-commissioned fixed worker')),sources=[prop.id])
            model=json.loads(artifact.read_text())
            prior_evaluation=next((r for r in self.data.events('model_evaluation') if r.data['payload']['candidate_id']==record.id),None)
            if prior_evaluation:
                evaluation=prior_evaluation;measured=evaluation.data['payload']['metrics']
            else:
                measured=evaluate(model,snapshot,on_progress=on_progress,wall_seconds=self.wall_seconds)
                consulted=set(measured['test_observations'])
                reused=any(consulted.intersection(r.data['payload']['metrics']['test_observations']) for r in self.data.events('model_evaluation'))
                measured['fresh_holdout']=not reused
                evaluation=self.data.append('model_evaluation',dict(candidate_id=record.id,metrics=measured),sources=[record.id,dataset_id],producer='independent-model-evaluator')
            from .qualification import reasons as assess
            reasons=assess(measured,self.gates)
            decision=QualificationDecision(record.id,evaluation.id,not reasons,tuple(reasons))
            qualification=next((r for r in self.data.events('model_qualification') if r.data['payload']['decision']['candidate_id']==record.id),None)
            qualification=qualification or self.data.append('model_qualification',dict(decision=document(decision),gates=self.gates),sources=[evaluation.id])
            atomic_json(artifact.parent/'model-card.json',dict(candidate=candidate,metrics=measured,
                decision=document(decision),limitations=['host only','no timed transition qualification','no object coordinates','human approval required']))
            return dict(status='QUALIFIED_PENDING_APPROVAL' if not reasons else 'REJECTED',candidate_id=record.id,evaluation_id=evaluation.id,qualification_id=qualification.id)
        except (OSError,ValueError,RuntimeError,InterruptedError) as exc:
            self.data.append('model_worker_deferred',dict(proposal_id=prop.id,reason=str(exc)),sources=[prop.id])
            return dict(status='DEFERRED',reason=str(exc))

    def _worker(self,proposal,snapshot_record,on_progress):
        dataset=snapshot_record.data['payload']
        receipt=self.root/'receipts'/(digest(asdict(proposal))+'.json')
        if receipt.exists():
            retained=json.loads(receipt.read_text());path=Path(retained['artifact'])
            if sha(path)!=retained['sha256']:raise ValueError('completed training receipt changed')
            return path
        if len(dataset['dataset']['rows'])>proposal.max_frames: raise ValueError('frame budget exceeded')
        # Seal final test out of the trainer input, including metadata/labels.
        training=dict(dataset['dataset'],rows=[r for r in dataset['dataset']['rows'] if r['partition']!='test'])
        repo=Path(__file__).resolve().parents[2]
        env={k:os.environ[k] for k in ('PATH','LANG') if k in os.environ}
        env.update(PYTHONPATH=str(repo),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
        with tempfile.TemporaryDirectory(prefix='training-',dir=self.root) as temp:
            work=Path(temp); config=work/'config.json'
            atomic_json(config,dict(proposal=asdict(proposal),dataset=training,dataset_digest=dataset['dataset_digest']))
            if sum(p.stat().st_size for p in work.iterdir())>proposal.disk_mb*1024**2:raise ValueError('worker scratch disk budget exceeded')
            with (work/'worker.log').open('wb') as log:
                process=subprocess.Popen([sys.executable,'-m','learning.model_learning.worker',str(config)],cwd=work,env=env,
                    stdout=log,stderr=log,start_new_session=True)
                start=time.monotonic()
                try:
                    while process.poll() is None:
                        if on_progress: on_progress()
                        if sum(p.stat().st_size for p in work.iterdir())>proposal.disk_mb*1024**2:raise InterruptedError('worker scratch disk budget exceeded')
                        if time.monotonic()-start>proposal.wall_seconds: raise InterruptedError('worker wall budget exceeded')
                        time.sleep(.02)
                    if process.returncode!=0: raise RuntimeError('bounded worker failed (returncode '+str(process.returncode)+'): '+(work/'worker.log').read_text()[-1000:])
                finally:
                    if process.poll() is None: os.killpg(process.pid,signal.SIGKILL)
                    process.wait()
            if sum(p.stat().st_size for p in work.iterdir())>proposal.disk_mb*1024**2:raise ValueError('worker scratch disk budget exceeded')
            artifact=work/'model.json'
            if not artifact.is_file() or artifact.stat().st_size>proposal.disk_mb*1024**2: raise ValueError('missing/oversize model')
            destination=self.root/'models'/sha(artifact);destination.mkdir(parents=True,exist_ok=True)
            target=destination/'model.json'
            if target.exists() and sha(target)!=sha(artifact): raise ValueError('immutable model conflict')
            if not target.exists(): target.write_bytes(artifact.read_bytes());target.chmod(0o444)
            receipt.parent.mkdir(exist_ok=True)
            atomic_json(receipt,dict(artifact=str(target),sha256=sha(target),proposal=asdict(proposal)))
            return target

    def candidate(self,identifier):
        p=self.journal.get(identifier).data['payload']
        if p.get('category')!='model_candidate': raise ValueError('registered candidate required')
        candidate=p['candidate']
        if sha(candidate['artifact'])!=candidate['sha256']: raise ValueError('model artifact changed')
        if candidate.get('implementation_sha256')!=sha(Path(__file__).with_name('robotron.py')):raise ValueError('inference implementation changed; requalification required')
        return candidate

    def shadow(self,candidate_id,observation_id):
        model=json.loads(Path(self.candidate(candidate_id)['artifact']).read_text())
        row=next(r for r in self.data.rows() if r['observation_id']==observation_id)
        prediction=predict(model,frame(row))
        return self.data.append('model_shadow',dict(candidate_id=candidate_id,observation_id=observation_id,prediction=prediction),sources=[candidate_id,observation_id])

    def active(self):
        from learning.deployment import CapabilityDeployment
        return CapabilityDeployment(self.journal).active('perception-shadow')
