"""Adoption plans are not authority. All native identities/receipts below are fixtures."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import pytest
from tools.runtime_adoption.promotion import validate,Refusal,canonical,plan,release_candidate
from tools.runtime_adoption.inventory import collect,manual_guards


@pytest.fixture
def qualified():
    identity=dict(sha='a'*40,tree='b'*40);baseline=dict(sha='c'*40,tree='d'*40)
    guard={'learning/consultation.py':'f'*64}
    manifest=dict(schema='charlie-adoption-candidate-v2',version='fixture-only',candidate=identity,baseline=baseline,
        rollback=dict(sha='e'*40,backup_manifests={'/fixture/backup-manifest.json':'f'*64}),
        state_migration='none',unreconciled_branches=[],protected={'/fixture/evidence.sqlite3':'e'*64},
        manual_llm_guards=dict(baseline_preserved=True,resource_limits_changed=False,autonomous_enabled=False,
            guardian_started=False,source_sha256=guard),required_ci=['full','contracts','baseline-llm'],
        abilities=[dict(id='stationary',enabled=False,dependencies=[],native_gates={},required_native_gates=['N0','N1'])])
    inventory=dict(baseline={**baseline,'dirty':False},candidate={**identity,'dirty':False},
        approvals=dict(approval_binding=True),manual_llm_guards=dict(baseline=guard,candidate=guard),
        protected=[dict(path='/fixture/evidence.sqlite3',sha256='e'*64),dict(path='/fixture/backup-manifest.json',sha256='f'*64)])
    receipts=[dict(candidate=identity,suite=s,conclusion='success',passed=10,failed=0,completed_at=1000,
        artifact_sha256='f'*64,url='https://github.com/mrgarmise/charlie/actions/runs/123') for s in manifest['required_ci']]
    manifest['ci_bundle_sha256']=hashlib.sha256(canonical(receipts)).hexdigest()
    return manifest,inventory,receipts


def test_review_plan_is_nonmutating_and_source_does_not_claim_native_acceptance(qualified):
    m,i,r=qualified;before=copy.deepcopy((m,i,r))
    answer=validate(m,i,r,now=1001)
    assert answer['mutations_performed']==[] and answer['stage']=='source'
    assert (m,i,r)==before
    proposal=release_candidate(m)
    assert proposal['approved'] is False and proposal['installed'] is False


@pytest.mark.parametrize('fault',['unknown-baseline','dirty','wrong-tree','missing-ci','failed-ci','stale-ci','backup','evidence',
    'state','order','branch','resource-flag','resource-bytes','autonomous','guardian','duplicate','empty-ci'])
def test_refuses_unsafe_or_unproven_promotion(qualified,fault):
    m,i,r=qualified
    if fault=='unknown-baseline':i['approvals']['approval_binding']=False
    if fault=='dirty':i['candidate']['dirty']=True
    if fault=='wrong-tree':r[0]['candidate']={**r[0]['candidate'],'tree':'0'*40}
    if fault=='missing-ci':r.pop()
    if fault=='failed-ci':r[0]['conclusion']='failure'
    if fault=='stale-ci':r[0]['completed_at']=-900000
    if fault=='backup':m['rollback']['backup_manifests']={}
    if fault=='evidence':i['protected'][0]['sha256']='1'*64
    if fault=='state':m['state_migration']='reset-original-notebook'
    if fault=='order':m['abilities'][0]['dependencies']=['missing']
    if fault=='branch':m['unreconciled_branches']=['unreviewed-donor']
    if fault=='resource-flag':m['manual_llm_guards']['resource_limits_changed']=True
    if fault=='resource-bytes':i['manual_llm_guards']['candidate']={'learning/consultation.py':'0'*64}
    if fault=='autonomous':m['manual_llm_guards']['autonomous_enabled']=True
    if fault=='guardian':m['manual_llm_guards']['guardian_started']=True
    if fault=='duplicate':m['abilities'].append(copy.deepcopy(m['abilities'][0]))
    if fault=='empty-ci':r[0]['passed']=0
    with pytest.raises(Refusal):validate(m,i,r,now=1001)


def signed(tmp_path,m,abilities,stage='enablement'):
    import base64
    # Ephemeral TEST ONLY key; it is not an operational credential or approval.
    private=tmp_path/'TEST_ONLY_private.pem';public=tmp_path/'TEST_ONLY_public.pem'
    subprocess.run(['openssl','genpkey','-algorithm','ED25519','-out',str(private)],check=True,capture_output=True)
    subprocess.run(['openssl','pkey','-in',str(private),'-pubout','-out',str(public)],check=True,capture_output=True)
    record=dict(schema='charlie-adoption-approval-v2',candidate=m['candidate'],stage=stage,abilities=sorted(abilities),
        reviewer='TEST-ONLY-INDEPENDENT-REVIEWER',issued_at=1000,expires_at=1100,manifest_sha256=hashlib.sha256(canonical(m)).hexdigest())
    message=tmp_path/'message';signature=tmp_path/'signature';message.write_bytes(canonical(record))
    subprocess.run(['openssl','pkeyutl','-sign','-inkey',str(private),'-rawin','-in',str(message),'-out',str(signature)],check=True,capture_output=True)
    return dict(record=record,signature=base64.b64encode(signature.read_bytes()).decode()),public,hashlib.sha256(public.read_bytes()).hexdigest()


@pytest.mark.parametrize('gate',['firmware','STOP','ACK','question','native','approval','signature','trust-pin','scope','expiry','upgrade-order'])
def test_native_and_approval_gates_are_independent(tmp_path,qualified,gate):
    m,i,r=qualified;a=m['abilities'][0]
    a.update(motion=True,touches_firmware=True,autonomous_consultation=True,installed_firmware_sha256='f'*64,
        physical_stop_verified=True,rp2040_ack_ttl_qualified=True,authentic_eligible_question=True,
        native_gates={g:dict(status='passed',candidate=m['candidate'],evidence_sha256='f'*64,independent_review=True) for g in ('N0','N1')})
    approval,key,pin=signed(tmp_path,m,['stationary'])
    if gate=='firmware':a['installed_firmware_sha256']=None
    if gate=='STOP':a['physical_stop_verified']=False
    if gate=='ACK':a['rp2040_ack_ttl_qualified']=False
    if gate=='question':a['authentic_eligible_question']=False
    if gate=='native':a['native_gates']['N1']['status']='unknown'
    if gate=='approval':approval=None
    if gate=='signature':approval['signature']='A'*88
    if gate=='trust-pin':pin='0'*64
    if gate=='scope':approval['record']['candidate']={'sha':'0'*40,'tree':'0'*40}
    if gate=='expiry':approval['record']['expires_at']=1001
    if gate=='upgrade-order':
        m['abilities'].append(dict(id='prerequisite',enabled=False,dependencies=[]));a['dependencies']=['prerequisite']
    if gate in ('firmware','STOP','ACK','question','native','upgrade-order'):
        approval,key,pin=signed(tmp_path,m,['stationary'])
    with pytest.raises(Refusal):validate(m,i,r,stage='enablement',selected=['stationary'],approval=approval,
        key_path=key,key_sha256=pin,now=1001)


def test_valid_signature_only_produces_a_dry_review(tmp_path,qualified):
    m,i,r=qualified;approval,key,pin=signed(tmp_path,m,[],stage='master')
    answer=validate(m,i,r,stage='master',approval=approval,key_path=key,key_sha256=pin,now=1001)
    assert answer['mutations_performed']==[] and answer['eligible_for_operator_review']


def test_no_universal_enable_or_apply_cli():
    import sys
    for action in ('apply','enable-everything','deploy','install','flash'):
        r=subprocess.run([sys.executable,'-m','tools.runtime_adoption',action],capture_output=True,text=True)
        assert r.returncode!=0


def test_unknown_or_duplicate_json_cannot_be_evidence(tmp_path):
    from tools.runtime_adoption.promotion import load
    p=tmp_path/'bad.json'
    for text in ('{"accepted":true,"accepted":false}','{"deadline":NaN}'):
        p.write_text(text)
        with pytest.raises(Refusal):load(p)


def test_deterministic_plan_preserves_per_ability_native_holds():
    a=dict(id='z',purpose='fixture',stages={'native':'UNKNOWN','motion':'NOT APPLICABLE'},next_step='measure',rollback='original pin')
    assert plan(dict(abilities=[a]))==plan(dict(abilities=[a]))
    assert plan(dict(abilities=[a]))['actions'][0]['missing_gates']==['native']


def test_approved_manual_llm_guard_functions_and_resources_are_preserved():
    root=Path(__file__).resolve().parents[1]
    baseline=json.loads((root/'docs/runtime-adoption/evidence/approved-baseline.json').read_text())
    assert manual_guards(root)==baseline['manual_llm_guards']


def test_guard_fingerprint_uses_exact_source_not_interpreter_ast_format(tmp_path,monkeypatch):
    import ast,shutil
    from tools.runtime_adoption.inventory import GUARD_FILES
    root=Path(__file__).resolve().parents[1]
    for name in (*GUARD_FILES,'learning/consultation_activation.py'):
        target=tmp_path/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,target)
    def forbidden(*args,**kwargs):raise AssertionError('AST dump is interpreter-version dependent')
    monkeypatch.setattr(ast,'dump',forbidden)
    before=manual_guards(tmp_path);assert before==manual_guards(root)
    path=tmp_path/'learning/consultation_activation.py'
    path.write_text(path.read_text().replace('35 <= expires - issued <= 120','34 <= expires - issued <= 120'))
    assert manual_guards(tmp_path)['function:validate_approval']!=before['function:validate_approval']


def test_transferred_runtime_sources_are_tracked_and_match_reviewed_manifest():
    root=Path(__file__).resolve().parents[1]
    path=root/'docs/runtime-adoption/evidence/firmware-source-transfer.json'
    if not path.exists():return  # Core increment precedes the optional firmware transfer.
    for row in json.loads(path.read_text()):
        name=row['path']
        if not name.startswith(('networking/','firmware/','hardware/','motion/','ui/','tests/','tools/')):continue
        tracked=subprocess.run(['git','-C',str(root),'ls-files','--error-unmatch','--',name],capture_output=True)
        assert tracked.returncode==0,'reviewed source omitted from candidate: '+name
        indexed=subprocess.run(['git','-C',str(root),'show',':'+name],capture_output=True,check=True).stdout
        assert hashlib.sha256(indexed).hexdigest()==row['candidate_sha256'],'reviewed source differs in Git index: '+name
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==row['candidate_sha256'],name


def test_signed_review_cannot_be_reused_for_changed_manifest_or_ci_bundle(tmp_path,qualified):
    m,i,r=qualified;approval,key,pin=signed(tmp_path,m,[],stage='master')
    m['version']='changed-after-review'
    with pytest.raises(Refusal,match='signed review'):
        validate(m,i,r,stage='master',approval=approval,key_path=key,key_sha256=pin,now=1001)
    m['version']='fixture-only';r[0]['artifact_sha256']='0'*64
    with pytest.raises(Refusal,match='CI bundle'):
        validate(m,i,r,stage='master',approval=approval,key_path=key,key_sha256=pin,now=1001)
