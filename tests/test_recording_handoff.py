"""No controller constructed: exact completion barrier and receipt corruption."""
import json
import time
from PIL import Image
from memory.episode_identity import finalize_capture
from experiments.ppal.progress_evidence import CaptureEvidence
from experiments.ppal.marathon_robotron import recording_readiness,safe_to_restart


def capture(root):
    root.mkdir();r=CaptureEvidence(root,'simulated-handoff',{})
    r.capture(Image.new('RGB',(20,20)),dict(timestamp=time.monotonic()));r.close()
    report=dict(recording_pipeline=r.telemetry(),recording_error=None,score_summary={'worker_finished':True})
    (root/'report.json').write_text(json.dumps(report));finalize_capture(root)
    return report


def test_consecutive_distinct_completed_recorders_ready_without_controller(tmp_path):
    a=capture(tmp_path/'first');b=capture(tmp_path/'second')
    assert recording_readiness(tmp_path/'first',a)['status']=='ready'
    assert recording_readiness(tmp_path/'second',b)['status']=='ready'
    assert not safe_to_restart(a,capture_root=tmp_path/'first') # receipt alone is no terminal boundary


def test_open_failed_corrupt_live_and_unfinished_score_block_next_game(tmp_path):
    report=capture(tmp_path/'first');root=tmp_path/'first'
    for mutation in ({'recording_error':'failed flush'}, {'recording_pipeline':{'writer_alive':True}}, {'score_summary':{'worker_finished':False}}):
        assert recording_readiness(root,{**report,**mutation})['status']=='blocked'
    state=json.loads((root/'recording-state.json').read_text());state['status']='incomplete'
    (root/'recording-state.json').write_text(json.dumps(state))
    assert recording_readiness(root,report)['status']=='blocked'
    assert not safe_to_restart(report)
