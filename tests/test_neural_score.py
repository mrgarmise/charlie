import json
import time
import types
import numpy as np
import pytest
from PIL import Image,ImageDraw
from experiments.ppal.neural_score.contract import decode,preprocess,crop_quality,OUTPUT,sha
from experiments.ppal.neural_score.backends import Backend,Admission
from experiments.ppal.neural_score.reader import NeuralHUDReader
from experiments.ppal.neural_score.corpus import freeze,verify
from experiments.ppal.eyes.calibration import Calibration
from experiments.ppal.robotron_score_system import RobotronScoreSystem


def logits(text):
    a=np.full(OUTPUT,-8.,dtype=np.float32);a[:,10,:,:]=8
    for i,c in enumerate(text):
        index=3+i*3;a[:,:,0,index]=-8.;a[:,int(c),0,index]=8
    return a

class Fake:
    mode='cpu-reference'
    def __init__(self,text='100'):self.text=text
    def infer(self,x):return logits(self.text),dict(backend='FAKE engineering adapter',device_seconds=None)

@pytest.mark.parametrize('text',['0','00','11','100','2200','9999999','3500'])
def test_ctc_repeated_full_strings(text):
    r=decode(logits(text));assert r['digits']==text and r['score']==int(text)

@pytest.mark.parametrize('kind',['blank','uncertain-blank','edge','leading-zero','long','nonfinite','shape'])
def test_abstention(kind):
    a=logits('100')
    if kind=='blank':a=logits('')
    elif kind=='uncertain-blank':a[:,:,0,1]=0
    elif kind=='edge':a[:,:,0,0]=-8;a[:,1,0,0]=8
    elif kind=='leading-zero':a=logits('010')
    elif kind=='long':a=logits('12345678')
    elif kind=='nonfinite':a[0,0,0,1]=float('nan')
    elif kind=='shape':a=a[:,:,:,:2]
    if kind in ('nonfinite','shape'):
        with pytest.raises(ValueError):decode(a)
    else:assert decode(a)['score'] is None


def scene():
    image=Image.new('RGB',(640,600));draw=ImageDraw.Draw(image)
    # HUD strip maps raw y48..96 -> corrected y0..96 for calibration below.
    draw.rectangle((100,61,130,78),fill='white');draw.rectangle((480,61,510,78),fill='white')
    return image


def reader(backend=None,clock=lambda:10.1):
    return NeuralHUDReader(Calibration(((0,.16),(1,.16),(1,.96),(0,.96))),backend or Fake(),{},clock=clock)


def test_geometry_above_arena_and_independent_channels():
    class Channels(Fake):
        count=0
        def infer(self,x):
            self.count+=1;return logits('11' if self.count==1 else '2200'),{}
    r=reader(Channels());r.bind_source(t=10.,source={'observation_id':'f','timestamp_basis':'sensor exposure'})
    result=r.read(scene());assert result.player1_score==11 and result.player2_score==2200
    assert r.last_packet['raw_hud_quad'][0][1]==pytest.approx(48.)
    assert r.last_packet['channels'][0]['crop_box_hud']!=r.last_packet['channels'][1]['crop_box_hud']

@pytest.mark.parametrize('at',[None,True,float('nan'),9.,11.])
def test_missing_invalid_stale_future_source(at):
    r=reader();r.bind_source(t=at,source={'observation_id':'f','timestamp_basis':'sensor exposure'})
    assert r.read(scene()).player1_score is None


def test_missing_basis_repeated_and_late():
    r=reader();r.bind_source(t=10,source={'observation_id':'f'})
    assert r.read(scene()).player1_score is None
    source={'observation_id':'f','timestamp_basis':'sensor exposure'}
    r.bind_source(t=10,source=source);assert r.read(scene()).player1_score==100
    r.bind_source(t=10,source=source);assert r.read(scene()).player1_score is None
    values=iter([10.1,11.]);r=reader(clock=lambda:next(values));r.bind_source(t=10,source=source)
    assert r.read(scene()).player1_score is None

@pytest.mark.parametrize('variant',['blank','glare','clipped','dim'])
def test_bad_crop(variant):
    im=Image.new('RGB',(100,32),'white' if variant=='glare' else 'black')
    if variant=='clipped':ImageDraw.Draw(im).rectangle((0,5,10,25),fill='white')
    if variant=='dim':ImageDraw.Draw(im).rectangle((20,5,40,25),fill=(20,20,20))
    assert crop_quality(im)


