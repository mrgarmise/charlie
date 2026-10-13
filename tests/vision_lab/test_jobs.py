"""Real worker lifecycle and ML controls; generated fixtures are never Robotron evidence."""
import json
import os
from pathlib import Path
import time
import pytest
from vision_lab.demo import create,wait
from vision_lab.store import file_hash,Lab
from vision_lab.jobs import Jobs


def test_queued_cancellation_validation_and_restart(tmp_path):
    lab,m=create(tmp_path/'fixture');jobs=Jobs(lab)
    try:
        with pytest.raises(ValueError):jobs.submit('train',dict(dataset_id=m['id'],epochs=True))
        with pytest.raises(ValueError):jobs.submit('index',dict(source_id='x',deadline_seconds=float('nan')))
        job=jobs.submit('index',dict(source_id=lab.items('sources')[0]['id']));jobs.cancel(job['id'])
        end=time.monotonic()+10
        while lab.get('jobs',job['id'])['status'] not in ('cancelled','completed') and time.monotonic()<end:time.sleep(.1)
        row=lab.get('jobs',job['id'])
        if row['status']=='cancelled':assert wait(lab,jobs.restart(job['id']),30)['counts']['unchanged']==8
        assert row['status'] in ('cancelled','completed')
    finally:jobs.close()


@pytest.mark.skipif(os.environ.get('VISION_LAB_ML_TESTS')!='1',reason='Set VISION_LAB_ML_TESTS=1 with optional CPU ML dependencies for real optimizer/export tests')
def test_real_train_frozen_baseline_evaluate_export_and_no_activation(tmp_path):
    from vision_lab.adapter import CandidateDetector
    from experiments.ppal.eyes.pipeline import VisionPipeline
    from PIL import Image
    lab,m=create(tmp_path/'fixture');jobs=Jobs(lab)
    p=dict(dataset_id=m['id'],epochs=1,imgsz=64,batch=2,threads=2,device='cpu')
    try:
        first=wait(lab,jobs.submit('train',dict(p)),180)
        assert first['optimizer_steps']>0 and first['initial_weights_sha256']!=first['trained_weights_sha256']
        p.update(epochs=2,baseline_id=first['id']);second=wait(lab,jobs.submit('train',p),180)
        assert second['parameters']['baseline_sha256']==first['checkpoint_sha256']
        result=wait(lab,jobs.submit('evaluate',dict(model_id=second['id'],dataset_id=m['id'],partition='test',baseline_id=first['id'])),60)
        assert result['candidate']['samples']==2 and result['baseline']['samples']==2 and result['authenticity']=='synthetic-fixture'
        assert lab.annotation(m['frames'][0]['frame_id'])['revision']==1
        with pytest.raises(ValueError,match='already exposed'):jobs.submit('train',p)
        exported=wait(lab,jobs.submit('export',dict(model_id=second['id'])),120)
        assert exported['export_check']['onnxruntime_checked'] and exported['target']=='hailo8l' and not exported['hef_created']
        assert (lab.root/'models'/second['id']/'deployment.zip').stat().st_size>1000
        from vision_lab.sources import add_source,index_source
        extra=tmp_path/'new-SYNTHETIC-observations';extra.mkdir()
        Image.new('RGB',(96,96),(9,80,120)).save(extra/'new.png')
        source=add_source(lab,dict(root=str(extra),authenticity='synthetic-fixture'))
        index_source(lab,source['id']);fresh=lab.frames(source['id'])[0]
        suggested=wait(lab,jobs.submit('suggest',dict(model_id=second['id'],frame_ids=[fresh['id']])),60)
        assert suggested['proposals'][0]['source_frame_id']==fresh['id']
        assert lab.annotation(fresh['id'])['revision']==0
        assert lab.get('suggestions',fresh['id'])['physical_authorization'] is False
        held=next(f for f in m['frames'] if f['role']=='test')
        with pytest.raises(RuntimeError,match='Held-out'):
            wait(lab,jobs.submit('suggest',dict(model_id=second['id'],frame_ids=[held['frame_id']])),60)
        detector=CandidateDetector(lab,second['id']);r=m['frames'][0]
        with Image.open(lab.root/'pixels'/(r['pixel_sha']+'.png')) as im:
            packet=detector.observe(im,source_frame_id=r['frame_id'],timestamp=r['timestamp']);view=VisionPipeline(detector).process(im,1)
        assert packet['observation_only'] and packet['physical_authorization'] is False and view.world is None
        assert 'OBSERVATION ONLY' in view.status
        old_model_bytes=file_hash(lab.root/'models'/first['id']/'best.pt')
        assert old_model_bytes==first['checkpoint_sha256']
    finally:jobs.close()


@pytest.mark.skipif(os.environ.get('VISION_LAB_ML_TESTS')!='1',reason='Optional real CPU cancellation/resume test')
def test_real_cancel_preserves_epoch_and_resumes_in_new_job(tmp_path):
    lab,m=create(tmp_path/'fixture');jobs=Jobs(lab)
    try:
        job=jobs.submit('train',dict(dataset_id=m['id'],epochs=10,imgsz=64,batch=2,threads=2,device='cpu'))
        end=time.monotonic()+120
        while time.monotonic()<end:
            row=lab.get('jobs',job['id'])
            if row.get('progress',{}).get('epoch',0)>=1:break
            if row['status']=='failed':pytest.fail(row['error'])
            time.sleep(.02)
        assert row.get('progress',{}).get('epoch',0)>=1
        jobs.cancel(job['id'])
        end=time.monotonic()+15
        while lab.get('jobs',job['id'])['status']!='cancelled' and time.monotonic()<end:time.sleep(.05)
        assert lab.get('jobs',job['id'])['status']=='cancelled'
        checkpoint=lab.root/'jobs'/job['id']/'run'/'weights'/'last.pt';sha=file_hash(checkpoint)
        restarted=jobs.restart(job['id']);assert restarted['parameters']['resume_sha256']==sha
        result=wait(lab,restarted,180)
        assert result['optimizer_steps']>0 and result['job_id']!=job['id']
        assert file_hash(checkpoint)==sha # Source checkpoint is not overwritten by resume.
    finally:jobs.close()


def test_restart_marks_stale_job_and_refuses_competing_worker(tmp_path):
    import fcntl
    lab,_=create(tmp_path/'fixture')
    lab.put('jobs','retained',dict(id='retained',status='running',kind='index',parameters={},worker_pid=999999999))
    jobs=Jobs(lab)
    try:assert lab.get('jobs','retained')['status']=='interrupted'
    finally:jobs.close()
    with (lab.root/'worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(RuntimeError,match='second scheduler'):Jobs(lab)


def test_unknown_process_identity_never_signalled(tmp_path,monkeypatch):
    from vision_lab.jobs import own_worker,stop_retained
    import os
    called=[];monkeypatch.setattr(os,'killpg',lambda *a:called.append(a))
    job=dict(id='synthetic',worker_pid=os.getpid(),worker_start_ticks='wrong-process-generation')
    assert not own_worker(job,tmp_path)
    stop_retained(job,tmp_path);assert called==[]
