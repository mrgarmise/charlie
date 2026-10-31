"""Independent, artifact-bound admission for the existing actuator gateway.

Accepts external measured evidence only. It cannot manufacture observations,
qualify a device from registry discovery, or commission/arm hardware.
"""
import hashlib
import json
from pathlib import Path
import time
from memory.evidence import digest
from learning.mobile_safety import artifact, finite, runtime_hash, require_timed_motion
from experiments.ppal.mobile_navigation import MotionLease

GROUPS = {'chassis': 'elegoo-chassis', 'camera-pan': 'elegoo-camera-pan', 'telemetry': 'elegoo-telemetry'}
STAGES = {
    'chassis': ('local_expiry','explicit_stop','tcp_loss','pi_loss','wheels_up','floor_braking','power_cutoff','preemption'),
    'camera-pan': ('pan_envelope','pan_stop','pan_loss','pan_alignment','preemption'),
    'telemetry': ('installed_read_only','range_accuracy','yaw_accuracy','freshness','disconnect'),
}


def validate_actuator_report(report):
    group = report.get('group')
    if (report.get('schema') != 'charlie.actuator.qualification.v1' or group not in GROUPS
            or report.get('authentic') is not True or report.get('runtime_sha256') != runtime_hash()
            or not all(report.get(k) for k in ('witness','hardware_id','zone','measured_utc'))):
        raise ValueError('current witnessed actuator qualification required')
    protocol = artifact(report['protocol_artifact'])
    for key in ('firmware_sha256','bridge_sha256'):
        value = report.get(key)
        if not isinstance(value,str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('verified firmware identity required')
        if protocol.get(key) != value:
            raise ValueError('protocol and qualification identities differ')
    if protocol.get('installed_match') is not True:
        raise ValueError('installed firmware/bridge match not established')
    envelope = report['envelope']
    if group == 'chassis':
        require_timed_motion(protocol)
        if (protocol.get('local_expiry_verified') is not True
                or protocol.get('motion') != {'LEFT':1,'RIGHT':2,'FORWARD':3,'REVERSE':4}
                or set(envelope.get('directions',[])) != {'LEFT','RIGHT'}
                or type(envelope.get('max_pwm')) is not int or not 1 <= envelope['max_pwm'] <= 35
                or not finite(envelope.get('max_duration')) or not 0 < envelope['max_duration'] <= .2
                or not finite(envelope.get('max_stop_seconds')) or not 0 < envelope['max_stop_seconds'] <= .5
                or not finite(envelope.get('max_stop_m')) or not 0 < envelope['max_stop_m'] <= .5):
            raise ValueError('independently measured bounded chassis envelope required')
    if group == 'camera-pan':
        if (protocol.get('pan') != {'N':5,'D1':1} or protocol.get('pan_stop_verified') is not True
                or envelope.get('position_command_verified') is not True
                or not finite(envelope.get('min_degrees')) or not finite(envelope.get('max_degrees'))
                or not 20 <= envelope['min_degrees'] < envelope['max_degrees'] <= 160
                or not finite(envelope.get('max_settle_seconds')) or not 0 < envelope['max_settle_seconds'] <= 1
                or not finite(envelope.get('max_stop_seconds')) or not 0 < envelope['max_stop_seconds'] <= .5
                or not finite(envelope.get('max_stop_degrees')) or not 0 < envelope['max_stop_degrees'] <= 5):
            raise ValueError('independently measured pan envelope and stopping required')
    if group == 'telemetry':
        if (protocol.get('ultrasonic_read_only') is not True or protocol.get('ultrasonic') != {'N':21,'D1':2}
                or protocol.get('yaw_read_only') is not True or protocol.get('yaw') != {'N':24}):
            raise ValueError('installed read-only query semantics required')
    identities, raw_hashes = set(), set()
    if group != 'telemetry':
        producer = report.get('sensor_producer_sha256')
        if not isinstance(producer,str) or len(producer) != 64 or any(c not in '0123456789abcdef' for c in producer):
            raise ValueError('independent safety producer identity required')
    for stage in STAGES[group]:
        trials = report.get('trials',{}).get(stage,[])
        if len(trials) < 3:
            raise ValueError('three independent trials required: '+stage)
        direction_counts = {'LEFT': 0, 'RIGHT': 0}
        for ref in trials:
            trial = artifact(ref)
            if (trial.get('authentic') is not True or trial.get('passed') is not True
                    or trial.get('stage') != stage or trial.get('group') != group
                    or trial.get('hardware_id') != report['hardware_id'] or trial.get('zone') != report['zone']
                    or trial.get('firmware_sha256') != report['firmware_sha256']
                    or not trial.get('witness') or not trial.get('utc') or not trial.get('measurements')
                    or not trial.get('raw_artifacts') or not trial.get('trial_id')
                    or trial['trial_id'] in identities):
                raise ValueError('distinct authentic witnessed measurements required: '+stage)
            identities.add(trial['trial_id'])
            for raw in trial['raw_artifacts']:
                path = Path(raw['path'])
                if not path.is_file() or path.stat().st_size > 128*1024*1024:
                    raise ValueError('bounded original measurement required')
                raw_digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if raw_digest != raw['sha256'] or raw_digest in raw_hashes:
                    raise ValueError('original measurement changed or reused')
                raw_hashes.add(raw_digest)
            if group == 'chassis' and stage in ('wheels_up','floor_braking'):
                direction = trial.get('direction')
                measured = trial['measurements']
                if (direction not in direction_counts or measured.get('command_pwm') != envelope['max_pwm']
                        or measured.get('requested_seconds') != envelope['max_duration']):
                    raise ValueError('each direction must exercise the measured envelope')
                direction_counts[direction] += 1
            if group == 'camera-pan' and stage == 'pan_envelope':
                measured = trial['measurements']
                if (measured.get('min_degrees') != envelope['min_degrees']
                        or measured.get('max_degrees') != envelope['max_degrees']
                        or not finite(measured.get('settle_seconds'))
                        or not finite(measured.get('uncertainty_seconds'))
                        or measured['settle_seconds'] < 0 or measured['uncertainty_seconds'] < 0
                        or measured['settle_seconds']+measured['uncertainty_seconds'] > envelope['max_settle_seconds']):
                    raise ValueError('pan envelope and settle measurements required')
            if group == 'camera-pan' and stage in ('pan_stop','pan_loss','preemption'):
                measured = trial['measurements']
                if (not finite(measured.get('stop_seconds')) or not finite(measured.get('uncertainty_seconds'))
                        or not finite(measured.get('post_stop_degrees')) or not finite(measured.get('uncertainty_degrees'))
                        or min(measured['stop_seconds'],measured['uncertainty_seconds'],measured['post_stop_degrees'],measured['uncertainty_degrees']) < 0
                        or measured['stop_seconds']+measured['uncertainty_seconds'] > envelope['max_stop_seconds']
                        or measured['post_stop_degrees']+measured['uncertainty_degrees'] > envelope['max_stop_degrees']):
                    raise ValueError('measured pan stopping exceeds envelope')
            if group == 'chassis' and stage in ('local_expiry','explicit_stop','tcp_loss','pi_loss','floor_braking'):
                measured = trial['measurements']
                if (not finite(measured.get('stop_seconds')) or not finite(measured.get('uncertainty_seconds'))
                        or measured['stop_seconds'] < 0 or measured['uncertainty_seconds'] < 0
                        or measured['stop_seconds']+measured['uncertainty_seconds'] > envelope['max_stop_seconds']
                        or not finite(measured.get('post_stop_m')) or not finite(measured.get('uncertainty_m'))
                        or measured['post_stop_m'] < 0 or measured['uncertainty_m'] < 0
                        or measured['post_stop_m']+measured['uncertainty_m'] > envelope['max_stop_m']):
                    raise ValueError('measured stopping exceeds envelope')
        if group == 'chassis' and stage in ('wheels_up','floor_braking') and min(direction_counts.values()) < 3:
            raise ValueError('three separate trials per chassis direction required')
    return report


def evaluate_actuator(journal, report_ref):
    report = validate_actuator_report(artifact(report_ref))
    return journal.append('observation',dict(category='actuator_physical_qualification',
        report=report,report_artifact=report_ref,passed=True,runtime_sha256=runtime_hash()),
        episode='actuator-qualification',producer='independent-actuator-evaluator',version='actuator-safety-v1')


class ActuatorSafetyAuthority:
    def __init__(self, deployment, *, hardware_id, zone, feed=None, clock=time.monotonic):
        self.deployment,self.hardware_id,self.zone = deployment,hardware_id,zone
        self.feed = Path(feed) if feed else None
        self.clock = clock

    def active(self, group, boot_id):
        activation = self.deployment.active(GROUPS[group])
        if not activation or not activation.get('candidate_id'):
            raise PermissionError('independent group activation absent')
        auth = activation['authorization']; now = self.clock()
        if (auth.get('boot_id') != boot_id or auth.get('hardware_id') != self.hardware_id
                or auth.get('zone') != self.zone or auth.get('execution') != ('read-only' if group == 'telemetry' else 'physical')
                or auth.get('mode') != 'supervised_trial'
                or not finite(auth.get('issued_at')) or not finite(auth.get('expires_at'))
                or not auth['issued_at'] <= now < auth['expires_at'] <= auth['issued_at']+600):
            raise PermissionError('fresh boot/device/zone-bound supervised authority required')
        row = self.deployment.journal.get(activation['qualification_id'])
        payload = row.data['payload']
        if row.data['producer'] != 'independent-actuator-evaluator' or payload.get('passed') is not True:
            raise PermissionError('independent actuator evaluation required')
        report = validate_actuator_report(artifact(payload['report_artifact']))
        if report != payload['report'] or report['group'] != group or report['hardware_id'] != self.hardware_id or report['zone'] != self.zone:
            raise PermissionError('activation differs from qualified device/group/zone')
        return activation, report

    def _snapshot(self, request, report, boot_id):
        if self.feed is None or self.feed.stat().st_size > 256*1024:
            raise PermissionError('independent bounded safety feed unavailable')
        feed = json.loads(self.feed.read_text())
        if (feed.get('schema') != 'charlie.actuator.safety.v1' or feed.get('boot_id') != boot_id
                or feed.get('hardware_id') != self.hardware_id or feed.get('zone') != self.zone
                or feed.get('source') != request.source or feed.get('observation_id') != request.observation_id
                or feed.get('firmware_sha256') != report['firmware_sha256']
                or feed.get('producer_sha256') != report.get('sensor_producer_sha256')
                or not report.get('sensor_producer_sha256') or not finite(feed.get('at'))
                or not 0 <= self.clock()-feed['at'] <= .25
                or feed.get('capture_timing_verified') is not True
                or not finite(feed.get('capture_age_seconds')) or not 0 <= feed['capture_age_seconds'] <= .25
                or feed['capture_age_seconds'] + self.clock()-feed['at'] > .25):
            raise PermissionError('fresh source/firmware-bound independent safety measurements required')
        required = ('power_ok','human_clear','animal_clear','stop_available','zone_inspected')
        required += ('floor_clear','blind_spots_clear','lateral_clear') if request.group == 'chassis' else ('pan_clear','pan_pose_known')
        if any(feed.get(key) is not True for key in required):
            raise PermissionError('independent environment or actuator safety veto')
        # A command acknowledgement is not measured servo position. Every
        # source-bound request must match an independently measured current pan.
        measured, expected = feed.get('pan_degrees'), request.parameters.get('expected_pan_degrees')
        if (not finite(measured) or not finite(expected) or not 20 <= measured <= 160
                or abs(measured-expected) > 2):
            raise PermissionError('independently measured pan disagrees with tracker')
        return feed

    def admit(self, request, evidence, *, boot_id):
        activation, report = self.active(request.group,boot_id)
        if getattr(evidence,'authentic',False) is not True or request.source != 'elegoo-v4':
            raise PermissionError('authentic ELEGOO decision frame required')
        feed = self._snapshot(request,report,boot_id)
        if feed.get('frame_sha256') != evidence.metadata()['sha256']:
            raise PermissionError('safety frame pixels do not match decision source')
        auth = activation['authorization']
        return dict(group=request.group,request_id=request.id,boot_id=boot_id,
            lease=MotionLease(auth['mode'],auth['expires_at'],activation['activation_key'],boot_id),
            envelope=report['envelope'],activation_key=activation['activation_key'],feed_digest=digest(feed))

    def safe(self, request, grant):
        try:
            activation, report = self.active(request.group,grant['boot_id'])
            return (activation['activation_key'] == grant['activation_key'] and
                    digest(self._snapshot(request,report,grant['boot_id'])) == grant['feed_digest'])
        except (OSError,KeyError,ValueError,PermissionError):
            return False

    def telemetry_protocol(self, *, boot_id):
        activation,report = self.active('telemetry',boot_id)
        return dict(artifact(report['protocol_artifact']),read_only_connection_authorized=True,
                    evidence_id=activation['qualification_id'],firmware_identity=report['firmware_sha256'])


def main(argv=None):
    """Inspect/evaluate/install EXTERNAL evidence and authority; never device I/O."""
    import argparse
    from memory.evidence import EvidenceJournal
    from learning.deployment import CapabilityDeployment
    p=argparse.ArgumentParser(description=main.__doc__)
    p.add_argument('--journal',type=Path,required=True)
    sub=p.add_subparsers(dest='action',required=True)
    status=sub.add_parser('status');status.add_argument('--boot-id',required=True)
    status.add_argument('--hardware-id',required=True);status.add_argument('--zone',required=True)
    evaluate=sub.add_parser('evaluate');evaluate.add_argument('report',type=Path)
    activate=sub.add_parser('activate');activate.add_argument('qualification');activate.add_argument('authorization',type=Path)
    revoke=sub.add_parser('revoke');revoke.add_argument('target',choices=GROUPS.values());revoke.add_argument('--reason',required=True);revoke.add_argument('--source',required=True)
    args=p.parse_args(argv)
    if args.action=='status' and not args.journal.exists():
        print(json.dumps(dict(status='NEEDS_QUALIFICATION',device_connections=0)));return
    journal=EvidenceJournal(args.journal,read_only=args.action=='status')
    try:
        deployment=CapabilityDeployment(journal)
        if args.action=='status':
            authority=ActuatorSafetyAuthority(deployment,hardware_id=args.hardware_id,zone=args.zone)
            from learning.face_trial import authorization_status
            from types import SimpleNamespace
            result=authorization_status(SimpleNamespace(authority=authority,boot_id=args.boot_id,stop_uncertain=(args.journal.parent/'elegoo-uncertain-motion.lock').exists()))
        elif args.action=='evaluate':
            row=evaluate_actuator(journal,dict(path=str(args.report.resolve()),sha256=hashlib.sha256(args.report.read_bytes()).hexdigest()))
            result=dict(record_id=row.id)
        elif args.action=='activate':
            if args.authorization.stat().st_size>65536:raise ValueError('bounded external authorization required')
            row=deployment.activate_actuator(args.qualification,authorization=json.loads(args.authorization.read_text()))
            result=dict(record_id=row.id)
        else:
            row=deployment.revoke_actuator(args.target,reason=args.reason,authorization={'source':args.source})
            result=dict(record_id=row.id)
        print(json.dumps(dict(result,device_connections=0)))
    finally:journal.close()


if __name__=='__main__':main()