def test_extended_roi_mistake_abstains():
    r=NeuralHUDReader(Calibration(((0,.01),(1,.01),(1,1),(0,1))),Fake(),{},clock=lambda:10.)
    r.bind_source(t=10,source={'observation_id':'a','timestamp_basis':'sensor'})
    assert r.read(scene()).player1_score is None

@pytest.mark.parametrize('error',[ImportError('SDK'),FileNotFoundError('HEF'),TimeoutError('timeout'),ValueError('shape/target'),RuntimeError('driver')])
def test_required_and_preferred(error):
    def fail():raise error
    cpu=types.SimpleNamespace(infer=lambda x:(logits('11'),{}))
    with pytest.raises(type(error)):Backend('hailo-required',lambda:cpu,fail).infer(None)
    values,meta=Backend('hailo-preferred',lambda:cpu,fail).infer(None)
    assert decode(values)['score']==11 and meta['backend']=='cpu-reference' and meta['health_event']


def test_admission_nonblocking_priority():
    gate=Admission();gate.urgent.set()
    with pytest.raises(RuntimeError):
        with gate.score():pass
    gate.urgent.clear()
    gate.suspend('upstream thermal/memory guard')
    with pytest.raises(RuntimeError):
        with gate.score():pass
    gate.resume()
    with gate.score():pass
    gate.urgent.clear()
    with gate.score():
        with pytest.raises(RuntimeError):
            with gate.score():pass
    with gate.score():pass


def test_existing_score_tracker_no_boundary_or_self_authority():
    r=reader();system=RobotronScoreSystem(r.calibration,reader=r,self_channel=None,confirm_baseline=True)
    source={'observation_id':'a','timestamp_basis':'sensor exposure'}
    result=system.observe(scene(),t=10.,source=source)
    assert result.self_score is None and system.reader.last_packet['official_game_score'] is False
    assert result.player1.observed_score==100


def row(tmp_path,n,label='100',role='train',session=None):
    im=Image.new('RGB',(100,32),(n*40,n*40,n*40));path=tmp_path/f'{n}.png';im.save(path)
    return dict(image=str(path),sha256=sha(path),verified=True,reviewer='human-fixture',annotation_ids=['fixture'],label=label,role=role,session=session or str(n),synthetic=True)


def test_manifest_immutable_and_leakage(tmp_path):
    a=row(tmp_path,0);b=dict(a,role='test',session='other')
    with pytest.raises(ValueError,match='leakage'):freeze([a,b],tmp_path/'bad.json')
    path=tmp_path/'manifest.json';freeze([a],path);assert verify(path)['rows'][0]['label']=='100'
    with pytest.raises(FileExistsError):freeze([a],path)
    with pytest.raises(ValueError):freeze([dict(a,role='test')],tmp_path/'moved.json',previous=[path])
    data=json.loads(path.read_text());data['rows'][0]['label']='2200';path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='digest'):verify(path)

@pytest.mark.parametrize('value',['001',123,'１２','12345678'])
def test_invalid_training_label(tmp_path,value):
    with pytest.raises(ValueError):freeze([row(tmp_path,0,label=value)],tmp_path/'bad.json')


def test_corpus_preserves_unreadable_and_zero(tmp_path):
    record=freeze([row(tmp_path,0,label=None),row(tmp_path,1,label='0'),row(tmp_path,2,label='')],tmp_path/'data.json')
    assert [r['label'] for r in record['rows']]==[None,'0','']
    other=freeze([row(tmp_path,3,label='00')],tmp_path/'visible-two-zeros.json')
    assert verify(tmp_path/'visible-two-zeros.json')['rows'][0]['label']=='00'


def test_raw_recognition_metrics_separate_abstention():
    from experiments.ppal.neural_score.evaluate import metrics
    rows=[dict(label='2200',prediction=decode(logits('1100')),wall_seconds=.1),dict(label='100',prediction=decode(logits('')),wall_seconds=.2)]
    m=metrics(rows);assert m['coverage']==.5 and m['correct']==0 and m['high_confidence_wrong']==1


def test_corpus_sticky_splits_and_final_consultation(tmp_path):
    from experiments.ppal.neural_score.corpus import consult_test,assert_trainable
    a=row(tmp_path,0,role='test');path=tmp_path/'first.json';freeze([a],path)
    with pytest.raises(ValueError):freeze([dict(a,role='train')],tmp_path/'second.json')
    consult_test(path)
    with pytest.raises(ValueError):consult_test(path)
    with pytest.raises(ValueError):assert_trainable(path)


