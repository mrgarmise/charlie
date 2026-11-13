"""Information interface to the existing Executive and immutable EvidenceJournal.

No camera, actuator, policy activation, new memory store or model dependencies.
Queue times are UTC epoch; source monotonic timestamps never cross boots.
"""
from dataclasses import asdict, dataclass
from datetime import datetime
import math
import time
from .evidence import digest

CATEGORY = 'human_interaction'
VERSION = 'human-interaction-v1'
TYPES = {'identify_entity': 'Which label describes this tracked entity?',
         'interpret_result': 'How should this recorded result be interpreted?',
         'clarify_objective': 'Which recorded objective needs review?'}
CLOSED = {'answered', 'unknown', 'dismissed', 'expired', 'superseded'}


def bounded(value, limit):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit


@dataclass(frozen=True)
class InformationNeed:
    owner: str
    kind: str
    subject: str
    proposition: str
    candidates: tuple[str, ...]
    sources: tuple[str, ...]
    reason: str
    observed_at: float
    consequence: float
    uncertainty: float
    priority: int
    alternative_available: bool = False
    confidence: float | None = None
    ttl: float = 86400

    def validate(self):
        if self.kind not in TYPES or not all(bounded(x, 1024) for x in
                (self.owner, self.subject, self.proposition, self.reason)):
            raise ValueError('bounded typed grounding required')
        if (not 2 <= len(self.candidates) <= 12 or len(set(self.candidates)) != len(self.candidates)
                or not all(bounded(x, 120) for x in self.candidates) or not 1 <= len(self.sources) <= 32):
            raise ValueError('bounded candidates and evidence required')
        for x in (self.consequence, self.uncertainty, self.confidence):
            if x is not None and (type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1):
                raise ValueError('invalid confidence or value')
        if (type(self.priority) is not int or not 0 <= self.priority <= 3
                or type(self.alternative_available) is not bool
                or not math.isfinite(self.observed_at) or self.observed_at < 0
                or not math.isfinite(self.ttl) or not 60 <= self.ttl <= 604800):
            raise ValueError('invalid timing or priority')


