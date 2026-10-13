"""Truthful local inventory and explicit, application-only release operations."""
import argparse
import contextlib
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ('numpy', 'Pillow', 'opencv-python-headless', 'pyserial', 'mpremote')
AUTH = ('CHARLIE_NECK_MOTION_AUTHORIZED', 'CHARLIE_NECK_SUPERVISED', 'CHARLIE_MOBILE_ENABLED')


def command(args, cwd=None):
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=10)
        return p.stdout.strip() if p.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def hash_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def identity(root):
    root = Path(root).resolve()
    manifest = read_json(root / 'installed-release.json')
    sha = command(['git', 'rev-parse', 'HEAD'], root) if (root / '.git').exists() else None
    return dict(path=str(root), commit=sha or (manifest or {}).get('commit'),
                branch=command(['git', 'symbolic-ref', '--short', '-q', 'HEAD'], root) if sha else None,
                tag=command(['git', 'describe', '--tags', '--exact-match'], root) if sha else None,
                dirty=bool(command(['git', 'status', '--porcelain'], root)) if sha else None,
                release=read_json(root / 'release' / 'capabilities.json'), installed_manifest=manifest)


def processes(proc=Path('/proc')):
    result = []
    for p in proc.glob('[0-9]*'):
        try:
            args = (p / 'cmdline').read_bytes().decode(errors='replace').split('\0')
            cwd = (p / 'cwd').resolve(strict=True)
            matching = any(a.endswith('/main.py') or a == 'main.py' or a.startswith('experiments.ppal.') for a in args)
            if not matching:
                continue
            script = next((a for a in args if a.endswith('/main.py') or a == 'main.py'), None)
            source = ((cwd / script).resolve().parent if script else cwd)
            if not (source / 'learning' / 'lifecycle.py').is_file():
                continue
            # Do not expose arbitrary arguments or process environments (may contain secrets).
            flags = [a for a in args if a in ('--offline', '--hardware', '--allow-offline-improvements')]
            state = None
            if '--learning-state' in args:
                state = str((cwd / args[args.index('--learning-state') + 1]).resolve())
            result.append(dict(pid=int(p.name), process_start_ticks=(p/'stat').read_text().rsplit(')',1)[1].split()[19], executable=str((p / 'exe').resolve(strict=True)),
                checkout=str(source), options=flags, learning_state=state,
                checkout_identity=identity(source),
                running_commit='unknown until matching Executive startup receipt is verified'))
        except (OSError, ValueError, IndexError):
            continue
    return result


def notebook(state):
    state = Path(state).expanduser().resolve()
    db = state / 'learning-evidence.sqlite3'
    result = dict(path=str(state), exists=db.is_file(), authoritative='operator-selected; no migration performed')
    if not db.is_file():
        return result
    with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=2) as c:
        result['records'] = c.execute('SELECT count(*) FROM records').fetchone()[0]
        first = c.execute('SELECT id FROM records ORDER BY sequence LIMIT 1').fetchone()
        result['identity_anchor_first_record'] = first[0] if first else None
        result['last_record'] = c.execute('SELECT id,committed_at FROM records ORDER BY sequence DESC LIMIT 1').fetchone()
    result['executive'] = read_json(state / 'development-status.json')
    result['operational'] = read_json(state / 'development-operational-status.json')
    checkpoints = list(state.rglob('checkpoint.json'))
    if checkpoints:
        latest = max(checkpoints, key=lambda p: p.stat().st_mtime)
        from memory.evidence import digest
        d=read_json(latest) or {}
        result['last_checkpoint'] = dict(path=str(latest), sha256=hash_file(latest), modified_at=latest.stat().st_mtime,
            state_digest_verified=d.get('state_digest')==digest({k:v for k,v in d.items() if k!='state_digest'}) if d.get('state_digest') else None)
    else:
        result['last_checkpoint'] = None
    return result


def thermal():
    samples = []
    errors = []
    for p in Path('/sys/class/thermal').glob('thermal_zone*/temp'):
        try:
            value = float(p.read_text()) / 1000
            if not 0 <= value <= 150:
                raise ValueError('invalid temperature')
            samples.append(dict(sensor=str(p), temperature_c=value))
        except (OSError, ValueError) as e:
            errors.append(dict(sensor=str(p), error=str(e)))
    return dict(samples=samples, errors=errors, latest_temperature_c=max((x['temperature_c'] for x in samples), default=None),
                observation='real local sensors only; unavailable is not a cool reading')