def test_real_optimizer_export_and_resume(tmp_path):
    pytest.importorskip('torch');pytest.importorskip('onnxruntime');pytest.importorskip('onnx')
    from experiments.ppal.neural_score.train import synthetic,train
    from experiments.ppal.neural_score.backends import CPU
    root=tmp_path/'synthetic';synthetic(root,count=12)
    result=train(root/'manifest.json',tmp_path/'model',steps=2,batch=2)
    assert result['weights_changed'] and result['steps']==2 and result['export']['onnxruntime_checked']
    from experiments.ppal.neural_score.compile import validate_graph
    graph=validate_graph(tmp_path/'model'/'score.onnx')
    import onnx
    graph.graph.output[0].type.tensor_type.shape.dim[-1].dim_value=32
    bad=tmp_path/'wrong-shape.onnx';onnx.save(graph,bad)
    with pytest.raises(ValueError,match='shape'):validate_graph(bad)
    backend=CPU(tmp_path/'model'/'score.onnx',result['onnx_sha256'])
    value,timing=backend.infer(np.zeros((1,3,32,256),dtype=np.float32));assert value.shape==OUTPUT
    resumed=train(root/'manifest.json',tmp_path/'resumed',steps=1,batch=2,resume=tmp_path/'model'/'score.pt')
    assert resumed['total_steps']==3 and resumed['resume_sha256']==result['checkpoint_sha256']


def test_score_worker_integration_partition_and_shutdown(tmp_path):
    from experiments.ppal.score_observer import ScoreObserver
    source={'timestamp_basis':'sensor monotonic exposure'}
    now=time.monotonic()
    observer=ScoreObserver(reader().calibration,tmp_path/'score.jsonl',reader_factory=lambda cal:NeuralHUDReader(cal,Fake(),{},max_age=2.))
    observer.submit(scene(),timestamp=now,sample=1,preceding_action=None,observation_id='a',screen={'phase':'attract'},capture_metadata=source)
    observer.queue.join()
    assert observer.gameplay_report is None
    observer.submit(scene(),timestamp=time.monotonic(),sample=2,preceding_action=None,observation_id='b',screen={'phase':'gameplay'},capture_metadata=source)
    observer.queue.join();observer.close()
    assert not observer.thread.is_alive() and observer.gameplay_report is not None
    rows=[json.loads(line) for line in (tmp_path/'score.jsonl').read_text().splitlines()]
    assert rows[0]['score_partition']=='non_gameplay' and rows[1]['neural_score']['source']['timestamp_basis']==source['timestamp_basis']
    before=observer.dropped;observer.submit(scene(),timestamp=now,sample=3,preceding_action=None)
    assert observer.dropped==before+1


def test_hailo_sdk_stream_contract(monkeypatch,tmp_path):
    import sys,subprocess
    from experiments.ppal.neural_score.backends import Hailo
    path=tmp_path/'model.hef';path.write_bytes(b'FAKE engineering HEF')
    calls=[]
    class Context:
        def __enter__(self):return self
        def __exit__(self,*a):calls.append('closed')
    class HEF:
        def __init__(self,path):pass
        def get_input_vstream_infos(self):return [types.SimpleNamespace(shape=(32,256,3),name='images',format=types.SimpleNamespace(order='NHWC'))]
        def get_output_vstream_infos(self):return [types.SimpleNamespace(shape=(1,64,11),name='logits',format=types.SimpleNamespace(order='NHWC'))]
    class Group:
        def create_params(self):return {}
        def activate(self,*a):return Context()
    class Device(Context):
        def configure(self,*a):return [Group()]
    class Params:
        @staticmethod
        def make_from_network_group(group,**kwargs):
            assert kwargs['format_type']=='FLOAT32' and kwargs['quantized'] is False
            assert kwargs['timeout_ms']==200 and kwargs['queue_size']==1
            return {}
    class Pipeline(Context):
        def __init__(self,*a):pass
        def infer(self,inputs):
            assert inputs['images'].shape==(1,32,256,3)
            assert inputs['images'].max()<=1
            return {'logits':logits('2200').transpose(0,2,3,1)}
    sdk=types.SimpleNamespace(HEF=HEF,Device=types.SimpleNamespace(scan=lambda:['fake']),VDevice=Device,
        ConfigureParams=types.SimpleNamespace(create_from_hef=lambda *a,**k:{}),HailoStreamInterface=types.SimpleNamespace(PCIe=1),
        InputVStreamParams=Params,OutputVStreamParams=Params,FormatType=types.SimpleNamespace(FLOAT32='FLOAT32'),InferVStreams=Pipeline)
    monkeypatch.setitem(sys.modules,'hailo_platform',sdk)
    monkeypatch.setattr(subprocess,'run',lambda *a,**kw:types.SimpleNamespace(stdout='Architecture HAILO8L'))
    contract=dict(architecture='hailo8l',hef_sha256=sha(path),normalization='host /255; no embedded normalization')
    h=Hailo(path,contract,timeout_ms=200)
    result,timing=h.infer(np.zeros((1,3,32,256),dtype=np.float32))
    assert decode(result)['score']==2200 and len(calls)==3
    monkeypatch.setattr(subprocess,'run',lambda *a,**kw:types.SimpleNamespace(stdout='Architecture HAILO8'))
    with pytest.raises(ValueError,match='hailo8l'):Hailo(path,contract)
    with pytest.raises(ValueError):Hailo(path,dict(contract,hef_sha256='wrong'))
    with pytest.raises(ValueError):Hailo(path,dict(contract,normalization='unknown'))


