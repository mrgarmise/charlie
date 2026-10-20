import pytest
from PIL import Image
from experiments.ppal.detector_bridge import (Frame,Letterbox,DetectorBridge,tracking_pairs,rich_world,HailoBackend)
from experiments.ppal.eyes.tracking import SpriteTracker
from experiments.ppal.robotron_agency import VisualAgency

class Fake:
    name='fake'
    def __init__(self,label='player'): self.label=label
    def infer(self,frame): return [dict(label=self.label,box=(40,20,60,40),confidence=.8,class_scores=None)]

def frame(at=1,id='a'): return Frame(id,Image.new('RGB',(200,100)),at,'sensor monotonic exposure',{'session':'fixture NOT gameplay'})
def bridge(backend=None,**kw): return DetectorBridge(lambda:backend or Fake(),model={'sha256':'fixture'},clock=lambda:1.1,**kw)

def test_schema_timestamp_geometry_and_no_self():
    packet=bridge().observe(frame()); row=packet['objects'][0]
    assert packet['exposure_at']==1 and packet['timestamp_basis']=='sensor monotonic exposure'
    assert row['bbox_board']==[20,20,30,40] and row['legacy_kind']=='unknown'
    assert row['class_scores'] is None and packet['self_authorization'] is False
    agency=VisualAgency();agency.observe(tracking_pairs(packet),observed_at=1)
    assert agency.agency.self_id is None

@pytest.mark.parametrize('size',[(200,100),(100,200),(173,91)])
def test_letterbox_roundtrip(size):
    t=Letterbox(*size,640);box=(10,10,size[0]-10,size[1]-10);px,py=t.padding
    mapped=[v*t.scale+(px if i%2==0 else py) for i,v in enumerate(box)]
    assert t.restore(mapped)==pytest.approx(box)

@pytest.mark.parametrize('at',[0,2,float('nan'),True])
def test_invalid_or_stale(at):
    with pytest.raises(ValueError):bridge().observe(frame(at))

def test_duplicate_reordered():
    b=bridge();b.observe(frame())
    with pytest.raises(ValueError): b.observe(frame())
    with pytest.raises(ValueError): b.observe(frame(.9,'b'))

def test_late_result():
    times=iter([1.1,1.1,1.9]);b=DetectorBridge(lambda:Fake(),model={},clock=lambda:next(times))
    with pytest.raises(ValueError,match='late'):b.observe(frame())

@pytest.mark.parametrize('exc',[ImportError('Hailo absent'),TimeoutError('timeout'),ValueError('shape mismatch'),RuntimeError('device')])
def test_explicit_failure_and_fallback(exc):
    def fail(): raise exc
    b=DetectorBridge(fail,model={},clock=lambda:1.1)
    with pytest.raises(type(exc)):b.observe(frame())
    b=DetectorBridge(fail,model={},fallback=Fake('unresolved-family'),mode='fallback',clock=lambda:1.1)
    p=b.observe(frame());assert p['fallback_event'] and p['model'] is None
    assert p['objects'][0]['legacy_kind']=='unknown' and not p['physical_authorization']

def test_class_transition_stable_id_and_motion():
    tracker=SpriteTracker();fake=Fake('grunt')
    for tick,label in enumerate(['grunt','human','unknown']):
        fake.label=label
        b=DetectorBridge(lambda:fake,model={},clock=lambda:1+tick*.1)
        p=b.observe(frame(1+tick*.1,str(tick)))
        assignments=tracker.update(tick,[d for d,_ in tracking_pairs(p)],observed_at=1+tick*.1)
        assert assignments=={0:1}
    world=rich_world(tracker,1.2)
    assert world['tracks'][0]['velocity_units']=='board units/second'
    assert len(world['tracks'][0]['history'])==3

@pytest.mark.parametrize('box',[(1,1,500,4),(3,3,2,2),(1,1,float('nan'),4)])
def test_invalid_boxes(box):
    fake=Fake();fake.infer=lambda frame:[dict(label='player',box=box)]
    with pytest.raises(ValueError):bridge(fake).observe(frame())

def test_deterministic_and_no_camera_owner():
    a=bridge().observe(frame());b=bridge().observe(frame());assert a==b
    import inspect
    import experiments.ppal.detector_bridge as module
    source=inspect.getsource(module)
    assert 'PiCameraSource' not in source and 'controller.execute' not in source

