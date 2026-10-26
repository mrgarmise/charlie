"""Read-only consolidation for native_robotron_trial; never opens a control socket."""
import argparse
import json
import math
import shutil
from pathlib import Path
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

from tools import native_robotron_trial as runner

DEFAULT_CAMPAIGN = Path('/home/five/charlie-native-trials/original-marathon-20261025')


def binding(path):
    return dict(path=str(path.resolve()), sha256=runner.checksum(path))


def inventory(roots, excluded):
    """Retain original bytes, paths and scope; names alone confer no qualification."""
    rows = []
    seen = set()
    for root in roots:
        paths = root.rglob('*') if root.is_dir() else [root]
        for path in paths:
            if (path.suffix not in ('.json', '.xml', '.txt', '.log') or not path.is_file()
                    or path.is_symlink() or excluded == path or excluded in path.parents):
                continue
            path = path.resolve()
            if path in seen:
                continue
            seen.add(path)
            try:
                row = dict(binding(path), size=path.stat().st_size, kind='historical',
                           qualification='original scope only; not current readiness')
                if path.suffix == '.json':
                    doc = json.loads(path.read_text())
                    if isinstance(doc, dict):
                        row['scope'] = {k: doc[k] for k in ('schema', 'runtime_revision',
                            'host_boot_id', 'reviewed_at', 'source', 'qualification_scope') if k in doc}
                        if isinstance(doc.get('proofs'), dict):
                            row['kind'] = 'review'
                            row['document'] = doc
                elif path.suffix == '.xml':
                    row['kind'] = 'test_receipt'
                    try:
                        row['coverage'] = runner.verify_software_receipt(path)
                        row['socket_coverage'] = 'PASS'
                    except Exception as exc:
                        row['socket_coverage'] = 'FAIL'
                        row['detail'] = str(exc)
                rows.append(row)
            except (OSError, ValueError) as exc:
                rows.append(dict(path=str(path), kind='unreadable', detail=str(exc)))
    return sorted(rows, key=lambda r: r['path'])


def assemble(rows, revision, boot, now):
    """Merge independently reviewed parts, without refreshing any attestation."""
    checks = {}
    selected = {}
    times = []
    for key in runner.PROOFS:
        valid, stale, broken = [], [], []
        for row in rows:
            doc = row.get('document', {})
            if key not in doc.get('proofs', {}):
                continue
            proof = doc['proofs'][key]
            try:
                path = Path(proof['path']).expanduser()
                if not path.is_absolute():
                    raise ValueError('proof path must be absolute')
                if runner.checksum(path) != proof['sha256']:
                    raise ValueError('proof hash changed')
                if key == 'software_tests':
                    runner.verify_software_receipt(path, require_lease=True)
                at = doc.get('reviewed_at')
                if (type(at) not in (int, float) or not math.isfinite(at)
                        or doc.get('runtime_revision') != revision
                        or doc.get('host_boot_id') != boot or not 0 <= now-at <= 3600):
                    stale.append(row['path'])
                    continue
                valid.append((proof, row, at))
            except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
                broken.append(dict(path=row['path'], detail=str(exc)))
        # A contradictory current attestation cannot silently be outvoted.
        current_broken = [r for r in broken if any(x['path'] == r['path'] and
            x.get('document', {}).get('runtime_revision') == revision and
            x.get('document', {}).get('host_boot_id') == boot for x in rows)]
        if current_broken or len({v[0]['sha256'] for v in valid}) > 1:
            checks[key] = dict(status='FAIL', detail='conflicting or changed current proof',
                               evidence=current_broken + [v[1]['path'] for v in valid])
        elif valid:
            proof, row, at = min(valid, key=lambda v: v[2])
            selected[key] = dict(proof)
            times.append(at)
            checks[key] = dict(status='PASS', evidence=row['path'], proof=proof,
                               detail='existing independent review reused within original scope')
        else:
            checks[key] = dict(status='STALE' if stale else 'NEEDS OPERATOR VERIFICATION',
                               evidence=stale + broken,
                               detail='review original evidence and bind current applicability; rerun only if required')
    review = None
    if len(selected) == len(runner.PROOFS):
        review = dict(runtime_revision=revision, host_boot_id=boot,
                      reviewed_at=min(times), proofs=selected)
    return checks, review