class HumanInteractionGateway:
    def __init__(self, journal, *, clock=time.time, max_pending=32, daily_budget=8,
                 cooldown=3600, max_age=300):
        self.journal, self.clock = journal, clock
        if (not 1 <= max_pending <= 256 or not 1 <= daily_budget <= 128
                or not 0 <= cooldown <= 604800 or not 1 <= max_age <= 86400):
            raise ValueError('invalid queue policy')
        self.max_pending, self.daily_budget = max_pending, daily_budget
        self.cooldown, self.max_age = cooldown, max_age

    def _rows(self):
        return self.journal.category_records('event', CATEGORY)

    def _event(self, episode, payload, sources=()):
        return self.journal.append('event', dict(category=CATEGORY, **payload), episode=episode,
            sources=sources, producer='HumanInteractionGateway', version=VERSION)

    def questions(self):
        result = {}
        for row in self._rows():
            p = row.data['payload']
            if p['op'] == 'queued':
                result[row.id] = dict(p, id=row.id, status='pending', history=[])
            elif p.get('question_id') in result:
                q = result[p['question_id']]
                q['history'].append(dict(p, evidence_id=row.id))
                if p['op'] == 'status':
                    q['status'] = p['status']
                elif p['op'] == 'answer':
                    q.update(status='unknown' if p['value'] is None else 'answered',
                             answer=p, answer_id=row.id)
        for q in result.values():
            if q['status'] in ('pending', 'failed') and self.clock() >= q['expires_at']:
                q['status'] = 'expired'
        return result

    def consider(self, need):
        with self.journal.batch():
            return self._consider(need)

    def _consider(self, need):
        """Existing Executive submits a detected need; transparent deferred policy."""
        need.validate()
        now = self.clock()
        records = [self.journal.get(s) for s in need.sources]
        episodes = {r.data['episode'] for r in records}
        if len(episodes) != 1:
            raise ValueError('consolidate cross-episode evidence first')
        ages = [now-datetime.fromisoformat(r.committed_at).timestamp() for r in records]
        if not 0 <= now-need.observed_at <= self.max_age or any(not 0 <= a <= self.max_age for a in ages):
            return dict(asked=False, reason='stale_or_future_evidence')
        questions = self.questions()
        key = digest(dict(owner=need.owner, kind=need.kind, subject=need.subject))
        for q in reversed(list(questions.values())):
            if q['dedup_key'] == key and (q['status'] in ('pending', 'failed') or now-q['created_at'] < self.cooldown):
                return dict(asked=False, reason='duplicate_or_cooldown', question_id=q['id'])
        value = need.uncertainty*need.consequence
        if value < .25 or need.alternative_available or need.priority < 1:
            return dict(asked=False, reason='observe_or_defer', value_of_information=value)
        if (sum(q['status'] in ('pending', 'failed') for q in questions.values()) >= self.max_pending
                or sum(now-q['created_at'] < 86400 for q in questions.values()) >= self.daily_budget):
            return dict(asked=False, reason='interruption_budget')
        row = self._event(next(iter(episodes)), dict(op='queued', need=asdict(need),
            created_at=now, expires_at=now+need.ttl, dedup_key=key, urgency=need.priority,
            deferrable=True, cooldown=self.cooldown,
            response_schema=dict(value='candidate or null for unknown', explanation='optional <=2048 characters'),
            policy=dict(value_of_information=value, rule='uncertainty*consequence >= .25; no alternative; priority >= 1'),
            fallback='continue other eligible work; never infer an answer',
            provenance=dict(decider='LearningExecutive', identity='charlie', authority='information only')),
            need.sources)
        return dict(asked=True, question_id=row.id)

    def transition(self, question_id, status, reason):
        with self.journal.batch():
            return self._transition(question_id, status, reason)

    def _transition(self, question_id, status, reason):
        if status not in {'dismissed', 'expired', 'superseded', 'failed', 'pending'} or not bounded(reason, 1024):
            raise ValueError('invalid transition')
        q = self.questions()[question_id]
        if (status == 'expired' and self.clock() < q['expires_at']):
            raise ValueError('not expired')
        if q['status'] in CLOSED or (status == 'pending' and q['status'] != 'failed'):
            raise ValueError('closed question or invalid retry')
        return self._event(self.journal.get(question_id).data['episode'], dict(op='status',
            question_id=question_id, status=status, reason=reason, at=self.clock()), [question_id])

    def answer(self, question_id, *, value, explanation='', operator, request_id):
        with self.journal.batch():
            return self._answer(question_id, value=value, explanation=explanation,
                                operator=operator, request_id=request_id)

    def _answer(self, question_id, *, value, explanation, operator, request_id):
        if (not bounded(operator, 120) or not bounded(request_id, 128) or len(request_id) < 8
                or not isinstance(explanation, str) or len(explanation) > 2048
                or (value is not None and not isinstance(value, str))):
            raise ValueError('invalid answer metadata')
        q = self.questions()[question_id]
        if value is not None and value not in q['need']['candidates']:
            raise ValueError('answer outside schema')
        signature = dict(value=value, explanation=explanation, operator=operator)
        for row in self._rows():
            p = row.data['payload']
            if p['op'] == 'answer' and p['request_id'] == request_id:
                if p['question_id'] != question_id or any(p[k] != v for k,v in signature.items()):
                    raise ValueError('conflicting replay')
                return row
        if q['status'] not in ('pending', 'failed'):
            raise ValueError('question no longer answerable')
        with self.journal.batch():
            return self._event(self.journal.get(question_id).data['episode'], dict(op='answer',
                question_id=question_id, **signature, request_id=request_id, at=self.clock(),
                source='human:'+operator, fallible=True, confidence=None,
                physical_authorization=False, model_update=False), [question_id])

    def results(self, owner):
        consumed = {r.data['payload']['answer_id'] for r in self._rows()
                    if r.data['payload']['op'] == 'consumed' and r.data['payload']['owner'] == owner}
        return [dict(question_id=q['id'], evidence_id=q['answer_id'], answer=q['answer'], need=q['need'])
                for q in self.questions().values() if q['need']['owner'] == owner
                and 'answer_id' in q and q['answer_id'] not in consumed]

    def receive(self, owner):
        """Atomically route new answers to a requester-owned review observation.

        Durable review inbox only: downstream algorithms must independently review
        it. External side effects are deliberately excluded from this transaction.
        """
        delivered = []
        with self.journal.batch():
            for result in self.results(owner):
                answer = self.journal.get(result['evidence_id'])
                review = self.journal.append('observation', dict(category='human_answer_review',
                    owner=owner, question_id=result['question_id'], answer_id=answer.id,
                    answer=result['answer'], status='pending_independent_review',
                    physical_authorization=False, model_update=False),
                    episode=answer.data['episode'], sources=[answer.id],
                    producer=owner+':human-review-intake', version=VERSION)
                self.acknowledge(owner, answer.id)
                delivered.append(review)
        return delivered

    def acknowledge(self, owner, answer_id):
        row = self.journal.get(answer_id); p = row.data['payload']
        if p.get('category') != CATEGORY or p.get('op') != 'answer':
            raise ValueError('not an answer')
        if self.questions()[p['question_id']]['need']['owner'] != owner:
            raise ValueError('wrong requester')
        return self._event(row.data['episode'], dict(op='consumed', owner=owner, answer_id=answer_id), [answer_id])


def detect_need(journal, evidence_id, *, now, reason, consequence, priority, alternative_available=False):
    """Adapters read committed records. No random questions or inferred pet identity."""
    row = journal.get(evidence_id); p = row.data['payload']
    common = dict(sources=(row.id,), observed_at=now, reason=reason, consequence=consequence,
                  priority=priority, alternative_available=alternative_available)
    if p.get('category') == 'mobile_perception':
        t = p['tracking'].get('target')
        if (not t or t.get('ambiguous') or not t.get('observed')
                or t.get('lifecycle') != 'confirmed' or not t.get('id')):
            return None
        support = t.get('species_posterior', {})
        if set(support) != {'cat', 'dog'} or any(not math.isfinite(v) or not 0 <= v <= 1 for v in support.values()):
            return None
        if abs(sum(support.values())-1) > .001 or min(support.values()) < .25:
            return None
        frame = p['observation']['frame']
        if not 0 <= frame['received_at']-t['at'] <= 1:
            return None
        return InformationNeed(owner='pet_observe', kind='identify_entity',
            subject=row.data['episode']+':'+frame['source']+':'+t['id'],
            proposition='Conflicting cat/dog support on one session-bound track; individual identity unverified',
            candidates=('cat', 'dog'), uncertainty=1-max(support.values()), confidence=t.get('confidence'), **common)
    if p.get('category') == 'score_review_proposal':
        confidence = p.get('confidence')
        if confidence is None or not math.isfinite(confidence) or not 0 <= confidence < .75:
            return None
        return InformationNeed(owner='robotron', kind='interpret_result', subject=row.id,
            proposition='Uncertain recorded score proposal: '+str(p.get('proposed_score')),
            candidates=('readable score proposal', 'unreadable or ambiguous result'),
            uncertainty=1-confidence, confidence=confidence, **common)
    return None
