"""Normal face session adapter; reuses existing owners, tracker and recorder.

This module never qualifies or authorizes an actuator. No hardware is initialized
on import; main.py supplies the application feeder, executor and telemetry owner.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
from dataclasses import asdict
import json
from pathlib import Path
import signal
import threading
import time


def authorization_status(executor):
    groups = {}
    for group in ('telemetry','camera-pan','chassis'):
        try:
            if executor.stop_uncertain:raise PermissionError('uncertain motion incident retained')
            if getattr(executor,'_safety_stopped',False):raise PermissionError('emergency STOP latched')
            if executor.authority is None:raise PermissionError('independent authority missing')
            executor.authority.active(group,executor.boot_id)
            groups[group] = dict(installed=True)
        except (OSError,ValueError,KeyError,PermissionError) as exc:
            groups[group] = dict(installed=False,reason=str(exc)[:512])
    return dict(boot_id=executor.boot_id,groups=groups,
        ready=all(g['installed'] for g in groups.values()),
        dispatch_requires_fresh_safety_feed=True,physical_acceptance=False)


class FaceTrialEvidence:
    """Adapter to the existing bounded FIFO evidence writer, never a camera."""
    def __init__(self, directory, executor):
        from experiments.ppal.progress_evidence import CaptureEvidence
        from learning.mobile_safety import runtime_hash
        import subprocess
        self.directory=Path(directory)
        self.directory.mkdir(mode=0o700,parents=True,exist_ok=False)
        repo=Path(__file__).resolve().parents[1]
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
        dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True))
        import hashlib
        model_sha=hashlib.sha256((repo/'face_detection_yunet.onnx').read_bytes()).hexdigest()
        self.writer=CaptureEvidence(self.directory,'face:'+executor.boot_id,
            dict(code_revision=revision,dirty_worktree=dirty,model_sha256=model_sha,
                 runtime_sha256=runtime_hash(),boot_id=executor.boot_id,
                 utc=datetime.now(timezone.utc).isoformat(),monotonic=time.monotonic(),
                 wall_seconds=time.time(),physical_outcome='unverified'),
            capacity=8,record_capacity=256,byte_capacity=32*1024*1024,visual_hz=5.)
        self.writer.preparing=False
        self.executor=executor;self.wire_sequence=0;self.sequences={};self.frame_id=None;self.last_state=None;self.faults={}

    def observation(self, frame, face):
        from PIL import Image
        self.frame_id=getattr(frame,'frame_id',getattr(frame,'id',None))
        self.writer.capture(Image.fromarray(frame.image[:,:,::-1]),
            dict(frame.metadata(),timestamp=frame.received_at,clock='host monotonic receipt; exposure unknown'))
        self.writer.event('face_selection',dict(frame_id=self.frame_id,authentic=frame.authentic,
            selected_face=face,identity='face detected; person identity unverified'),at=time.monotonic())

    def poll(self, face=None):
        if self.writer.latest_observation is None:return
        car=self.executor.base.car
        history=car.wire_history(self.wire_sequence)
        if history['events'] or history['evicted']:
            self.writer.event('face_wire',history,at=time.monotonic())
            self.wire_sequence=history['latest']
            if history['evicted']:raise OSError('wire evidence overrun; trial inconclusive')
        for source in ('elegoo-actuator-state','elegoo-pose','elegoo-ultrasonic'):
            try:rows=self.executor.bus.recent_observations(source,max_age=5.)
            except OSError as exc:
                if self.faults.get(source)!=str(exc):
                    self.writer.event('face_source_fault',dict(source=source,error=str(exc)),at=time.monotonic())
                    self.faults[source]=str(exc)
                continue
            if rows:self.faults.pop(source,None)
            for row in rows:
                key=(source,row.generation);prior=self.sequences.get(key,-1)
                if row.sequence<=prior:continue
                self.writer.event('face_shared_observation',dict(source=source,sequence=row.sequence,
                    generation=row.generation,received_at=row.received_at,values=row.values,
                    provenance=row.provenance,history_gap=prior>=0 and row.sequence!=prior+1),at=time.monotonic())
                self.sequences[key]=row.sequence
        if face is not None:
            state=dict(frame_id=self.frame_id,status=face.last_status,alignment=asdict(face.mobile.align),
                pan_command_estimate=face.behavior.pan,independent_pose=False)
            if state!=self.last_state:
                self.writer.event('face_tracking_state',state,at=time.monotonic())
                from copy import deepcopy
                self.last_state=deepcopy(state)

    def close(self):
        self.writer.close()


def run_face(args, resources, frame_bus, executor, telemetry, *, supervise=lambda:None):
    resources.apply()
    from attention.manager import AttentionManager
    from behaviors.mobile_face_runtime import MobileFaceRuntime
    from learning.resources import ResourceGuard
    from stimulus.bus import StimulusBus
    from stimulus.keyboard import KeyboardStimulus
    from memory.gateway import MemoryGateway
    guard=ResourceGuard(resources);guard.check(force=True)
    events=StimulusBus()
    with ExitStack() as owners:
        evidence=FaceTrialEvidence(args.face_evidence_dir,executor)
        owners.callback(evidence.close)
        attention=AttentionManager(events,mobile_enabled=False,emergency_stop=executor.emergency_stop)
        owners.callback(attention.close)
        face=None
        # STOP/cancellation precede writer flush and closing shared owners.
        closed=[False]
        def close_face():
            if closed[0]:return
            closed[0]=True
            try:
                if face is not None:face.close()
            finally:evidence.poll(face)
        owners.callback(close_face)
        keyboard=KeyboardStimulus(events,emergency_only=True,on_emergency=executor.emergency_stop,stop_on_eof=True)
        owners.callback(keyboard.close)
        if threading.current_thread() is threading.main_thread():
            previous=signal.getsignal(signal.SIGTERM)
            def terminate(signum,frame):raise KeyboardInterrupt('supervised face trial terminated')
            signal.signal(signal.SIGTERM,terminate)
            owners.callback(signal.signal,signal.SIGTERM,previous)
        disposition='NOT_STARTED';error=None
        wait_started=time.monotonic();previous=None;last_check=0.;started=None;disk_check=0.;last_telemetry=0.
        try:
            while True:
                supervise();guard.check()
                attention.update(None)
                if attention.emergency_stopped:
                    disposition='OPERATOR_STOPPED_UNEVALUATED';break
                now=time.monotonic()
                if started is None:
                    if now-last_check>=1.:
                        status=authorization_status(executor);last_check=now
                        if status!=previous:print(json.dumps(dict(face_trial='AWAITING_INDEPENDENT_AUTHORIZATION',**status)),flush=True);previous=status
                        if status['ready']:
                            from vision.mobile_face import MobileFaceDetector
                            detector=MobileFaceDetector(model_path=str(Path(__file__).resolve().parents[1]/'face_detection_yunet.onnx'))
                            face=MobileFaceRuntime(frame_bus,events,executor,detector=detector,
                                memory_gateway=MemoryGateway(),observation_callback=evidence.observation)
                            started=time.monotonic();disposition='RECORDED_UNEVALUATED'
                    if started is None:
                        if now-wait_started>=args.face_authorization_wait:raise TimeoutError('independent actuator authorizations not installed; no trial started')
                        time.sleep(.02);continue
                if now-started>=args.face_trial_seconds or attention.emergency_stopped:break
                if now-last_telemetry>=.1:
                    telemetry.poll();last_telemetry=time.monotonic()
                    pose=frame_bus.latest_observation('elegoo-pose',max_age=.25)
                    if pose is None or pose.values.get('yaw_valid') is not True:
                        raise OSError('full trial requires fresh verified yaw')
                face.observe();attention.update(None);evidence.poll(face)
                if face.last_status and face.last_status.get('state') in ('MOTION_UNAVAILABLE','SOURCE_FAULT'):
                    raise RuntimeError('physical trial inconclusive: '+str(face.last_status))
                if now-disk_check>=1.:
                    disk_check=now
                    if sum(p.stat().st_size for p in evidence.directory.rglob('*.png'))>256*1024*1024:
                        raise OSError('trial pixel disk budget exceeded; preserve incomplete trial')
                time.sleep(.02)
        except KeyboardInterrupt:
            disposition='OPERATOR_STOPPED_UNEVALUATED'
            executor.emergency_stop()
        except BaseException as exc:
            disposition='FAILED_OR_INCONCLUSIVE';error=dict(type=type(exc).__name__,message=str(exc)[:1000])
            raise
        finally:
            try:close_face()
            finally:
                evidence.writer.append_line(evidence.directory/'steps.jsonl',dict(
                    category='face_trial_disposition',disposition=disposition,error=error,
                    at=time.monotonic(),utc=datetime.now(timezone.utc).isoformat(),
                    physical_acceptance=False,independent_evaluation_required=True,
                    resources=guard.sample,recording=evidence.writer.telemetry()))
