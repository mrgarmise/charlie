"""Object Recognition in the normal app; its existing Executive imports evidence."""
from contextlib import ExitStack
import json
from pathlib import Path
import subprocess
import time
from uuid import uuid4


def run_objects(args, resources, frame_bus, *, supervise=lambda: None, actuator_executor=None, telemetry=None):
    from attention.object_display_runtime import attach
    from learning.mobile import MobileEvidenceAdapter
    from learning.resources import ResourceGuard
    from memory.evidence import EvidenceJournal
    from stimulus.bus import StimulusBus
    from stimulus.keyboard import KeyboardStimulus
    from vision.mobile_models import HailoObjects, UnavailableDepth
    from vision.mobile_perception import MobilePerception
    from vision.object_recognition import ObjectRecognition

    config = json.loads(args.object_model_manifest.read_text())
    if config.get('schema') != 'charlie.mobile.models.v1':
        raise ValueError('existing hash-bound Hailo object manifest required')
    objects = dict(config['objects'], include_all=True)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'],
        cwd=Path(__file__).resolve().parents[1], text=True).strip()
    state = args.learning_state.resolve()
    state.mkdir(parents=True, exist_ok=True)
    with ExitStack() as lifecycle:
        detector = HailoObjects(**objects)
        lifecycle.callback(detector.close)
        journal = EvidenceJournal(state/'mobile-evidence.sqlite3')
        lifecycle.callback(journal.close)
        evidence = MobileEvidenceAdapter(journal, episode='objects:'+uuid4().hex, revision=revision)
        perception = MobilePerception(detector, UnavailableDepth(), resources=ResourceGuard(resources),
                                      revision=revision, clock=time.monotonic)
        bus = StimulusBus()
        labels, owned = attach(args.object_label_display, clock=time.monotonic, port=args.object_label_port)
        if owned is not None:
            lifecycle.callback(owned.close)
        recognition = ObjectRecognition(frame_bus, perception, evidence, bus, labels)
        lifecycle.callback(recognition.close)
        recognition.select_camera(args.camera_source)
        face_runtime = None
        if actuator_executor is not None:
            from behaviors.mobile_face_runtime import MobileFaceRuntime
            face_runtime = MobileFaceRuntime(frame_bus,recognition.attention_bus,actuator_executor)
            lifecycle.callback(face_runtime.close)
            recognition.attention.emergency_stop_callback = actuator_executor.emergency_stop
        from ui.dashboard import attach_dashboard
        def borrow_recognition(execution_id):
            previous=recognition.sources.name or args.camera_source
            previous_episode=evidence.episode
            previous_store=getattr(recognition,'artifact_store',None)
            from vision.mobile_perception import FrameArtifactStore, SelectiveFrameArtifacts
            recognition.artifact_store=SelectiveFrameArtifacts(FrameArtifactStore(state/'operator-demo-frames'))
            evidence.episode='operator-demo:'+execution_id
            recognition.invalidate('operator demonstration start')
            recognition.select_camera('pi')
            recognition.output_allowed=lambda: demonstration.running and not demonstration.cancel_requested and time.monotonic()-demonstration.started<15
            class Borrow:
                def step(self):return recognition.step()
                def close(self):
                    recognition.output_allowed=lambda:True
                    evidence.episode=previous_episode
                    recognition.artifact_store=previous_store
                    recognition.invalidate('operator demonstration end')
                    recognition.select_camera(previous)
            return Borrow()
        demonstration=attach_dashboard(args,resources,frame_bus,recognition.attention,lifecycle,factory=borrow_recognition)
        telemetry_at = 0.
        keyboard = KeyboardStimulus(bus, object_mode=True,
            on_emergency=actuator_executor.emergency_stop if actuator_executor is not None else None)
        lifecycle.callback(keyboard.close)
        count = 0
        started = time.monotonic()
        try:
            while not recognition.stopped:
                supervise()
                if args.object_frames is not None and count >= args.object_frames:
                    break
                if args.object_seconds is not None and time.monotonic()-started >= args.object_seconds:
                    break
                recognition.controls()
                if recognition.stopped:break
                if demonstration is not None:
                    demonstration.tick()
                    if demonstration.active is not None:
                        time.sleep(.02)
                        continue
                if recognition.stopped:break
                if telemetry is not None and time.monotonic()-telemetry_at >= .1:
                    telemetry.poll();telemetry_at=time.monotonic()
                if face_runtime is not None:
                    face_runtime.observe()
                    recognition.attention.update(None)
                try:
                    result = recognition.step()
                except (OSError, ValueError) as exc:
                    print(json.dumps(dict(status='recognition suspended', reason=str(exc), motion_authorized=False)),flush=True)
                    time.sleep(.1)
                    continue
                if result:
                    count += 1
                    print(json.dumps(result, allow_nan=False), flush=True)
                time.sleep(.02)
        except KeyboardInterrupt:
            pass