def test_hef_integrity(tmp_path):
    path=tmp_path/'model.hef';path.write_bytes(b'not a HEF')
    with pytest.raises(ValueError,match='integrity'):HailoBackend(path,sha256='wrong',classes=['player'])

def test_low_score_keeps_candidate_without_semantic_admission():
    fake=Fake('grunt');fake.infer=lambda f:[dict(label='grunt',box=(10,10,20,20),confidence=.3)]
    p=bridge(fake).observe(frame())
    assert p['objects'][0]['legacy_kind']=='unknown' and p['objects'][0]['label']=='grunt'
    assert len(tracking_pairs(p))==1


def test_cpu_template_preserves_legacy_semantics():
    from experiments.ppal.detector_bridge import TemplateBackend
    from experiments.ppal.eyes.detectors import Detection
    class Existing:
        def detect(self,image):return [Detection('threat',(1,1),(1,1,4,4),9)]
    assert bridge(TemplateBackend(Existing())).observe(frame())['objects'][0]['legacy_kind']=='threat'


def test_hailo_startup_checks_with_fake_sdk(tmp_path,monkeypatch):
    import sys,types,hashlib,subprocess
    path=tmp_path/'custom.hef';path.write_bytes(b'fixture NOT HEF')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    class HEF:
        def __init__(self,path):pass
        def get_input_vstream_infos(self):return [types.SimpleNamespace(shape=(640,640,3),name='input')]
        def get_output_vstream_infos(self):return [types.SimpleNamespace(format=types.SimpleNamespace(order='HAILO_NMS'))]
    monkeypatch.setitem(sys.modules,'hailo_platform',types.SimpleNamespace(HEF=HEF,Device=types.SimpleNamespace(scan=lambda:['fixture'])))
    monkeypatch.setattr(subprocess,'run',lambda *a,**kw:types.SimpleNamespace(stdout='Architecture HAILO8L'))
    backend=HailoBackend(path,sha256=digest,classes=['player'])
    assert backend.name=='hailort-hef'
    with pytest.raises(ValueError,match='shape'):HailoBackend(path,sha256=digest,classes=['player'],size=320)
    monkeypatch.setattr(subprocess,'run',lambda *a,**kw:types.SimpleNamespace(stdout='Architecture HAILO8'))
    with pytest.raises(ValueError,match='hailo8l'):HailoBackend(path,sha256=digest,classes=['player'])


def test_replay_cli_is_repeatable_and_protects_output(tmp_path,monkeypatch):
    import json,sys
    from experiments.ppal import replay_detectors
    image=tmp_path/'frame.png';frame().image.save(image)
    manifest=tmp_path/'frames.jsonl'
    manifest.write_text(json.dumps(dict(image='frame.png',frame_id='a',exposure_at=1.,timestamp_basis='fixture exposure',provenance={'authenticity':'SYNTHETIC'}))+'\n')
    profile=tmp_path/'profile.json';profile.write_text('{}')
    from experiments.ppal.eyes.sprites import SpriteDetector
    monkeypatch.setattr(SpriteDetector,'load',lambda p:types.SimpleNamespace(detect=lambda f:[]))
    import types
    outputs=[]
    for i in range(2):
        out=tmp_path/f'out{i}.jsonl'
        monkeypatch.setattr(sys,'argv',['replay',str(manifest),'--output',str(out),'--backend','template','--profile',str(profile)])
        replay_detectors.main();row=json.loads(out.read_text());row.pop('replay_processing_seconds');outputs.append(row)
    assert outputs[0]==outputs[1] and outputs[0]['freshness_age'] is None
    with pytest.raises(FileExistsError):replay_detectors.main()