def host_batch(output, controller):
    result = {}
    # Keep independent telemetry even when the stricter live monitor refuses a sample.
    for key, path in dict(boot_id='/proc/sys/kernel/random/boot_id',
            temperature_millidegrees='/sys/class/thermal/thermal_zone0/temp',
            memory='/proc/meminfo').items():
        try:
            result[key] = Path(path).read_text().strip()
        except OSError as exc:
            result[key] = dict(error=str(exc))
    result['storage'] = dict(zip(('total', 'used', 'free'), shutil.disk_usage(output)))
    commands = dict(processes=['ps', '-eo', 'pid,ppid,uid,comm,args'],
        system_services=['systemctl', '--no-pager', 'list-units', '--type=service', '--state=running'],
        user_services=['systemctl', '--user', '--no-pager', 'list-units', '--type=service', '--state=running'])
    # ICMP only: even opening/closing a legacy controller TCP connection may release it.
    commands['controller_reachability'] = ['ping', '-n', '-c', '1', '-W', '2', controller]
    for key, cmd in commands.items():
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            result[key] = dict(returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)
        except (OSError, subprocess.TimeoutExpired) as exc:
            result[key] = dict(error=str(exc))
    try:
        result['resources'] = runner.sample(disk_path=output)
        result['resource_stop_reason'] = runner.stop_reason(result['resources'])
    except Exception as exc:
        result['resource_error'] = str(exc)
    result['devices'] = sorted(str(p) for pattern in ('video*', 'media*', 'v4l-subdev*', 'hailo*', 'ttyACM*', 'ttyUSB*')
                               for p in Path('/dev').glob(pattern))
    result['lease_client'] = dict(binding(runner.ROOT/'experiments/ppal/arcade_transport.py'),
        mechanism='existing progressing-action LEASE renewal; native launcher requires CHARLIE_CONTROLLER_LEASE=required',
        qualification='source identity only; installed endpoint and physical release require independent evidence')
    result['controller_scope'] = 'ICMP reachability only; no TCP connection, lease acquisition, NEUTRAL or control commands'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-revision', required=True)
    parser.add_argument('--campaign', type=Path, default=DEFAULT_CAMPAIGN)
    parser.add_argument('--output', type=Path, help='fresh directory outside checkout and campaign; default /tmp')
    parser.add_argument('--evidence-root', type=Path, action='append', help='additional evidence files/directories (repeatable)')
    parser.add_argument('--controller-host', default='charlie-arcade.local')
    args = parser.parse_args(argv)
    campaign = args.campaign.expanduser().resolve()
    output = args.output.expanduser().resolve() if args.output else Path(tempfile.mkdtemp(prefix='charlie-native-preflight-'))
    for protected in (runner.ROOT, campaign):
        if output == protected or protected in output.parents or output in protected.parents:
            parser.error('output must be separate from source and prepared campaign')
    if args.output:
        output.mkdir(parents=True, exist_ok=False)
    now = time.time()
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=runner.ROOT, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=runner.ROOT, text=True)
    roots = [runner.ROOT/'docs/validation', Path('/home/five/charlie-native-trials')]
    roots += sorted(Path('/home/five').glob('charlie-native-preflight-*'))
    roots += sorted(Path(tempfile.gettempdir()).glob('charlie-native-preflight-*'))
    roots += args.evidence_root or []
    rows = inventory(roots, output)
    checks, review = assemble(rows, revision, boot, now)
    checks['installed_source'] = dict(status='PASS' if revision == args.expected_revision and not dirty else 'FAIL',
        revision=revision, expected_revision=args.expected_revision, dirty=dirty)
    native = Path('/proc/1/comm').read_text().strip() == 'systemd'
    checks['native_host'] = dict(status='PASS' if native else 'NEEDS OPERATOR VERIFICATION',
        detail='native systemd host required; restricted namespace is not a hardware failure')
    host = host_batch(output, args.controller_host)
    checks['host_health'] = dict(status='FAIL' if host.get('resource_stop_reason') else
        ('NEEDS OPERATOR VERIFICATION' if 'resource_error' in host else 'PASS'),
        detail=host.get('resource_stop_reason') or host.get('resource_error') or 'native resource thresholds satisfied')
    reach = host['controller_reachability']
    checks['controller_reachability'] = dict(status='PASS' if reach.get('returncode') == 0 else 'NEEDS OPERATOR VERIFICATION',
        detail='ICMP only; installed lease/release qualification remains an independent proof')
    campaign_info = {}
    try:
        from learning import campaign as infrastructure
        state = infrastructure.read(campaign/'campaign.json')
        campaign_info = dict(binding(campaign/'campaign.json'), source=state['source'], phase=state['phase'],
            mode=state.get('mode'), physical_authorization=state.get('physical_authorization'))
        if state['source'] != infrastructure.source_identity():
            raise ValueError('campaign frozen to different source; preserve original; separately prepare/review a new campaign for changed runtime')
        if state.get('mode') != '3-meditation-3' or state.get('games') != 6 or state.get('blocks') != 2:
            raise ValueError('expected existing 3 / meditation / 3 campaign')
        checks['campaign_source'] = dict(status='PASS')
        grant = infrastructure.read(campaign/'authority.json')
        infrastructure.check_authority(campaign, state, grant)
        checks['campaign_authority'] = dict(status='PASS', detail='existing grant only; no authority issued')
    except Exception as exc:
        key = 'campaign_authority' if 'campaign_source' in checks else 'campaign_source'
        checks[key] = dict(status='NEEDS OPERATOR VERIFICATION' if key == 'campaign_authority' else 'FAIL', detail=str(exc))
    if review and all(c['status'] == 'PASS' for k, c in checks.items() if k != 'campaign_authority'):
        path = output/'review-candidate.json'
        path.write_text(json.dumps(review, indent=2)+'\n')
        try:
            runner.verify_review(path, revision)
            path.rename(output/'review.json')
            review_path = str(output/'review.json')
            checks['review_validity'] = dict(status='PASS')
        except Exception as exc:
            checks['review_validity'] = dict(status='FAIL', detail=str(exc))
            review_path = None
    else:
        review_path = None
    outstanding = {k: v for k, v in checks.items() if v['status'] != 'PASS'}
    overall = ('FAIL' if any(v['status'] == 'FAIL' for v in checks.values()) else
               'STALE' if any(v['status'] == 'STALE' for v in checks.values()) else
               'NEEDS OPERATOR VERIFICATION' if outstanding else 'PASS')
    software_candidates = [{k: r[k] for k in ('path', 'sha256', 'coverage', 'socket_coverage', 'detail', 'qualification') if k in r}
                           for r in rows if r['kind'] == 'test_receipt']
    report = dict(software_candidates=software_candidates, schema='charlie-native-preflight-v1', at=now, runtime_revision=revision,
        host_boot_id=boot, armed=False, status=overall, checks=checks, host=host,
        campaign=campaign_info, inventory=rows, review_path=review_path,
        operator_review=dict(outstanding=list(outstanding), instruction=
            'One review: resolve only listed items using original evidence; attest factual current scope in the existing review schema. '
            'Do not repeat valid historical tests solely due to age. No physical authorization is granted.'))
    # Invalid telemetry stays a failed check but must not destroy the diagnostic report.
    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        if isinstance(value, dict):
            return {k: finite(v) for k, v in value.items()}
        if isinstance(value, list):
            return [finite(v) for v in value]
        return value
    (output/'report.json').write_text(json.dumps(finite(report), indent=2, allow_nan=False)+'\n')
    summary = '\n'.join([overall]+[f"{v['status']}: {k}" + (' — '+v['detail'] if v.get('detail') else '') for k, v in checks.items()]+[
        'Historical software receipts: '+str(len(software_candidates))+' (coverage and original scope in report.json)',
        'Single operator review: '+(', '.join(outstanding) or 'none'),
        'Review: '+(review_path or 'not issued'), 'Report: '+str(output/'report.json')])+'\n'
    (output/'summary.txt').write_text(summary)
    print(summary, end='')
    return 0 if overall == 'PASS' else 1
