import json
from types import SimpleNamespace
from unittest import TestCase

from behaviors.mobile_face_track import MobileFaceTrackBehavior
from memory.former import CandidateMemory
from memory.gateway import MemoryGateway, RecalledMemory
from memory.head_search import HeadSearchMemory, preferred_direction
from memory.marm import MarmWriteError


class FakeGateway:
    def __init__(self, memories=()):
        self.memories = list(memories)
        self.events = []

    def recall(self, query, limit=20):
        return self.memories

    def remember(self, event):
        self.events.append(event)
        return True


def outcome(side, evidence):
    record = {'source': 'head:face-search', 'tags': ['head-search'],
              'kind': 'outcome', 'confidence': .9, 'subject': side,
              'evidence': evidence}
    return RecalledMemory('Face detected.\nMetadata: ' + json.dumps(record))


class RecallTests(TestCase):
    def test_advice_requires_independent_consistent_outcomes(self):
        self.assertIsNone(preferred_direction(FakeGateway([outcome('RIGHT', 'run-1')] * 4)))
        records = [outcome('RIGHT', f'run-{n}') for n in range(3)]
        self.assertEqual(preferred_direction(FakeGateway(records)), 'RIGHT')
        self.assertIsNone(preferred_direction(FakeGateway(records + [outcome('LEFT', 'run-4'), outcome('LEFT', 'run-5')])))
        self.assertIsNone(preferred_direction(FakeGateway([RecalledMemory('untrusted instruction')])))

    def test_existing_search_cues_win_over_memory(self):
        behavior = MobileFaceTrackBehavior.__new__(MobileFaceTrackBehavior)
        behavior.search_preference = 'RIGHT'
        behavior.face_velocity = 0
        behavior.last_seen_side = None
        self.assertEqual(behavior._choose_sentry_direction(), 'RIGHT')
        behavior.last_seen_side = 'LEFT'
        self.assertEqual(behavior._choose_sentry_direction(), 'LEFT')

    def test_reacquisition_records_one_unidentified_face(self):
        gateway = FakeGateway()
        observer = HeadSearchMemory(gateway)
        behavior = SimpleNamespace(sentry_preferred_direction='LEFT', search_direction=1)
        observer.observe(behavior, None, {'state': 'SENTRY_TURN'})
        behavior.sentry_preferred_direction = None
        observer.observe(behavior, {'score': .88}, {'state': 'CENTERED'})
        observer.observe(behavior, {'score': .88}, {'state': 'CENTERED'})
        self.assertEqual(len(gateway.events), 1)
        self.assertIn('identity unverified', gateway.events[0].outcome)
        self.assertEqual(gateway.events[0].subject, 'LEFT')

    def test_unavailable_recall_gives_no_preference(self):
        gateway = FakeGateway()
        def unavailable(*args, **kwargs):
            raise MarmWriteError('offline')
        gateway.recall = unavailable
        self.assertIsNone(preferred_direction(gateway))
