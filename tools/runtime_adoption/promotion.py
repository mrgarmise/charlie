"""Validate evidence for an operator review. This module never applies a release."""
import base64
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
import time
from .inventory import digest

STAGES=('source','master','release','enablement')
HEX40=re.compile('[0-9a-f]{40}')
HEX64=re.compile('[0-9a-f]{64}')


class Refusal(ValueError):pass


def require(condition, reason):
    if not condition:raise Refusal(reason)


def hexmatch(pattern,value):return isinstance(value,str) and bool(pattern.fullmatch(value))


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def load(path):
    p=Path(path);require(not p.is_symlink() and p.is_file(),'regular evidence file required')
    raw=p.read_bytes();require(len(raw)<=4*1024*1024,'evidence exceeds bound')
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'duplicate evidence key');result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(Refusal('nonfinite evidence')))


def verify_record(record, *, key_path, key_sha256, candidate, stage, abilities, now):
    """Explicit operator-pinned Ed25519 public key; never trusts a key in a receipt."""
    require(hexmatch(HEX64,key_sha256 or ''),'independent trust-key pin required')
    key=digest(key_path);require(key['sha256']==key_sha256,'review key changed')
    data=record.get('record',{})
    require(data.get('schema')=='charlie-adoption-approval-v2','approval record schema')
    require(data.get('candidate')==candidate and data.get('stage')==stage,'approval source/stage mismatch')
    require(data.get('abilities')==sorted(abilities),'approval ability scope mismatch')
    require(isinstance(data.get('reviewer'),str) and bool(data['reviewer'].strip()),'named independent reviewer required')
    expires=data.get('expires_at');issued=data.get('issued_at')
    require(all(type(x) in (int,float) and math.isfinite(x) for x in (issued,expires)),'finite review times')
    require(issued<=now<expires and expires-issued<=7*86400,'expired or overlong review')
    try:signature=base64.b64decode(record.get('signature',''),validate=True)
    except ValueError as e:raise Refusal('invalid signature encoding') from e
    require(len(signature)==64,'Ed25519 approval signature required')
    with tempfile.TemporaryDirectory(prefix='charlie-adoption-verify-') as directory:
        root=Path(directory);(root/'message').write_bytes(canonical(data));(root/'signature').write_bytes(signature)
        p=subprocess.run(['openssl','pkeyutl','-verify','-pubin','-inkey',str(Path(key_path).resolve()),
            '-rawin','-in',str(root/'message'),'-sigfile',str(root/'signature')],capture_output=True,timeout=5)
    require(p.returncode==0,'independent approval signature invalid')
    return data


