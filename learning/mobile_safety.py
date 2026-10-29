"""Independent mobile qualification records for existing CapabilityDeployment.

No hardware I/O; no Executive authority. External measurements stay immutable.
"""
import hashlib
import json
import math
from pathlib import Path
from memory.evidence import digest

RUNTIME_FILES=('experiments/ppal/eyes/run_active_vision.py','experiments/ppal/eyes/active_vision.py','run_elegoo_head2.py','run_elegoo_head2_diagnostic.py','memory/head_search.py','learning/object_runtime.py','vision/object_recognition.py','stimulus/keyboard.py','hardware/rp2040_controller.py','motion/controller.py','learning/actuator_safety.py','motion/rp2040_requests.py','behaviors/mobile_face_runtime.py','behaviors/mobile_face_track.py','vision/mobile_face.py','motion/elegoo_executor.py','motion/mobile_requests.py','hardware/elegoo_telemetry.py','stimulus/bus.py','hardware/elegoo_camera.py','hardware/hailo_session.py','hardware/elegoo_mobile.py','motion/mobile_base.py','experiments/ppal/mobile_navigation.py',
 'attention/manager.py','behaviors/mobile_observe.py','learning/mobile.py','learning/mobile_runtime.py',
 'learning/mobile_safety.py','learning/capabilities.py','learning/deployment.py','main.py',
 'memory/learning_projects.py','memory/evaluator.py','learning/resources.py',
 'vision/mobile_perception.py','vision/mobile_tracking.py','vision/mobile_models.py')
REQUIRED=('stationary_vision','explicit_stop','tcp_loss','pi_loss','local_expiry','power_cutoff',
 'wheels_up','floor_braking','obstacle_abort','edge_abort','target_loss','preemption')


def runtime_hash():
    root=Path(__file__).resolve().parents[1]
    return digest({p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in RUNTIME_FILES})


def finite(x):return type(x) in (int,float) and math.isfinite(x)


def artifact(ref):
    path=Path(ref['path'])
    if not path.is_file() or path.stat().st_size>8*1024*1024:raise ValueError('bounded qualification artifact required')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ref.get('sha256'):raise ValueError('qualification artifact changed')
    return json.loads(raw)


TIMED_MOTION_PROTOCOL = dict(N=2, T_unit='milliseconds',
    completion_ack='tagged_ok_after_local_stop', zero_duration='forbidden')


def require_timed_motion(protocol):
    if protocol.get('timed_motion') != TIMED_MOTION_PROTOCOL:
        raise ValueError('installed N2 millisecond completion protocol not qualified')


