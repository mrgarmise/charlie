"""Read-only native acceptance diagnostics; software fixture only."""
import json
from pathlib import Path
from memory.evidence import EvidenceJournal
from memory.learning_projects import LearningExecutive, SCOPE
from tools.inspect_developmental_progress import inspect


def test_inspection_preserves_distinct_projects_and_failure_without_owner(tmp_path, monkeypatch):
    journal=EvidenceJournal(tmp_path/'learning-evidence.sqlite3')
    ids=['original-investigation-a','original-investigation-b']
    for identifier in ids:
        journal.append('event',dict(op='proposed',project=dict(id=identifier,
            goal='same question; distinct evidence',scope=dict(episode=identifier),
            status='blocked',origins=[identifier],hypothesis_evidence=[],
            experiment_history=[])),episode=SCOPE,producer='LearningExecutive',version='fixture')
    rejected=journal.append('event',dict(category='preserved_meditation_rejection',
        context_id='original-investigation-a',source_sha256='original-source-hash',
        resumption_condition='independent valid replacement'),episode='fixture',
        producer='Reflection',version='fixture')
    original=[(r.id,r.document,r.committed_at) for r in journal.records()]
    journal.close()
    status=dict(error='original finite-value failure',physical_authorization=False)
    (tmp_path/'development-status.json').write_text(json.dumps(status))
    def forbidden(*args,**kwargs):raise AssertionError('inspection constructed active owner')
    monkeypatch.setattr(LearningExecutive,'__init__',forbidden)
    report=inspect(tmp_path)
    assert list(report['projects'])==ids
    assert report['projects'][ids[0]]['origins']==[ids[0]]
    assert report['projects'][ids[1]]['scope']!=report['projects'][ids[0]]['scope']
    assert report['status']==status
    assert report['developmental_records'][0]['id']==rejected.id
    assert report['developmental_records'][0]['payload']['source_sha256']=='original-source-hash'
    journal=EvidenceJournal(tmp_path/'learning-evidence.sqlite3',read_only=True)
    assert [(r.id,r.document,r.committed_at) for r in journal.records()]==original
    journal.close()


def test_pi_captures_prior_status_before_regressions():
    script=Path('tools/accept_episode_identity_pi.sh').read_text()
    assert script.index('> "$report/pre-development.json"')<script.index('-m pytest')
    assert script.count('> "$report/pre-development.json"')==1
