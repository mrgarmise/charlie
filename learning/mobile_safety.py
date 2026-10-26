"""Independent mobile qualification records for existing CapabilityDeployment.

No hardware I/O; no Executive authority. External measurements stay immutable.
"""
import hashlib
import json
import math
from pathlib import Path
from memory.evidence import digest

RUNTIME_FILES=('hardware/elegoo_mobile.py','motion/mobile_base.py','experiments/ppal/mobile_navigation.py',
 'attention/manager.py','behaviors/mobile_observe.py','learning/mobile.py','learning/mobile_runtime.py',
 'learning/mobile_safety.py','learning/capabilities.py','learning/deployment.py','main.py',
 'vision/mobile_perception.py','vision/mobile_tracking.py','vision/mobile_models.py')
REQUIRED=('stationary_vision','explicit_stop','tcp_loss','pi_loss','local_expiry','power_cutoff',
 'wheels_up','floor_braking','obstacle_abort','edge_abort','target_loss','preemption','proxy_follow')


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


def validate_report(report, *, autonomous=False):
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
    env=report['envelope']
    if (type(env.get('max_pwm')) is not int or not 1<=env['max_pwm']<=35
            or not finite(env.get('max_duration')) or not 0<env['max_duration']<=.2
            or not finite(env.get('max_stop_seconds')) or not 0<env['max_stop_seconds']<=.5
            or not finite(env.get('max_stop_m')) or not 0<env['max_stop_m']<=.5
            or not finite(env.get('stand_off_m')) or env['stand_off_m']<1
            or not finite(env.get('margin_m')) or env['margin_m']<2*env['max_stop_m']
            or env['stand_off_m']<=env['margin_m']):raise ValueError('measured conservative envelope required')
    required=REQUIRED+(('live_pet_follow','voluntary_decline','restart_revoke') if autonomous else ())
    if not isinstance(report.get('sensor_producer_sha256'),str) or len(report['sensor_producer_sha256'])!=64:
        raise ValueError('qualified sensor producer code identity required')
    for stage in required:
        trials=report.get('trials',{}).get(stage,[])
        if len(trials)<3:raise ValueError('three independent measured trials required: '+stage)
        groups=set()
        for ref in trials:
            row=artifact(ref)
            if (row.get('stage')!=stage or row.get('authentic') is not True or row.get('passed') is not True
                    or row.get('hardware_id')!=report['hardware_id'] or row.get('zone')!=report['zone']
                    or row.get('firmware_sha256')!=report['firmware_sha256'] or not row.get('witness')
                    or not row.get('utc') or not row.get('measurements') or not row.get('raw_artifacts')):
                raise ValueError('incomplete independent trial: '+stage)
            if not row.get('trial_id') or row['trial_id'] in groups:raise ValueError('independent trial identities required')
            groups.add(row['trial_id'])
            for raw in row['raw_artifacts']:
                p=Path(raw['path'])
                if hashlib.sha256(p.read_bytes()).hexdigest()!=raw['sha256']:raise ValueError('raw measurement changed')
            if stage in ('explicit_stop','tcp_loss','pi_loss','local_expiry','floor_braking'):
                m=row['measurements']
                if (not finite(m.get('stop_seconds')) or not 0<=m['stop_seconds']<=env['max_stop_seconds']
                        or not finite(m.get('post_stop_m')) or not 0<=m['post_stop_m']<=env['max_stop_m']):
                    raise ValueError('stopping measurements exceed envelope')
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
    report=validate_report(artifact(p['report_artifact']),autonomous=auth['mode']=='qualified_autonomous')
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
        self.current=None;self.failure='no fresh qualified sensor context'

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
                    or not report.get('sensor_producer_sha256') or feed.get('scene')!='live-animal-grounded'
                    or feed.get('capture_timing_verified') is not True
                    or not finite(feed.get('capture_age_seconds')) or not 0<=feed['capture_age_seconds']<=.5
                    or not finite(feed.get('at')) or not 0<=now-feed['at']<=.25):
                raise ValueError('frame-bound animal/sensor/capture provenance unavailable')
            models=out.get('model',[])
            if not any(m.get('sha256')==report['model_sha256'] for m in models):raise ValueError('model differs from qualification')
            required=('pet_willing','human_clear','zone_inspected','power_ok')
            if any(feed['sensors'].get(k) is not True for k in required):raise ValueError('welfare/intrusion/zone/power unverified')
            out['raw_frame']=deepcopy(frame)
            frame.update(source_age_known=True,pan_deg=feed['pan_deg'],yaw_deg=feed['yaw_deg'])
            out.update(qualification='native-qualified',sensors=feed['sensors'],grounded_animal=True)
            out['safety_provenance']=dict(qualification_id=active['qualification_id'],firmware_sha256=report['firmware_sha256'],
                bridge_sha256=report['bridge_sha256'],sensor_producer_sha256=report['sensor_producer_sha256'])
            self.current=dict(observation=out,tracking=tracking,activation=active,report=report,at=feed['at'])
            self.failure=None
        except (KeyError,TypeError,ValueError,OSError) as exc:self.failure=str(exc)
        return out

    def safe(self,proposal):
        from experiments.ppal.mobile_navigation import MobileNavigator
        if self.current is None:return False
        active,report=self.activation();c=self.current
        if active['activation_key']!=c['activation']['activation_key'] or self.clock()-c['at']>.25:return False
        from experiments.ppal.mobile_navigation import MobileLimits
        limits=MobileLimits(stand_off_m=report['envelope']['stand_off_m']+report['envelope']['margin_m'],
            max_duration=min(.2,report['envelope']['max_duration']))
        check=MobileNavigator(limits,clock=self.clock).propose(c['observation'],c['tracking'],c['observation']['sensors'])
        return (not check['reasons'] and check['action']==proposal['action'] and
                check['frame_id']==proposal['frame_id'] and check.get('direction')==proposal.get('direction'))
