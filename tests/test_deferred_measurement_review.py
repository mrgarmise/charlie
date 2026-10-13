"""Synthetic interface fixtures, not independent Robotron trajectories."""
import hashlib,json,shutil
from pathlib import Path
import pytest
from PIL import Image
from memory.evidence import EvidenceJournal
from memory.evaluator import MemoryEvaluator
from learning.lifecycle import DevelopmentLifecycle
from learning.acquisition import retain_dependency_request,investigate_requests
from experiments.ppal.inspect_robotron_score import evidence_queue,review_evidence,evidence_review_artifact


def camera_episode(root):
    root.mkdir(parents=True);(root/'report.json').write_text('{}')
    j=EvidenceJournal(root/'session-evidence.sqlite3')
    for i in range(3):
        filename='original-'+str(i)+'.png';Image.new('RGB',(40,30),(20+i,30,40)).save(root/filename)
        observation=j.append('observation',dict(category='camera_observation',source_path=filename),
            episode='explicit-synthetic-episode',at=i*.15,producer='ObservedCamera',version='test',provenance={'synthetic':True})
        j.append('observation',dict(category='camera_capture',observation_id=observation.id,
            artifact=dict(path=filename,sha256=hashlib.sha256((root/filename).read_bytes()).hexdigest())),
            episode=observation.data['episode'],at=i*.15,sources=[observation.id],producer='ObservedCamera',version='test',provenance={'synthetic':True})
    j.close();return root


def setup(tmp_path):
    root=camera_episode(tmp_path/'recordings'/'game');life=DevelopmentLifecycle(tmp_path/'state',[root.parent])
    life.executive._event(dict(op='proposed',project=dict(id='existing-fixture-project',
        goal='Retained fixture temporal question',status='paused',experiment_history=[],origins=[],hypothesis_evidence=[])),[])
    bookmark=life.executive._event(dict(op='evidence_continuation',project_id='existing-fixture-project',
        original_question='Retained fixture temporal question',required_evidence=['Independent board trajectories'],
        acceptance_criteria={'interface':'existing independent_motion_corpus acquisition inbox'},physical_authorization=False),[])
    r=retain_dependency_request(life.journal,bookmark.id,work_id='existing-fixture-project',
        required_evidence=bookmark.data['payload']['required_evidence'],reason='Fixture dependency')
    investigate_requests(life.dataset,[root.parent],provenance=life.provenance)
    return life,root,r,evidence_queue(life.journal)[0]


def positions():return [dict(id='reviewer-claimed-player',role='player',positions=[[4,5],[6,5],[8,6]])]


def test_request_driven_camera_review_and_restart_immutable_correction(tmp_path):
    life,root,r,q=setup(tmp_path)
    assert q['request_id']==r.id and q['synthetic'] and len(q['frames'])==3
    assert q['original_question']=='Retained fixture temporal question'
    before=life.journal.get(q['id']).document
    a=review_evidence(life.journal,q['id'],annotator='fixture reviewer',verdict='confirm',objects=positions(),independent=True)
    assert review_evidence(life.journal,q['id'],annotator='fixture reviewer',verdict='confirm',objects=positions(),independent=True).id==a.id
    correction=positions();correction[0]['positions'][1]=[7,5]
    b=review_evidence(life.journal,q['id'],annotator='fixture reviewer',verdict='correct',objects=correction,independent=True)
    assert b.data['payload']['supersedes']==a.id and life.journal.get(q['id']).document==before
    evaluation=life.journal.category_records('observation','evidence_annotation_evaluation')[-1].data['payload']
    assert evaluation['measurements'][0]['displacement']==[3,0]
    assert evaluation['status']=='unresolved' and not evaluation['independent_motion_corpus']
    assert 'calibrated' in ' '.join(evaluation['deficiencies'])
    count=len(life.journal.records());life.close()
    life=DevelopmentLifecycle(tmp_path/'state',[root.parent]);assert evidence_queue(life.journal)[0]['review_status']=='correct'
    investigate_requests(life.dataset,[root.parent],provenance=life.provenance)
    # The first result update conveys the newly available Evaluator receipt; next is unchanged.
    assert not investigate_requests(life.dataset,[root.parent],provenance=life.provenance)
    assert len(life.journal.category_records('event','evidence_review_request'))==1
    assert not life.journal.category_records('observation','independent_motion_corpus')
    life.close()


