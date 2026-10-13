"""Real filesystem/Git/SQLite release controls; no hardware or service writes."""
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import pytest
from charlie_ops import operator as ops
from memory.evidence import EvidenceJournal


def notebook(tmp_path):
    state=tmp_path/'history';state.mkdir()
    (state/'offline.lock').touch()
    j=EvidenceJournal(state/'learning-evidence.sqlite3')
    row=j.append('event',dict(category='historical_failure',reason='preserve original failure'),episode='original',producer='engineering-fixture',version='test-v1')
    j.close()
    (state/'meditations'/'retained-commission').mkdir(parents=True)
    (state/'meditations'/'retained-commission'/'checkpoint.json').write_text(json.dumps(dict(commission_id='retained-commission')))
    return state,row.id


def git(repo,*args):
    return subprocess.check_output(['git',*args],cwd=repo,text=True).strip()


@pytest.fixture
def repository(tmp_path):
    repo=tmp_path/'repo';repo.mkdir();git(repo,'init')
    git(repo,'config','user.name','Engineering Test');git(repo,'config','user.email','test@example.invalid')
    (repo/'release').mkdir();(repo/'release'/'capabilities.json').write_text(json.dumps(dict(version='test',physical=False)))
    (repo/'main.py').write_text('raise SystemExit(0)\n');git(repo,'add','.');git(repo,'commit','-m','first')
    first=git(repo,'rev-parse','HEAD');git(repo,'update-ref','refs/remotes/origin/master',first)
    (repo/'main.py').write_text('raise SystemExit(1)\n');git(repo,'commit','-am','second')
    second=git(repo,'rev-parse','HEAD');git(repo,'update-ref','refs/remotes/origin/master',second)
    return repo,first,second


def test_real_release_stage_deploy_rollback_preserves_state(repository,tmp_path,monkeypatch):
    repo,first,second=repository;root=tmp_path/'installed';state,anchor=notebook(tmp_path)
    original=ops.hash_file(state/'learning-evidence.sqlite3')
    monkeypatch.setattr(ops,'ROOT',repo)
    ops.stage(repo,first,root);ops.stage(repo,second,root)
    with pytest.raises(ValueError,match='approved'):ops.deploy(root,first)
    ops.deploy(root,first,approved=True);ops.deploy(root,second,approved=True)
    report=ops.status(state,root)
    assert report['source']['commit']==second and report['installed']['commit']==second
    assert report['notebook']['identity_anchor_first_record']==anchor
    assert report['master']['installed_only_and_master_only_commit_counts']=='0\t0'
    assert ops.deploy(root,rollback=True,approved=True)['commit']==first
    assert (root/'current').resolve()==root/'releases'/first
    assert ops.hash_file(state/'learning-evidence.sqlite3')==original
    assert not report['authorization'].get('physical_authorization')


def test_tampered_release_cannot_deploy_or_replace_existing_pointer(repository,tmp_path):
    repo,first,second=repository;root=tmp_path/'installed'
    ops.stage(repo,first,root);ops.stage(repo,second,root);ops.deploy(root,first,approved=True)
    (root/'releases'/second/'main.py').write_text('tampered')
    with pytest.raises(ValueError,match='integrity'):ops.deploy(root,second,approved=True)
    assert (root/'current').resolve()==root/'releases'/first


def test_untracked_release_files_and_existing_directory_fail_closed(repository,tmp_path):
    repo,first,_=repository;root=tmp_path/'installed';ops.stage(repo,first,root)
    p=root/'releases'/first/'unreviewed.py';p.write_text('unreviewed')
    with pytest.raises(ValueError,match='file set'):ops.deploy(root,first,approved=True)
    p.unlink();(root/'current').mkdir()
    with pytest.raises(ValueError,match='managed symlink'):ops.deploy(root,first,approved=True)


def test_staging_requires_exact_published_source_and_never_overwrites(repository,tmp_path):
    repo,first,_=repository;root=tmp_path/'installed'
    with pytest.raises(ValueError,match='exact'):ops.stage(repo,'master',root)
    ops.stage(repo,first,root)
    with pytest.raises(FileExistsError):ops.stage(repo,first,root)
    git(repo,'update-ref','-d','refs/remotes/origin/master')
    with pytest.raises(ValueError,match='remote'):ops.stage(repo,first,tmp_path/'other')