def validate_report(report, *, autonomous=False, live_pet=False):
    """Require measured trials, identities, margins and retained original files.

    Witness assertions are externally supplied evidence, never inferred by code.
    Validation of records does not independently witness the physical experiment.
    """
    if (report.get('schema')!='charlie.mobile.qualification.v1' or report.get('authentic') is not True
            or report.get('runtime_sha256')!=runtime_hash() or not report.get('witness')
            or not report.get('zone') or not report.get('hardware_id') or not report.get('measured_utc')):
        raise ValueError('current runtime and authentic witnessed zone qualification required')
    for key in ('firmware_sha256','bridge_sha256','model_sha256'):
        if not isinstance(report.get(key),str) or len(report[key])!=64 or any(c not in '0123456789abcdef' for c in report[key]):
            raise ValueError('verified firmware/bridge/model hashes required')
    protocol=artifact(report['protocol_artifact'])
    if (protocol.get('firmware_sha256')!=report['firmware_sha256'] or protocol.get('bridge_sha256')!=report['bridge_sha256']
            or protocol.get('installed_match') is not True or protocol.get('motion')!={'LEFT':1,'RIGHT':2,'FORWARD':3,'REVERSE':4}
            or protocol.get('local_expiry_verified') is not True):raise ValueError('installed bounded protocol not qualified')
    require_timed_motion(protocol)
    env=report['envelope']
    if (type(env.get('max_pwm')) is not int or not 1<=env['max_pwm']<=35
            or not finite(env.get('max_duration')) or not 0<env['max_duration']<=.2
            or not finite(env.get('max_stop_seconds')) or not 0<env['max_stop_seconds']<=.5
            or not finite(env.get('max_stop_m')) or not 0<env['max_stop_m']<=.5
            or not finite(env.get('stand_off_m')) or env['stand_off_m']<1
            or not finite(env.get('margin_m')) or env['margin_m']<2*env['max_stop_m']
            or env['stand_off_m']<=env['margin_m']):raise ValueError('measured conservative envelope required')
    directions=report.get('direction_envelopes',{})
    if set(directions)!={'LEFT','RIGHT','FORWARD','REVERSE'}:raise ValueError('direction-specific calibration required')
    for direction,limits in directions.items():
        if (type(limits.get('max_pwm')) is not int or not 1<=limits['max_pwm']<=env['max_pwm']
                or not finite(limits.get('max_duration')) or not 0<limits['max_duration']<=env['max_duration']):
            raise ValueError('invalid direction-specific envelope: '+direction)
    required=REQUIRED+(('proxy_follow',) if live_pet or autonomous else ())+ (('live_pet_follow','voluntary_decline','restart_revoke') if autonomous else ())
    if not isinstance(report.get('sensor_producer_sha256'),str) or len(report['sensor_producer_sha256'])!=64:
        raise ValueError('qualified sensor producer code identity required')
    for stage in required:
        trials=report.get('trials',{}).get(stage,[])
        if len(trials)<3:raise ValueError('three independent measured trials required: '+stage)
        groups=set();direction_counts={d:0 for d in directions}
        for ref in trials:
            row=artifact(ref)
            if (row.get('stage')!=stage or row.get('authentic') is not True or row.get('passed') is not True
                    or row.get('hardware_id')!=report['hardware_id'] or row.get('zone')!=report['zone']
                    or row.get('firmware_sha256')!=report['firmware_sha256'] or not row.get('witness')
                    or not row.get('utc') or not row.get('measurements') or not row.get('raw_artifacts')
                    or not row.get('surface') or not finite(row.get('battery_v')) or not 0<row['battery_v']<30):
                raise ValueError('incomplete independent trial: '+stage)
            if not row.get('trial_id') or row['trial_id'] in groups:raise ValueError('independent trial identities required')
            groups.add(row['trial_id'])
            if stage in ('wheels_up','floor_braking'):
                direction=row.get('direction')
                if direction not in directions:raise ValueError('measured motion direction required')
                direction_counts[direction]+=1
                m=row['measurements'];limits=directions[direction]
                if m.get('command_pwm')!=limits['max_pwm'] or m.get('requested_seconds')!=limits['max_duration']:
                    raise ValueError('trial must exercise declared direction envelope')
            for raw in row['raw_artifacts']:
                p=Path(raw['path'])
                if hashlib.sha256(p.read_bytes()).hexdigest()!=raw['sha256']:raise ValueError('raw measurement changed')
            if stage in ('explicit_stop','tcp_loss','pi_loss','local_expiry','floor_braking'):
                m=row['measurements']
                if (not finite(m.get('stop_uncertainty_seconds')) or not 0<=m['stop_uncertainty_seconds']<=.05
                        or not finite(m.get('distance_uncertainty_m')) or not 0<=m['distance_uncertainty_m']<=.02
                        or not finite(m.get('stop_seconds')) or m['stop_seconds']<0
                        or not m['stop_seconds']+m['stop_uncertainty_seconds']<=env['max_stop_seconds']
                        or not finite(m.get('post_stop_m')) or m['post_stop_m']<0
                        or not m['post_stop_m']+m['distance_uncertainty_m']<=env['max_stop_m']):
                    raise ValueError('stopping measurements exceed envelope')
        if stage in ('wheels_up','floor_braking') and min(direction_counts.values())<3:
            raise ValueError('each direction requires three distinct measured envelope trials')
    if (len({r['sha256'] for s in required for r in report['trials'][s]})!=sum(len(report['trials'][s]) for s in required)):
        raise ValueError('trial files must be distinct; replays are not independent')
    return report


def evaluate(journal, report_ref, *, autonomous=False):
    report=validate_report(artifact(report_ref),autonomous=autonomous)
    return journal.append('observation',dict(category='mobile_physical_qualification',report=report,
        report_artifact=report_ref,passed=True,autonomous=autonomous,runtime_sha256=runtime_hash()),
        episode='mobile-qualification',producer='independent-mobile-evaluator',version='mobile-safety-v1')


