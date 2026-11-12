"""Explicit-path, secret-free source/approval inventory. No device I/O or services."""
import hashlib
import ast
import json
import os
from pathlib import Path
import re
import subprocess


def git(root, *args):
    p=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,timeout=15,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    if p.returncode:raise ValueError('Git inventory unavailable: '+str(root))
    return p.stdout.strip()


def digest(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError('regular original file required')
    before=path.stat();h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    after=path.stat()
    if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError('file changed during read-only inventory')
    return dict(path=str(path),bytes=after.st_size,sha256=h.hexdigest())


def source(root):
    root=Path(root).resolve()
    return dict(path=str(root),sha=git(root,'rev-parse','HEAD'),tree=git(root,'rev-parse','HEAD^{tree}'),
        branch=git(root,'rev-parse','--abbrev-ref','HEAD'),dirty=bool(git(root,'status','--porcelain')),
        parents=git(root,'show','-s','--format=%P','HEAD').split(),
        local_branches=git(root,'for-each-ref','--format=%(refname:short) %(objectname)','refs/heads').splitlines(),
        remotes=git(root,'remote').splitlines())  # never URLs that can contain credentials


GUARD_FILES=('learning/consultation.py','learning/resources.py','tools/historical_question_qualification.py')

def manual_guards(root):
    root=Path(root);result={name:digest(root/name)['sha256'] for name in GUARD_FILES}
    tree=ast.parse((root/'learning/consultation_activation.py').read_text())
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name in ('private_read','validate_approval'):
            result['function:'+node.name]=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
    return result


def approvals(ops, baseline):
    ops=Path(ops).resolve();result=dict(path=str(ops),files={},approved_sha=None,approval_binding=False)
    for name in ('approved.sha','QUALIFICATION.md','start-stationary.sh','run-historical-consultation.py'):
        p=ops/name
        if p.is_file():result['files'][name]=digest(p)
    p=ops/'approved.sha'
    if p.is_file():
        pin=p.read_text().strip()
        if not re.fullmatch('[0-9a-f]{40}',pin):raise ValueError('invalid approval pin')
        result['approved_sha']=pin
        result['approval_binding']=pin==baseline['sha'] and baseline['dirty'] is False
    # Markers are observations, never permission to remove, clear or retry.
    result['durable_markers']=[]
    for directory in (ops/'state',Path.home()/'.local/share/charlie/neck'):
        if directory.exists():
            for p in sorted(directory.glob('*')):
                if p.is_file() and ('uncertain' in p.name or p.name.endswith('.lock')):
                    result['durable_markers'].append(digest(p))
    return result


def observed_processes():
    result=[];inaccessible=0
    for p in Path('/proc').glob('[0-9]*'):
        try:
            name=(p/'comm').read_text().strip()
            args=(p/'cmdline').read_bytes().split(b'\0')
            if name=='ollama' or any(a.endswith(b'/main.py') or a==b'main.py' for a in args):
                # Never return arbitrary command lines or /proc environ.
                result.append(dict(pid=int(p.name),name=name,cwd=str((p/'cwd').resolve()),
                    flags=[a.decode() for a in args if a in (b'--offline',b'--hardware',b'--native-meditation')]))
        except (OSError,ValueError):inaccessible+=1
    return dict(visible=result,inaccessible=inaccessible,
        scope='current process namespace only; absence does not establish native idle or owner completeness')


def collect(baseline, candidate, ops, protected=()):
    b=source(baseline);c=source(candidate)
    return dict(schema='charlie-runtime-inventory-v2',baseline=b,candidate=c,
        approvals=approvals(ops,b),manual_llm_guards=dict(baseline=manual_guards(baseline),candidate=manual_guards(candidate)),protected=[digest(p) for p in protected],processes=observed_processes(),
        devices=[str(p) for pattern in ('video*','media*','hailo*','ttyACM*','ttyUSB*') for p in Path('/dev').glob(pattern)],
        installed_firmware='UNKNOWN: no device readback authorized or performed',
        native_owners='UNKNOWN until host namespace/unit and physical owner reconciliation',
        mutations_performed=[],operational_release_owner='existing charlie-ops approval hierarchy; not this tool')
