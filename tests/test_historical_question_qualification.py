"""Focused no-hardware tests; source/journal and fake provider only."""
from pathlib import Path
import pytest
from memory.evidence import EvidenceJournal
from tools.historical_question_qualification import load_question, prompt_for, run_once


def fixture_source(tmp_path):
    p = tmp_path / 'old.sqlite3'
    j = EvidenceJournal(p)
    origin = j.append('event', {'category':'perceptual_experiment_proposal',
        'proposal':{'question':'Can temporal estimation improve without promoting uncertain track links?'}},
        episode='old-episode', producer='Reflection', version='old-v1')
    question = j.append('event', {'category':'learning_project_proposal',
        'proposal':{'goal':'Can temporal estimation improve without promoting uncertain track links?',
                    'motivation':'Higher prediction error across gaps',
                    'open_questions':['Temporal estimates may fail across gaps']}},
        episode='old-episode', producer='Reflection', version='old-v1', sources=[origin.id])
    j.close()
    return p, question.id


class QualifiedFake:
    calls = []
    instance = None
    def __init__(self, approval):
        self.retained_called = False
        self.closed = False
        QualifiedFake.instance = self
    def consult(self, prompt):
        self.calls.append(prompt)
        return dict(answer='Test temporal models offline on held-out episodes.',
                    identity={'model_digest':'a'*64}, model='qwen3:1.7b')
    def retained(self):
        self.retained_called = True
    def status(self):
        return {'state':'completed-unload-confirmed'}
    def close(self):
        self.closed = True


def test_authentic_record_ingestion_and_durable_retention(tmp_path):
    p, question_id = fixture_source(tmp_path)
    item = load_question(p, question_id)
    assert 'temporal estimation' in item['question']
    assert 'Historical investigation' in prompt_for(item)
    approval = tmp_path / 'approval';approval.write_text('{}')
    notebook = tmp_path / 'new-notebook'
    QualifiedFake.calls = []
    result = run_once(p, question_id, notebook, approval, provider_factory=QualifiedFake)
    assert len(QualifiedFake.calls) == 1
    assert QualifiedFake.instance.retained_called
    assert QualifiedFake.instance.closed
    journal = EvidenceJournal(notebook/'learning-evidence.sqlite3', read_only=True)
    records = journal.records('event')
    assert [r.data['payload']['op'] for r in records] == ['selected','submitted','answered']
    assert records[-1].data['payload']['trust'] == 'unverified_hypothesis'
    assert records[-1].data['payload']['original_question_id'] == question_id
    assert records[-1].id == result['evidence_id']
    journal.close()
    with pytest.raises(ValueError, match='exists'):
        run_once(p, question_id, notebook, approval, provider_factory=QualifiedFake)
    assert len(QualifiedFake.calls) == 1


def test_missing_approval_never_contacts_provider(tmp_path):
    p, question_id = fixture_source(tmp_path)
    QualifiedFake.calls = []
    with pytest.raises(ValueError, match='approval'):
        run_once(p, question_id, tmp_path/'new', tmp_path/'missing', provider_factory=QualifiedFake)
    assert not QualifiedFake.calls
    assert not (tmp_path/'new').exists()


def test_provider_failure_is_deferred_no_retry(tmp_path):
    p, question_id = fixture_source(tmp_path)
    approval = tmp_path/'approval'; approval.write_text('{}')
    class Failing(QualifiedFake):
        def consult(self, prompt):
            self.calls.append(prompt)
            raise RuntimeError('simulated failure')
    notebook = tmp_path/'failed-notebook'
    QualifiedFake.calls = []
    with pytest.raises(RuntimeError, match='simulated failure'):
        run_once(p, question_id, notebook, approval, provider_factory=Failing)
    journal = EvidenceJournal(notebook/'learning-evidence.sqlite3', read_only=True)
    records = journal.records('event')
    assert [r.data['payload']['op'] for r in records] == ['selected','submitted','deferred']
    assert records[-1].data['payload']['no_automatic_retry'] is True
    journal.close()
    with pytest.raises(ValueError, match='exists'):
        run_once(p, question_id, notebook, approval, provider_factory=Failing)
    assert len(QualifiedFake.calls) == 1
