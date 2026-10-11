"""Accelerated clocks and controllerless evidence: no physical acceptance claims."""
import json
import sys
import pytest
from experiments.ppal.progress_supervision import Progress,WorkWatchdog,supervise
from memory.episode_identity import artifact_manifest
from memory.evidence import EvidenceJournal
from experiments.ppal.game_evidence import preserve_game
from experiments.ppal.marathon_robotron import safe_to_restart
from test_marathon_camera_session import completed


def test_completed_work_survives_more_than_ninety_seconds(tmp_path):
    clock=[0.]
    p=Progress(tmp_path/'progress.json',clock=lambda:clock[0])
    p.enter('finalizing');p.operation('capture_identity_verification')
    watch=WorkWatchdog()
    assert watch.observe(p.data,0.,processing=90.) is None
    for n in range(1,37):
        clock[0]=n*10.
        p.checkpoint({'artifact_verified':n})
        assert watch.observe(p.data,clock[0],processing=90.) is None
    assert clock[0]==360.
    assert watch.observe(p.data,451.,processing=90.)=='processing_stall'


def test_unchanged_reports_phase_resets_and_invalid_counters_do_not_refresh(tmp_path):
    p=Progress(tmp_path/'p.json',clock=lambda:0.)
    p.enter('finalizing');p.operation('journal_commit')
    watch=WorkWatchdog();watch.observe(p.data,0.,processing=90.)
    for now in range(1,91):
        p.update(updated_at=now,phase_started_at=now,work_completed_at=now)
        assert watch.observe(p.data,float(now),processing=90.) is None
    assert watch.observe(p.data,91.,processing=90.)=='processing_stall'
    for counter in (float('nan'),float('inf'),'999999',-1):
        assert watch.observe({**p.data,'work_sequence':counter},92.,processing=90.)=='processing_stall'


@pytest.mark.parametrize('productive',[True,False])
def test_real_supervisor_counts_work_not_writes(tmp_path,productive):
    path=tmp_path/'p.json'
    body=("import time\nfrom experiments.ppal.progress_supervision import Progress\n"
          f"p=Progress({str(path)!r})\np.enter('finalizing');p.operation('capture_hash')\n"
          "for n in range(12):\n " +
          ("p.checkpoint({'chunk':n});p.operation_completed()" if productive else "p.update(work_completed_at=time.monotonic())")+
          "\n time.sleep(.04)\n")
    rc=supervise([sys.executable,'-c',body],path,processing=.15,silence=2.,poll=.01,grace=.2)
    result=json.loads(path.with_name('p-supervisor.json').read_text())
    assert rc==(0 if productive else 124)
    assert result['last_progress']['operation']=='capture_hash'
    assert result['reaped']
    if not productive:assert result['reason']=='processing_stall'


def test_hash_progress_retains_identical_manifest(tmp_path):
    for n in range(636):(tmp_path/f'frame-{n:04d}.bin').write_bytes(bytes([n%256])*17)
    expected=artifact_manifest(tmp_path)
    events=[]
    assert artifact_manifest(tmp_path,on_progress=events.append)==expected
    assert sum(e['operation']=='artifact_hash_complete' for e in events)==636


def test_interrupted_commit_reconciles_once_and_never_changes_originals(tmp_path):
    root=tmp_path/'game';report=completed(root)
    original=artifact_manifest(root)
    journal=EvidenceJournal(tmp_path/'games.sqlite3')
    def interrupt(name):
        if name=='game_completion_journal_commit':raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        preserve_game(journal,root,marathon=tmp_path,returncode=0,report=report,on_operation=interrupt)
    assert not journal.records('game_completion')
    journal.close()
    journal=EvidenceJournal(tmp_path/'games.sqlite3');events=[]
    first=preserve_game(journal,root,marathon=tmp_path,returncode=0,report=report,on_progress=events.append)
    assert first['classification']=='completed'
    again=preserve_game(journal,root,marathon=tmp_path,returncode=0,report=report,on_progress=events.append)
    assert again['record_id']==first['record_id']
    assert len(journal.records('game_completion'))==1
    assert artifact_manifest(root)==original
    assert any(e.get('operation')=='game_completion_committed' for e in events)
    journal.close()
    # Durable receipt alone never authorizes START without independent terminal evidence.
    assert not safe_to_restart({**report,'episode_end':{'confirmed':False}},0,capture_root=root)
    (root/'report.json').write_text('{}')
    assert not safe_to_restart(report,0,capture_root=root)


def test_marathon_interrupt_after_completed_worker_retains_returncode(tmp_path,monkeypatch):
    from experiments.ppal import marathon_robotron as m,game_evidence as ge
    from test_experiment_return import gateway
    from test_marathon_deferred import args
    a=args(tmp_path)
    real=ge.preserve_game;calls=[]
    def driver(cmd,timeout):
        root=__import__('pathlib').Path(cmd[cmd.index('--output')+1])
        calls.append(root);completed(root);return 0
    def interrupted(*values,**options):
        if len(calls)==1 and not getattr(interrupted,'raised',False):
            interrupted.raised=True;raise KeyboardInterrupt()
        return real(*values,**options)
    monkeypatch.setattr(ge,'preserve_game',interrupted)
    monkeypatch.setattr(m,'reflect_marathon',lambda *v,**kw:{'phase':'checkpointed'})
    doc=m.developmental_marathon(a,driver=driver,gateway=gateway(tmp_path))
    assert len(calls)==1 # interrupted handoff does not authorize next START
    assert doc['completion_counts']['completed']==1
    j=EvidenceJournal(a.learning_root/'game-evidence.sqlite3',read_only=True)
    assert j.records('game_completion')[0].data['payload']['returncode']==0
    assert len(j.records('game_completion'))==1;j.close()


def test_progress_owner_handoff_preserves_sequence_and_offline_units(tmp_path):
    clock=[0.];path=tmp_path/'progress.json'
    first=Progress(path,clock=lambda:clock[0]);first.enter('finalizing')
    first.operation_completed()
    watch=WorkWatchdog();watch.observe(first.data,0.,processing=90.)
    clock[0]=60.
    second=Progress(path,clock=lambda:clock[0]);second.enter('processing')
    second.checkpoint({'operation':'offline_committed_work'})
    second.operation_completed()
    assert second.data['work_sequence']>first.data['work_sequence']
    assert watch.observe(second.data,60.,processing=90.) is None
    assert watch.observe(second.data,140.,processing=90.) is None
    second.update(processing_units=1) # backwards-compatible committed units
    assert watch.observe(second.data,140.,processing=90.) is None
    assert watch.observe(second.data,231.,processing=90.)=='processing_stall'