def test_busy_hailo_does_not_move_contention_to_cpu():
    from experiments.ppal.neural_score.backends import Busy
    def deny(x):raise Busy('reserved')
    b=Backend('hailo-preferred',lambda:pytest.fail('must not use CPU on admission denial'),lambda:types.SimpleNamespace(infer=deny))
    with pytest.raises(Busy):b.infer(None)


def test_severe_blur_and_uncalibrated_logits():
    from PIL import ImageFilter
    im=Image.new('RGB',(100,32));ImageDraw.Draw(im).rectangle((40,10,45,22),fill='white')
    assert crop_quality(im.filter(ImageFilter.GaussianBlur(20)))
    assert 'uncalibrated' in decode(logits('100'))['uncertainty']


def test_review_adapter_reuses_readonly_journal_without_changing_original(tmp_path):
    from memory.evidence import EvidenceJournal,digest
    from experiments.ppal.score_observer import ScoreObserver
    from experiments.ppal.neural_score.corpus import from_reviews
    image=tmp_path/'raw.png';scene().save(image);path=tmp_path/'review.sqlite3'
    cal=reader().calibration;j=EvidenceJournal(path)
    p=ScoreObserver.review_proposal(j,image,source_episode='original-game',timestamp=1.,clock='fixture',
        proposed=100,confidence=.99,partition='training',synthetic=False,
        context=dict(source_session='session',score_channel=1,calibration_geometry_digest=digest(dict(corners=cal.corners,output_size=cal.output_size))))
    first=ScoreObserver.annotate_review(j,p.id,annotator='fixture-human',verdict='correct',value=100,reason='engineering fixture; not authentic gameplay',independent=True)
    ScoreObserver.annotate_review(j,p.id,annotator='fixture-human',verdict='correct',value=2200,reason='fixture supersession',independent=True,supersedes=first.id)
    j.close();before=sha(path);j=EvidenceJournal(path,read_only=True)
    try:r=from_reviews(j,cal,tmp_path/'corpus')
    finally:j.close()
    assert len(r['rows'])==1 and r['rows'][0]['label']=='2200'
    assert r['rows'][0]['reviewer']=='fixture-human' and sha(path)==before


def test_quantization_drift_does_not_disappear_in_tracker():
    from experiments.ppal.neural_score.evaluate import quantization_comparison
    a=logits('100');b=logits('1100')
    assert quantization_comparison(a,a)['maximum_absolute_logit_error']==0
    report=quantization_comparison(a,b);assert not report['accepted_digits_match'] and report['maximum_absolute_logit_error']>0
    with pytest.raises(ValueError):quantization_comparison(a,b[:,:,:,:4])


def test_channels_cannot_split_same_original_across_roles(tmp_path):
    a=row(tmp_path,0);b=row(tmp_path,3,role='test')
    a['source_image_sha256']=b['source_image_sha256']='same original raw frame'
    with pytest.raises(ValueError,match='full-frame'):freeze([a,b],tmp_path/'bad.json')


def test_score_queue_overflow_shutdown_is_bounded(tmp_path):
    import threading
    from experiments.ppal.score_observer import ScoreObserver
    ready=threading.Event();release=threading.Event()
    class Slow:
        def read(self,im):
            ready.set();release.wait(1.)
            from experiments.ppal.robotron_hud import RobotronHUDObservation
            return RobotronHUDObservation(None,None,0.,0.)
    observer=ScoreObserver(reader().calibration,tmp_path/'scores.jsonl',reader_factory=lambda c:Slow())
    observer.submit(scene(),timestamp=1.,sample=1,preceding_action=None);assert ready.wait(.5)
    for sample in range(2,8):observer.submit(scene(),timestamp=float(sample),sample=sample,preceding_action=None)
    assert observer.queue.qsize()<=2 and observer.dropped>=3
    release.set();observer.close();observer.close();assert not observer.thread.is_alive()
