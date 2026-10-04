"""Normal application adapter. The existing Executive owns every learning turn.

One supervised child keeps SQLite and bounded investigations away from vision's
real-time loop. It has no camera, motion or controller transport.
"""
from pathlib import Path
import json
import time
import fcntl
from dataclasses import asdict
from memory.evidence import EvidenceJournal, digest
from memory.learning_projects import LearningExecutive
from memory.gateway import MemoryGateway
from memory.evaluator import MemoryEvaluator
from memory.store import JsonlStore
from .datasets import ExperienceDataset, SCOPE, sha
from .foundry import atomic_json


class MeditationYield(Exception):
    """Expected cooperative resource interruption; never a completed finding."""


class DevelopmentLifecycle:
    def __init__(self, output, roots, *, budget_seconds=10., offline_authority=None, history_roots=()):
        self.output = Path(output).resolve()
        self.roots = [Path(r).resolve() for r in roots]
        self.history_roots = [Path(r).resolve() for r in history_roots]
        if not 1 <= budget_seconds <= 60:
            raise ValueError('normal application learning budget must be 1..60 seconds')
        if any(self.output == r or r in self.output.parents for r in self.roots):
            raise ValueError('notebook must be separate from original evidence')
        self.output.mkdir(parents=True, exist_ok=True)
        self.lock = (self.output/'offline.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.lock.close()
            raise
        self.journal = EvidenceJournal(self.output/'learning-evidence.sqlite3')
        self.dataset = ExperienceDataset(self.journal, self.output/'pixels')
        self.gateway = MemoryGateway(store=JsonlStore(self.output/'memory.jsonl'),
            evaluator=MemoryEvaluator(self.output/'evaluator.sqlite3'))
        self.executive = LearningExecutive(self.journal, self.gateway)
        self.budget = budget_seconds
        self.authority = offline_authority
        import subprocess
        repo=Path(__file__).resolve().parents[1]
        revision=subprocess.run(['git','rev-parse','HEAD'],cwd=repo,capture_output=True,text=True)
        dirty=subprocess.run(['git','status','--porcelain'],cwd=repo,capture_output=True,text=True)
        self.provenance=dict(code_revision=revision.stdout.strip() if revision.returncode==0 else None,
            dirty_worktree=bool(dirty.stdout),test_environment='offline process; no hardware capability initialized')
        self.error = None
        self.phase = 'idle'
        self._status()

    def _status(self, error=None):
        if error is not None: self.error=error
        from .deployment import CapabilityDeployment
        projects = self.executive.projects()
        rows = self.journal.records()
        findings = [r for r in rows if r.data['kind']=='resolution']
        requests = [p.get('developmental_bookmark') for p in projects.values()
            if p.get('developmental_bookmark')]
        active = CapabilityDeployment(self.journal).active('offline-shadow')
        current = next((p for p in reversed(list(projects.values())) if p['status']=='active'), None)
        if not current:
            current = next((p for p in reversed(list(projects.values())) if p.get('experiment_history')), None)
        summary=(self.phase,current['goal'] if current else None,self.error)
        if summary!=getattr(self,'last_summary',None):
            print('Development:',self.phase,'|',summary[1] or 'no project','|',self.error or '',flush=True)
            self.last_summary=summary
        from .episode_identity import current_conflicts
        atomic_json(self.output/'development-status.json', dict(schema='charlie-development-status-v1',
            phase=self.phase, last_activity=getattr(self,'last_activity',self.phase), current_project=current['id'] if current else None,
            current_question=current['goal'] if current else None,
            projects={k:dict(goal=v['goal'],status=v['status'],progress=v.get('progress',{}),next_direction=v.get('next_direction')) for k,v in projects.items()},
            latest_findings=[dict(id=r.id,**r.data['payload']) for r in findings[-3:]],
            latest_operational_outcome=next((dict(id=r.id,metrics=r.data['payload']['metrics'],changed_decisions=r.data['payload']['changed_decisions'])
                for r in reversed(rows) if r.data['payload'].get('category')=='offline_operational_outcome'),None),
            evidence_requests=requests, identity_conflicts=current_conflicts(self.journal), activation=active,
            physical_authorization=False, physical_score_improvement='UNKNOWN', error=self.error,
            provenance=self.provenance,
            authorization_requests=[r.data['payload'] for r in rows if r.data['payload'].get('category')=='offline_authorization_request'
                and not any(a.data['payload'].get('proposal_id')==r.data['payload']['proposal_id'] for a in rows
                    if a.data['payload'].get('category')=='capability_activation')]))

    def _phase(self, phase):
        self.phase = phase
        self._status()

    def acquire(self):
        from .retrospective import discover_episodes, merge_history
        from .cycle import ingest_episode
        from .archive_audit import audit, ingest as qualification
        from .meditation import qualify_corpus
        from .acquisition import maintain_episode_identity
        from .episode_identity import verified_tracks
        changed = False
        self.available_tracks = {}
        for source in self.history_roots:
            receipt=merge_history(source,self.output)
            self.journal.append('event',dict(category='normal_history_restore',receipt=receipt),
                episode=SCOPE,producer='existing-evidence-consolidation',version='normal-lifecycle-v1')
        for record in self.journal.records('observation'):
            p=record.data['payload']
            if p.get('category')=='normal_meditation_result':
                original=Path(p['result_path'])
                candidates=[original,self.output/'meditations'/p['context_id']/'result.json']
                candidates+=list((self.output/'recovered-history').glob('*/meditations/'+p['context_id']+'/**/result.json'))
                if not any(path.is_file() and sha(path)==p['result_sha256'] for path in candidates):
                    raise ValueError('durable meditation result changed or unavailable')
        for root in discover_episodes(self.roots):
            before = len(self.journal.records())
            identity=maintain_episode_identity(root,self.journal)
            if identity['status']!='verified':
                changed |= len(self.journal.records()) != before
                continue
            ingest_episode(root, self.dataset, self.gateway)
            qualification(self.journal, audit(root,identity=identity))
            changed |= len(self.journal.records()) != before
        self.available_tracks = verified_tracks(self.journal)
        # Independent acquisition owners deliver hash-bound qualifications here.
        # This adapter validates them; it never generates labels or authority.
        inbox = self.output/'acquisition-inbox'
        for path in sorted(inbox.glob('*.json')):
            key = sha(path)
            imported = [r for r in self.journal.records('event') if
                r.data['payload'].get('category')=='acquisition_delivery' and r.data['payload'].get('sha256')==key]
            if imported:
                continue
            try:
                record = qualify_corpus(self.dataset, path)
            except (ValueError,OSError) as exc:
                self.journal.append('event',dict(category='acquisition_delivery_rejected',sha256=key,
                    reason=str(exc)),episode=SCOPE,producer='existing-acquisition-capability',version='normal-lifecycle-v1')
                continue
            self.journal.append('event', dict(category='acquisition_delivery',sha256=key,record_id=record.id),
                episode=SCOPE, sources=[record.id],producer='existing-acquisition-capability',version='normal-lifecycle-v1')
            changed = True
        return changed

    def reflect_experience(self, context_id, commission_id):
        """Executive-commissioned existing track meditation, checkpointed by iteration."""
        from experiments.ppal.meditate_robotron import meditate, quality
        from .meditation import consume
        context = self.journal.get(context_id).data['payload']
        episode = context['source_episode']
        marker = next((r.data['payload'] for r in self.journal.records('event') if
            r.data['payload'].get('category')=='retrospective_ingestion' and r.data['payload']['context_id']==context_id), None)
        source = self.available_tracks.get(episode)
        result_path=self.output/'meditations'/context_id/'result.json'
        if result_path.exists() and json.loads(result_path.read_text()).get('status')=='unavailable' and source is not None and source.is_file():
            result_path=result_path.parent/sha(source)/'result.json'
        checkpoint=result_path.parent/'checkpoint.json'
        result_path.parent.mkdir(parents=True,exist_ok=True)
        if result_path.exists():
            result=json.loads(result_path.read_text())
        elif source is None or not source.exists():
            result=dict(status='unavailable',source_episode=episode,
                reason='Original tracks unavailable; context questions retained, no tracks reconstructed from summaries')
            atomic_json(result_path,result)
        else:
            source_hash=sha(source)
            if checkpoint.exists():
                saved=json.loads(checkpoint.read_text())
                if 'state_digest' in saved and saved['state_digest'] != digest({k:v for k,v in saved.items() if k!='state_digest'}):
                    raise ValueError('meditation checkpoint integrity mismatch')
                if saved.get('context_id',context_id)!=context_id or saved.get('commission_id',commission_id)!=commission_id:
                    raise ValueError('meditation checkpoint commission mismatch')
                if saved['source_sha256']!=source_hash:
                    raise ValueError('meditation source changed')
                tracks=saved['tracks'];history=saved['history'];merges=saved['merges']
                reconstruction=saved.get('reconstruction',{})
            else:
                tracks=json.loads(source.read_text()).get('tracks',[])
                history=[];merges=[];reconstruction={}
            # Explicit bounded algorithm; no invented independent observations.
            deadline=time.monotonic()+self.budget
            def progress():
                try:
                    self.yield_for_primary()
                except InterruptedError as exc:
                    self._phase('experiencing')
                    raise MeditationYield(str(exc)) from exc
                if time.monotonic()>deadline:
                    raise MeditationYield('meditation yielded at bounded resource deadline')
            def save_checkpoint():
                document=dict(source_sha256=source_hash,tracks=tracks,
                    history=history,merges=merges,reconstruction=reconstruction,
                    context_id=context_id,commission_id=commission_id)
                document['state_digest']=digest(document)
                atomic_json(checkpoint,document)
            try:
                # A stable saved iteration is already complete, even if the
                # process stopped between its checkpoint and result publication.
                while len(history)<6 and (not history or history[-1]['merges']):
                    progress()
                    tracks, step, additions=meditate(tracks,iterations=1,
                        on_progress=progress,resume_state=reconstruction)
                    iteration=len(history)+1
                    history.extend(dict(h,iteration=iteration) for h in step)
                    merges.extend(dict(m,iteration=iteration) for m in additions)
                    save_checkpoint()
            except MeditationYield as exc:
                if sha(source)!=source_hash:
                    raise ValueError('meditation source changed during computation')
                save_checkpoint()
                self.journal.append('event',dict(category='normal_meditation_yield',
                    context_id=context_id,commission_id=commission_id,
                    checkpoint_path=str(checkpoint),checkpoint_sha256=sha(checkpoint),
                    completed_iterations=len(history),reason=str(exc),status='resumable'),
                    episode=SCOPE,sources=[context_id,commission_id],
                    producer='Reflection',version='normal-lifecycle-v1')
                return None
            if sha(source)!=source_hash:
                raise ValueError('meditation source changed during computation')
            result=dict(status='completed',quality=quality(tracks),history=history,merges=merges,
                source_episode=episode,source_sha256=source_hash,tracks=tracks,
                qualification='retrospective unverified track reconstruction',
                origin='Executive-commissioned existing predictive meditation')
            atomic_json(result_path,result)
        sources=[context_id,commission_id]
        if result['status']=='completed' and all(isinstance(result['quality'][k]['mean_error'],(int,float)) for k in ('adjacent','gaps')):
            finding=consume(self.dataset,result_path,source_episode=episode,prior_use=marker['prior_use'] if marker else context.get('prior_use','diagnostic'))
            sources.append(finding.id)
        return self.journal.append('observation',dict(category='normal_meditation_result',
            context_id=context_id,source_episode=episode,result_path=str(result_path),
            result_sha256=sha(result_path),status=result['status']),episode=SCOPE,sources=sources,
            producer='Reflection',version='normal-lifecycle-v1',provenance=self.provenance)

    def evidence_eligible(self, payload):
        from .episode_identity import eligible
        return eligible(self.journal,payload)

    def requests(self):
        qualifications = [r for r in self.journal.records('observation') if
            r.data['payload'].get('category')=='observation_qualification' and self.evidence_eligible(r.data['payload'])]
        plans = {r.data['payload']['plan']['prediction_id']:r.data['payload']['plan']
            for r in self.journal.records('event') if r.data['payload'].get('category')=='offline_experiment_plan'}
        for identifier, project in self.executive.projects().items():
            if project['method']=='meditation-motion' and project['status'] in ('paused','blocked'):
                self.executive.retain_developmental_request(identifier)
            if project['method'] not in ('meditation-motion','evidence-review') or project['status'] not in ('paused','blocked') or not project['experiment_history']:
                continue
            outcome = project['experiment_history'][-1]
            if outcome['result'] not in ('unresolved','contradicted'):
                continue
            plan = plans[outcome['prediction_id']]
            if project['method']=='evidence-review' and plan.get('predicate')!='capture_horizon_supported':
                continue
            origins = {self.journal.get(i).data['payload'].get('source_episode') for i in plan['source_evidence']}
            matching = [r.id for r in qualifications if r.data['payload']['source_episode'] in origins]
            if matching and project['method']!='meditation-motion':
                self.executive.retain_evidence_request(identifier,self.journal,matching)

    def operational_feedback(self):
        """Reconcile guarded offline deployment and subsequent existing-brain use.

        Validation streams are reused diagnostics, explicitly not fresh final or
        physical experience. Outcomes return to the same Executive notebook.
        """
        from .deployment import CapabilityDeployment
        from .meditation import shadow, world_from_frame, motion_error
        from experiments.ppal.forebrain import Forebrain
        from experiments.ppal.hindbrain import Hindbrain
        deployment = CapabilityDeployment(self.journal)
        for row in self.journal.records('event'):
            p = row.data['payload']
            if p.get('category')!='model_deployment_proposal' or p.get('target')!='offline-shadow' or not p.get('eligible'):
                continue
            measured = self.journal.get(p['evaluation_id']).data['payload']
            candidate = measured.get('candidate',{})
            if candidate.get('spec',{}).get('adapter')!='meditation-motion-v1':
                continue
            resolution = self.journal.resolution_for(p.get('prediction_id'))
            if not resolution or resolution.data['payload']['result']!='supported':
                continue
            if any(r.data['payload'].get('revoked_proposal')==row.id for r in self.journal.records('event')):
                continue
            applied = [r for r in self.journal.records('event') if r.data['payload'].get('category')=='capability_activation' and r.data['payload'].get('proposal_id')==row.id]
            if not applied:
                if not self.authority:
                    self.journal.append('event',dict(category='offline_authorization_request',proposal_id=row.id,
                        target='offline-shadow',physical_authorization=False),episode=row.data['episode'],
                        sources=[row.id],producer='independent-deployment-boundary',version='normal-lifecycle-v1')
                    continue
                if self.authority.get('target')!='offline-shadow' or self.authority.get('execution')!='offline' or not self.authority.get('source'):
                    raise ValueError('external offline-only authority required')
                self._phase('evaluating')
                s = shadow(self.journal,row.id)
                deployment.activate(row.id,target='offline-shadow',shadow_id=s.id,
                    authorization=dict(self.authority,proposal_id=row.id))
            previous = [r for r in self.journal.records('observation') if r.data['payload'].get('category')=='offline_operational_outcome' and r.data['payload'].get('proposal_id')==row.id]
            if previous:
                self.executive.receive_operational_outcome(previous[0].id)
                metric=previous[0].data['payload']['metrics']
                active=deployment.active('offline-shadow')
                if active and active.get('proposal_id')==row.id and metric['candidate']>=metric['baseline'] and self.authority:
                    deployment.rollback('offline-shadow',reason='Subsequent offline diagnostic failed frozen baseline; retain finding',
                        authorization=self.authority,to_baseline=True)
                continue
            active = deployment.active('offline-shadow')
            if not active or active.get('proposal_id')!=row.id:
                continue  # Never re-activate an older proposal after a newer one.
            corpus = self.journal.get(candidate['dataset_digest']).data['payload']['corpus']
            episodes = [e for e in corpus['episodes'] if e['partition']=='validation']
            decisions = []
            for episode in episodes:
                adapter = deployment.planning_adapter()
                f,h,bf,bh = Forebrain(),Hindbrain(),Forebrain(),Hindbrain()
                for frame in episode['frames']:
                    if sha(frame['artifact']['path'])!=frame['artifact']['sha256']:
                        raise ValueError('operational input artifact changed')
                    world = world_from_frame(frame)
                    intent, action = adapter.decide(world,frame['timestamp'],f,h)
                    bi, ba = bh.decide(world,bf.update(world))
                    decisions.append(dict(timestamp=frame['timestamp'],source_episode=episode['source_episode'],
                        artifact_sha256=frame['artifact']['sha256'],action=asdict(action),baseline_action=asdict(ba),
                        intent=asdict(intent),baseline_intent=asdict(bi)))
            metric = motion_error(candidate['spec'],episodes)
            observation = self.journal.append('observation',dict(category='offline_operational_outcome',
                proposal_id=row.id,prediction_id=p['prediction_id'],activation_key=active['activation_key'],
                decisions=decisions,changed_decisions=sum(d['action']!=d['baseline_action'] for d in decisions),
                metrics=metric,evidence_use='reused validation diagnostic',controller_writes=0,
                physical_score_improvement='UNKNOWN'),episode=row.data['episode'],sources=[row.id,resolution.id],
                producer='existing-planner-offline-outcome',version='normal-lifecycle-v1',provenance=self.provenance)
            self.executive.receive_operational_outcome(observation.id)
            if metric['candidate']>=metric['baseline'] and self.authority:
                deployment.rollback('offline-shadow',reason='Subsequent offline diagnostic failed frozen baseline; retain finding',
                    authorization=self.authority,to_baseline=True)

    def yield_for_primary(self):
        from .cycle import gameplay_active
        if gameplay_active():
            raise InterruptedError('primary gameplay owns time-critical resources; checkpoint learning')

    def turn(self):
        return self.executive.develop(self)

    def close(self):
        self.last_activity=self.phase
        self._phase('stopped')
        self.journal.close()
        self.lock.close()


def run(output, roots, *, budget_seconds=10., interval=5., turns=None, offline_authority=None, history_roots=()):
    """Application-owned worker; bounded polling delegates all decisions to Executive."""
    import signal
    if not .05 <= interval <= 300 or (turns is not None and turns<1):
        raise ValueError('bounded cadence and positive turns required')
    import os
    os.nice(10)  # Vision/control retain host CPU priority.
    stopped = False
    def stop(*unused):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    lifecycle = DevelopmentLifecycle(output,roots,budget_seconds=budget_seconds,offline_authority=offline_authority,history_roots=history_roots)
    try:
        count=0
        while not stopped and (turns is None or count<turns):
            try:
                lifecycle.turn()
            except Exception as exc:
                lifecycle.phase='blocked'
                lifecycle._status(error=type(exc).__name__+': '+str(exc))
                if turns is not None:
                    raise
            count+=1
            deadline=time.monotonic()+interval
            while not stopped and (turns is None or count<turns) and time.monotonic()<deadline:
                time.sleep(min(.1,max(0,deadline-time.monotonic())))
    finally:
        lifecycle.close()
