"""Normal offline entrypoint with explicitly synthetic interpretation fixtures."""
import hashlib
import subprocess
import sys
import pytest

from memory.evidence import EvidenceJournal
from memory.human_interaction import HumanInteractionGateway
from tests.test_object_recognition import setup_session, feed


def run(state, enabled=True, models=False):
    command = [sys.executable, 'main.py', '--offline', '--learning-state', str(state),
               '--learning-turns', '1', '--learning-interval', '.05', '--learning-budget', '1']
    if enabled:
        command.append('--human-questions')
    if models:
        command.append('--model-learning')
    result = subprocess.run(command, capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('models', [False, True])
def test_normal_import_question_answer_and_restart_preserve_source(tmp_path, models):
    state = tmp_path/'state'; state.mkdir()
    session = setup_session(tmp_path/'source')
    try:
        for i in range(3):
            feed(session, 1.+i*.1, sequence=i)
        original = session.journal.category_records('observation', 'mobile_perception')[-1]
        payload = original.data['payload']
    finally:
        session.session.close(); session.transport.close(); session.journal.close()
    # Controlled fixture tests authentic admission; this is not sensor evidence.
    payload['observation']['frame']['authentic'] = True
    payload['tracking']['target']['species_posterior'] = dict(cat=.55, dog=.45)
    source_path = state/'mobile-evidence.sqlite3'
    source = EvidenceJournal(source_path)
    row = source.append('observation', payload, episode='synthetic-runtime',
                        producer='controlled-fixture', version='1')
    source.close()
    before = hashlib.sha256(source_path.read_bytes()).hexdigest()
    run(state, enabled=False)
    journal = EvidenceJournal(state/'learning-evidence.sqlite3')
    assert not HumanInteractionGateway(journal).questions()
    journal.close()
    run(state, models=models)
    journal = EvidenceJournal(state/'learning-evidence.sqlite3')
    service = HumanInteractionGateway(journal)
    questions = service.questions()
    assert len(questions) == 1
    q = next(iter(questions.values()))
    assert q['need']['sources'] == [row.id]
    assert journal.get(row.id).document == row.document
    assert journal.get(row.id).committed_at == row.committed_at
    service.answer(q['id'], value='cat', operator='synthetic-reviewer', request_id='runtime-answer')
    journal.close()
    run(state, models=models)
    run(state, models=models)
    journal = EvidenceJournal(state/'learning-evidence.sqlite3')
    try:
        reviews = journal.category_records('observation', 'human_answer_review')
        assert len(reviews) == 1
        assert reviews[0].data['payload']['physical_authorization'] is False
        assert not journal.category_records('event', 'capability_activation')
        assert len(HumanInteractionGateway(journal).questions()) == 1
    finally:
        journal.close()
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == before
