"""Deferred review software fixtures; no physical games or certified scores."""
import json
from pathlib import Path
from PIL import Image
from memory.evidence import EvidenceJournal
from experiments.ppal.score_observer import ScoreObserver


def game(root,n=1,*,photo=True):
    root.mkdir(parents=True)
    (root/'report.json').write_text(json.dumps(dict(simulation=True,result='GAME OVER',
        score=n*100,episode_end=dict(confirmed=True,evidence=dict(terminal_capture_timestamps=[float(n)])),
        planning_mode='fixture-policy',session_timing=dict(started_at=0.,stopped_at=float(n)+1))))
    if photo:
        Image.new('RGB',(20,20),(n%256,20,40)).save(root/'original.png')
        (root/'score.jsonl').write_text(json.dumps(dict(timestamp=float(n),observation_id='fixture-camera-'+str(n),
            raw_frame='original.png',p1=dict(observed_score=n*100,confidence=.9)))+'\n')
    return root


def test_thirty_attempts_are_queued_without_review_and_missing_image_survives(tmp_path):
    j=EvidenceJournal(tmp_path/'journal.sqlite3')
    for n in range(1,31):
        root=game(tmp_path/f'game-{n}',n,photo=n!=10)
        first=ScoreObserver.queue_game(j,root,session='fixture-session',number=n,synthetic=True)
        assert ScoreObserver.queue_game(j,root,session='fixture-session',number=n,synthetic=True).id==first.id
    records=j.category_records('observation','score_game_record')
    assert len(records)==30 and len(j.category_records('observation','score_review_proposal'))==29
    assert records[9].data['payload']['proposal_id'] is None
    assert all(r.data['payload']['physical_authorization'] is False for r in records)
    assert not j.category_records('observation','score_human_annotation')
    j.verify();j.close()


def test_interrupted_attempt_remains_and_original_score_not_rewritten(tmp_path):
    j=EvidenceJournal(tmp_path/'journal.sqlite3');root=tmp_path/'missing'
    first=ScoreObserver.queue_game(j,root,session='fixture',number=1,interrupted=True)
    assert first.data['payload']['result']=='interrupted'
    game(root)
    later=ScoreObserver.queue_game(j,root,session='fixture',number=1,synthetic=True)
    assert later.data['payload']['previous']==first.id
    proposal=j.get(later.data['payload']['proposal_id'])
    before=proposal.document
    annotation=ScoreObserver.annotate_review(j,proposal.id,annotator='fixture reviewer',verdict='correct',value=200,
        reason='fixture correction',independent=True)
    ScoreObserver.annotate_review(j,proposal.id,annotator='fixture reviewer',verdict='correct',value=300,
        reason='later fixture correction',independent=True,supersedes=annotation.id)
    assert j.get(proposal.id).document==before
    assert len(j.category_records('observation','score_human_annotation'))==2
    j.close()


def test_batch_review_restart_filters_and_missing_original(tmp_path):
    from experiments.ppal.inspect_robotron_score import queue_rows,review_game
    path=tmp_path/'journal.sqlite3';j=EvidenceJournal(path)
    first=ScoreObserver.queue_game(j,game(tmp_path/'one'),session='fixture',number=1,synthetic=True)
    second=ScoreObserver.queue_game(j,game(tmp_path/'two',2,photo=False),session='fixture',number=2,synthetic=True)
    original=j.get(first.data['payload']['proposal_id']).document
    review_game(j,first.id,annotator='fixture',verdict='confirm',independent=True)
    review_game(j,second.id,annotator='fixture',verdict='insufficient')
    assert [p['review_status'] for p in queue_rows(j)]==['confirmed','insufficient']
    j.close();j=EvidenceJournal(path)
    assert [p['review_status'] for p in queue_rows(j)]==['confirmed','insufficient']
    review_game(j,first.id,annotator='fixture',verdict='correct',value=700,independent=True)
    assert queue_rows(j)[0]['review_status']=='corrected'
    assert j.get(first.data['payload']['proposal_id']).document==original
    Image.new('RGB',(20,20),'red').save(tmp_path/'one'/'original.png')
    import pytest
    with pytest.raises(ValueError,match='changed'):review_game(j,first.id,annotator='fixture',verdict='confirm')
    j.close()


def test_aliases_do_not_inflate_queue_or_qualified_averages(tmp_path):
    import shutil
    from experiments.ppal.inspect_robotron_score import queue_rows,performance_history
    root=game(tmp_path/'one');(root/'capture-origin.json').write_text(json.dumps({'capture_id':'explicit-software-capture'}))
    shutil.copytree(root,tmp_path/'alias')
    j=EvidenceJournal(tmp_path/'journal.sqlite3')
    for n,r in enumerate((root,tmp_path/'alias'),1):ScoreObserver.queue_game(j,r,session='fixture',number=n,synthetic=True)
    assert len(queue_rows(j))==1
    assert performance_history(j)=={} # reported GAME OVER and high confidence do not qualify
    j.close()