def validate(manifest, inventory, receipts, *, stage='source', selected=(), approval=None,
             key_path=None,key_sha256=None,now=None,source_root=None):
    now=time.time() if now is None else now
    require(stage in STAGES,'unknown adoption stage')
    require(manifest.get('schema')=='charlie-adoption-candidate-v2','candidate schema')
    candidate=manifest.get('candidate',{});baseline=manifest.get('baseline',{})
    for identity in (candidate,baseline):
        require(hexmatch(HEX40,identity.get('sha','')) and hexmatch(HEX40,identity.get('tree','')),'exact source identities required')
    require(inventory.get('baseline',{}).get('sha')==baseline['sha'] and inventory['baseline'].get('tree')==baseline['tree'],'unknown local approved runtime identity')
    require(inventory.get('approvals',{}).get('approval_binding') is True and inventory['baseline'].get('dirty') is False,'local approval binding unavailable')
    require(inventory.get('candidate',{}).get('sha')==candidate['sha'] and inventory['candidate'].get('tree')==candidate['tree']
            and inventory['candidate'].get('dirty') is False,'candidate checkout identity mismatch or dirty source')
    require(manifest.get('state_migration')=='none','incompatible state migration')
    require(manifest.get('rollback',{}).get('sha') and manifest['rollback'].get('backup_manifests'),'missing rollback or backups')
    require(manifest.get('unreconciled_branches')==[],'unreconciled branches')
    old={x['path']:x['sha256'] for x in inventory.get('protected',[])}
    for path,expected in manifest.get('protected',{}).items():require(old.get(path)==expected,'altered or missing protected evidence: '+path)
    require(bool(manifest.get('protected')),'protected evidence inventory required')
    for path,expected in manifest['rollback']['backup_manifests'].items():
        require(old.get(path)==expected,'missing or changed backup manifest')
    guards=manifest.get('manual_llm_guards',{})
    require(guards.get('baseline_preserved') is True and guards.get('resource_limits_changed') is False,
            'changed Ollama/consultation resource guards')
    require(guards.get('autonomous_enabled') is False and guards.get('guardian_started') is False,
            'unauthorized autonomous scheduler/guardian')
    require(bool(guards.get('source_sha256')),'manual consultation guard source binding missing')
    observed=inventory.get('manual_llm_guards',{})
    require(bool(observed.get('baseline')) and observed.get('baseline')==observed.get('candidate'),
            'approved manual LLM source/resource guards changed')
    require(all(guards['source_sha256'].get(k)==v for k,v in observed['baseline'].items() if not k.startswith('function:')),
            'manual guard manifest does not bind approved baseline')
    if source_root is not None:
        root=Path(source_root).resolve()
        for name,expected in guards['source_sha256'].items():
            p=root/name
            require(root in p.resolve().parents and not p.is_symlink(),'unsafe guard source path')
            require(digest(p)['sha256']==expected,'changed manual consultation guard: '+name)
    requirements=manifest.get('required_ci',[]);require({'full','contracts','baseline-llm'}<=set(requirements),'missing mandatory CI suites')
    known={}
    for receipt in receipts:
        require(receipt.get('candidate')==candidate,'CI SHA/tree mismatch')
        require(receipt.get('conclusion')=='success' and receipt.get('failed')==0,'failed or unknown CI')
        require(type(receipt.get('passed')) is int and receipt['passed']>0,'empty CI receipt')
        stamp=receipt.get('completed_at')
        require(type(stamp) in (int,float) and math.isfinite(stamp) and 0<=now-stamp<=7*86400,'stale or future CI')
        require(hexmatch(HEX64,receipt.get('artifact_sha256','')),'CI artifact binding required')
        require(str(receipt.get('url','')).startswith('https://github.com/mrgarmise/charlie/actions/runs/'),'independent CI origin missing')
        require(receipt.get('suite') not in known,'duplicate suite receipt');known[receipt['suite']]=receipt
    require(set(requirements)<=set(known),'required exact-head CI missing')
    abilities=manifest.get('abilities',[]);ids=[a.get('id') for a in abilities]
    require(all(isinstance(x,str) and x for x in ids) and len(ids)==len(set(ids)),'duplicate/invalid ability IDs')
    by_id={a['id']:a for a in abilities};visited=set();visiting=set()
    def visit(identifier):
        require(identifier in by_id,'missing dependency '+str(identifier))
        require(identifier not in visiting,'dependency cycle')
        if identifier in visited:return
        visiting.add(identifier)
        for dep in by_id[identifier].get('dependencies',[]):visit(dep)
        visiting.remove(identifier);visited.add(identifier)
    for identifier in ids:visit(identifier)
    selected=sorted(selected)
    require(not set(selected)-set(ids),'unknown selected ability')
    if stage=='enablement':require(len(selected)==1,'one explicitly reviewed ability per enablement plan')
    if stage!='source':
        require(approval is not None,'separate operator approval required')
        verify_record(approval,key_path=key_path,key_sha256=key_sha256,candidate=candidate,stage=stage,abilities=selected,now=now)
    enabled=set(selected)|{a['id'] for a in abilities if a.get('enabled') is True}
    for a in abilities:
        require(type(a.get('enabled')) is bool,'explicit enabled/disabled state required')
        if stage in ('release','enablement') and a['id'] in enabled:
            for dep in a.get('dependencies',[]):require(dep in enabled,'improper upgrade order: disabled prerequisite')
            for gate in a.get('required_native_gates',[]):
                evidence=a.get('native_gates',{}).get(gate,{})
                require(evidence.get('status')=='passed' and evidence.get('candidate')==candidate
                        and hexmatch(HEX64,evidence.get('evidence_sha256','')),'unverified native gate '+gate)
                require(evidence.get('independent_review') is True,'native review missing')
            if a.get('touches_firmware') or a.get('motion'):
                require(hexmatch(HEX64,a.get('installed_firmware_sha256','')),'unknown firmware')
            if a.get('motion'):require(a.get('physical_stop_verified') is True,'missed physical STOP')
            if a.get('autonomous_consultation'):
                require(a.get('rp2040_ack_ttl_qualified') is True,'absent RP2040 ACK/TTL qualification')
                require(a.get('authentic_eligible_question') is True,'unqualified authentic question')
    return dict(schema='charlie-adoption-review-v2',candidate=candidate,baseline=baseline,stage=stage,
        eligible_for_operator_review=True,selected=selected,mutations_performed=[],
        authority='planning only; no install, pointer switch, service, firmware or capability activation')


def plan(ledger):
    result=[]
    for a in sorted(ledger['abilities'],key=lambda x:x['id']):
        missing=[g for g,v in a.get('stages',{}).items() if v in ('PENDING','UNKNOWN','BLOCKED')]
        result.append(dict(id=a['id'],purpose=a['purpose'],next_action=a.get('next_step'),
            missing_gates=missing,owner='human operator + independent reviewer',
            preflight='verify exact source/firmware/approval/evidence and independent owners',
            measurement='retain authentic timing/resources/source identity and adverse observations',
            success='all applicable hash-bound gates pass; no later stage inferred',
            stop='STOP, uncertainty, stale evidence, resource veto, authority mismatch or lost owner',
            rollback=a['rollback']))
    return dict(schema='charlie-adoption-plan-v2',actions=result,mutations_performed=[])


def release_candidate(manifest):
    # A versioned BOM, never a qualification receipt or installed-release pointer.
    require(manifest.get('schema')=='charlie-adoption-candidate-v2','candidate schema')
    return dict(schema='charlie-release-candidate-v2',version=manifest['version'],source=manifest['candidate'],
        baseline=manifest['baseline'],rollback=manifest['rollback'],state_migration='none',
        capabilities=[{k:a.get(k) for k in ('id','enabled','dependencies','native_gates','required_native_gates')} for a in manifest['abilities']],
        provenance_sha256=hashlib.sha256(canonical(manifest)).hexdigest(),installed=False,approved=False)