def active_mobile(deployment, *, now, boot_id, hardware_id, zone):
    active=deployment.active('mobile-pet-follow')
    if not active or not active.get('candidate_id'):raise ValueError('no active mobile qualification')
    auth=active['authorization']
    if (auth.get('boot_id')!=boot_id or auth.get('hardware_id')!=hardware_id or auth.get('zone')!=zone
            or not finite(auth.get('expires_at')) or not now<auth['expires_at']
            or auth.get('execution')!='physical' or not finite(auth.get('issued_at'))
            or not auth['issued_at']<=now or not 0<auth['expires_at']-auth['issued_at']<=600):raise ValueError('fresh boot-bound physical authority required')
    q=deployment.journal.get(active['qualification_id'])
    if q.data['producer']!='independent-mobile-evaluator':raise ValueError('independent mobile evaluator required')
    p=q.data['payload']
    if p.get('passed') is not True or p.get('runtime_sha256')!=runtime_hash():raise ValueError('runtime qualification changed')
    report=validate_report(artifact(p['report_artifact']),autonomous=auth['mode']=='qualified_autonomous',live_pet=auth.get('purpose')=='live_pet')
    if report!=p['report'] or report['hardware_id']!=hardware_id or report['zone']!=zone:raise ValueError('qualification identity changed')
    return active,report


class MobileSafetyContext:
    """Snapshot from an independently qualified sensor producer, never invented.

    Scalar ultrasonic alone cannot produce pet range, floor or lateral coverage.
    No feed producer is installed by this mission. An absent feed fails closed.
    """
    def __init__(self,deployment,*,boot_id,hardware_id,zone,feed=None,clock=None):
        import time
        self.deployment,self.boot_id,self.hardware_id,self.zone=deployment,boot_id,hardware_id,zone
        self.feed=Path(feed) if feed else None;self.clock=clock or time.monotonic
        self.current=None;self.failure='no fresh qualified sensor context';self.health_check=None

    def activation(self):
        return active_mobile(self.deployment,now=self.clock(),boot_id=self.boot_id,
                             hardware_id=self.hardware_id,zone=self.zone)

    def bind(self,observation,tracking):
        """Only annotate a copy after independent provenance/measurement checks."""
        from copy import deepcopy
        out=deepcopy(observation);self.current=None
        try:
            active,report=self.activation()
            if self.feed is None or self.feed.stat().st_size>256*1024:raise ValueError('bounded fresh safety feed missing')
            feed=json.loads(self.feed.read_text());frame=out['frame'];target=tracking.get('target')
            now=self.clock()
            if (feed.get('schema')!='charlie.mobile.safety-snapshot.v1' or not frame.get('authentic')
                    or feed.get('boot_id')!=self.boot_id or feed.get('hardware_id')!=self.hardware_id
                    or feed.get('zone')!=self.zone or feed.get('frame_id')!=frame['id']
                    or feed.get('frame_sha256')!=frame.get('sha256') or target is None
                    or feed.get('track_id')!=target['id'] or feed.get('firmware_sha256')!=report['firmware_sha256']
                    or feed.get('producer_sha256')!=report.get('sensor_producer_sha256')
                    or not report.get('sensor_producer_sha256')
                    or feed.get('scene')!=('proxy-grounded' if active['authorization'].get('purpose')=='proxy' else 'live-animal-grounded')
                    or feed.get('capture_timing_verified') is not True
                    or not finite(feed.get('capture_age_seconds')) or not 0<=feed['capture_age_seconds']<=.5
                    or not finite(feed.get('at')) or not 0<=now-feed['at']<=.25
                    or feed['capture_age_seconds']+now-feed['at']>.5):
                raise ValueError('frame-bound animal/sensor/capture provenance unavailable')
            models=out.get('model',[])
            if not any(m.get('sha256')==report['model_sha256'] for m in models):raise ValueError('model differs from qualification')
            if abs(feed['sensors'].get('yaw',{}).get('degrees',float('inf'))-feed['yaw_deg'])>2:
                raise ValueError('camera and chassis pose disagree')
            required=('pet_willing','human_clear','zone_inspected','power_ok')
            if any(feed['sensors'].get(k) is not True for k in required):raise ValueError('welfare/intrusion/zone/power unverified')
            out['raw_frame']=deepcopy(frame)
            frame.update(source_age_known=True,pan_deg=feed['pan_deg'],yaw_deg=feed['yaw_deg'])
            out.update(qualification='native-qualified',sensors=feed['sensors'],
                grounded_animal=feed['scene']=='live-animal-grounded',grounded_proxy=feed['scene']=='proxy-grounded')
            out['safety_provenance']=dict(qualification_id=active['qualification_id'],firmware_sha256=report['firmware_sha256'],
                bridge_sha256=report['bridge_sha256'],sensor_producer_sha256=report['sensor_producer_sha256'])
            self.current=dict(observation=out,tracking=tracking,activation=active,report=report,at=feed['at'],
                              capture_age_seconds=feed['capture_age_seconds'],feed_digest=digest(feed))
            self.failure=None
        except (KeyError,TypeError,ValueError,OSError) as exc:self.failure=str(exc)
        return out

    def safe(self,proposal):
        from experiments.ppal.mobile_navigation import MobileNavigator
        if self.current is None:return False
        if self.health_check is not None:self.health_check()
        active,report=self.activation();c=self.current
        if self.feed is None or self.feed.stat().st_size>256*1024:return False
        if digest(json.loads(self.feed.read_text()))!=c['feed_digest']:return False
        feed_age=self.clock()-c['at']
        if (active['activation_key']!=c['activation']['activation_key'] or not finite(feed_age)
                or not 0<=feed_age<=.25 or c['capture_age_seconds']+feed_age>.5):return False
        from experiments.ppal.mobile_navigation import MobileLimits
        limits=MobileLimits(stand_off_m=report['envelope']['stand_off_m']+report['envelope']['margin_m'],
            max_duration=min(.2,report['envelope']['max_duration']))
        check=MobileNavigator(limits,clock=self.clock).propose(c['observation'],c['tracking'],c['observation']['sensors'])
        return (not check['reasons'] and check['action']==proposal['action'] and
                check['frame_id']==proposal['frame_id'] and check.get('direction')==proposal.get('direction'))



