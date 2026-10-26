"""Charlie's normal application: attention/vision plus Executive development.

--offline runs the same lifecycle without initializing physical capabilities.
"""
import os
import sys
sys.dont_write_bytecode = True
from contextlib import ExitStack, contextmanager
import argparse
import json
import multiprocessing
from pathlib import Path
import time


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--offline',dest='offline',action='store_true',help='no camera, motion, firmware or game transport (default)')
    mode.add_argument('--hardware',dest='offline',action='store_false',help='explicit separately authorized hardware startup; CAL-1 gates still apply')
    p.set_defaults(offline=True)
    p.add_argument('--learning-state',type=Path,default=Path.home()/'.local/share/charlie/development')
    p.add_argument('--episode-root',type=Path,action='append',default=[])
    p.add_argument('--history-root',type=Path,action='append',default=[],help='preserve and additively restore an existing notebook')
    p.add_argument('--learning-budget',type=float,default=10.)
    p.add_argument('--learning-interval',type=float,default=5.)
    p.add_argument('--learning-turns',type=int,help='bound nonthermal attempt slots; progress counted separately')
    p.add_argument('--learning-cpu-cores',type=int,default=2)
    p.add_argument('--learning-memory-mb',type=int,default=768)
    p.add_argument('--learning-temperature-c',type=float,default=75.)
    p.add_argument('--learning-recovery-temperature-c',type=float,default=65.)
    p.add_argument('--learning-thermal-stabilization',type=float,default=5.)
    p.add_argument('--learning-cooldown-poll',type=float,default=1.)
    p.add_argument('--learning-require-thermal',action='store_true',help='fail closed without thermal telemetry; automatic on ARM Linux')
    p.add_argument('--learning-wall-seconds',type=float,help='cooperative wall deadline; bounded runs default 300s')
    p.add_argument('--learning-cooldown-seconds',type=float,help='maximum continuous cooldown; bounded runs default 120s')
    p.add_argument('--allow-offline-improvements',action='store_true',
        help='external authority for independently qualified offline-shadow candidates only')
    mobile=p.add_mutually_exclusive_group()
    mobile.add_argument('--mobile-replay',type=Path,help='unarmed offline mobile fixture replay')
    mobile.add_argument('--mobile-observe',action='store_true',help='unarmed car-camera perception only; no Deck or mobile actuator initialization')
    p.add_argument('--mobile-manifest',type=Path,help='hash-bound Hailo-8L object/depth export contracts')
    p.add_argument('--mobile-frames',type=int,default=10000)
    p.add_argument('--mobile-seconds',type=float,default=300.)
    p.add_argument('--mobile-max-faults',type=int,default=10)
    p.add_argument('--mobile-retain',choices=['none','events','all'],default='events')
    p.add_argument('--mobile-captures',type=int,default=100)
    p.add_argument('--object-recognition',action='store_true',help='normal stationary Hailo object mode; explicit --hardware required; no motion/navigation')
    p.add_argument('--camera-source',choices=['pi','elegoo'],default='pi',help='camera identity; Pi IMX708 by default')
    p.add_argument('--object-model-manifest',type=Path,default=Path.home()/'charlie-mobile-models/mobile-models.json')
    p.add_argument('--elegoo-stream-url',help='override only the ELEGOO video endpoint')
    p.add_argument('--object-frames',type=int,help='optional bounded recognition session')
    p.add_argument('--object-seconds',type=float,help='optional bounded recognition duration')
    p.add_argument('--object-label-display',choices=['off','dry-run','rp2040'],default='off',help='opt-in stabilized object labels; rp2040 needs reviewed firmware and separately authorized hardware use')
    p.add_argument('--object-label-port',default='/dev/ttyACM0')
    p.add_argument('--object-label-replay',type=Path,help='no-device JSONL event-to-display diagnostic')
    return p