@pytest.mark.parametrize('value',[float('nan'),float('inf'),True,-1,100])
def test_invalid_measurement_rejected(tmp_path,value):
    life,root,r,q=setup(tmp_path);objects=positions();objects[0]['positions'][0][0]=value
    with pytest.raises(ValueError):review_evidence(life.journal,q['id'],annotator='fixture',verdict='correct',objects=objects)
    assert not life.journal.category_records('observation','evidence_human_annotation');life.close()


def test_changed_original_abstention_and_aliases(tmp_path):
    life,root,r,q=setup(tmp_path);copy=root.parent/'alias';shutil.copytree(root,copy)
    investigate_requests(life.dataset,[root.parent],provenance=life.provenance)
    assert len(evidence_queue(life.journal))==1
    (root/'original-0.png').unlink()
    assert evidence_review_artifact(life.journal,q['frames'][0]['artifact'])==copy/'original-0.png'
    (copy/'original-0.png').unlink()
    with pytest.raises(ValueError):review_evidence(life.journal,q['id'],annotator='fixture',verdict='confirm',objects=positions())
    a=review_evidence(life.journal,q['id'],annotator='fixture',verdict='cannot_determine',reason='Original unavailable')
    assert a.data['payload']['verdict']=='cannot_determine'
    MemoryEvaluator.reconcile_evidence_annotations(life.journal)
    assert not life.journal.category_records('observation','independent_motion_corpus');life.close()


def test_disagreement_and_synthetic_feedback_do_not_qualify(tmp_path):
    from experiments.ppal.reflect_robotron import expose_measurement_review_contexts
    life,root,r,q=setup(tmp_path)
    review_evidence(life.journal,q['id'],annotator='one',verdict='confirm',objects=positions(),independent=True)
    other=positions();other[0]['id']='a-different-claimed-identity'
    review_evidence(life.journal,q['id'],annotator='two',verdict='correct',objects=other,independent=True)
    reports=MemoryEvaluator.reconcile_evidence_annotations(life.journal)
    assert all('disagree' in ' '.join(life.journal.get(i).data['payload']['deficiencies']) for i in reports)
    assert expose_measurement_review_contexts(life.dataset)==[]
    assert not life.journal.category_records('observation','independent_motion_corpus');life.close()


def test_real_http_shared_operator_server(tmp_path):
    import subprocess,sys,urllib.request,urllib.error,re,socket,time
    life,root,r,q=setup(tmp_path);path=life.journal.path;life.close()
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    script='from experiments.ppal.inspect_robotron_score import serve_review;import sys;serve_review(sys.argv[1],port=int(sys.argv[2]))'
    process=subprocess.Popen([sys.executable,'-c',script,str(path),str(port)],stdout=subprocess.PIPE)
    base=f'http://127.0.0.1:{port}'
    try:
        for _ in range(100):
            try:
                page=urllib.request.urlopen(base+'/evidence',timeout=1).read().decode();break
            except (OSError,urllib.error.URLError):time.sleep(.02)
        else:raise AssertionError('shared review server did not start')
        token=re.search(r"const token='([^']+)'",page).group(1)
        rows=json.load(urllib.request.urlopen(base+'/queue'))['evidence'];assert len(rows)==1
        raw=urllib.request.urlopen(base+'/image?review='+q['id']+'&frame=0').read()
        assert raw==(root/'original-0.png').read_bytes()
        data=json.dumps(dict(id=q['id'],annotator='fixture',verdict='confirm',objects=positions(),independent=True)).encode()
        response=urllib.request.urlopen(urllib.request.Request(base+'/evidence-review',data=data,
            headers={'X-Review-Token':token,'Content-Type':'application/json'}));assert response.status==200
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(urllib.request.Request(base+'/evidence-review',data=data))
        assert exc.value.code==403
    finally:process.terminate();process.wait(timeout=5)
    j=EvidenceJournal(path);assert evidence_queue(j)[0]['review_status']=='confirm'
    assert len(j.category_records('observation','evidence_annotation_evaluation'))==1;j.verify();j.close()
