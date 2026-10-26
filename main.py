"""Charlie's normal application: attention/vision plus Executive development.

--offline runs the same lifecycle without initializing physical capabilities.
"""
import os
import sys
sys.dont_write_bytecode = True
from contextlib import ExitStack
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
    mobile.add_argument('--pet-abilities',action='store_true',help='normal AttentionManager/Executive pet abilities using existing mobile sensing')
    mobile.add_argument('--pet-follow',action='store_true',help='same abilities; physical follow still requires independent current activation')
    p.add_argument('--list-capabilities',action='store_true',help='inspect normal ability catalog without initializing any devices')
    p.add_argument('--mobile-zone',default='unqualified',help='independently inspected zone identity')
    p.add_argument('--mobile-hardware-id',default='unverified',help='verified physical car identity')
    p.add_argument('--mobile-safety-feed',type=Path,help='independently qualified, frame-bound sensor snapshots; absent fails closed')
    p.add_argument('--mobile-manifest',type=Path,help='hash-bound Hailo-8L object/depth export contracts')
    p.add_argument('--mobile-frames',type=int,default=10000)
    p.add_argument('--mobile-seconds',type=float,default=300.)
    p.add_argument('--mobile-max-faults',type=int,default=10)
    p.add_argument('--mobile-retain',choices=['none','events','all'],default='events')
    p.add_argument('--mobile-captures',type=int,default=100)
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    if args.list_capabilities:
        from learning.capabilities import default_registry
        print(json.dumps(default_registry().describe(),indent=2));return
    if args.learning_turns and not args.offline:
        raise ValueError('bounded acceptance runs must be offline')
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
    if args.mobile_replay or args.mobile_observe or args.pet_abilities or args.pet_follow:
        if args.pet_follow and args.offline:
            raise ValueError('physical pet following requires explicit --hardware; --offline never actuates')
        if not args.pet_follow and not args.offline:
            raise ValueError('mobile observation entry point cannot combine with --hardware')
        from learning.mobile_runtime import run_mobile
        run_mobile(args,resources)
        return
    if args.offline:
        run(args.learning_state,roots,**kwargs)
        return
    # Spawn a single application-owned child; no hardware objects are inherited.
    process=multiprocessing.get_context('spawn').Process(target=run,args=(args.learning_state,roots),kwargs=kwargs)
    process.start()
    next_worker_restart=0.
    try:
        with ExitStack() as lifecycle:
            from motion.controller import Deck
            from attention.manager import AttentionManager
            from stimulus.bus import StimulusBus
            from stimulus.keyboard import KeyboardStimulus
            from vision.camera import Camera
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
            attention=AttentionManager(bus,mobile_enabled=os.environ.get('CHARLIE_MOBILE_ENABLED')=='1')
            lifecycle.callback(attention.close)
            KeyboardStimulus(bus)
            camera=Camera()
            lifecycle.callback(camera.close)
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
                if not process.is_alive() and time.monotonic()>=next_worker_restart:
                    process.join()
                    print('Development worker interrupted; resuming durable Executive state',flush=True)
                    process=multiprocessing.get_context('spawn').Process(target=run,args=(args.learning_state,roots),kwargs=kwargs)
                    process.start()
                    next_worker_restart=time.monotonic()+5.  # Supervision, not another learning scheduler.
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
