"""Local owner approval for the fixed Batch A foreground development profile."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys

from .inventory import digest
from .promotion import load, require
from . import stationary as s

APPROVAL = 'supervised-development.json'
EVIDENCE = 'drafts/final-qualification-20261126'
SCOPE = 'batch-a-supervised-development-v1'
OWNER_ATTESTATIONS = (
    'live Pico ACK and visible label clear',
    'observational STOP, cleanup and device release',
    'thermal/resource checks and guarded transport scope',
    'isolated restore scope',
    'installed firmware unchanged since native readback',
    'single foreground owner, potential alternate privileged access and physical motion prohibited',
)


def foreground():
    require(os.getuid() == 1000 and os.geteuid() == os.getuid()
            and sys.stdin.isatty() and os.tcgetpgrp(0) == os.getpgrp(),
            'Charlie owner must be at the foreground terminal')


def confirm_isolation():
    require(input('Confirm on-site supervision and isolated motion power. Type MOTION POWER ISOLATED: ')
            == 'MOTION POWER ISOLATED', 'physical isolation not confirmed')


def hardware_identity():
    devices = {}
    for name in ('ttyACM0', 'hailo0'):
        info = Path('/dev', name).stat()
        require(stat.S_ISCHR(info.st_mode) and info.st_uid == 0 and info.st_gid == 20
                and stat.S_IMODE(info.st_mode) == 0o660, 'device permissions changed')
        sysfs = Path(f'/sys/dev/char/{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}').resolve(strict=True)
        parent = next((p for p in sysfs.parents
                       if (p / ('idVendor' if name == 'ttyACM0' else 'vendor')).is_file()), None)
        require(parent is not None, 'device identity unavailable')
        fields = (('idVendor', 'idProduct', 'bcdDevice', 'serial') if name == 'ttyACM0'
                  else ('vendor', 'device', 'revision'))
        identity = {field: (parent / field).read_text().strip() for field in fields}
        devices[name] = dict(identity=identity, sysfs=str(sysfs), node_inode=info.st_ino)
    require(devices['ttyACM0']['identity'] == dict(idVendor='2e8a', idProduct='0005',
            bcdDevice='0100', serial='e6614103e77a9421'), 'Pico USB identity changed')
    require(devices['hailo0']['identity'] == dict(vendor='0x1e60', device='0x2864', revision='0x01')
            and Path('/sys/module/hailo_pci/version').read_text().strip() == '4.23.0',
            'Hailo hardware or driver identity changed')
    return devices


def artifacts(ctl):
    folder = ctl.review / EVIDENCE
    n0 = folder / 'draft-N0-supervised.json'
    restore = folder / 'restore-review-pending.json'
    draft = load(n0)
    receipt = load(restore)
    require(draft['candidate'] == receipt['candidate'] == s.CANDIDATE and draft['gate'] == 'N0'
            and draft['ability'] == s.A and receipt['isolated_restore_verified'] is True
            and receipt['preserved_working_state'] is True
            and receipt['isolated_record_counts']['approved'] == 4648
            and receipt['isolated_record_counts']['approved_missing_in_candidate'] == 0,
            'Batch A identity or isolated restore evidence missing')
    required = {'n0-host-inspection.md', 'n0-pico-restoration-operator-report.md',
                'micropython-build.txt', 'usb.txt', 'inventory.jsonl', 'SHA256SUMS'}
    require(required <= {Path(p).name for p in draft['artifacts']}, 'mandatory N0 artifacts missing')
    observation = receipt['rehearsal_observations']
    protected = {**draft['artifacts'], **receipt['backup_manifests'],
                 observation['path']: observation['sha256']}
    for path, expected in protected.items():
        require(digest(Path(path))['sha256'] == expected, 'Batch A evidence changed')
    return {str(n0): s.sha(n0), str(restore): s.sha(restore)}


def bindings(ctl, log):
    # Keep the original qualification prerequisites, including owner/device guards.
    s.qualification_preflight(ctl, s.selection(ctl.normal))
    for state in ('state', 'batch-a-state'):
        notebook = ctl.ops / state / 'learning-evidence.sqlite3'
        require(notebook.resolve() == notebook, 'redirected notebook')
        with closing(sqlite3.connect(notebook.as_uri() + '?mode=ro', uri=True)) as db:
            require(db.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'notebook integrity check failed')
    binding = ctl.bindings()
    require(binding['logs']['guarded_session']['clean_shutdown_logged'] is True,
            'historical guarded cleanup evidence missing')
    log = Path(log)
    require(log.parent == ctl.ops / 'logs' and log.name.startswith('stationary-qualification-'),
            'use the exact-profile qualification log')
    with log.open() as stream:
        header = stream.readline()
    require(header.startswith('BEGIN QUALIFICATION '), 'qualification header missing')
    identity = json.loads(header.removeprefix('BEGIN QUALIFICATION '))
    require(all(identity[k] == v for k, v in dict(candidate=s.CANDIDATE, motion_authorized=False,
            controller_sha=binding['controller_sha'], controller_tree=binding['controller_tree'],
            original_launcher=s.ORIGINAL, boot=binding['boot_id']).items()),
            'qualification log belongs to another build, boot or scope')
    report = s.evidence(log, None, binding['hef_sha256'])
    require(report['clean_shutdown_logged'], 'qualification cleanup evidence missing')
    with log.open() as stream:
        require(any(line.startswith('STATIONARY STOP REQUESTED: recognition shutdown;')
                    for line in stream), 'qualification observational STOP missing')
    cleanup = log.with_suffix('.cleanup.json')
    require(load(cleanup) == dict(log_sha256=report['sha256'], idle_and_device_guards_passed=True),
            'qualification cleanup receipt mismatch')
    return dict(scope=SCOPE, candidate=s.CANDIDATE, baseline=s.BASELINE, bindings=binding,
                hardware=hardware_identity(), artifacts=artifacts(ctl),
                qualification_log=str(log), qualification_sha256=report['sha256'],
                cleanup_sha256=s.sha(cleanup), owner_attestations=list(OWNER_ATTESTATIONS))


def approve(ctl, log):
    foreground()
    path = ctl.review / APPROVAL
    require(not path.exists() and not path.is_symlink(), 'owner approval already exists')
    record = bindings(ctl, log)
    print(json.dumps(record, indent=2, sort_keys=True), flush=True)
    require(input('Type APPROVE SUPERVISED BATCH A: ') == 'APPROVE SUPERVISED BATCH A',
            'owner approval declined')
    require(bindings(ctl, log) == record, 'approval inputs changed while awaiting owner')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())


def admit(ctl):
    foreground()
    path = ctl.review / APPROVAL
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o600, 'invalid local owner approval file')
    record = load(path)
    require(bindings(ctl, record['qualification_log']) == record, 'owner approval binding changed')
    confirm_isolation()
    require(bindings(ctl, record['qualification_log']) == record, 'launch inputs changed while awaiting owner')
    return s.sha(path)
