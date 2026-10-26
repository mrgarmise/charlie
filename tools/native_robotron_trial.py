"""Foreground host-only durable marathon runner; never a sandbox escape or service.

Uses existing marathon/control supervision. Operator-reviewed independent stop,
release and host-readiness proofs are mandatory; this monitor cannot certify them.
"""
import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.ppal.progress_supervision import stop_process

PROOFS = ('independent_physical_stop', 'independent_neutral_release',
          'controller_identity_and_lease', 'camera_ownership',
          'display_fixed_focus_and_framing', 'host_monitoring', 'software_tests')


def checksum(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def verify_review(path, revision):
    review = json.loads(Path(path).read_text())
    if (review.get('host_boot_id') != Path('/proc/sys/kernel/random/boot_id').read_text().strip()
            or not isinstance(review.get('reviewed_at'), (int,float))
            or not 0 <= time.time()-review['reviewed_at'] <= 3600):
        raise ValueError('fresh same-boot independent host review required')
    if review.get('runtime_revision') != revision:
        raise ValueError('host review must name the exact runtime revision')
    for key in PROOFS:
        proof = review.get('proofs', {}).get(key, {})
        source = Path(proof.get('path', '')).expanduser().resolve(strict=True)
        if not source.is_file() or checksum(source) != proof.get('sha256'):
            raise ValueError('missing or changed independently reviewed proof: '+key)
    verify_software_receipt(review['proofs']['software_tests']['path'])
    return review


def required_socket_cases():
    prior = json.loads((ROOT/'docs/validation/native-integration-20261021/test-report.json').read_text())
    required = {r['test'] for r in prior['full_run']['failed_cases']
                if 'Operation not permitted' in r['message']}
    if len(required) != 34:
        raise ValueError('original socket acceptance list must contain 34 cases')
    return required


LEASE_CASES = {
    'tests.test_arcade_controller_lease_client::'+name for name in (
        'test_each_progressing_action_renews_even_when_positions_unchanged',
        'test_unsupported_lease_fails_closed_without_gameplay',
        'test_expired_renewal_closes_connection',
        'test_old_local_timer_cannot_interrupt_renewed_hold')}


def verify_software_receipt(path, *, require_lease=False):
    """Historical receipts need coverage/integrity, not an arbitrary new test run."""
    tree = ET.parse(path)
    cases = list(tree.iter('testcase'))
    if (not cases or any(t.find(k) is not None for t in cases for k in ('failure','error','skipped'))
            or any(int(t.get(k, '0')) for t in tree.iter('testsuite')
                   for k in ('failures', 'errors', 'skipped'))):
        raise ValueError('native software receipt must pass without blocked checks')
    actual = {t.attrib.get('classname', '')+'::'+t.attrib.get('name', '') for t in cases}
    if not required_socket_cases() <= actual:
        raise ValueError('receipt must exercise all 34 originally blocked socket cases')
    if require_lease and not LEASE_CASES <= actual:
        raise ValueError('receipt must exercise all four controller lease socket cases')
    return dict(cases=len(cases), original_socket_cases=34, lease_socket_cases=len(LEASE_CASES & actual))


def sample(root_pid=None, disk_path=ROOT):
    """Native /proc/sysfs plus native vcgencmd; no camera/controller commands."""
    temp = float(Path('/sys/class/thermal/thermal_zone0/temp').read_text())/1000
    flags = subprocess.check_output(['vcgencmd','get_throttled'],text=True,timeout=2).strip()
    if not flags.startswith('throttled='):
        raise ValueError('invalid throttling telemetry')
    throttled = int(flags.split('=',1)[1],16)
    memory = {line.split(':')[0]:int(line.split()[1])*1024
              for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line}
    processes = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():continue
        try:
            status = dict(line.split(':',1) for line in (entry/'status').read_text().splitlines() if ':' in line)
            stat = (entry/'stat').read_text().rsplit(')',1)[1].split()
            processes[int(entry.name)] = dict(ppid=int(status['PPid']),uid=int(status['Uid'].split()[0]),
                rss=int(status.get('VmRSS','0 kB').split()[0])*1024,
                cpu_ticks=int(stat[11])+int(stat[12]))
        except FileNotFoundError:continue
    owned = {root_pid} if root_pid else set()
    while True:
        children = {pid for pid,p in processes.items() if p['ppid'] in owned}
        more = children-owned
        if not more:break
        owned.update(more)
    device_owners = {}
    # Host-visible descriptors, not stale PID files, establish local ownership.
    for pid,process in processes.items():
        # Other-user/root ownership needs independent host review; do not
        # require root permissions merely to inspect unrelated daemons.
        if process['uid'] != os.getuid():continue
        try:
            for descriptor in (Path('/proc')/str(pid)/'fd').iterdir():
                try:target=os.readlink(descriptor)
                except FileNotFoundError:continue
                if target.startswith(('/dev/video','/dev/media','/dev/v4l-subdev','/dev/hailo')):
                    device_owners.setdefault(target,[]).append(pid)
        except FileNotFoundError:continue
        except PermissionError:
            # Unknown same-user ownership is not safe to assume away.
            raise RuntimeError('host device ownership not fully visible; require an approved ownership monitor')
    return dict(at=time.time(), monotonic=time.monotonic(), temperature_c=temp,
        throttled=throttled, available_memory_bytes=memory['MemAvailable'],
        free_disk_bytes=shutil.disk_usage(disk_path).free,
        worker_pids=sorted(owned), rss_bytes=sum(processes.get(pid,{}).get('rss',0) for pid in owned),
        cpu_ticks=sum(processes.get(pid,{}).get('cpu_ticks',0) for pid in owned),
        ownership_scope_uid=os.getuid(),
        ownership_scope='same-user descriptors; cross-user ownership requires independent host review',
        device_owners={key:sorted(set(pids)) for key,pids in device_owners.items()})


def stop_reason(row):
    if not math.isfinite(row['temperature_c']) or not 0 <= row['temperature_c'] < 75:
        return 'temperature unavailable/invalid or >=75C'
    if row['throttled'] != 0:return 'throttling flags set'
    if row['available_memory_bytes'] < 512*1024**2:return 'available memory below 512 MiB'
    if row['rss_bytes'] > 768*1024**2:return 'worker RSS exceeds conservative 768 MiB limit'
    if row['free_disk_bytes'] < 2*1024**3:return 'free disk below 2 GiB'
    owners = {pid for pids in row['device_owners'].values() for pid in pids}
    if not owners <= set(row['worker_pids']):return 'device owner outside trial worker tree'
    return None


def main():
    if '--preflight' in sys.argv[1:]:
        from tools.native_preflight import main as preflight
        raise SystemExit(preflight([arg for arg in sys.argv[1:] if arg != '--preflight']))
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-revision',required=True)
    parser.add_argument('--review',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--campaign',type=Path,required=True,help='prepared learning.campaign --marathon state; existing authority required')
    parser.add_argument('--run',action='store_true',help='explicit foreground native launch after review; otherwise inspect only')
    args=parser.parse_args()
    args.output=args.output.expanduser().resolve()
    if args.output == ROOT or ROOT in args.output.parents:
        parser.error('fresh evidence output must be outside the source checkout')
    if Path('/proc/1/comm').read_text().strip() != 'systemd':
        parser.error('ordinary native systemd host required; do not bypass a restricted namespace')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dirty=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()
    if revision != args.expected_revision or dirty:
        parser.error('clean checkout at exact expected revision required')
    review=verify_review(args.review,revision)
    disk_path=args.output.parent
    if not disk_path.is_dir():parser.error('create the evidence parent directory first')
    initial=sample(disk_path=disk_path)
    reason=stop_reason(initial)
    if reason:parser.error(reason)
    policy_identity={'campaign':str(args.campaign.resolve()),'selection':'frozen campaign grants; no wrapper policy substitution'}
    if not args.run:
        print(json.dumps(dict(native_checks=initial,policy=policy_identity,review_verified=True,armed=False),indent=2))
        return
    args.output=args.output.expanduser().resolve()
    args.output.mkdir(parents=True,exist_ok=False)
    for name,proof in review['proofs'].items():
        target=args.output/(name+'-'+Path(proof['path']).name)
        shutil.copyfile(proof['path'],target)
        if checksum(target) != proof['sha256']:
            raise ValueError('proof changed before launch: '+name)
    (args.output/'operator-review.json').write_text(json.dumps(review,indent=2)+'\n')
    command=[sys.executable,'-m','learning.campaign','run',str(args.campaign.resolve()),'--arm']
    # Prevent an ambient policy/semantic selection from contradicting the freeze.
    env=os.environ.copy()
    # Required server capability; renewal happens in gameplay execute(), never
    # in this independent monitor, so frozen workers lose their controller lease.
    env['CHARLIE_CONTROLLER_LEASE']='required'
    env.pop('CHARLIE_LEARNING_STATE',None)
    identity=dict(revision=revision,command=command,policy=policy_identity,
                  campaign=str(args.campaign.resolve()),
                  configuration_sha256={str(p.relative_to(ROOT)):checksum(p)
                      for p in (ROOT/'config/robotron').rglob('*') if p.is_file()},
                  review_sha256=checksum(args.review),started_at=time.time())
    (args.output/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
    child=None;reason=None;reaped=True
    def interrupted(signum,frame):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,interrupted)
    signal.signal(signal.SIGHUP,interrupted)
    with (args.output/'native-resources.jsonl').open('x',buffering=1) as trace, \
         (args.output/'runner.log').open('x') as log:
        try:
            trace.write(json.dumps(initial)+'\n');trace.flush();os.fsync(trace.fileno())
            child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            previous=None
            while child.poll() is None:
                if (args.output/'STOP').exists():
                    reason='operator stop file';break
                row=sample(child.pid,disk_path=disk_path)
                if previous:
                    dt=row['monotonic']-previous['monotonic']
                    row['worker_cpu_percent']=100*max(0,row['cpu_ticks']-previous['cpu_ticks'])/os.sysconf('SC_CLK_TCK')/max(dt,.001)
                previous=row
                trace.write(json.dumps(row)+'\n');trace.flush();os.fsync(trace.fileno())
                reason=stop_reason(row)
                if reason:break
                time.sleep(1)
        except KeyboardInterrupt:reason='operator interrupt'
        except Exception as exc:reason='monitoring failure: '+repr(exc)
        finally:
            if child:reaped=stop_process(child)
            result=dict(reason=reason or 'child exited; independently inspect completions',
                reaped=reaped,returncode=child.returncode if child else None,
                automatic_restart=False,game_completion='not inferred by wrapper',
                neutral_release='must independently verify acknowledgment and physical stop path')
            (args.output/'runner-result.json').write_text(json.dumps(result,indent=2)+'\n')
    if reason or not reaped or child.returncode:raise SystemExit(1)


if __name__=='__main__':main()
