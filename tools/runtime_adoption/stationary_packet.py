"""Build an unsigned request from actual host inputs. No approval or switch is created."""
from pathlib import Path

from .candidate import assemble
from .inventory import collect, git
from .promotion import load, require
from .stationary import A, B, BASELINE, CANDIDATE, SCOPES, sha


def proposal(ctl, scope):
    from .stationary import ROOT
    ctl.preserved()
    inputs = load(ctl.review / 'inputs.json')
    receipts = load(ctl.review / 'ci.json')
    backups = [str(Path(p).resolve(strict=True)) for p in inputs['backup_manifests']]
    require(bool(backups), 'backup manifests required')
    restore = Path(inputs['restore_receipt']).resolve(strict=True)
    paths = set(backups) | {str(ctl.review / 'controller-ci.json'), str(restore), str(ctl.fallback),
                            str(ctl.ops / 'approved.sha'), str(ctl.ops / 'QUALIFICATION.md'),
                            str(ctl.ops / 'run-historical-consultation.py')}
    rows = []
    for sid, gates in getattr(ctl, "scopes", SCOPES).items():
        evidence = {}
        for gate in gates if sid == scope else ():
            path = Path(inputs['gate_receipts'][sid][gate]).resolve(strict=True)
            receipt = load(path)
            require(receipt['ability'] == sid and receipt['gate'] == gate and
                    receipt['candidate'] == getattr(ctl, 'candidate', CANDIDATE) and
                    receipt['controller_sha'] == git(ROOT, 'rev-parse', 'HEAD'), 'wrong native receipt')
            require(receipt['artifacts'] and all(sha(Path(p)) == h for p, h in receipt['artifacts'].items()),
                    'missing or changed native measurement')
            paths.update(receipt['artifacts'])
            evidence[gate] = dict(receipt, evidence_sha256=sha(path))
            paths.add(str(path))
        rows.append(dict(id=sid, source_present=True, enabled=False, dependencies=[],
                         dependencies_present=['pr-04', 'pr-10', 'pr-11'] if sid == A else ['pr-04'],
                         dependencies_active_if_needed=[A] if sid == B else [],
                         provenance=['pr-11', 'pr-12', 'pr-25'] if sid == A else ['pr-04', 'pr-21'],
                         required_native_gates=list(gates), native_gates=evidence,
                         authority_envelope='ELEGOO frames, Hailo inference, RP2040 labels' if sid == A
                         else 'operator local read of existing Executive status',
                         stop_conditions=['review expiry', 'owner or identity change', 'STOP', 'thermal veto'],
                         rollback='restore pinned normal launcher' if sid == A else 'disable local status'))
    if getattr(ctl, 'primary', A) != A:
        rows[0].update(provenance=['pr-44', 'pr-49', 'pr-50'], dependencies_present=[],
                       dependencies_active_if_needed=[], authority_envelope='shared ELEGOO camera and Hailo; signed display selection; no motion',
                       rollback='restore original pinned normal launcher')
    inv = collect(ctl.old, ctl.new, ctl.ops, sorted(paths))
    ledger = load(ROOT / 'docs/runtime-adoption/abilities.json')
    manifest = assemble(ledger, inv, receipts, rollback_sha=BASELINE['sha'], backup_manifests=backups)
    manifest['abilities'] = rows
    manifest['stationary'] = ctl.bindings()
    manifest['backup_qualification'] = dict(load(restore), evidence_sha256=sha(restore))
    manifest['default_authority'] = 'deny'
    return manifest
