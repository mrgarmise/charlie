"""Scoped isolated rehearsal; never restore over the working operator notebooks."""
import json
from pathlib import Path
import shutil
import time

from charlie_ops.operator import backup, verify_backup
from .promotion import require
from .stationary import CANDIDATE, sha


def rehearse(ctl, destination):
    ctl.preserved()
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    manifests = {}
    for name in ('state', 'batch-a-state'):
        src = ctl.ops / name
        archive = destination / 'snapshot' / name
        # Existing Backup uses the notebook lock and SQLite's online backup API.
        captured = backup(src, archive)
        isolated = destination / 'isolated' / name
        shutil.copytree(archive, isolated)
        restored = verify_backup(isolated)
        require(restored == captured and restored['identity'], 'isolated notebook identity mismatch')
        original_files = {str(p.relative_to(src)) for p in src.rglob('*') if p.is_file()
                          and p.name != 'offline.lock' and not p.name.endswith(('-wal', '-shm'))}
        manifest = archive / 'backup-manifest.json'
        require(set(json.loads(manifest.read_text())['files']) == original_files,
                'notebook backup scope mismatch')
        manifests[str(manifest)] = sha(manifest)
    controls = destination / 'snapshot/controls'
    controls.mkdir()
    paths = [ctl.fallback, ctl.models] + [ctl.ops / p for p in (
        'approved.sha', 'QUALIFICATION.md', 'run-historical-consultation.py', 'start-stationary.sh',
        'batch-a-operator-pin.sha', 'start-stationary-batch-a.sh')]
    controls_manifest = {}
    for i, path in enumerate(paths):
        out = controls / str(i)
        shutil.copyfile(path, out)
        controls_manifest[str(path)] = dict(file=out.name, sha256=sha(path))
    isolated = destination / 'isolated/controls'
    shutil.copytree(controls, isolated)
    for item in controls_manifest.values():
        require(sha(isolated / item['file']) == item['sha256'], 'control restore mismatch')
    manifest = controls / 'manifest.json'
    manifest.write_text(json.dumps(controls_manifest, indent=2))
    manifests[str(manifest)] = sha(manifest)
    result = dict(candidate=CANDIDATE, backup_manifests=manifests, completed_at=time.time(),
                  isolated_restore_verified=True, state_compatible=False, complete_scope_verified=False,
                  independent_review=False, status='pending', preserved_working_state=True,
                  remaining='review host-specific scope, state lineage, firmware, calibration and model identities')
    (destination / 'restore-observations.json').write_text(json.dumps(result, indent=2))
    return result
