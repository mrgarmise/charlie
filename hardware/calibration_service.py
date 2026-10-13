"""Permanent CAL-1 request adapter; never grants authority or owns a camera/PWM.

Requests are projections of Charlie's existing append-only EvidenceJournal.
Supervisors use the existing UART calibration state machine. Completion of a
session is evidence, not qualification, activation, or resolution of a request.
"""
import math
import time
import uuid
from pathlib import Path

from .neck_calibration import CalibrationJournal, ProfileRepository, SupervisedCalibration
from .neck_health import NeckHealth


class CalibrationService:
    EPISODE = 'neck-calibration-requests-v1'
    REASONS = {'missing', 'invalid', 'incompatible', 'quarantined', 'degraded', 'uncertain'}

    def __init__(self, controller, repository, journal, executive=None, *, clock=time.monotonic):
        self.controller, self.repository, self.journal = controller, repository, journal
        self.executive, self.clock = executive, clock
        self.health = None
        self.profile = None
        self.previous_pose = None
        self.last_poll = -math.inf
        self.session = None
        self.unobserved = 0
        self.brain = None
        # Recover a crash after committing a request but before Reflection.
        for request in self.requests().values():
            self._reflect_request(request['request_id'], self.journal.get(request['evidence_ids'][0]))
        self._sync_dispositions()

    @classmethod
    def open(cls, controller, directory):
        """Open durable Pi state only; reuse the caller's sole RP2040 link."""
        from memory.evidence import EvidenceJournal
        from memory.gateway import MemoryGateway
        from memory.learning_projects import LearningExecutive
        directory = Path(directory)
        journal = EvidenceJournal(directory / 'requests.sqlite3')
        executive = LearningExecutive(journal, MemoryGateway())
        return cls(controller, ProfileRepository(directory / 'profiles'), journal, executive)

    def event(self, op, **payload):
        return self.journal.append('event', dict(category='neck_calibration_request', op=op,
            physical_authorization=False, **payload), episode=self.EPISODE,
            producer='CalibrationService', version='1')

    def requests(self, *, pending_only=True):
        requests = {}
        for row in self.journal.records('event'):
            if row.data['episode'] != self.EPISODE:
                continue
            p = row.data['payload']
            if p.get('category') != 'neck_calibration_request':
                continue
            if p['op'] == 'requested':
                requests[p['request_id']] = dict(p, status='pending', evidence_ids=[row.id])
            elif p.get('request_id') in requests:
                request = requests[p['request_id']]
                request['evidence_ids'].append(row.id)
                if p['op'] == 'evidence_added':
                    request['latest_evidence'] = p['evidence']
                if p['op'] in ('resolved', 'dismissed'):
                    request.update(status=p['op'], disposition=p)
        return {k: v for k, v in requests.items()
                if not pending_only or v['status'] == 'pending'}

    def request(self, reason, evidence, *, profile_id=None):
        if reason not in self.REASONS or not isinstance(evidence, dict) or not evidence:
            raise ValueError('typed reason and supporting evidence required')
        # Repeated observations consolidate into one discoverable open request.
        for request in self.requests(pending_only=False).values():
            if (request['reason'] == reason and request['profile_id'] == profile_id
                    and (request['status'] == 'pending' or
                         request['status'] == 'dismissed' and request['evidence'] == evidence)):
                if (request['status'] == 'pending' and
                        request.get('latest_evidence', request['evidence']) != evidence):
                    self.event('evidence_added', request_id=request['request_id'], evidence=evidence)
                return request['request_id']
        request_id = uuid.uuid4().hex
        row = self.event('requested', request_id=request_id, reason=reason,
                         profile_id=profile_id, evidence=evidence)
        self._reflect_request(request_id, row)
        return request_id

    def _reflect_request(self, request_id, row):
        if self.executive is not None:
            if any(p.get('scope', {}).get('request_id') == request_id
                   for p in self.executive.projects().values()):
                return
            from memory.learning_projects import reflect_project_opportunities
            hypothesis = dict(method='supervised_neck_recalibration',
                scope=dict(request_id=request_id, profile_id=row.data['payload']['profile_id']),
                expected='independently qualified neck calibration and safe recovery',
                conditions=[dict(supervised=True), dict(supervised=False)],
                observed_conditions=[dict(supervised=False)], evidence_ids=[row.id],
                requires=['physical_authorization', 'supervision', 'electrical_clearance'])
            proposals = reflect_project_opportunities(self.journal, self.EPISODE, [hypothesis])
            for proposal in proposals:
                self.executive.propose(proposal['proposal'], self.journal, [proposal['evidence_id']])

    def refresh(self):
        """Read-only profile audit. Never activate, fall back, or clear markers."""
        try:
            profile = self.repository.active()
        except (OSError, ValueError, TypeError, KeyError) as exc:
            reason = 'missing' if isinstance(exc, FileNotFoundError) else 'invalid'
            if 'quarantined' in str(exc).lower() or 'unclean' in str(exc).lower():
                reason = 'quarantined'
            elif 'incompatible' in str(exc).lower():
                reason = 'incompatible'
            self.request(reason, dict(error=str(exc), motion_permitted=False))
            self.profile = None
            self.health = None
            return None
        if self.profile is None or self.profile['calibration_id'] != profile['calibration_id']:
            self.profile = profile
            self.health = NeckHealth(self.controller, profile['calibration_id'], self._health_event,
                repository=self.repository, response_model=profile.get('visual_response'))
            self.previous_pose = None
        return profile

    def _sync_dispositions(self):
        if self.executive is None:
            return
        for request in self.requests(pending_only=False).values():
            if request['status'] == 'pending':
                continue
            for project in self.executive.projects().values():
                if (project.get('scope', {}).get('request_id') == request['request_id']
                        and project['status'] not in ('completed', 'abandoned', 'superseded')):
                    self.executive.transition(project['id'],
                        'superseded' if request['status'] == 'resolved' else 'abandoned',
                        'CAL-1 request ' + request['status'], self.journal,
                        [request['evidence_ids'][-1]])

    def _health_event(self, report):
        self.event('health_observation', report=report)
        if report.get('physical_authorization') is False and 'reason' in report:
            self.request('degraded', report, profile_id=report['profile_id'])

    def observe_primary(self, corners=None, *, telemetry=None, expected_transition=False,
                        visual_tracking_available=False, observation_evidence=None):
        try:
            return self._observe_primary(corners, telemetry=telemetry,
                expected_transition=expected_transition,
                visual_tracking_available=visual_tracking_available,
                observation_evidence=observation_evidence)
        except Exception:
            # Persistence/processing failure cannot leave permission alive.
            try:
                self.controller.neck_uncertain()
            finally:
                self.controller.stop()
            raise

    def _observe_primary(self, corners=None, *, telemetry=None, expected_transition=False,
                         visual_tracking_available=False, observation_evidence=None):
        """Consume existing observations, at most one telemetry poll/second.

        Corners must be newly observed fixed-scene references in profile pixels,
        never the saved calibration polygon or a moving tracked object. Primary
        ownership forbids neck movement, so even without visual references an
        unexpected commanded-position change revokes permission. Tracking loss
        alone is uncertainty, not proof of a mechanical fault.
        """
        now = self.clock()
        if self.session is not None:
            # The explicit supervisor consumes this same installed authority;
            # primary monitoring cannot interfere with its evidence protocol.
            return None
        if now - self.last_poll < 1:
            return None
        self.last_poll = now
        self.event('primary_observation', visual_tracking_available=visual_tracking_available,
                   fixed_scene_reference_available=NeckHealth.valid(corners),
                   evidence=observation_evidence or {}, physical_position_measured=False)
        profile = self.refresh()
        status = telemetry if telemetry is not None else self.controller.motion_status()
        if not status:
            if self.health is not None:
                return self.health.unsafe('primary-task neck telemetry unavailable')
            self.controller.stop()
            return self.request('uncertain', dict(reason='neck telemetry unavailable',
                                                  visual_tracking_available=visual_tracking_available))
        if profile is None:
            if status.get('armed') or status.get('pwm_active'):
                self.controller.neck_uncertain()
                self.controller.stop()
            return None
        envelope = status.get('envelope') or {}
        if envelope.get('calibration_id') != profile['calibration_id'] or status.get('profile_invalid'):
            return self.health.unsafe('Pi/RP2040 profile mismatch or invalid profile')
        pose = [status.get('pan'), status.get('tilt')]
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in pose):
            return self.health.unsafe('invalid primary-task neck telemetry',
                                      reported_positions=[repr(v) for v in pose])
        if (status.get('moving') or status.get('owner') in ('CALIBRATION', 'ACTIVE_VISION')
                or self.previous_pose is not None and
                any(abs(a-b) > .05 for a, b in zip(pose, self.previous_pose))):
            return self.health.unsafe('unexpected neck command during primary ownership')
        self.previous_pose = pose
        # Lack of fixed-scene evidence is not a mechanical diagnosis. Repeated
        # inability to supervise an energized neck still revokes permission.
        self.unobserved = (self.unobserved + 1 if status.get('pwm_active') and
                           not self.health.valid(corners) else 0)
        if self.unobserved >= self.health.persistence:
            return self.health.unsafe('fixed-scene neck evidence unavailable during primary task')
        return self.health.observe(corners, telemetry=status, expected_transition=expected_transition)

    def supervised_session(self, request_id, evidence_path, *, simulated=False, prepared_evidence=None):
        """Explicit supervisor entry; preparation never grants GP10/PWM permission."""
        if request_id not in self.requests() or self.session is not None:
            raise ValueError('one pending request and no active supervisor required')
        evidence = prepared_evidence or CalibrationJournal(evidence_path, simulated=simulated, journal=self.journal)
        if evidence.path.resolve() != Path(evidence_path).resolve() or evidence.simulated != simulated:
            raise ValueError('prepared evidence identity/provenance mismatch')
        archived = None
        for row in self.journal.records('event'):
            p = row.data['payload']
            if row.data['episode'] == self.EPISODE and p.get('op') == 'session_closed':
                archived = p.get('run_id')
        self.session = SupervisedCalibration(self.controller, evidence, archived_run_id=archived)
        self.event('session_opened', request_id=request_id, evidence_path=str(evidence.path.resolve()))
        return self.session

    def close_session(self, *, retain_qualified=False):
        if self.session is None:
            return
        session, self.session = self.session, None
        retain = False
        try:
            status = session.poll()
            motion = self.controller.motion_status() if retain_qualified else None
            eligible = bool(retain_qualified and status['state'] == 'CLOSED' and motion
                          and motion.get('armed') and not motion.get('profile_invalid')
                          and (motion.get('envelope') or {}).get('independently_qualified')
                          and motion.get('owner') is None and not motion.get('moving'))
            if not eligible:
                session.close()
            self.event('session_closed', run_id=status['run_id'], state=status['state'],
                       evidence_path=str(session.evidence.path.resolve()))
            # Retain authority only after the closure is durably recorded.
            retain = eligible
        finally:
            try:
                if not retain:
                    self.controller.stop()
                self.controller.calibration_sink = session.previous_sink
            finally:
                session.evidence.close()

    def attach_brain(self, **options):
        from .calibration_behavior import CalibrationBehavior
        self.brain = CalibrationBehavior(self, **options)
        return self.brain

    def observe_frame(self, frame, target=None):
        if self.brain is not None:
            self.brain.update(frame, target)
            if self.brain.authorized:
                return self.brain.corrected_frame(frame)
        return self.observe_primary(visual_tracking_available=bool(target),
            observation_evidence=dict(frame_available=frame is not None,
                target_visible=bool(target), fixed_scene_displacement='unavailable; target may move'))

    def resolve(self, request_id, *, evidence):
        """Independent qualification/activation must already exist externally."""
        request = self.requests()[request_id]
        if self.session is not None:
            raise ValueError('close supervised session before resolution')
        profile = self.repository.active()
        if not evidence or profile['calibration_id'] == request['profile_id']:
            raise ValueError('new independently qualified active profile and evidence required')
        row = self.event('resolved', request_id=request_id, evidence=evidence,
                         qualified_profile_id=profile['calibration_id'])
        self._sync_dispositions()
        return row

    def dismiss(self, request_id, *, actor, reason, evidence):
        if request_id not in self.requests() or not all((actor, reason, evidence)):
            raise ValueError('explicit actor, rationale and evidence required')
        row = self.event('dismissed', request_id=request_id, actor=actor,
                         reason=reason, evidence=evidence)
        self._sync_dispositions()
        return row

    def close(self):
        try:
            self.close_session()
        finally:
            self.journal.close()
