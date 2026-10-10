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
from .resources import ResourceUnavailable


class MeditationYield(Exception):
    """Expected cooperative resource interruption; never a completed finding."""


class DevelopmentLifecycle:
    def __init__(self, output, roots, *, budget_seconds=10., offline_authority=None, history_roots=(), resources=None):
        from .resources import ResourceGuard
        self.resources=ResourceGuard(resources)
        self._stage_cache={}
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
        self.reflection_dependency_blocked = False
        self.reflection_dependency = None
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
        activity=getattr(self,'current_activity',{}) or {}
        question=current['goal'] if current else None
        if self.phase=='reflecting' and activity.get('kind')=='meditation':
            current=None  # A retained agenda is not this context's commission.
            context=self.journal.get(activity['context_id']).data['payload']['context']
            question=next((q['question'] for q in context.get('questions',[]) if q.get('question')),None)
        activity_description=('Meditation '+activity['context_id']+' for '+activity['source_episode']
            if self.phase=='reflecting' and activity.get('kind')=='meditation' else None)
        outcome=getattr(self,'last_turn',{})
        work=self.executive.work_states()
        satisfied={r.data['payload']['request_id'] for r in rows if r.data['payload'].get('category')=='acquisition_dependency_satisfied'}
        summary=(self.phase,activity_description or question,self.error,outcome.get('reason'))
        if summary!=getattr(self,'last_summary',None):
            print('Development:',self.phase,'|',summary[1] or 'no project','|',self.error or outcome.get('reason',''),flush=True)
            self.last_summary=summary
        from .episode_identity import current_conflicts
        atomic_json(self.output/'development-status.json', dict(schema='charlie-development-status-v1',
            phase=self.phase, last_activity=getattr(self,'last_activity',self.phase), current_project=current['id'] if current else None,
            current_question=question,activity_description=activity_description,
            projects={k:dict(goal=v['goal'],status=v['status'],progress=v.get('progress',{}),next_direction=v.get('next_direction')) for k,v in projects.items()},
            latest_findings=[dict(id=r.id,**r.data['payload']) for r in findings[-3:]],
            rejected_preserved_findings=[dict(id=r.id,**r.data['payload']) for r in rows
                if r.data['payload'].get('category')=='preserved_meditation_rejection'],
            latest_operational_outcome=next((dict(id=r.id,metrics=r.data['payload']['metrics'],changed_decisions=r.data['payload']['changed_decisions'])
                for r in reversed(rows) if r.data['payload'].get('category')=='offline_operational_outcome'),None),
            developmental_work=self.executive.work_states(),turn_outcome=getattr(self,'last_turn',None),
            current_activity=getattr(self,'current_activity',None),
            evidence_requests=requests+[r.data['payload'] for r in rows if r.data['payload'].get('category')=='learning_evidence_request'
                and r.id not in satisfied and work.get(r.data['payload'].get('work_id'),{}).get('status')!='completed'], identity_conflicts=current_conflicts(self.journal), activation=active,
            physical_authorization=False, physical_score_improvement='UNKNOWN', error=self.error,
            provenance=self.provenance,
            resources=self.resources.sample,
            analytical_progress=[dict(context_id=p.parent.name,**self.meditation_stages(p))
                for p in sorted((self.output/'meditations').glob('**/checkpoint.json'))],
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
        roots=list(self.roots)
        # A marathon relinquishes primary resources and hands evidence to this
        # same owner. It never starts a competing Executive in an owned notebook.
        for handoff_path in sorted((self.output/'marathon-handoffs').glob('*.json')):
            handoff=json.loads(handoff_path.read_text())
            if (handoff.get('schema')!='charlie-marathon-handoff-v1'
                    or handoff.get('physical_authorization') is not False
                    or handoff_path.stem!=digest(handoff)):
                raise ValueError('invalid marathon acquisition handoff')
            roots.extend(Path(p).resolve() for p in handoff['episodes'])
            prior=self.journal.category_records('event','marathon_history_acquired')
            if any(r.data['payload']['handoff_id']==handoff_path.stem for r in prior):continue
            source=EvidenceJournal(handoff['project_evidence'],read_only=True)
            try:
                for identifier in handoff['retained_project_ids']:source.get(identifier)
                self.journal.merge_from(source)
            finally:source.close()
            self.journal.append('event',dict(category='marathon_history_acquired',
                handoff_id=handoff_path.stem,session=handoff['session'],
                retained_project_ids=handoff['retained_project_ids'],
                interpretation='original project history; no additional gameplay or authority'),
                episode=SCOPE,producer='existing-evidence-consolidation',version='normal-lifecycle-v1')
            changed=True
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
        for root in discover_episodes(roots):
            before = len(self.journal.records())
            identity=maintain_episode_identity(root,self.journal)
            if identity['status']!='verified':
                changed |= len(self.journal.records()) != before
                continue
            ingest_episode(root, self.dataset, self.gateway)
            qualification(self.journal, audit(root,identity=identity))
            changed |= len(self.journal.records()) != before
        self.available_tracks = verified_tracks(self.journal)
        # Existing content-addressed acquisition inbox. Location receipts keep
        # old evidence IDs; these bytes cannot become another experience.
        locations=self.dataset.locate_artifacts(self.output/'pixels',partial=True)
        from .acquisition import satisfy_artifact_requests
        fulfilled=satisfy_artifact_requests(self.dataset)
        changed |= bool(locations or fulfilled)
        # Independent acquisition owners deliver hash-bound qualifications here.
        # This adapter validates them; it never generates labels or authority.
        inbox = self.output/'acquisition-inbox'
        for path in sorted(inbox.glob('*.json')):
            key = sha(path)
            from .acquisition import qualification_inputs
            inputs=qualification_inputs(path,self.journal)
            imported = [r for r in self.journal.records('event') if
                r.data['payload'].get('sha256')==key and
                (r.data['payload'].get('category')=='acquisition_delivery' or
                 r.data['payload'].get('category')=='acquisition_delivery_rejected' and
                 r.data['payload'].get('qualification_inputs')==inputs)]
            if imported:
                continue
            try:
                record = qualify_corpus(self.dataset, path)
            except (ValueError,OSError,TypeError,AttributeError,KeyError) as exc:
                self.journal.append('event',dict(category='acquisition_delivery_rejected',sha256=key,
                    reason=str(exc),qualification_inputs=inputs),episode=SCOPE,producer='existing-acquisition-capability',version='normal-lifecycle-v1')
                continue
            self.journal.append('event', dict(category='acquisition_delivery',sha256=key,record_id=record.id),
                episode=SCOPE, sources=[record.id],producer='existing-acquisition-capability',version='normal-lifecycle-v1')
            changed = True
        self.acquisition_roots=roots
        changed |= bool(self.respond_to_requests())
        return changed

    def respond_to_requests(self):
        """Report this turn's source discovery for newly retained dependencies."""
        from .acquisition import investigate_requests
        return investigate_requests(self.dataset,getattr(self,'acquisition_roots',self.roots),
            provenance=self.provenance)

    def reflect_experience(self, context_id, commission_id):
        """Executive-commissioned existing track meditation, checkpointed by iteration."""
        from experiments.ppal.meditate_robotron import meditate, quality
        from .meditation import acquire_preserved
        context = self.journal.get(context_id).data['payload']
        episode = context['source_episode']
        marker = next((r.data['payload'] for r in self.journal.records('event') if
            r.data['payload'].get('category')=='retrospective_ingestion' and r.data['payload']['context_id']==context_id), None)
        source = self.available_tracks.get(episode)
        result_path=self.output/'meditations'/context_id/'result.json'
        if result_path.exists() and json.loads(result_path.read_text()).get('status')=='unavailable' and source is not None and source.is_file():
            result_path=result_path.parent/sha(source)/'result.json'
        checkpoint=result_path.parent/'checkpoint.json'
        original_checkpoint=self.output/'meditations'/context_id/'checkpoint.json'
        if result_path.parent!=original_checkpoint.parent and original_checkpoint.is_file():
            # A recovered source resumes retained work, even if an older
            # unavailable-result receipt was published during interruption.
            checkpoint=original_checkpoint
        result_path.parent.mkdir(parents=True,exist_ok=True)
        if result_path.exists():
            result=json.loads(result_path.read_text())
        elif source is None or not source.exists():
            if checkpoint.is_file():
                saved=json.loads(checkpoint.read_text())
                if 'state_digest' in saved and saved['state_digest']!=digest({k:v for k,v in saved.items() if k!='state_digest'}):
                    raise ValueError('meditation checkpoint integrity mismatch')
                if saved.get('context_id',context_id)!=context_id or saved.get('commission_id',commission_id)!=commission_id:
                    raise ValueError('meditation checkpoint commission mismatch')
                expected=context.get('inventory',{}).get('tracks.json')
                if expected and saved['source_sha256']!=expected:
                    raise ValueError('meditation checkpoint source mismatch')
                from .acquisition import retain_dependency_request
                missing=dict(type='preserved_tracks_artifact',source_episode=episode,
                    sha256=saved['source_sha256'],context_id=context_id,commission_id=commission_id)
                retain_dependency_request(self.journal,commission_id,work_id=context_id,
                    required_evidence=[missing],reason='Original tracks unavailable for retained checkpoint; qualify exact source before resumption')
                self.reflection_dependency_blocked=True
                self.reflection_dependency=missing
                return None  # Preserve the partial checkpoint; no invented result.
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
                except ResourceUnavailable as exc:
                    self._phase('waiting for resources')
                    raise MeditationYield(str(exc)) from exc
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
                atomic_json(checkpoint,document,compact=True)
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
        finding_validation=None
        if result['status']=='completed':
            finding,rejected=acquire_preserved(self.dataset,result_path,source_episode=episode,
                prior_use=marker['prior_use'] if marker else context.get('prior_use','diagnostic'),context_id=context_id)
            sources.append(finding.id if finding else rejected.id)
            finding_validation='accepted diagnostic' if finding else 'rejected; dependency retained'
        receipt=self.journal.append('observation',dict(category='normal_meditation_result',
            context_id=context_id,source_episode=episode,result_path=str(result_path),
            result_sha256=sha(result_path),status=result['status'],finding_validation=finding_validation),episode=SCOPE,sources=sources,
            producer='Reflection',version='normal-lifecycle-v1',provenance=self.provenance)
        if result['status']=='unavailable':
            from .acquisition import retain_dependency_request
            missing=dict(type='preserved_tracks_artifact',source_episode=episode,
                sha256=context.get('inventory',{}).get('tracks.json'),context_id=context_id,commission_id=commission_id)
            retain_dependency_request(self.journal,receipt.id,work_id=context_id,
                required_evidence=[missing],reason='Original tracks unavailable; an availability receipt is not a completed investigation')
            self.reflection_dependency_blocked=True
            self.reflection_dependency=missing
            return None
        return receipt

    def meditation_files(self, context_id):
        base=self.output/'meditations'/context_id
        return sorted(base.glob('**/checkpoint.json'))

    def meditation_stages(self, path):
        """Measured computation, explicitly separate from qualified learning."""
        try:
            info=path.stat();key=(info.st_ino,info.st_size,info.st_mtime_ns)
            cached=self._stage_cache.get(path)
            if cached and cached[0]==key:return dict(cached[1])
            p=json.loads(path.read_text())
            if 'state_digest' in p and p['state_digest']!=digest({k:v for k,v in p.items() if k!='state_digest'}):
                raise ValueError('checkpoint integrity mismatch')
            history=p['history'];r=p.get('reconstruction',{})
        except (OSError,ValueError,KeyError,TypeError) as exc:
            return dict(checkpoint_available=False,reason=str(exc))
        result=dict(checkpoint_available=True,completed_iterations=len(history),completed_left_tracks=r.get('left',0),
            neighbor_cursor=r.get('neighbor',0),retained_plausible_links=len(r.get('candidates',[])),
            reconstructed_links=sum(h.get('merges',0) for h in history),
            interpretation='Computational progress only; reconstructed identities remain unverified')
        self._stage_cache[path]=(key,result)
        return dict(result)

    def meditation_progress(self, context_id):
        # Hash-bound computed content/cursors only; timestamps and heartbeat
        # files cannot provide evidence of intellectual progress.
        stages=[]
        for path in self.meditation_files(context_id):
            p=json.loads(path.read_text());r=p.get('reconstruction',{})
            stages.append(dict(source=p['source_sha256'],iterations=len(p['history']),
                tracks=digest(p['tracks']),left=r.get('left',0),neighbor=r.get('neighbor',0),
                candidates=len(r.get('candidates',[])),rebuilt=digest(r.get('rebuilt'))))
        return digest(stages)

    def meditation_dependency(self, context_id):
        context=self.journal.get(context_id).data['payload']
        source=self.available_tracks.get(context['source_episode'])
        from experiments.ppal import meditate_robotron
        from . import cycle,resources
        from dataclasses import asdict
        return digest(dict(source=sha(source) if source and source.is_file() else None,
            checkpoint=self.meditation_progress(context_id),budget=self.budget,
            implementation=sha(Path(meditate_robotron.__file__)),
            resource_implementation=sha(Path(resources.__file__)),ownership_implementation=sha(Path(cycle.__file__)),
            resource_budget=asdict(self.resources.policy)))

    def investigation_inputs(self):
        import importlib.util
        from .cycle import default_registry
        observations=[r.id for r in self.journal.records() if
            r.data['kind'] in ('observation','resolution') and
            r.data['payload'].get('category')!='consolidated_evidence_reference']
        identity=[r.id for r in self.journal.records('event') if r.data['payload'].get('category') in
            ('episode_identity_binding','episode_identity_alias','episode_identity_quarantine','episode_identity_location',
             'experience_artifact_location','acquisition_dependency_satisfied')]
        # Only retained unfinished work can wake on a computed checkpoint.
        # Heartbeats, waiting receipts and completed experiments never do.
        work=self.executive.work_states()
        checkpoints={p['prediction_id']:self.executive.experiment_progress(self.output/'models',p['prediction_id'])
            for row in self.journal.category_records('event','offline_experiment_plan')
            for p in [row.data['payload']['plan']]
            if work.get(p.get('project_id'),{}).get('status')=='blocked'}
        return digest(dict(observations=observations,identity=identity,torch=importlib.util.find_spec('torch') is not None,
            budget=self.budget,checkpoints=checkpoints,capabilities=default_registry().describe(),
            implementation=self.executive.execution_implementation()))

    def pending_work(self):
        contexts={r.id:r.data['payload'] for r in self.journal.category_records('observation','learning_context_reference')
            if r.data['payload'].get('source_episode')}
        results=[r.data['payload'] for r in self.journal.category_records('observation','normal_meditation_result')]
        completed_episodes={r['source_episode'] for r in results if r['status']=='completed'}
        unavailable={r['context_id'] for r in results if r['status']=='unavailable'}
        # Uncommissioned eligible contexts still need Executive attention. An
        # unavailable receipt bookmarks missing input, not a completed finding.
        if any(p['source_episode'] not in completed_episodes and self.evidence_eligible(p) and
                (i not in unavailable or p['source_episode'] in self.available_tracks) and
                self.executive.work_ready(i,self.meditation_dependency(i)) for i,p in contexts.items()):
            return True
        import importlib.util
        available={'model-diagnostics','meditation-motion','evidence-review'}
        if importlib.util.find_spec('torch') is not None:
            available|={'cnn-reconstruction','cnn-classification','cnn-validation-extension'}
        return self.executive.select(methods=available,
            resources={'offline-slot','RGB-examples','torch','model-evaluation','context-evidence','meditation-evidence'},
            authorized_methods=available,inspect=True)['project'] is not None

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

        # Expose precise infeasible portfolio gates through the same request
        # owner; repeats reuse the request even across restart.
        deferred=next((r for r in reversed(self.journal.records('event'))
            if r.data['payload'].get('op')=='portfolio_deferred'),None)
        if deferred:
            from .acquisition import retain_dependency_request
            for item in deferred.data['payload']['alternatives']:
                project=self.executive.projects()[item['project_id']]
                if project.get('developmental_bookmark'):continue
                missing=list(item['missing_resources'])+[str(x) for x in item['unmet_dependencies']]
                if not item['method_available']:missing.append('Available implementation/runtime for '+project['method'])
                if not item['authorized']:missing.append('Existing method execution authorization for '+project['method'])
                if project.get('hold'):missing.append(project.get('completion_rationale') or 'New independently qualified evidence for the retained investigation')
                if missing:retain_dependency_request(self.journal,deferred.id,work_id=project['id'],
                    required_evidence=missing,reason='Existing portfolio prerequisites are unavailable')

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
            active_policy=deployment.active('offline-shadow')
            policy_available=False
            if active_policy and active_policy.get('proposal_id')==row.id:
                try:
                    deployment.export_policy('offline-shadow',self.output/'ppal-policy.json')
                    from experiments.ppal.qualified_policy import load_policy
                    load_policy(self.output/'ppal-policy.json')
                    policy_available=True
                except ValueError as exc:
                    self.journal.append('event',dict(category='qualified_policy_export_blocked',proposal_id=row.id,
                        reason=str(exc),resumption='Independent runtime qualification for retained candidate; baseline retained'),
                        episode=row.data['episode'],sources=[row.id],producer='independent-deployment-boundary',version='ppal-policy-v1')
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
                from experiments.ppal.qualified_policy import load_policy
                policy=load_policy(self.output/'ppal-policy.json') if policy_available else None
                pf,ph = Forebrain(policy=policy),Hindbrain(policy=policy)
                adapter=deployment.planning_adapter()
                f,h,bf,bh = Forebrain(),Hindbrain(),Forebrain(),Hindbrain()
                for frame in episode['frames']:
                    if sha(frame['artifact']['path'])!=frame['artifact']['sha256']:
                        raise ValueError('operational input artifact changed')
                    world = world_from_frame(frame)
                    intent, action = adapter.decide(world,frame['timestamp'],f,h)
                    pi,pa=ph.decide(world,pf.update(world),timestamp=frame['timestamp'])
                    bi, ba = bh.decide(world,bf.update(world))
                    decisions.append(dict(timestamp=frame['timestamp'],source_episode=episode['source_episode'],
                        artifact_sha256=frame['artifact']['sha256'],action=asdict(action),baseline_action=asdict(ba),
                        qualified_policy_action=asdict(pa),qualified_policy_intent=asdict(pi),
                        policy_provenance=dict(forebrain=pf.last_reason,hindbrain=ph.last_decision),
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
        self.resources.check()

    def turn(self):
        from .resources import ResourceUnavailable
        try:self.resources.check(force=True)
        except (ResourceUnavailable,InterruptedError) as exc:
            self.last_turn=dict(progress_occurred=False,reason=str(exc),next_direction='Yield resources; retain existing work')
            self.current_activity=dict(kind='resource_wait',reason=str(exc))
            self._phase('waiting for resources' if isinstance(exc,ResourceUnavailable) else 'experiencing')
            return
        self.reflection_dependency_blocked=False
        self.reflection_dependency=None
        try:return self.executive.develop(self)
        except ResourceUnavailable as exc:
            # Existing worker supervision checkpoints/stops its child. The
            # committed plan remains owned by the Executive for resumption.
            self.last_turn=dict(progress_occurred=False,reason=str(exc),next_direction='Yield resources; resume retained work')
            self.current_activity=dict(kind='resource_wait',reason=str(exc))
            self._phase('waiting for resources')

    def close(self):
        self.last_activity=self.phase
        self._phase('stopped')
        self.journal.close()
        self.lock.close()


def run(output, roots, *, budget_seconds=10., interval=5., turns=None, offline_authority=None, history_roots=(), resources=None):
    """Application-owned worker; bounded polling delegates all decisions to Executive."""
    import signal
    if not .05 <= interval <= 300 or (turns is not None and turns<1):
        raise ValueError('bounded cadence and positive turns required')
    import os
    from .resources import DevelopmentResources
    resources=resources or DevelopmentResources()
    resources.apply()
    os.nice(10)  # Vision/control retain host CPU priority.
    stopped = False
    def stop(*unused):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    lifecycle = DevelopmentLifecycle(output,roots,budget_seconds=budget_seconds,offline_authority=offline_authority,history_roots=history_roots,resources=resources)
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
