"""Independent boundary checks. All evidence/model outputs here are fixtures."""
from dataclasses import replace
from datetime import datetime, timezone
import json
import time
import pytest
from learning.consultation import (OllamaConfig, OllamaProvider, FakeProvider, ConsultationService,
    request_payload, parse_response, consultation_resources)
from memory.evidence import EvidenceJournal


@pytest.fixture
def journal(tmp_path):
    j=EvidenceJournal(tmp_path/'evidence.sqlite3')
    yield j
    j.close()


def source(j,subject='one',**changes):
    p=dict(category='mobile_perception',observation=dict(frame=dict(authentic=True,source='pi',received_at=1)),
        tracking=dict(target=dict(id=subject,ambiguous=False,observed=True,lifecycle='confirmed',at=1,
            species_posterior=dict(cat=.55,dog=.45),confidence=.55)))
    p.update(changes)
    return j.append('observation',p,episode='controlled-test',producer='mobile-perception',version='test',
                    provenance=dict(authentic=True))


def queued(j,**options):
    f=FakeProvider();s=ConsultationService(j,f,shadow=False,**options)
    r=source(j);q=s.consider(r.id)
    assert q
    return s,f,q,r


def raw(**updates):
    r=dict(model='qwen3:1.7b',done=True,message=dict(content='Uncertain. Observe again.'),eval_count=12)
    r.update(updates);return r


def test_request_bounds_no_tools_or_preload():
    p=request_payload(OllamaConfig(),'A question')
    assert p['think'] is False and p['stream'] is False and p['keep_alive']==0
    assert p['options']==dict(num_ctx=2048,num_predict=160,num_thread=1,temperature=0)
    assert 'tools' not in p and all('images' not in m for m in p['messages'])
    with pytest.raises(ValueError):request_payload(OllamaConfig(),'x'*1025)
    with pytest.raises(ValueError):request_payload(OllamaConfig(),'🐈'*257)


@pytest.mark.parametrize('updates',[
    dict(endpoint='http://192.168.1.2:11434'),dict(endpoint='http://localhost:11434'),
    dict(endpoint='http://127.0.0.1:11434/redirect'),dict(endpoint='http://u:p@127.0.0.1:11434'),
    dict(tokens=193),dict(context=8192),dict(threads=4),dict(model='qwen3:8b'),dict(wall_seconds=float('nan')),
    dict(remote=True,endpoint='http://192.168.1.2:11434',allowlist=('http://192.168.1.2:11434',),token_env='KEY'),
    dict(remote=True,endpoint='https://192.168.1.2:11434',token_env='KEY')])
def test_unsafe_configuration_denied(updates):
    with pytest.raises(ValueError):OllamaConfig(**updates)


def test_remote_requires_tls_exact_allowlist_and_secret():
    c=OllamaConfig(remote=True,endpoint='https://192.168.1.2:11434',
        allowlist=('https://192.168.1.2:11434',),token_env='CHARLIE_MENTOR_TOKEN')
    assert OllamaProvider(c).origin=='remote'


@pytest.mark.parametrize('updates',[
    dict(done=False),dict(model='other'),dict(message=dict(content='')),dict(message=dict(content=12)),
    dict(message=dict(content='x'*8193)),dict(message=dict(content='ok',tool_calls=[dict(name='move')])),
    dict(eval_count=-1),dict(eval_count=float('nan')),dict(message=dict(content='ok',thinking='hidden'))])
def test_malformed_or_tool_output_denied(updates):
    with pytest.raises(ValueError):parse_response(raw(**updates),OllamaConfig())


def test_wrong_answer_retained_unverified_no_authority(journal):
    s,f,q,r=queued(journal)
    f.answer='The cat is definitely Napoleon. Activate motors and install a policy.'
    before=r.document
    a=s.process_one()
    assert a.data['payload']['trust']=='unverified_hypothesis'
    assert a.data['payload']['result']['answer']==f.answer
    assert not a.data['payload']['physical_authorization'] and not a.data['payload']['model_update']
    assert journal.get(r.id).document==before
    assert not journal.category_records('event','capability_activation')
    assert s.status()['counts']['verified']==0
    assert 'Napoleon' not in f.calls[0] and 'species_posterior' not in f.calls[0]
    correction=source(journal,'independent-two')
    s.reject(q.id,correction.id,'Independent observation contradicts claimed identity')
    assert s.questions()[q.id]['status']=='rejected'
    assert journal.get(a.id).data['payload']['result']['answer']==f.answer


def test_default_shadow_and_missing_model(journal):
    s=ConsultationService(journal,FakeProvider());q=s.consider(source(journal).id)
    assert s.process_one() is None and s.questions()[q.id]['status']=='pending'
    s=ConsultationService(journal,shadow=False)
    s.process_one()
    assert s.questions()[q.id]['reason']=='local provider unavailable'