def status(state, release_root):
    running = processes()
    nb = notebook(state)
    op = nb.get('operational') or {}
    for row in running:
        if (row['pid'] == op.get('pid') and row['checkout'] == op.get('checkout')
                and row['process_start_ticks'] == op.get('process_start_ticks')):
            row['running_commit'] = op.get('code_revision', 'unknown')
    try:
        ticks=(Path('/proc')/str(op.get('pid'))/'stat').read_text().rsplit(')',1)[1].split()[19]
        nb['executive_process_current']=ticks==op.get('process_start_ticks') and op.get('state')!='clean shutdown'
    except (OSError,IndexError):
        nb['executive_process_current']=False
    current = Path(release_root) / 'current'
    installed = identity(current) if current.is_symlink() and current.exists() else None
    source = identity(ROOT)
    master = command(['git', 'rev-parse', 'refs/remotes/origin/master'], ROOT)
    compare = None
    installed_sha = (installed or {}).get('commit')
    if master and installed_sha:
        compare = command(['git', 'rev-list', '--left-right', '--count', installed_sha + '...' + master], ROOT)
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return dict(host=os.uname().nodename, source=source, installed=installed, running=running,
        services=command(['systemctl', 'show', 'charlie.service', '--property=ActiveState,SubState,MainPID,ExecStart,FragmentPath,DropInPaths']),
        thermal=thermal(), notebook=nb, python=dict(executable=sys.executable, version=sys.version, dependencies=versions),
        authorization=dict(operator_environment_requests={k: os.environ.get(k, 'unset') for k in AUTH},
            physical_permission='not established by status or source inclusion', policy_activation='not authorized by release'),
        master=dict(last_fetched_sha=master, installed_only_and_master_only_commit_counts=compare,
                    freshness='local fetched ref; run git fetch origin for a current comparison'),
        runtime_verification='this host only; no assertion about an inaccessible Raspberry Pi')


def worktrees(repo):
    raw = command(['git', 'worktree', 'list', '--porcelain'], repo)
    if raw is None:
        raise ValueError('Git inventory unavailable')
    observed = processes()
    result = []
    for section in raw.split('\n\n'):
        rows = section.splitlines()
        p = Path(rows[0][9:])
        dirty = command(['git', 'status', '--porcelain', '--untracked-files=all'], p)
        unpublished = command(['git', 'log', '--format=%H', 'HEAD', '--not', '--remotes=origin'], p)
        evidence = [str(x.relative_to(p)) for pattern in ('*.sqlite3', 'memory.jsonl', 'checkpoint.json', 'capture-manifest.json') for x in p.rglob(pattern) if '.git' not in x.parts]
        active = [r['pid'] for r in observed if Path(r['checkout']) == p.resolve()]
        result.append(dict(git=rows, path=str(p), uncommitted=dirty, unpublished_commits=unpublished,
            evidence=evidence, active_pids=active, cleanup_eligible=dirty == '' and unpublished == '' and not evidence and not active,
            cleanup='inventory only; retain until rollback and historical provenance reviewed'))
    return result


@contextlib.contextmanager
def state_lock(state):
    # Opening an existing inode is essential: deleting or replacing it breaks ownership.
    path = Path(state) / 'offline.lock'
    stream = path.open('rb') if path.exists() else None
    try:
        if stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Refuse legacy writers without a lock, too.
        if any(p['learning_state'] == str(Path(state).resolve()) for p in processes()):
            raise ValueError('active application references notebook; stop it with separate approval first')
        yield
    finally:
        if stream:
            stream.close()


def verify_backup(destination):
    root = Path(destination).resolve()
    manifest = read_json(root / 'backup-manifest.json')
    if not manifest:
        raise ValueError('backup manifest missing')
    for name, sha in manifest['files'].items():
        p = (root / name).resolve()
        if root not in p.parents or hash_file(p) != sha:
            raise ValueError('backup artifact integrity mismatch: ' + name)
        if p.suffix == '.sqlite3':
            with sqlite3.connect(p.as_uri() + '?mode=ro', uri=True) as c:
                if c.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('SQLite integrity check failed')
    db = root / 'learning-evidence.sqlite3'
    if db.is_file():
        # Reuse immutable evidence validation only, never initialize a new journal.
        from memory.evidence import EvidenceJournal
        j = EvidenceJournal(db, read_only=True)
        try:
            j.verify()
        finally:
            j.close()
    return dict(verified=True, files=len(manifest['files']), source=manifest['source'], identity=notebook(root).get('identity_anchor_first_record'))