def calibration_trial(journal, trial_ref, *, execute=False, base_factory=None):
    """One explicitly supervised empty-bench/floor pulse, never a follower.

    Allows staged qualification without needing an already-passed follow trial.
    The dry-run default opens no device. Installed protocol proof remains required.
    """
    trial=artifact(trial_ref)
    if (trial.get('schema')!='charlie.mobile.calibration-trial.v1' or trial.get('runtime_sha256')!=runtime_hash()
            or trial.get('stage') not in ('wheels_up','empty_floor') or not trial.get('witness')
            or not trial.get('hardware_id') or not trial.get('zone') or trial.get('supervised') is not True
            or any(trial.get(k) is not True for k in ('power_cutoff_accessible','no_animals','no_people_in_path','isolated_flat_test_area'))):
        raise ValueError('current reviewed supervised isolated calibration trial required')
    protocol=artifact(trial['protocol_artifact'])
    if (protocol.get('installed_match') is not True or protocol.get('firmware_sha256')!=trial.get('firmware_sha256')
            or protocol.get('bridge_sha256')!=trial.get('bridge_sha256') or not trial.get('firmware_sha256')
            or protocol.get('motion')!={'LEFT':1,'RIGHT':2,'FORWARD':3,'REVERSE':4}
            or protocol.get('local_expiry_source_verified') is not True):
        raise ValueError('installed source-bound timer protocol required before first motor trial')
    require_timed_motion(protocol)
    if trial['stage']=='wheels_up' and trial.get('wheels_clear') is not True:raise ValueError('wheels must be raised')
    if trial['stage']=='empty_floor':
        safety=artifact(trial['local_safety_artifact'])
        if (safety.get('hardware_id')!=trial['hardware_id'] or safety.get('firmware_sha256')!=trial['firmware_sha256']
                or safety.get('independently_measured') is not True or not safety.get('witness')
                or any(safety.get(k) is not True for k in ('explicit_stop','tcp_loss','pi_loss','local_expiry','power_cutoff'))
                or not safety.get('raw_artifacts')):raise ValueError('measured car-local safety required before floor trial')
        for raw in safety['raw_artifacts']:
            if hashlib.sha256(Path(raw['path']).read_bytes()).hexdigest()!=raw['sha256']:raise ValueError('local safety evidence changed')
    direction,pwm,seconds=trial.get('direction'),trial.get('pwm'),trial.get('seconds')
    if (direction not in ('LEFT','RIGHT','FORWARD','REVERSE') or type(pwm) is not int or not 1<=pwm<=35
            or not finite(seconds) or not 0<seconds<=.2):raise ValueError('single bounded low-speed trial required')
    request=dict(category='mobile_calibration_attempt',trial_artifact=trial_ref,stage=trial['stage'],
        direction=direction,pwm=pwm,seconds=seconds,executed=None,physically_observed=None,
        disposition='reviewed dry-run; no device' if not execute else 'physical attempt; measurements still required')
    if execute:
        import time
        from uuid import uuid4
        from experiments.ppal.mobile_navigation import MotionLease
        from learning.resources import ResourceGuard
        if base_factory is None:
            from motion.mobile_base import MobileBase
            base_factory=MobileBase
        guard=ResourceGuard();guard.check(force=True)
        base=base_factory();boot=uuid4().hex
        try:
            base.connect();lease=MotionLease('supervised_trial',time.monotonic()+.5,trial['witness'],boot)
            try:
                request['wire_result']=base.pulse(direction,pwm=pwm,seconds=seconds,lease=lease,boot_id=boot,
                    envelope={'max_pwm':35,'max_duration':.2},safety_check=lambda:(guard.check(force=True) is None))
            except BaseException as exc:
                request.update(error=type(exc).__name__,delivery='unknown; inspect actual controller and measurements')
                raise
        finally:
            try:request['stop']=base.stop_verified()
            finally:
                try:base.close()
                finally:journal.append('event',request,episode='mobile-calibration',producer='supervised-calibration',version='mobile-safety-v1')
        return request
    journal.append('event',request,episode='mobile-calibration',producer='supervised-calibration',version='mobile-safety-v1')
    return request

