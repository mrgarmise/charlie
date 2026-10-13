import builtins
import json
import shutil
import numpy as np
import pytest
from PIL import Image
from learning.datasets import sha
from learning.portable import NumpyClassifier, export, TOLERANCE
from learning.operational import load_manifest
from learning.deployment import CapabilityDeployment
from memory.evidence import EvidenceJournal


def contract():
    return dict(target='ppal-semantics', input='RGB-candidate-crop',
                classes=['human', 'threat'], threshold=.5, eligible=True)


def candidate(channels=(4,), kernel=3, activation='relu'):
    return dict(identifier='controlled', classes=['human', 'threat'], spec=dict(
        family='small-cnn', objective='classification', channels=list(channels),
        kernel=kernel, activation=activation, size=16, epochs=2, lr=.01, seed=0, patience=2))


@pytest.mark.parametrize('channels,kernel,activation', [
    ((4,),3,'relu'), ((8,16),5,'relu'), ((4,8,16),3,'gelu')])
def test_portable_tensor_math_matches_existing_model(tmp_path,channels,kernel,activation):
    torch=pytest.importorskip('torch')
    from learning.foundry import build
    c=candidate(channels,kernel,activation)
    torch.manual_seed(9);reference=build(c['spec'],2).eval()
    path=tmp_path/'weights.npz'
    np.savez(path,**{k:v.detach().numpy() for k,v in reference.state_dict().items()})
    model=NumpyClassifier(c,contract(),path,sha(path))
    rng=np.random.default_rng(7)
    for n in range(4):
        image=Image.fromarray(rng.integers(0,256,(20+n,30+n,3),dtype=np.uint8))
        x=np.array(image.resize((16,16),Image.Resampling.BILINEAR),dtype=np.float32)/255.
        with torch.no_grad():p=reference(torch.from_numpy(x.transpose(2,0,1)).unsqueeze(0)).softmax(1)[0].numpy()
        assert np.max(np.abs(model.probabilities(image)-p))<TOLERANCE


def test_numpy_only_abstention_and_corrupt_tensor_rejection(tmp_path):
    c=candidate();path=tmp_path/'weights.npz'
    weights={'0.0.weight':np.zeros((4,3,3,3),dtype=np.float32),
             '0.0.bias':np.zeros(4,dtype=np.float32),
             '3.weight':np.zeros((2,4),dtype=np.float32),
             '3.bias':np.zeros(2,dtype=np.float32)}
    np.savez(path,**weights)
    model=NumpyClassifier(c,contract(),path,sha(path))
    assert model.infer(Image.new('RGB',(16,16)))['status']=='UNKNOWN'
    weights['3.bias'][0]=np.nan;np.savez(path,**weights)
    with pytest.raises(ValueError,match='invalid portable'):NumpyClassifier(c,contract(),path,sha(path))


def test_export_relocates_without_torch_and_keeps_rollback_authority(tmp_path,monkeypatch):
    pytest.importorskip('torch')
    from test_ala_operational import lab
    authority=dict(source='external-lab-grant',target='ppal-semantics',allowed_domains=['controlled-lab'])
    source=tmp_path/'source';source.mkdir()
    ds,g,report=lab(source,authority)
    original=report['results'][0]['result']['deployment']['manifest']
    result=report['results'][0]['result']
    deploy=CapabilityDeployment(ds.journal)
    # Two activations make normal previous-model rollback require historical
    # weights. Explicit baseline release must still work after transfer.
    deploy.activate(result['operational_proposal'],target='ppal-semantics',
        authorization=dict(source='second-lab-grant',target='ppal-semantics',proposal_id=result['operational_proposal']),
        shadow_id=result['shadow_id'])
    deploy.export('ppal-semantics',original)
    before=[(r.id,r.document) for r in ds.journal.records()]
    portable=export(original,tmp_path/'bundle')
    assert [(r.id,r.document) for r in ds.journal.records()][:len(before)]==before
    # Export is a transport check, not another training/test experiment.
    ds.journal.verify();ds.journal.close()
    moved=tmp_path/'moved';shutil.move(str(portable.parent),moved)
    shutil.rmtree(source)
    original_import=builtins.__import__
    def no_torch(name,*args,**kwargs):
        if name=='torch' or name.startswith('torch.'):raise AssertionError('Torch imported on Pi path')
        return original_import(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',no_torch)
    manifest=moved/'semantic-activation.json'
    active,model=load_manifest(manifest)
    assert model.infer(Image.new('RGB',(24,24),(220,11,10)))['label']=='human'
    from learning.readiness import audit
    crop=moved/'crops';crop.mkdir();Image.new('RGB',(24,24),(220,11,10)).save(crop/'example.png')
    audit_report=audit(root=moved,manifest=manifest,crops=crop,batches=1)
    assert audit_report['inference_benchmark']['crops_per_batch']==16
    assert not audit_report['physical_authorization'] and not audit_report['candidate']['physical_gate_qualified']
    with pytest.raises(ValueError,match='readiness'):load_manifest(manifest,physical=True)
    with pytest.raises(FileExistsError):export(original,moved)
    journal=EvidenceJournal(moved/'learning-evidence.sqlite3')
    CapabilityDeployment(journal).rollback('ppal-semantics',reason='local revocation',
        authorization=dict(source='operator',target='ppal-semantics'),to_baseline=True)
    journal.close()
    with pytest.raises(ValueError,match='current authorized'):load_manifest(manifest)


def test_exported_weights_and_linkage_cannot_be_substituted(tmp_path):
    pytest.importorskip('torch')
    from test_ala_operational import lab
    authority=dict(source='external-lab-grant',target='ppal-semantics',allowed_domains=['controlled-lab'])
    ds,g,report=lab(tmp_path,authority)
    manifest=export(report['results'][0]['result']['deployment']['manifest'],tmp_path/'bundle')
    value=json.loads(manifest.read_text())
    value['runtime']['sha256']='0'*64;manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='linkage'):load_manifest(manifest)
    value['runtime']['sha256']=sha(tmp_path/'bundle/weights.npz');manifest.write_text(json.dumps(value))
    (tmp_path/'bundle/weights.npz').write_bytes(b'modified')
    with pytest.raises(ValueError,match='weights changed'):load_manifest(manifest)