def backup(state, destination):
    state = Path(state).resolve()
    destination = Path(destination).resolve()
    if state == destination or state in destination.parents or destination in state.parents:
        raise ValueError('backup must be separate from source')
    if not (state / 'learning-evidence.sqlite3').is_file():
        raise ValueError('existing notebook required; never create substitute history')
    with state_lock(state):
        destination.mkdir(parents=True, exist_ok=False)
        files = {}
        for src in sorted(state.rglob('*')):
            if src.is_symlink():
                raise ValueError('resolve symlink evidence provenance explicitly before backup')
            if not src.is_file() or src.name == 'offline.lock' or src.name.endswith(('-wal', '-shm')):
                continue
            rel = src.relative_to(state)
            out = destination / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            if src.suffix == '.sqlite3':
                with sqlite3.connect(src.as_uri() + '?mode=ro', uri=True) as a, sqlite3.connect(out) as b:
                    a.backup(b)
            else:
                shutil.copy2(src, out)
            files[str(rel)] = hash_file(out)
        manifest = dict(schema='charlie-state-backup-v1', source=str(state), at=time.time(), files=files,
                        migrations_performed=False, rollback='restore only while stopped, after verifying identities; never overwrite original automatically')
        (destination / 'backup-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        return verify_backup(destination)


@contextlib.contextmanager
def release_lock(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'release.lock').open('a') as s:
        fcntl.flock(s, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield root


def atomic_pointer(root, name, target):
    temp = root / ('.' + name + '-' + uuid.uuid4().hex)
    temp.symlink_to(target)
    try:
        os.replace(temp, root / name)
    finally:
        temp.unlink(missing_ok=True)


def validate_release(path):
    path = Path(path).resolve()
    manifest = read_json(path / 'installed-release.json')
    if not manifest or not manifest.get('commit') or not manifest.get('files'):
        raise ValueError('staged release manifest required')
    for name, sha in manifest['files'].items():
        file = (path / name).resolve()
        if path not in file.parents or not file.is_file() or hash_file(file) != sha:
            raise ValueError('release integrity mismatch: ' + name)
    if set(manifest['files']) != {str(p.relative_to(path)) for p in path.rglob('*') if p.is_file() and p.name != 'installed-release.json'}:
        raise ValueError('release file set changed')
    return manifest


def stage(repo, revision, release_root):
    # Staging immutable source does not install dependencies, touch state, flash, or start processes.
    import re
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('exact published commit SHA required')
    repo = Path(repo).resolve()
    if command(['git', 'cat-file', '-t', revision], repo) != 'commit':
        raise ValueError('source commit unavailable; fetch it first')
    if command(['git', 'branch', '-r', '--contains', revision], repo) is None:
        raise ValueError('cannot check publication')
    if not command(['git', 'branch', '-r', '--contains', revision], repo):
        raise ValueError('revision not present on a fetched remote branch')
    with release_lock(release_root) as root:
        destination = root / 'releases' / revision
        destination.parent.mkdir(exist_ok=True)
        destination.mkdir(exist_ok=False)
        # Git archive supplies tracked source. No worktree mutation or untracked evidence copying.
        archive = subprocess.Popen(['git', 'archive', revision], cwd=repo, stdout=subprocess.PIPE)
        try:
            import tarfile
            with tarfile.open(fileobj=archive.stdout, mode='r|') as tar:
                tar.extractall(destination, filter='data')
            if archive.wait() != 0:
                raise ValueError('source archive failed; incomplete staging retained')
        finally:
            archive.stdout.close()
            if archive.poll() is None:
                archive.kill(); archive.wait()
        files = {str(p.relative_to(destination)): hash_file(p) for p in destination.rglob('*') if p.is_file()}
        manifest = dict(schema='charlie-installed-release-v1', commit=revision, source_repository=str(repo),
            staged_at=time.time(), files=files, state_migration=False, physical_activation=False,
            qualification='software release only; inspect release capabilities and native acceptance separately')
        (destination / 'installed-release.json').write_text(json.dumps(manifest, indent=2) + '\n')
        validate_release(destination)
        return dict(staged=str(destination), commit=revision, activated=False)


def deploy(release_root, revision=None, rollback=False, approved=False):
    if not approved:
        raise ValueError('--approved required for an independently approved application pointer change')
    with release_lock(release_root) as root:
        current = root / 'current'
        target = root / 'previous' if rollback else root / 'releases' / (revision or '')
        target = target.resolve(strict=True)
        if root / 'releases' not in target.parents:
            raise ValueError('target must be an immutable staged release')
        manifest = validate_release(target)
        old = current.resolve(strict=True) if current.is_symlink() else None
        if old == target:
            return dict(commit=manifest['commit'], changed=False, running_services_restarted=False)
        if current.exists() and not current.is_symlink():
            raise ValueError('current must be a managed symlink; do not overwrite directories')
        if old:
            validate_release(old)
            atomic_pointer(root, 'previous', old)
        atomic_pointer(root, 'current', target)
        return dict(commit=manifest['commit'], changed=True, rollback_target=str(old) if old else None,
                    running_services_restarted=False, notebook_modified=False,
                    next='verify readiness; service shutdown/start requires separate approval; existing process keeps its old version')


def readiness(state, release_root):
    report = status(state, release_root)
    errors = []
    for name in ('numpy', 'Pillow', 'opencv-python-headless', 'pyserial'):
        if not report['python']['dependencies'][name]:
            errors.append('missing dependency: ' + name)
    if report['installed']:
        try:
            validate_release(report['installed']['path'])
        except (OSError, ValueError) as e:
            errors.append(str(e))
    else:
        errors.append('no managed installed release')
    if not report['notebook']['exists']:
        errors.append('authoritative notebook unavailable; do not create a replacement')
    arm = os.uname().machine.lower().startswith(('arm', 'aarch64'))
    if arm and (report['thermal']['errors'] or report['thermal']['latest_temperature_c'] is None):
        errors.append('Pi thermal telemetry unavailable or invalid')
    temp = report['thermal']['latest_temperature_c']
    if (report['notebook'].get('operational') or {}).get('thermal',{}).get('suspended'):
        errors.append('retained thermal suspension; Executive must verify fresh stabilization and all resources')
    if temp is not None and temp >= 75:
        errors.append('development thermal ceiling reached')
    report.update(offline_ready=not errors, blocked_dependencies=errors,
                  physical_ready=False, physical_readiness='requires independent hardware approvals and existing native readiness gates')
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state', type=Path, default=Path.home() / '.local/share/charlie/development')
    p.add_argument('--release-root', type=Path, default=Path.home() / '.local/share/charlie/releases')
    sub = p.add_subparsers(dest='action', required=True)
    sub.add_parser('status'); sub.add_parser('readiness')
    w = sub.add_parser('worktrees'); w.add_argument('--repo', type=Path, default=ROOT)
    b = sub.add_parser('backup'); b.add_argument('destination', type=Path)
    v = sub.add_parser('verify-backup'); v.add_argument('destination', type=Path)
    s = sub.add_parser('stage'); s.add_argument('revision'); s.add_argument('--repo', type=Path, default=ROOT)
    d = sub.add_parser('deploy'); d.add_argument('revision'); d.add_argument('--approved', action='store_true')
    r = sub.add_parser('rollback'); r.add_argument('--approved', action='store_true')
    a = p.parse_args(argv)
    try:
        if a.action == 'status': result = status(a.state, a.release_root)
        elif a.action == 'readiness': result = readiness(a.state, a.release_root)
        elif a.action == 'worktrees': result = worktrees(a.repo)
        elif a.action == 'backup': result = backup(a.state, a.destination)
        elif a.action == 'verify-backup': result = verify_backup(a.destination)
        elif a.action == 'stage': result = stage(a.repo, a.revision, a.release_root)
        else: result = deploy(a.release_root, getattr(a, 'revision', None), a.action == 'rollback', a.approved)
        print(json.dumps(result, indent=2))
        return 1 if a.action == 'readiness' and not result['offline_ready'] else 0
    except (OSError, ValueError, sqlite3.DatabaseError) as e:
        print(json.dumps(dict(error=str(e), action=a.action, physical_activation=False)), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
