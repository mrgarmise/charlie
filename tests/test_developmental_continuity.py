"""Restart acceptance of bounded normal-owner work; constructed software inputs."""
from copy import deepcopy
import json
from types import SimpleNamespace
import pytest
from learning.continuity import compare_restart, ContinuityError
from learning.lifecycle import DevelopmentLifecycle, MeditationYield
from memory.evidence import digest, canonical
from tools.inspect_developmental_progress import inspect
from test_normal_learning_lifecycle import experience, startup, delivered_corpus
from test_meditation_yield import fragments
from experiments.ppal import meditate_robotron as meditation


@pytest.fixture
def advancing(tmp_path,monkeypatch):
    root=experience(tmp_path);state=tmp_path/'state'
    (root/'tracks.json').write_text(json.dumps(dict(tracks=fragments())))
    clock=[0.];original=meditation.predicted_link
    import learning.lifecycle as lifecycle
    monkeypatch.setattr(lifecycle,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    def compute(*args):
        value=original(*args);clock[0]+=2;return value
    monkeypatch.setattr(meditation,'predicted_link',compute)
    life=DevelopmentLifecycle(state,[root],budget_seconds=1);life.turn();life.close()
    before=inspect(state)
    life=DevelopmentLifecycle(state,[root],budget_seconds=1);life.turn();life.close()
    after=inspect(state)
    monkeypatch.undo()
    return state,root,before,after


def add(snapshot,data):
    snapshot['original_records'].append(dict(id=digest(data),document=canonical(data),committed_at='explicit-adversarial-fixture'))
    snapshot['records']+=1


def test_real_owner_advances_same_commission_across_restart(advancing):
    state,root,before,after=advancing
    report=compare_restart(before,after)
    assert report['continuity_passed'] and report['substantive_progress']
    assert report['classification']=='continued' and not report['steady_state_reached']
    assert report['runnable_work'] and not report['restart_exact']
    assert before['commissions']==after['commissions']
    # An actual normal entry point completes the retained commission and keeps
    # orchestrating other work; no manually commissioned intermediate stages.
    process=startup(state,[root],authorize=False)
    assert process.returncode==0,process.stderr
    final=inspect(state);report=compare_restart(after,final)
    assert report['completed_work'] and report['steady_state_reached']
    assert final['commissions']==before['commissions']
    assert startup(state,[root],authorize=False).returncode==0
    stable=compare_restart(final,inspect(state))
    assert stable['restart_exact'] and not stable['substantive_progress']


@pytest.mark.parametrize('change',['lost','reordered','recommitted'])
def test_history_cannot_be_lost_or_recommitted(advancing,change):
    _,_,before,after=advancing;after=deepcopy(after)
    if change=='lost':after['original_records'].pop(0);after['records']-=1
    elif change=='reordered':after['original_records'][:2]=reversed(after['original_records'][:2])
    else:after['original_records'][0]['committed_at']='reset clock'
    with pytest.raises(ContinuityError):compare_restart(before,after)


@pytest.mark.parametrize('category',['reflection_commission','learning_context_reference','normal_meditation_yield'])
def test_duplicate_causal_work_is_rejected(advancing,category):
    _,_,before,after=advancing;after=deepcopy(after)
    document=next(json.loads(r['document']) for r in after['original_records']
        if json.loads(r['document'])['payload'].get('category')==category or json.loads(r['document'])['kind']==category)
    document['version']='adversarial replay with a new content ID'
    add(after,document)
    with pytest.raises(ContinuityError,match='duplicate'):compare_restart(before,after)


def test_duplicate_completed_finding_is_rejected(tmp_path):
    root=experience(tmp_path);state=tmp_path/'state'
    assert startup(state,[root],authorize=False).returncode==0
    before=inspect(state);after=deepcopy(before)
    after['status']['turn_outcome']={'progress_occurred':False}
    document=next(json.loads(r['document']) for r in after['original_records'] if json.loads(r['document'])['kind']=='resolution')
    document['version']='adversarial repeated finding';add(after,document)
    with pytest.raises(ContinuityError,match='duplicate'):compare_restart(before,after)


@pytest.mark.parametrize('change',['cursor','commission','missing','integrity','history'])
def test_checkpoint_reset_or_identity_loss_fails(advancing,change):
    _,_,before,after=advancing;after=deepcopy(after);cp=after['checkpoints'][0]['document']
    if change=='cursor':cp['reconstruction']['neighbor']=0
    elif change=='commission':cp['commission_id']='fabricated commission'
    elif change=='missing':after['checkpoints']=[]
    elif change=='history':cp['history']=[dict(iteration=1,tracks_before=4,tracks_after=1,merges=3)]
    else:cp['state_digest']='invalid'
    if change!='integrity':cp['state_digest']=digest({k:v for k,v in cp.items() if k!='state_digest'})
    with pytest.raises(ContinuityError):compare_restart(before,after)


def test_arbitrary_timestamped_pseudo_evidence_is_not_continuation(advancing):
    _,_,before,after=advancing;after=deepcopy(after)
    data=json.loads(after['original_records'][-1]['document'])
    data.update(producer='adversarial replay',sources=[],payload={'category':'invented finding'},at=999)
    add(after,data)
    with pytest.raises(ContinuityError,match='unclassified'):compare_restart(before,after)


def test_runnable_work_cannot_be_hidden_as_waiting(advancing):
    _,_,before,after=advancing;after=deepcopy(after)
    after['status']['last_activity']='waiting for evidence'
    with pytest.raises(ContinuityError,match='runnable'):compare_restart(before,after)


def test_nonprogress_becomes_durable_block_and_status_churn_is_not_progress(tmp_path,monkeypatch):
    root=experience(tmp_path);state=tmp_path/'state'
    monkeypatch.setattr(meditation,'meditate',lambda *a,**k:(_ for _ in ()).throw(MeditationYield('controlled unavailable slice')))
    life=DevelopmentLifecycle(state,[root]);life.turn();before=inspect(state)
    for _ in range(6):life.turn()
    life.close();after=inspect(state)
    report=compare_restart(before,after)
    assert report['blocked_work'] and report['steady_state_reached']
    baseline=inspect(state)
    life=DevelopmentLifecycle(state,[root])
    for _ in range(4):life.turn()
    life.close();after=inspect(state)
    after['status'].update(pid=999,updated_at=12345)
    report=compare_restart(baseline,after)
    assert report['restart_exact'] and not report['substantive_progress']
    after['status']['turn_outcome']={'progress_occurred':True}
    with pytest.raises(ContinuityError,match='status claims'):compare_restart(baseline,after)


def test_completed_findings_continue_to_candidate_evaluation_under_normal_owner(tmp_path):
    root=experience(tmp_path);state=tmp_path/'state'
    assert startup(state,[root],authorize=False).returncode==0
    before=inspect(state);delivered_corpus(tmp_path,state)
    assert startup(state,[root],authorize=True).returncode==0
    after=inspect(state);report=compare_restart(before,after)
    assert report['substantive_progress'] and report['steady_state_reached']
    assert report['new_record_categories']['offline_operational_outcome']==1
    assert report['physical_authorization'] is False
    assert after['status']['latest_operational_outcome']['changed_decisions']>0


def test_offline_acceptance_rejects_authority_escalation(advancing):
    _,_,before,after=advancing;after=deepcopy(after)
    after['status']['physical_authorization']=True
    with pytest.raises(ContinuityError,match='authority'):compare_restart(before,after)
