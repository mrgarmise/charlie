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
        telemetry_at = 0.
        keyboard = KeyboardStimulus(bus, object_mode=True,
            on_emergency=actuator_executor.emergency_stop if actuator_executor is not None else None)
        lifecycle.callback(keyboard.close)
        count = 0
        started = time.monotonic()
        try:
            while not recognition.stopped:
                supervise()
                recognition.controls()
                if recognition.stopped:break
                if telemetry is not None and time.monotonic()-telemetry_at >= .1:
                    telemetry.poll();telemetry_at=time.monotonic()
                if face_runtime is not None:
                    face_runtime.observe()
                    recognition.attention.update(None)
                if args.object_frames is not None and count >= args.object_frames:
                    break
                if args.object_seconds is not None and time.monotonic()-started >= args.object_seconds:
                    break
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