@contextmanager
def application_camera_feeders(args, *, selected=('pi', 'elegoo'), pi_role='primary'):
    """Application lifecycle owns physical feeders; capabilities receive only a bus."""
    from stimulus.bus import StimulusBus
    from experiments.ppal.camera_session import CameraFeeder
    from experiments.ppal.eyes.passive import PassivePublisher, runtime_dir
    from vision.camera_source import capture_factory
    frame_bus = StimulusBus()
    from stimulus.bus import install_application_frames, remove_application_frames
    stream_url = args.elegoo_stream_url
    manifest = args.mobile_manifest if args.mobile_observe else args.object_model_manifest
    if stream_url is None and manifest is not None and manifest.is_file():
        stream_url = json.loads(manifest.read_text()).get('stream_url')
    stream_url = stream_url or 'http://192.168.4.1:81/stream'
    with ExitStack() as lifecycle:
        install_application_frames(frame_bus)
        lifecycle.callback(remove_application_frames,frame_bus)
        for name in selected:
            source_id = {'pi': 'pi-primary', 'elegoo': 'elegoo-v4'}[name]
            publisher = None
            try:
                directory = runtime_dir()
                if name == 'elegoo':
                    directory = directory/'elegoo-v4'
                    directory.mkdir(mode=0o700, exist_ok=True)
                publisher = PassivePublisher(directory)
                lifecycle.callback(publisher.close)
            except OSError:
                pass  # Optional passive UI storage never grants capture ownership.
            feeder = CameraFeeder(lambda name=name: capture_factory(name, stream_url=stream_url, pi_role=pi_role),
                                  frame_bus, source_id, publisher=publisher)
            lifecycle.callback(feeder.close)
            feeder.start()
        yield frame_bus


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    args=parser().parse_args(arguments)
    if args.object_recognition:
        if args.offline or args.mobile_replay or args.mobile_observe or args.object_label_replay:
            raise ValueError('Object Recognition requires explicit --hardware and application camera feeders')
        import math
        if (args.object_frames is not None and (not 1<=args.object_frames<=10000)
                or args.object_seconds is not None and (not math.isfinite(args.object_seconds) or not 0<args.object_seconds<=3600)):
            raise ValueError('bounded object session limits required')
        if not any(a == '--object-label-display' or a.startswith('--object-label-display=') for a in arguments):
            args.object_label_display = 'rp2040'

    if args.learning_turns and not args.offline:
        raise ValueError('bounded acceptance runs must be offline')
    if args.object_label_replay:
        if not args.offline or args.mobile_replay or args.mobile_observe or args.object_label_display=='rp2040':
            raise ValueError('object label replay is an isolated no-device diagnostic')
        from attention.object_display_runtime import replay
        replay(args.object_label_replay)
        return
    if args.mobile_replay and args.object_label_display=='rp2040':
        raise ValueError('fixture replay cannot activate a physical display')
    if args.object_label_display!='off' and args.offline and not (args.mobile_replay or args.mobile_observe):
        raise ValueError('object label display requires an existing observation source')
    roots=args.episode_root or [Path(__file__).resolve().parent/'robotron-runs']
    from learning.lifecycle import run
    from learning.resources import DevelopmentResources
    resources=DevelopmentResources(args.learning_cpu_cores,args.learning_memory_mb,args.learning_temperature_c,
        recovery_temperature_c=args.learning_recovery_temperature_c,
        stabilization_seconds=args.learning_thermal_stabilization,cooldown_poll_seconds=args.learning_cooldown_poll,
        require_thermal=args.learning_require_thermal)
    authority=(dict(source='normal application startup: explicit offline-improvement authorization',
        target='offline-shadow',execution='offline') if args.allow_offline_improvements else None)
    kwargs=dict(budget_seconds=args.learning_budget,interval=args.learning_interval,
                turns=args.learning_turns,offline_authority=authority,history_roots=args.history_root,resources=resources,
                wall_seconds=args.learning_wall_seconds,cooldown_seconds=args.learning_cooldown_seconds)
    if args.mobile_replay or args.mobile_observe:
        if not args.offline:
            raise ValueError('mobile observation entry point cannot combine with --hardware')
        from learning.mobile_runtime import run_mobile
        # A capability command subscribes to the already-running application's
        # publication. It never starts another camera feeder.
        run_mobile(args,resources)
        return
    if args.offline:
        run(args.learning_state,roots,**kwargs)
        return
    # Spawn a single application-owned child; no hardware objects are inherited.
    process=multiprocessing.get_context('spawn').Process(target=run,args=(args.learning_state,roots),kwargs=kwargs)
    process.start()
    next_worker_restart=0.
    def supervise_development():
        nonlocal process, next_worker_restart
        if not process.is_alive() and time.monotonic()>=next_worker_restart:
            process.join()
            print('Development worker interrupted; resuming durable Executive state',flush=True)
            process=multiprocessing.get_context('spawn').Process(target=run,args=(args.learning_state,roots),kwargs=kwargs)
            process.start()
            next_worker_restart=time.monotonic()+5.
    try:
        if args.object_recognition:
            from learning.object_runtime import run_objects
            with application_camera_feeders(args) as frame_bus:
                run_objects(args,resources,frame_bus,supervise=supervise_development)
            return
        with ExitStack() as lifecycle:
            from motion.controller import Deck
            from attention.manager import AttentionManager
            from stimulus.bus import StimulusBus
            from stimulus.keyboard import KeyboardStimulus
            from vision.camera_source import CameraSubscription, TrackingCamera
            from vision.detector import ColorDetector
            from vision.stimulus import VisionStimulus
            deck=Deck()
            lifecycle.callback(deck.body.close)
            lifecycle.callback(deck.stop)
            from hardware.calibration_service import CalibrationService
            neck=CalibrationService.open(deck.body,Path(os.environ.get('CHARLIE_NECK_STATE',str(Path.home()/'.local/share/charlie/neck'))))
            lifecycle.callback(neck.close)
            deck.calibration=neck
            neck.refresh()
            neck.attach_brain(authorized=os.environ.get('CHARLIE_NECK_MOTION_AUTHORIZED')=='1',
                supervised=os.environ.get('CHARLIE_NECK_SUPERVISED')=='1')
            bus=StimulusBus()
            from attention.object_display_runtime import attach
            labels,label_owned=attach(args.object_label_display,clock=time.monotonic,body=deck.body)
            if label_owned is not None:lifecycle.callback(label_owned.close)
            attention=AttentionManager(bus,mobile_enabled=os.environ.get('CHARLIE_MOBILE_ENABLED')=='1',object_labels=labels)
            lifecycle.callback(attention.close)
            keyboard=KeyboardStimulus(bus)
            lifecycle.callback(keyboard.close)
            frame_bus=lifecycle.enter_context(application_camera_feeders(args))
            sources=CameraSubscription(frame_bus)
            lifecycle.callback(sources.close)
            sources.switch(args.camera_source)
            camera=TrackingCamera(sources)
            detector=ColorDetector(lower=[105,150,70],upper=[125,255,160])
            if os.environ.get('CHARLIE_VISION_TARGET')=='face':
                from vision.detector import FaceDetector
                detector=FaceDetector(Path(__file__).resolve().parent/'face_detection_yunet.onnx')
            vision=VisionStimulus(camera,detector,bus,frame_observer=deck.observe_frame)
            bus.emit('idle')
            attention.update(deck)
            previous=None
            while True:
                vision.update()
                attention.update(deck)
                # Existing status surface: console, plus consumable status JSON.
                path=args.learning_state/'development-status.json'
                try:
                    status=json.loads(path.read_text())
                    summary=(status['phase'],status['current_question'],status.get('error'))
                    if summary!=previous:
                        print('Development:',*summary,flush=True)
                        previous=summary
                except (OSError,ValueError):
                    pass
                supervise_development()
                time.sleep(.02)
    finally:
        if process.is_alive():
            process.terminate()  # SIGTERM lets bounded work persist/close normally.
        process.join(timeout=args.learning_budget+10)
        if process.is_alive():
            process.kill()
            process.join()


if __name__=='__main__':
    main()