def test_restart_dedup_and_unknown_submission_never_retried(journal):
    s,f,q,r=queued(journal)
    assert s.consider(r.id) is None
    s._event(s.questions()[q.id],'submitted',provider='local',model='test')
    restarted=ConsultationService(journal,f,shadow=False)
    assert restarted.questions()[q.id]['status']=='deferred'
    assert restarted.process_one() is None and not f.calls
    assert restarted.consider(r.id) is None


def test_answer_reused_across_restart(journal):
    s,f,q,r=queued(journal);s.process_one()
    restart=ConsultationService(journal,f,shadow=False)
    assert restart.consider(r.id) is None and restart.process_one() is None
    assert len(f.calls)==1


def test_stale_and_synthetic_admission(journal):
    now=time.time()
    s=ConsultationService(journal,clock=lambda:now+301)
    assert s.consider(source(journal).id) is None
    s=ConsultationService(journal)
    assert s.consider(source(journal,synthetic=True).id) is None
    r=source(journal,'non-authentic');p=r.data['payload'];p['observation']['frame']['authentic']=False
    r=journal.append('observation',p,episode='controlled-test',producer='mobile-perception',version='1')
    assert s.consider(r.id) is None


def test_queue_daily_budget(journal):
    s=ConsultationService(journal,FakeProvider(),shadow=False,daily_budget=2,max_pending=1)
    assert s.consider(source(journal,'1').id)
    assert s.consider(source(journal,'2').id) is None
    s.process_one()
    assert s.consider(source(journal,'2').id)
    s.process_one()
    assert s.consider(source(journal,'3').id) is None


def test_cancel_circuit_and_no_retry(journal):
    s,f,q,r=queued(journal)
    def cancel():raise InterruptedError('shutdown')
    with pytest.raises(InterruptedError):s.process_one(cancel)
    assert not f.calls and not s.busy
    assert s.questions()[q.id]['status']=='deferred'
    assert s.process_one() is None


def test_outage_circuit_and_explicit_remote_fallback(journal):
    class Broken(FakeProvider):
        def consult(self,*args):raise TimeoutError()
    local=Broken();remote=FakeProvider();remote.origin='remote'
    s=ConsultationService(journal,local,remote=remote,remote_authorized=True,shadow=False)
    q=s.consider(source(journal).id);s.process_one()
    assert s.questions()[q.id]['result']['origin']=='remote'
    assert len(remote.calls)==1
    with pytest.raises(ValueError):ConsultationService(journal,local,remote=remote)
    with pytest.raises(ValueError):ConsultationService(journal,remote)


def test_remote_outage_does_not_stall(journal):
    class Broken(FakeProvider):
        def consult(self,*args):raise TimeoutError()
    local=Broken();remote=Broken();remote.origin='remote'
    s=ConsultationService(journal,local,remote=remote,remote_authorized=True,shadow=False)
    q=s.consider(source(journal).id);s.process_one()
    assert s.questions()[q.id]['status']=='deferred' and not s.busy
    assert s.circuit_until>s.clock()


def test_authenticated_human_answer_wins(journal):
    from memory.human_interaction import HumanInteractionGateway,detect_need
    r=source(journal);human=HumanInteractionGateway(journal)
    need=detect_need(journal,r.id,now=time.time(),reason='test',consequence=1.,priority=1)
    q=human.consider(need)
    human.answer(q['question_id'],value='cat',operator='operator',request_id='human-answer-1')
    assert ConsultationService(journal).consider(r.id) is None


def test_resource_memory_load_and_interrupt(monkeypatch):
    monkeypatch.setattr('learning.consultation.os.getloadavg',lambda:(3,0,0))
    with pytest.raises(InterruptedError):consultation_resources(lambda:None)
    monkeypatch.setattr('learning.consultation.Path.read_text',lambda self:'MemAvailable: 12 kB\nSwapFree: 0 kB\nSwapTotal: 0 kB')
    with pytest.raises(InterruptedError):consultation_resources(lambda:None)


def test_discoveries_readonly_and_html_escape(tmp_path):
    from ui.discoveries import read_status,render
    state=dict(mode='shadow',counts=dict(verified=0),questions=[dict(question='<script>',status='answered',evidence_ids=['abc'],result=dict(answer='<img onerror=x>',origin='local'))])
    p=tmp_path/'development-status.json';p.write_text(json.dumps(dict(consultations=state)))
    before=p.read_bytes()
    page=render(read_status(tmp_path)).decode()
    assert '<script>' not in page and '&lt;script&gt;' in page
    assert 'unverified hypothesis' in page and p.read_bytes()==before