def test_hailort_nms_execution_contract_and_timeout(monkeypatch):
    import types,sys,numpy as np
    calls=[]
    class Context:
        def __enter__(self): return self
        def __exit__(self,*args):calls.append('closed')
    class Group:
        def create_params(self):return {}
        def activate(self,p):return Context()
    class Device(Context):
        def configure(self,*a):return [Group()]
    class Params:
        @staticmethod
        def make_from_network_group(group,**kwargs):
            assert kwargs['timeout_ms']==200;return {}
    class Pipeline(Context):
        def __init__(self,*a):pass
        def infer(self,inputs):
            assert inputs['input'].shape==(1,640,640,3)
            return {'nms':[[np.array([[.35,.2,.45,.3,.9]])]]}
    sdk=types.SimpleNamespace(HEF=lambda p:None,VDevice=Device,ConfigureParams=types.SimpleNamespace(create_from_hef=lambda *a,**k:{}),HailoStreamInterface=types.SimpleNamespace(PCIe=1),InputVStreamParams=Params,OutputVStreamParams=Params,FormatType=types.SimpleNamespace(FLOAT32=1),InferVStreams=Pipeline)
    monkeypatch.setitem(sys.modules,'hailo_platform',sdk)
    b=object.__new__(HailoBackend);b.path='fixture';b.classes=['player'];b.size=640;b.timeout=.2;b.input_name='input'
    rows=b.infer(frame());assert rows[0]['box']==pytest.approx((40,20,60,40))
    assert DetectorBridge._normalize(rows,frame())[0]['legacy_kind']=='unknown'
    assert b.preprocessing(frame())['letterbox_padding']==(0,160)
    assert len(calls)==3
    b.classes.append('human')
    with pytest.raises(ValueError,match='class count'): b.infer(frame())

@pytest.mark.parametrize('dfc,available',[('3.33.0',True),('5.0.0',True),('3.33.0',False)])
def test_compile_bridge_training_only_calibration(tmp_path,monkeypatch,dfc,available):
    import sys,types,json,hashlib
    from experiments.ppal import compile_hailo_lab as module
    root=tmp_path/'lab';(root/'models'/'model').mkdir(parents=True)
    pt=root/'models'/'model'/'best.pt';pt.write_bytes(b'SYNTHETIC CHECKPOINT FIXTURE')
    sha=hashlib.sha256(pt.read_bytes()).hexdigest()
    model=dict(dataset_id='data',dataset_digest='digest',checkpoint_sha256=sha,parameters={'imgsz':640})
    manifest=dict(digest='digest',classes=['player'],frames=[dict(role='train',pixel_sha='train'),dict(role='test',pixel_sha='test')])
    class Lab:
        def __init__(self,p):self.root=p
        def get(self,*a):return model
    store=types.ModuleType('vision_lab.store');store.Lab=Lab;store.file_hash=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    datasets=types.ModuleType('vision_lab.datasets');datasets.verify_manifest=lambda *a:manifest;datasets.export_yolo=lambda *a:root/'dataset'
    monkeypatch.setitem(sys.modules,'vision_lab',types.ModuleType('vision_lab'))
    monkeypatch.setitem(sys.modules,'vision_lab.store',store);monkeypatch.setitem(sys.modules,'vision_lab.datasets',datasets)
    class Model:
        def __init__(self,p):pass
        def export(self,**kw):
            assert kw['name']=='hailo8l'
            config=json.loads(Path(kw['data']).read_text())
            assert config['train']==config['val']=='train/images'
            output=tmp_path/'compiled';output.mkdir();(output/'fixture.hef').write_bytes(b'SYNTHETIC NOT REAL HEF');return output
    from pathlib import Path
    ultra=types.ModuleType('ultralytics');ultra.YOLO=Model;ultra.__version__='test-fake'
    exporter=types.ModuleType('ultralytics.engine.exporter');exporter.export_formats=lambda:{'Argument':['hailo'] if available else []}
    monkeypatch.setitem(sys.modules,'ultralytics',ultra);monkeypatch.setitem(sys.modules,'ultralytics.engine',types.ModuleType('ultralytics.engine'));monkeypatch.setitem(sys.modules,'ultralytics.engine.exporter',exporter)
    monkeypatch.setattr(module.platform,'system',lambda:'Linux');monkeypatch.setattr(module.platform,'machine',lambda:'x86_64')
    monkeypatch.setattr(module.importlib.metadata,'version',lambda n:dfc)
    monkeypatch.setattr(sys,'argv',['compile','--lab-state',str(root),'--model-id','model','--output',str(tmp_path/'output')])
    if dfc.startswith('3.') and available:
        module.main();record=json.loads((tmp_path/'output'/'export.json').read_text())
        assert record['calibration_count']==1 and record['calibration_frames']==manifest['frames'][:1]
        assert record['qualification'].startswith('UNQUALIFIED')
    else:
        with pytest.raises(RuntimeError):module.main()
