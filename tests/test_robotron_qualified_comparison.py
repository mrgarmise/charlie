import json
import pytest
from learning.datasets import sha
from experiments.comparison.robotron import commit,evaluate,validate_certificates
from test_robotron_score_comparison import setup,records


def certified(j,protocol,tmp_path):
    proof=tmp_path/'proof.txt';proof.write_text('controlled independent measurement proof, no physical game')
    source=tmp_path/'report.json';source.write_text(json.dumps({'controlled_game':1}))
    frames=[]
    for n in range(2):
        path=tmp_path/f'terminal-{n}.png';path.write_bytes(f'controlled terminal capture {n}'.encode())
        frames.append(dict(path=str(path),sha256=sha(path),timestamp=float(n)))
    episode='episode:'+sha(source)
    start=tmp_path/'start.png';start.write_bytes(b'controlled new game start')
    def add(p):
        return j.append('observation',dict(p,status='verified',source_episode=episode,
            qualification_artifact=dict(path=str(proof),sha256=sha(proof))),
            episode=protocol.data['episode'],producer='independent-physical-measurement',version='controlled')
    boundary=add(dict(category='complete_game_boundary',complete_game=True,end_reason='GAME OVER',
        terminal_frames=frames,source_report=dict(path=str(source),sha256=sha(source)),
        start_state='new_game',start_frame=dict(path=str(start),sha256=sha(start),timestamp=-1.),
        protocol_id=protocol.id,slot=0,policy=protocol.data['payload']['schedule'][0]['policy']))
    score=add(dict(category='official_score_measurement',value=1200,phase='final',timestamp=1.,
        artifact_sha256=frames[1]['sha256'],boundary_certificate=boundary.id))
    row=dict(category='robotron_evaluation_episode',source_episode=episode,boundary_certificate=boundary.id,
        confirmed_terminal=True,slot=0,policy=protocol.data['payload']['schedule'][0]['policy'],
        conditions=protocol.data['payload']['conditions'],score_observations=[dict(value=1200,phase='final',timestamp=1.,
            qualification='independently_validated',artifact_sha256=frames[1]['sha256'],validation_evidence=score.id)])
    return row,frames,proof


def test_new_protocol_rejects_unresolved_qualification_strings(tmp_path):
    j,plan,old=setup(tmp_path)
    source=old.data['sources']
    p=commit(j,plan,conditions=old.data['payload']['conditions'],sources=source,episode=old.data['episode'])
    assert p.data['payload']['require_certificates'] is True
    result=evaluate(j,p.id,plan,records(j,p)).data['payload']['report']
    assert result['status']=='inconclusive' and len(result['failures'])==4
    with pytest.raises(ValueError,match='require certificates'):
        commit(j,plan,conditions=old.data['payload']['conditions'],sources=source,
               episode=old.data['episode'],require_certificates=False)


def test_exact_independent_certificate_and_capture_binding(tmp_path):
    j,plan,p=setup(tmp_path)
    row,frames,proof=certified(j,p,tmp_path)
    validate_certificates(j,row)
    row['score_observations'][0]['timestamp']=0.
    with pytest.raises(ValueError):validate_certificates(j,row)
    row['score_observations'][0]['timestamp']=1.
    proof.write_text('changed')
    with pytest.raises(ValueError,match='proof'):validate_certificates(j,row)


@pytest.mark.parametrize('change',['frame','episode','timeout','missing-boundary'])
def test_boundary_failure_is_inconclusive(tmp_path,change):
    j,plan,p=setup(tmp_path);row,frames,proof=certified(j,p,tmp_path)
    if change=='frame':open(frames[1]['path'],'wb').write(b'changed')
    if change=='episode':row['source_episode']='renamed-game'
    if change=='missing-boundary':row.pop('boundary_certificate')
    if change=='timeout':
        boundary=j.get(row['boundary_certificate']).data['payload'];boundary['end_reason']='TIME LIMIT'
        row['boundary_certificate']=j.append('observation',boundary,episode=p.data['episode'],
            producer='independent-physical-measurement',version='controlled').id
    with pytest.raises((ValueError,KeyError)):validate_certificates(j,row)
