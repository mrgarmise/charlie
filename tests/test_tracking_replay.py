import json

import pytest
from experiments.ppal.eyes.detectors import Detection
from experiments.ppal.robotron_agency import VisualAgency
from experiments.ppal.replay_tracking import replay


def test_replay_reproduces_exact_boxes_clocks_configuration_and_assignments(tmp_path):
    visual=VisualAgency(); rows=[]
    for tick in range(5):
        pairs=[(Detection('unknown',(10+tick,50),(0,0,10,20),100),{'class_scores':{'player':.1}})]
        row=visual.observe(pairs,'E' if tick else None,observed_at=1+tick*.15)
        rows.append({'sample':visual.tick,**row})
    path=tmp_path/'agency.jsonl';path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    result=replay(path)
    assert result['assignments_match'] and result['samples']==5 and result['tracks_created']==1
    rows[-1]['tracking']['detections'][0]['track_id']=999
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    result=replay(path)
    assert not result['assignments_match'] and len(result['mismatches'])==1


def test_legacy_incomplete_inputs_do_not_claim_exact_replay(tmp_path):
    path=tmp_path/'agency.jsonl';path.write_text(json.dumps({'sample':2,'evidence':[]})+'\n')
    with pytest.raises(ValueError,match='legacy endpoint'):replay(path)