def test_http_batch_review_preserves_originals_and_restart(tmp_path):
    """Real loopback HTTP transport, synthetic pictures; no browser or gameplay."""
    import subprocess,sys,urllib.request,urllib.error,re,socket,time
    from experiments.ppal.inspect_robotron_score import queue_rows
    path=tmp_path/'journal.sqlite3';j=EvidenceJournal(path)
    for n in range(1,31):ScoreObserver.queue_game(j,game(tmp_path/str(n),n,photo=n!=10),session='fixture',number=n,synthetic=True)
    j.close()
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    script='from experiments.ppal.inspect_robotron_score import serve_review;import sys;serve_review(sys.argv[1],port=int(sys.argv[2]))'
    process=subprocess.Popen([sys.executable,'-c',script,str(path),str(port)],stdout=subprocess.PIPE)
    base=f'http://127.0.0.1:{port}'
    try:
        for _ in range(100):
            try:
                page=urllib.request.urlopen(base,timeout=1).read().decode();break
            except (OSError,urllib.error.URLError):time.sleep(.02)
        else:raise AssertionError('HTTP review server did not start')
        token=re.search(r"const token='([^']+)'",page)
        if not token:token=re.search(r'const TOKEN="([^"]+)"',page)
        assert token,'rendered review token required'
        rows=json.load(urllib.request.urlopen(base+'/queue'))['games'];assert len(rows)==30
        row=rows[4]
        raw=urllib.request.urlopen(base+'/image?id='+row['proposal_id']).read()
        assert raw==(tmp_path/'5'/'original.png').read_bytes()
        data=json.dumps(dict(id=row['id'],annotator='fixture',verdict='correct',value=1234)).encode()
        req=urllib.request.Request(base+'/review',data=data,headers={'X-Review-Token':token.group(1),'Content-Type':'application/json'})
        assert urllib.request.urlopen(req).status==200
        try:urllib.request.urlopen(urllib.request.Request(base+'/review',data=data))
        except urllib.error.HTTPError as exc:assert exc.code==403
        else:raise AssertionError('missing token accepted')
    finally:
        process.terminate();process.wait(timeout=5)
    j=EvidenceJournal(path);rows=queue_rows(j)
    assert rows[4]['review_status']=='corrected' and rows[4]['proposed_score']==500
    assert rows[4]['annotations'][0]['value']==1234
    j.verify();j.close()


def test_review_cannot_mutate_sealed_source_and_annotation_is_atomic(tmp_path):
    from experiments.ppal.inspect_robotron_score import review_game
    import pytest
    root=game(tmp_path/'original');j=EvidenceJournal(root/'session-evidence.sqlite3')
    row=ScoreObserver.queue_game(j,root,session='fixture',number=1,synthetic=True)
    before=[r.id for r in j.records()]
    (root/'capture-manifest.json').write_text('{}')
    with pytest.raises(ValueError,match='sealed'):review_game(j,row.id,annotator='fixture',verdict='confirm')
    assert [r.id for r in j.records()]==before
    j.close()


def test_legacy_alias_and_relocated_original_review(tmp_path):
    import shutil
    from experiments.ppal.inspect_robotron_score import queue_rows,review_game
    root=game(tmp_path/'one');alias=tmp_path/'alias';shutil.copytree(root,alias)
    j=EvidenceJournal(tmp_path/'j.sqlite3')
    first=ScoreObserver.queue_game(j,root,session='fixture',number=1,synthetic=True)
    ScoreObserver.queue_game(j,alias,session='fixture',number=2,synthetic=True)
    assert len(queue_rows(j))==1
    (root/'original.png').unlink()
    review_game(j,first.id,annotator='fixture',verdict='confirm')
    annotation=j.category_records('observation','score_human_annotation')[-1]
    assert annotation.data['payload']['proposal_id']==first.data['payload']['proposal_id']
    j.close()


def test_preserved_historical_photograph_bytes_and_provenance(tmp_path):
    """Historical pixels, fixture review metadata; no authentic score label."""
    import hashlib
    fixture=Path(__file__).parent/'fixtures'/'robotron-developmental'
    origin=json.loads((fixture/'provenance.json').read_text())[0]
    photo=fixture/origin['path']
    assert hashlib.sha256(photo.read_bytes()).hexdigest()==origin['sha256']
    j=EvidenceJournal(tmp_path/'j.sqlite3')
    p=ScoreObserver.review_proposal(j,photo,source_episode=origin['source_run'],timestamp=0.,
        clock='fixture metadata; original capture time unavailable',proposed=None,confidence=0.,
        synthetic=True,context={'historical_provenance':origin,'original_capture_time_available':False})
    assert ScoreObserver.review_artifact(j,p.data['payload']).read_bytes()==photo.read_bytes()
    assert p.data['payload']['artifact']['sha256']==origin['sha256']
    assert ScoreObserver.review_metrics(j,partition='diagnostic')['eligible']==0
    j.verify();j.close()


def test_supporting_originals_remain_hash_bound_and_missing_input_pending(tmp_path):
    from experiments.ppal.inspect_robotron_score import queue_rows,review_game
    root=game(tmp_path/'one');Image.new('RGB',(20,20),'purple').save(root/'other.png')
    with (root/'score.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(timestamp=2.,raw_frame='other.png',p1={'observed_score':100,'confidence':.8}))+'\n')
    j=EvidenceJournal(tmp_path/'j.sqlite3');r=ScoreObserver.queue_game(j,root,session='fixture',number=1,synthetic=True)
    assert r.data['payload']['artifact']['path'].endswith('original.png') # terminal preferred
    assert len(r.data['payload']['additional_originals'])==1
    import hashlib
    extra=r.data['payload']['additional_originals'][0]
    assert hashlib.sha256(Path(extra['path']).read_bytes()).hexdigest()==extra['sha256']
    review_game(j,r.id,annotator='fixture',verdict='confirm')
    (root/'original.png').unlink()
    later=ScoreObserver.queue_game(j,root,session='fixture',number=1,synthetic=True)
    assert later.data['payload']['proposal_id']!=r.data['payload']['proposal_id']
    assert queue_rows(j)[0]['review_status']=='pending'
    j.close()