def main(argv=None):
    """Native acceptance tools. Only calibrate --execute-supervised can open a device."""
    import argparse
    import platform
    import socket
    p=argparse.ArgumentParser(description=main.__doc__)
    p.add_argument('--journal',type=Path)
    sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('inventory')
    e=sub.add_parser('evaluate');e.add_argument('--report',type=Path,required=True);e.add_argument('--autonomous',action='store_true')
    a=sub.add_parser('activate');a.add_argument('--qualification',required=True);a.add_argument('--authorization',type=Path,required=True)
    c=sub.add_parser('calibrate');c.add_argument('--trial',type=Path,required=True);c.add_argument('--execute-supervised',action='store_true')
    r=sub.add_parser('revoke');r.add_argument('--reason',required=True);r.add_argument('--source',required=True)
    args=p.parse_args(argv)
    if args.action=='inventory':
        try:address=socket.gethostbyname('charlie.local')
        except OSError:address=None
        print(json.dumps(dict(platform=platform.platform(),machine=platform.machine(),python=platform.python_version(),
            runtime_sha256=runtime_hash(),charlie_address=address,device_connections=0,physical_qualification=False)))
        return
    if args.journal is None:raise ValueError('--journal required for durable qualification/authority')
    from memory.evidence import EvidenceJournal
    from learning.deployment import CapabilityDeployment
    journal=EvidenceJournal(args.journal)
    try:
        if args.action=='evaluate':
            ref=dict(path=str(args.report.resolve()),sha256=hashlib.sha256(args.report.read_bytes()).hexdigest())
            row=evaluate(journal,ref,autonomous=args.autonomous)
        elif args.action=='activate':
            if args.authorization.stat().st_size>65536:raise ValueError('bounded authorization required')
            row=CapabilityDeployment(journal).activate_mobile(args.qualification,authorization=json.loads(args.authorization.read_text()))
        elif args.action=='calibrate':
            ref=dict(path=str(args.trial.resolve()),sha256=hashlib.sha256(args.trial.read_bytes()).hexdigest())
            print(json.dumps(calibration_trial(journal,ref,execute=args.execute_supervised)));return
        else:row=CapabilityDeployment(journal).revoke_mobile(reason=args.reason,authorization={'source':args.source})
        print(json.dumps(dict(record_id=row.id,action=args.action,device_connections=0)))
    finally:journal.close()


if __name__=='__main__':main()