def test_torch_unavailable_retains_projects_and_explains_deferral(tmp_path,monkeypatch):
    from test_ala_cycle import make
    from learning.cycle import investigate
    ds,g=make(tmp_path)
    original=__import__('importlib.util',fromlist=['find_spec']).find_spec
    monkeypatch.setattr('learning.cycle.importlib.util.find_spec',lambda n:None if n=='torch' else original(n))
    r=investigate(ds,g,driver=lambda *a,**kw:(_ for _ in ()).throw(AssertionError('training started')))
    assert r['results']==[] and r['projects'] and not r['resources']['torch_available']
    assert 'cnn-reconstruction' in r['resources']['unavailable_methods']
    assert 'Torch unavailable' in (tmp_path/'ala-report.md').read_text()
    assert not any(x.data['payload'].get('category')=='capability_activation' for x in ds.journal.records())


def test_offline_readiness_is_read_only_and_does_not_claim_physical_success(tmp_path):
    from test_ala_cycle import make
    from learning.readiness import audit
    ds,g=make(tmp_path)
    # Use the conventional handoff filename without regenerating records.
    path=tmp_path/'learning-evidence.sqlite3'
    destination=__import__('sqlite3').connect(path);ds.journal.conn.backup(destination);destination.close()
    before=sha(path)
    r=audit(root=tmp_path)
    assert sha(path)==before and r['evidence']['records']==7
    assert r['evidence']['verified_robotron_role_examples']==0 and r['gaps']
    assert not r['physical_authorization']
    j=EvidenceJournal(path,read_only=True)
    with pytest.raises(__import__('sqlite3').OperationalError):j.append('event',{},episode='test',producer='test',version='1')
    j.close()


def test_training_data_extension_cannot_recertify_reused_final_games(tmp_path):
    pytest.importorskip('torch')
    from test_ala_operational import lab
    from test_ala_cycle import driver
    from learning.cycle import investigate
    ds,g,first=lab(tmp_path)
    old=first['results'][0]['result']
    assert old['metrics']['fresh_final_evidence'] and old['operational_proposal']
    path=tmp_path/'additional.png';Image.new('RGB',(24,24),(220,40,10)).save(path)
    example=ds.add(path,episode='0',crop=(0,0,24,24),source={'kind':'controlled-lab'},metadata={'domain':'controlled-lab'})
    ds.annotate(example.id,'human',status='verified',source='independent_measurement',evidence='lab-generator')
    second=investigate(ds,g,budget_seconds=30,max_jobs=1,driver=driver)
    result=second['results'][0]['result']
    assert result['metrics']['improved']
    assert not result['metrics']['fresh_final_evidence'] and result['metrics']['prior_final_evaluations']==[old['evaluation_id']]
    assert result['operational_proposal'] is None
    assert not ds.journal.get(result['deployment_proposal']).data['payload']['eligible']
