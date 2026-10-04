"""Strategic project projection over the existing immutable evidence journal.

This is operational continuity, not a second knowledge store. Reflection owns
proposals, the existing Evaluator/chooser owns experiments, and selected project
conclusions pass through Experience/MemoryGateway like other interpretations.
No controller, code execution, authorization or real-time policy lives here.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import math

from .evidence import digest
from .former import Experience

SCOPE = 'learning-project-consolidation-v1'
VERSION = 'learning-projects-v1'
FINAL = {'completed', 'abandoned', 'superseded'}


def reflect_project_opportunities(journal, episode, hypotheses):
    """Lift typed evidence-backed hypotheses into reproducibility questions.

    The method adapter supplies measured expectations and available conditions,
    never a selected direction or next experiment. This deliberately small,
    rule-based Reflection policy generates no strategy or causal reward claims.
    """
    groups = {}
    for h in hypotheses:
        if not h.get('evidence_ids') or not h.get('conditions') or not h.get('observed_conditions'):
            continue
        if not isinstance(h.get('scope'), dict) or not all(isinstance(c, dict) for c in h['conditions']):
            raise ValueError('typed scope and conditions required')
        if any(any(k in h['scope'] and h['scope'][k] != v for k,v in c.items()) for c in h['conditions']):
            raise ValueError('conditions cannot change the project scope')
        revision = h.get('revision', '1')
        key = digest(dict(method=h['method'], scope=h['scope'], expected=h['expected'], revision=revision))
        group = groups.setdefault(key, dict(hypothesis=h, sources=[], observed=set()))
        group['sources'].extend(h['evidence_ids'])
        group['observed'].update(digest(c) for c in h['observed_conditions'])
    proposals = []
    for group in groups.values():
        h = group['hypothesis']; sources = list(dict.fromkeys(group['sources']))
        uncertainty = 1 - min(1., len(group['observed']) / len(h['conditions']))
        proposal = dict(originator='Reflection', method=h['method'], scope=h['scope'], expected=h['expected'],
            revision=h.get('revision', '1'),
            goal=f"Measure whether {h['expected']} repeats across conditions for {h['scope']}",
            motivation='Reduce uncertainty in an observed relationship before relying on it in later decisions; no performance benefit inferred',
            open_questions=['Does the measured relationship persist in new episodes and conditions?',
                            'Which unexamined conditions or interpretations remain?'],
            requires=h.get('requires', []), dependencies=h.get('dependencies', []),
            established_objective=h.get('established_objective'),
            objective_contribution=.5, learning_value=uncertainty, uncertainty=uncertainty, cost=.5, risk=.5,
            priority_provenance='declared generic reproducibility policy; uncovered-condition fraction, not learned score utility',
            tactical_hypothesis_evidence=sources,
            conditions=[dict(h['scope'], **c) for c in h['conditions']],
            observed_conditions=len(group['observed']), available_conditions=len(h['conditions']))
        record = journal.append('event', dict(category='learning_project_proposal', proposal=proposal),
            episode=episode, sources=sources, producer='Reflection', version=VERSION)
        proposals.append(dict(proposal=proposal, evidence_id=record.id))
    return proposals


@dataclass(frozen=True)
class CompletionCriteria:
    min_resolved: int = 3
    min_episodes: int = 2
    min_conditions: int = 2
    support_fraction: float = .8
    max_attempts: int = 8
    stagnation_window: int = 3

    def __post_init__(self):
        if (any(type(x) is not int or x < 1 for x in
                (self.min_resolved, self.min_episodes, self.min_conditions,
                 self.max_attempts, self.stagnation_window))
                or self.min_resolved < 2 or self.min_episodes < 2
                or self.max_attempts < self.min_resolved
                or not math.isfinite(self.support_fraction)
                or not 0 < self.support_fraction <= 1):
            raise ValueError('invalid cumulative completion criteria')


class LearningExecutive:
    def __init__(self, journal, gateway):
        self.journal, self.gateway = journal, gateway
        self.consolidate()

    def _remember_conclusion(self, event, project):
        p = event.data['payload']
        if p['op'] == 'assessment':
            changes = p['changes']
            if changes.get('status') != 'completed':
                return
            disposition = changes['disposition']
            summary = f"Learning project {project['id']}: {disposition}. {changes['completion_rationale']}"
            outcome = str(changes['progress']); source = 'learning-project:assessment'
            tags = ('learning-project', disposition, 'diagnostic')
        elif p['op'] == 'lifecycle' and p['status'] in FINAL:
            summary = f"Learning project {project['id']}: {p['status']}. {p['reason']}"
            outcome = 'Unresolved questions retained; no newly established semantic facts'
            source = 'learning-project:lifecycle'; tags = ('learning-project', p['status'], 'interpretation')
        else:
            return
        self.gateway.remember(Experience(kind='outcome', source=source, summary=summary,
            goal=project['goal'], outcome=outcome, subject=project['id'], significant=True,
            evidence=f'{self.journal.path.resolve()}#{event.id}', tags=tags))

    def consolidate(self):
        """Recover a crash between durable assessment and existing outbox handoff.

        MemoryEvaluator's existing evidence identity handles deduplication;
        there is no additional queue or memory lifecycle here.
        """
        projects = self.projects()
        for identifier, project in projects.items():
            if (project['status'] not in FINAL
                    and len(project['experiment_history']) != project.get('progress', {}).get('attempts', 0)):
                self.assess(identifier)
        projects = self.projects()
        for record in self.journal.records('event'):
            p = record.data['payload']
            if record.data['episode'] == SCOPE and p.get('project_id') in projects:
                self._remember_conclusion(record, projects[p['project_id']])

    def _event(self, payload, sources=()):
        return self.journal.append('event', payload, episode=SCOPE,
                                   sources=sources, producer='LearningExecutive', version=VERSION)

    def _reference(self, journal, identifier):
        record = journal.get(identifier)
        return self.journal.append('observation', dict(category='consolidated_evidence_reference',
            journal=str(journal.path.resolve()), record_id=record.id,
            source_episode=record.data['episode'], source_kind=record.data['kind']),
            episode=SCOPE, producer='existing-evidence-consolidation', version=VERSION)

    def projects(self):
        """Rebuild operational state; no mutable snapshot is authoritative."""
        projects = {}
        for record in self.journal.records('event'):
            if record.data['episode'] != SCOPE:
                continue
            p = record.data['payload']; op = p.get('op')
            if op == 'proposed':
                projects[p['project']['id']] = p['project']
            elif op == 'evidence_added':
                project = projects[p['project_id']]
                project['origins'].extend(p['origins'])
                project['hypothesis_evidence'].extend(p['hypothesis_evidence'])
                project['tactical_hypothesis_evidence'] = list(dict.fromkeys(
                    project.get('tactical_hypothesis_evidence', []) + p['tactical_hypothesis_evidence']))
            elif op == 'selected':
                for identifier, project in projects.items():
                    if project['status'] == 'active' and identifier != p['project_id']:
                        project['status'] = 'paused'
                        project['next_direction'] = 'resume after interruption'
                        project['interrupted_by'] = p['project_id']
                    if identifier in p.get('interrupted_projects', []):
                        project['interrupted_by'] = p['project_id']
                project = projects[p['project_id']]
                project.update(status='active', selection=p)
                project.pop('interrupted_by', None)
            elif op == 'outcome':
                projects[p['project_id']]['experiment_history'].append(p['outcome'])
            elif op == 'assessment':
                projects[p['project_id']].update(p['changes'])
            elif op == 'lifecycle':
                projects[p['project_id']].update(status=p['status'],
                    completion_rationale=p['reason'], lifecycle_evidence=p['evidence'],
                    hold=p['status'] in ('blocked', 'paused'))
            elif op == 'operational_feedback':
                projects[p['project_id']].update(next_direction=p['next_direction'],
                    operational_outcome=p['outcome_id'])
            elif op == 'evidence_continuation':
                projects[p['project_id']]['developmental_bookmark'] = dict(p, evidence_id=record.id)
        return projects

    def propose(self, proposal, source_journal, source_ids, *, criteria=None):
        """Accept typed Reflection output with preserved origin, never remote prose.

        Priority terms are explicit generic policy inputs, not learned utility or
        permission. The current producer derives them from observation counts.
        """
        if (proposal.get('originator') != 'Reflection' or not source_ids
                or not all(proposal.get(k) for k in
                           ('goal', 'motivation', 'scope', 'expected', 'method', 'open_questions'))):
            raise ValueError('evidence-backed Reflection proposal required')
        rows = [source_journal.get(i) for i in source_ids]
        if any(r.data['producer'] != 'Reflection'
               or r.data['payload'].get('category') != 'learning_project_proposal'
               or r.data['payload'].get('proposal') != proposal for r in rows):
            raise ValueError('project must match the preserved Reflection proposal exactly')
        for key in ('objective_contribution', 'learning_value', 'uncertainty', 'cost', 'risk'):
            value = proposal.get(key, .5)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError('portfolio terms must be finite 0..1')
        criteria = criteria or CompletionCriteria()
        identifier = digest(dict(method=proposal['method'], scope=proposal['scope'],
                                 expected=proposal['expected'], revision=proposal.get('revision', '1'), version=VERSION))
        existing = self.projects().get(identifier)
        old = set(existing['hypothesis_evidence']) if existing else set()
        fresh = [r for r in rows if r.id not in old]
        if not fresh:
            return identifier
        refs = [self._reference(source_journal, r.id) for r in fresh]
        origins = [dict(evidence_id=r.id, journal=str(source_journal.path.resolve()),
                        episode=r.data['episode']) for r in fresh]
        if existing:
            self._event(dict(op='evidence_added', project_id=identifier, origins=origins,
                             hypothesis_evidence=[r.id for r in fresh],
                             tactical_hypothesis_evidence=proposal.get('tactical_hypothesis_evidence', [])), [r.id for r in refs])
        else:
            project = dict(proposal, id=identifier, status='candidate', origins=origins,
                hypothesis_evidence=[r.id for r in fresh], success_criteria=asdict(criteria),
                experiment_history=[], current_understanding='tentative; no confirmed physical identity or causal score claim',
                progress={}, next_direction='ask existing chooser for a scoped experiment',
                completion_rationale=None)
            self._event(dict(op='proposed', project=project), [r.id for r in refs])
        return identifier

    def assess(self, project_id):
        project = self.projects()[project_id]
        if project['status'] in FINAL:
            return project
        history = project['experiment_history']; c = project['success_criteria']
        resolved = [h for h in history if h['result'] != 'unresolved']
        # Offline architecture variants sharing a held-out evidence group are
        # correlated trials; they cannot supply independent replication.
        offline = [h for h in resolved if h.get('experiment_kind') == 'offline']
        physical = [h for h in resolved if h.get('experiment_kind', 'physical') == 'physical']
        units=[]
        for h in offline:
            group=set(h.get('evidence_groups') or [h.get('independence_unit',h['episode'])])
            overlaps=[existing for existing in units if existing & group]
            for existing in overlaps:
                group.update(existing); units.remove(existing)
            units.append(group)
        effective_resolved = len(physical) + len(units)
        counts = Counter(h['result'] for h in history)
        episodes = {h['episode'] for h in physical} | {digest(sorted(unit)) for unit in units}
        conditions = {digest(h['condition']) for h in resolved}
        fraction = counts['supported'] / len(resolved) if resolved else None
        progress = dict(attempts=len(history), resolved=len(resolved), results=dict(counts),
                        episodes=len(episodes), conditions=len(conditions), support_fraction=fraction,
                        independent_physical_episodes=len({h['episode'] for h in physical}),
                        offline_trials=len(offline), independent_offline_evidence_units=len(units))
        status = project['status']; rationale = None; disposition = None
        # A single success/failure is never project completion.
        if (effective_resolved >= c['min_resolved'] and len(episodes) >= c['min_episodes']
                and len(conditions) >= c['min_conditions'] and fraction >= c['support_fraction']):
            status, disposition = 'completed', 'achieved'
            rationale = 'Cumulative diagnostic replication criterion met across episodes and conditions; not a causal score or SELF certification'
        elif len(resolved) >= max(c['min_resolved'], c['stagnation_window'] + 1):
            keys = [(digest(h['condition']), h['result']) for h in resolved]
            earlier = set(keys[:-c['stagnation_window']])
            available = {digest(condition) for condition in project.get('conditions', [])}
            if available and available <= conditions and all(k in earlier for k in keys[-c['stagnation_window']:]):
                status, disposition = 'completed', 'sufficiently_explored'
                rationale = 'Recent resolved experiments repeated existing distinctions without new evidence; further value is limited under this policy'
        if status != 'completed' and len(history) >= c['max_attempts']:
            status, disposition = 'paused', 'budget_exhausted'
            rationale = 'Declared attempt budget exhausted; objective not established, unresolved questions retained'
        changes = dict(progress=progress, status=status, completion_rationale=rationale,
            disposition=disposition, current_understanding=f'Diagnostic outcomes {dict(counts)}; provisional identity and score causation remain unresolved',
            next_direction='retain open questions for reconsideration' if rationale else 'continue scoped evidence collection')
        event = self._event(dict(op='assessment', project_id=project_id, changes=changes))
        if status == 'completed':
            self._remember_conclusion(event, project)
        return self.projects()[project_id]

    def record_result(self, project_id, plan, resolution, source_journal, *, episode):
        project = self.projects()[project_id]
        if plan.get('project_id') != project_id:
            raise ValueError('experiment belongs to a different project')
        record = source_journal.get(resolution['resolution_id'])
        payload = record.data['payload']
        if (record.data['kind'] != 'resolution' or payload['prediction_id'] != plan['prediction_id']
                or payload['result'] != resolution['result']):
            raise ValueError('actual prediction resolution required')
        if resolution['result'] != 'unresolved' and not any(
                source_journal.get(i).data['payload'].get('ee_episode') == episode
                for i in record.data['sources']):
            raise ValueError('resolved outcome must identify its actual episode')
        if any(h['prediction_id'] == plan['prediction_id'] for h in project['experiment_history']):
            return project
        ref = self._reference(source_journal, record.id)
        condition = plan.get('condition')
        if condition is None:
            condition = dict(body=plan['body'], fire=plan['fire'])
        if plan.get('expected') != project['expected'] or any(
                condition.get(k) != v for k, v in project['scope'].items()):
            raise ValueError('experiment escaped project question')
        outcome = dict(prediction_id=plan['prediction_id'], resolution_id=record.id,
            episode=episode, condition=condition,
            result=resolution['result'], reason=resolution['reason'], memory_id=plan['memory_id'],
            experiment_kind=plan.get('experiment_kind','physical'),
            independence_unit=plan.get('independence_unit',episode), dataset_id=plan.get('dataset_id'),
            evidence_groups=plan.get('evidence_groups',[]))
        self._event(dict(op='outcome', project_id=project_id, outcome=outcome), (ref.id,))
        return self.assess(project_id)

    def transition(self, project_id, status, reason, source_journal, source_ids):
        """Explicit evidence-backed interruption, supersession or abandonment.

        External readiness/authorization remains authoritative. This function
        records an interpretation; it cannot supply unavailable resources.
        """
        project = self.projects()[project_id]
        if status not in ('paused', 'blocked', 'candidate', 'abandoned', 'superseded') or not reason or not source_ids:
            raise ValueError('explicit lifecycle reason and evidence required')
        if project['status'] in FINAL:
            raise ValueError('closed project needs a new versioned proposal')
        refs = [self._reference(source_journal, i) for i in source_ids]
        event = self._event(dict(op='lifecycle', project_id=project_id, status=status,
                         reason=reason, evidence=list(source_ids)), [r.id for r in refs])
        if status in FINAL:
            self._remember_conclusion(event, project)

    def select(self, *, methods, resources, authorized_methods, urgent_projects=()):
        """Sticky portfolio selection; explicit prerequisites can interrupt it.

        Urgency must refer to previously recorded, evidence-backed projects. It
        does not authorize their method. Paused budgets need explicit renewal.
        """
        projects = self.projects(); alternatives = []
        for p in projects.values():
            if p['status'] in FINAL or p.get('disposition') == 'budget_exhausted':
                continue
            missing = sorted(set(p.get('requires', [])) - set(resources))
            unmet = [d for d in p.get('dependencies', [])
                     if projects.get(d, {}).get('disposition') != 'achieved']
            blocked = (missing or unmet or p['method'] not in methods
                       or p['method'] not in authorized_methods or p.get('hold', False))
            resolved = p.get('progress', {}).get('resolved', 0)
            terms = dict(objective_contribution=p.get('objective_contribution', .5),
                learning_value=p.get('learning_value', .5),
                remaining_uncertainty=p.get('uncertainty', .5)/(1+resolved),
                cost=p.get('cost', .5), risk=p.get('risk', .5))
            score = (terms['objective_contribution'] + terms['learning_value']
                     + terms['remaining_uncertainty'] - terms['cost'] - terms['risk'])
            alternatives.append(dict(project_id=p['id'], score=score, blocked=bool(blocked),
                terms=terms, opportunity_cost='foregone eligible alternatives shown in this selection',
                missing_resources=missing, unmet_dependencies=unmet,
                method_available=p['method'] in methods, authorized=p['method'] in authorized_methods,
                urgent=p['id'] in urgent_projects, status=p['status']))
            if blocked and p['status'] == 'active':
                self._event(dict(op='assessment', project_id=p['id'], changes=dict(status='blocked',
                    next_direction='await prerequisite; preserve hypotheses and history',
                    completion_rationale=f'Unavailable prerequisite: {alternatives[-1]}')))
        eligible = [a for a in alternatives if not a['blocked']]
        if not eligible:
            self._event(dict(op='portfolio_deferred', alternatives=alternatives,
                             reason='no feasible authorized project'))
            return dict(project=None, alternatives=alternatives, reason='no feasible authorized project; no justified experiment yet')
        urgent = [a for a in eligible if a['urgent']]
        active = [a for a in eligible if a['status'] == 'active']
        # Resuming an interrupted undertaking precedes starting a fresh one.
        resume = [a for a in eligible if projects[a['project_id']].get('interrupted_by')
                  and projects.get(projects[a['project_id']]['interrupted_by'], {}).get('status') in FINAL]
        chosen = max(urgent or active or resume or eligible, key=lambda a: (a['score'], a['project_id']))
        reason = ('evidenced interruption' if urgent else 'continue active project' if active
                  else 'resume interrupted project' if resume else 'generic value/uncertainty minus cost/risk policy')
        interrupted = [p['id'] for p in projects.values()
                       if p['status'] == 'active' and p['id'] != chosen['project_id']]
        self._event(dict(op='selected', project_id=chosen['project_id'], alternatives=alternatives,
                         interrupted_projects=interrupted, reason=reason))
        return dict(project=self.projects()[chosen['project_id']], alternatives=alternatives, reason=reason)

    def chooser_context(self, project_id):
        project = self.projects()[project_id]
        if project['status'] != 'active':
            raise ValueError('only an active project can delegate')
        return dict(project_id=project_id, objective=project['goal'], method=project['method'],
                    scope=project['scope'], expected=project['expected'],
                    criteria=project['success_criteria'],
                    evidence_notebook=str(self.journal.path.resolve()),
                    established_objective=project.get('established_objective'),
                    experiment_history=project['experiment_history'],
                    hypothesis_evidence=project.get('tactical_hypothesis_evidence', []))

    def commission(self, plan, source_journal):
        """Executive-owned durable bookmark and offline meditation dispatch.

        Discovery reports evidence; only a selected project can commission it.
        This records authority over investigation, never physical authority.
        """
        project = self.projects()[plan['project_id']]
        committed = [r.data['payload']['plan'] for r in source_journal.records('event')
                     if r.data['payload'].get('category') == 'offline_experiment_plan'
                     and r.data['payload']['plan']['prediction_id'] == plan['prediction_id']]
        if committed != [plan] or project['status'] != 'active' or plan['method'] != project['method']:
            raise ValueError('selected project and exact committed plan required')
        refs = [self._reference(source_journal, i) for i in plan['source_evidence']]
        bookmark = self._event(dict(op='investigation_bookmark', project_id=project['id'],
            prediction_id=plan['prediction_id'], question=project['goal'],
            evidence=list(plan['source_evidence']), method=plan['method'],
            physical_authorization=False), [r.id for r in refs])
        dispatch = self._event(dict(op='meditation_dispatch', project_id=project['id'],
            prediction_id=plan['prediction_id'], bookmark_id=bookmark.id,
            method=plan['method'], execution='offline'), [bookmark.id])
        return dict(bookmark_id=bookmark.id, dispatch_id=dispatch.id)

    def retain_evidence_request(self, project_id, source_journal, qualification_ids):
        """Bookmark the existing unresolved investigation at the hardware boundary.

        The request reports measured acquisition gaps, never authorizes a game
        or declares a candidate ready for deployment. Retry/reboot reuses it.
        """
        project = self.projects()[project_id]
        if (project['method'] not in ('meditation-motion','evidence-review')
                or project['status'] not in ('paused','blocked') or not project['experiment_history']):
            raise ValueError('existing paused investigation required')
        outcome = project['experiment_history'][-1]
        if outcome['result'] not in ('unresolved','contradicted'):
            raise ValueError('missing-evidence outcome required')
        qualification = []
        for identifier in qualification_ids:
            p = source_journal.get(identifier).data['payload']
            if p.get('category')!='observation_qualification':
                raise ValueError('actual observation qualification required')
            qualification.append(p)
        if not qualification:
            raise ValueError('qualification evidence required')
        # Require overlap with the investigation rather than attaching an
        # unrelated report or another candidate's gaps to this bookmark.
        plan = next(r.data['payload']['plan'] for r in source_journal.records('event')
            if r.data['payload'].get('category')=='offline_experiment_plan'
            and r.data['payload']['plan']['prediction_id']==outcome['prediction_id'])
        origins = {source_journal.get(i).data['payload'].get('source_episode') for i in plan['source_evidence']}
        if not origins.intersection(p['source_episode'] for p in qualification):
            raise ValueError('qualification must address this investigation evidence')
        needed = sorted({item for p in qualification for item in p['report']['required_new_evidence']})
        refs = [self._reference(source_journal,i) for i in [outcome['resolution_id'],*qualification_ids]]
        event = self._event(dict(op='evidence_continuation',project_id=project_id,
            prediction_id=outcome['prediction_id'],resolution_id=outcome['resolution_id'],
            original_question=project['goal'],qualification_keys=sorted(p['qualification_key'] for p in qualification),
            status='READY_FOR_PLAY',request_kind='evidence_acquisition_only',
            candidate_admitted=False,physical_authorization=False,firmware_authorization=False,
            servo_authorization=False,required_evidence=needed,
            next_direction='Await separately authorized acquisition; resume this project only after new qualified evidence',
            rollback='Keep baseline; no candidate activation or final-test reuse'),[r.id for r in refs])
        return event

    def develop(self, lifecycle):
        """One normal-operation turn, owned by this Executive, no second scheduler.

        Acquisition discovers availability; Reflection originates proposals;
        existing selection/chooser commissions only justified bounded work.
        """
        from learning.cycle import gameplay_active, investigate
        if lifecycle.executive is not self:
            raise ValueError('development adapter must use this Executive')
        if gameplay_active():
            lifecycle._phase('experiencing')
            return
        lifecycle._phase('reflecting')
        lifecycle.acquire()
        # The Executive chooses eligible new experience for bounded reflection.
        # A completed result is a durable checkpoint, not another experience.
        contexts=[r for r in self.journal.records('observation') if
            r.data['payload'].get('category')=='learning_context_reference' and r.data['payload'].get('source_episode')]
        results=[r.data['payload'] for r in self.journal.records('observation') if
            r.data['payload'].get('category')=='normal_meditation_result']
        completed_episodes={r['source_episode'] for r in results if r['status']=='completed'}
        unavailable={r['context_id'] for r in results if r['status']=='unavailable'}
        for context in contexts:
            episode=context.data['payload']['source_episode']
            if episode in completed_episodes or (context.id in unavailable and episode not in lifecycle.available_tracks):
                continue
            commission=self.journal.append('event',dict(category='reflection_commission',context_id=context.id,
                physical_authorization=False,reason='New preserved experience warrants bounded retrospective reflection'),
                episode=context.data['episode'],sources=[context.id],producer='LearningExecutive',version='normal-lifecycle-v1')
            lifecycle.reflect_experience(context.id,commission.id)
            break  # One bounded meditation per turn; existing portfolio gets time.
        # Held projects and identical imports cannot create new trials. Continue
        # any committed interruption before considering fresh opportunities.
        lifecycle._phase('investigating')
        report = investigate(lifecycle.dataset,lifecycle.gateway,executive=self,
            budget_seconds=lifecycle.budget,max_jobs=1,review_questions=True,
            diagnostics_only=False,on_progress=lifecycle.yield_for_primary)
        lifecycle.requests()
        lifecycle.operational_feedback()
        projects=self.projects()
        eligible=any(p['status'] in ('active','candidate') and not p.get('hold') for p in projects.values())
        lifecycle._phase('idle' if eligible or not projects else 'waiting for evidence')
        return report

    def receive_operational_outcome(self, identifier):
        """Durable diagnostic feedback, never credit offline motion as game score."""
        record=self.journal.get(identifier);payload=record.data['payload']
        if record.data['producer']!='existing-planner-offline-outcome' or payload.get('category')!='offline_operational_outcome' or payload.get('controller_writes')!=0:
            raise ValueError('actual offline planner outcome required')
        project=next((p for p in self.projects().values() if any(h['prediction_id']==payload['prediction_id'] for h in p['experiment_history'])),None)
        if not project:
            raise ValueError('operational outcome must belong to existing investigation')
        ref=self._reference(self.journal,identifier)
        event=self._event(dict(op='operational_feedback',project_id=project['id'],outcome_id=identifier,
            next_direction='Seek fresh task-outcome evidence; offline temporal accuracy does not establish score utility',
            physical_authorization=False),[ref.id])
        self.gateway.remember(Experience(kind='outcome',source='learning-project:operational-feedback',
            subject=project['id'],goal=project['goal'],summary='Offline activated candidate measured through existing planner',
            outcome=str(payload['metrics']),significant=True,evidence=event.id,tags=('offline','diagnostic','score-unknown')))
        return event