def test_backup_preserves_ids_checkpoints_and_detects_corruption(tmp_path):
    state,anchor=notebook(tmp_path);destination=tmp_path/'backup'
    original={str(p.relative_to(state)):ops.hash_file(p) for p in state.rglob('*') if p.is_file()}
    assert ops.backup(state,destination)['identity']==anchor
    assert ops.verify_backup(destination)['verified']
    assert original=={str(p.relative_to(state)):ops.hash_file(p) for p in state.rglob('*') if p.is_file()}
    assert json.loads((destination/'meditations'/'retained-commission'/'checkpoint.json').read_text())['commission_id']=='retained-commission'
    (destination/'meditations'/'retained-commission'/'checkpoint.json').write_text('{}')
    with pytest.raises(ValueError,match='integrity'):ops.verify_backup(destination)


def test_active_executive_lock_and_symlink_evidence_refuse_backup(tmp_path):
    state,_=notebook(tmp_path)
    with (state/'offline.lock').open('rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):ops.backup(state,tmp_path/'backup')
    (state/'external').symlink_to(tmp_path/'outside')
    with pytest.raises(ValueError,match='symlink'):ops.backup(state,tmp_path/'backup')


def test_absent_state_status_never_invents_runtime_or_notebook(tmp_path,monkeypatch):
    monkeypatch.setattr(ops,'processes',lambda:[])
    r=ops.status(tmp_path/'missing',tmp_path/'release')
    assert r['installed'] is None and r['running']==[] and not r['notebook']['exists']
    assert not (tmp_path/'missing').exists()
    assert ops.readiness(tmp_path/'missing',tmp_path/'release')['offline_ready'] is False


def test_worktree_inventory_preserves_unique_work(repository,tmp_path):
    repo,_,_=repository;(repo/'untracked.txt').write_text('unique')
    rows=ops.worktrees(repo)
    assert rows[0]['cleanup_eligible'] is False and 'untracked.txt' in rows[0]['uncommitted']
    assert (repo/'untracked.txt').read_text()=='unique'


def test_default_main_is_offline_and_imports_no_controller():
    import main
    assert main.parser().parse_args([]).offline is True
    assert main.parser().parse_args(['--hardware']).offline is False
    out=subprocess.check_output([sys.executable,'-c',"import main,sys; assert 'hardware.rp2040_controller' not in sys.modules; assert main.parser().parse_args([]).offline"],text=True)
    assert out==''


def test_hashing_real_meditation_input_yields_before_next_chunk(tmp_path):
    from learning.datasets import sha
    from learning.resources import ThermalSuspended
    p=tmp_path/'tracks.json';p.write_bytes(b'a'*(3*1024*1024));checks=[]
    def probe():
        checks.append(True)
        if len(checks)==2:raise ThermalSuspended('hot during source verification')
    with pytest.raises(ThermalSuspended):sha(p,check=probe)
    assert len(checks)==2
    assert sha(p)==hashlib.sha256(p.read_bytes()).hexdigest()


def test_integrated_thermal_guard_reaps_real_unresponsive_evaluator_worker(tmp_path):
    """Injected heat, real CPU child and escalation; no authentic thermal claim."""
    from learning.resources import ResourceGuard,DevelopmentResources,ThermalSuspended
    from experiments.ppal.progress_supervision import supervise
    import os,signal
    ready=tmp_path/'ready';script=tmp_path/'offline-evaluator.py'
    script.write_text("import os,signal\nfrom pathlib import Path\nsignal.signal(signal.SIGINT,signal.SIG_IGN)\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\nPath("+repr(str(ready))+").write_text(str(os.getpid()))\nwhile True: sum(range(1000))\n")
    guard=ResourceGuard(DevelopmentResources(require_thermal=True),owner=lambda:False,
        thermal_reader=lambda:75. if ready.exists() else 60.,memory_reader=lambda:(0,0))
    with pytest.raises(ThermalSuspended):
        supervise([sys.executable,str(script)],tmp_path/'evaluation-progress.json',on_poll=lambda:guard.check(force=True),
                  poll=.02,grace=.1,budget=5)
    pid=int(ready.read_text());report=json.loads((tmp_path/'evaluation-progress-supervisor.json').read_text())
    assert report['reason']=='resource_preemption' and report['reaped'] and report['last_progress'] is None
    with pytest.raises(ProcessLookupError):os.kill(pid,0)
    assert guard.suspended and guard.resume_count==0
