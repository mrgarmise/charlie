"""Charlie's normal application: attention/vision plus Executive development.

--offline runs the same lifecycle without initializing physical capabilities.
"""
import argparse
import json
import multiprocessing
from pathlib import Path
import time


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--offline',action='store_true',help='no camera, motion, firmware or game transport')
    p.add_argument('--learning-state',type=Path,default=Path.home()/'.local/share/charlie/development')
    p.add_argument('--episode-root',type=Path,action='append',default=[])
    p.add_argument('--history-root',type=Path,action='append',default=[],help='preserve and additively restore an existing notebook')
    p.add_argument('--learning-budget',type=float,default=10.)
    p.add_argument('--learning-interval',type=float,default=5.)
    p.add_argument('--learning-turns',type=int,help='bounded offline acceptance run')
    p.add_argument('--learning-cpu-cores',type=int,default=2)
    p.add_argument('--learning-memory-mb',type=int,default=768)
    p.add_argument('--learning-temperature-c',type=float,default=75.)
    p.add_argument('--allow-offline-improvements',action='store_true',
        help='external authority for independently qualified offline-shadow candidates only')
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    if args.learning_turns and not args.offline:
        raise ValueError('bounded acceptance runs must be offline')
    roots=args.episode_root or [Path(__file__).resolve().parent/'robotron-runs']
    from learning.lifecycle import run
    from learning.resources import DevelopmentResources
    resources=DevelopmentResources(args.learning_cpu_cores,args.learning_memory_mb,args.learning_temperature_c)
    authority=(dict(source='normal application startup: explicit offline-improvement authorization',
        target='offline-shadow',execution='offline') if args.allow_offline_improvements else None)
    kwargs=dict(budget_seconds=args.learning_budget,interval=args.learning_interval,
                turns=args.learning_turns,offline_authority=authority,history_roots=args.history_root,resources=resources)
    if args.offline:
        run(args.learning_state,roots,**kwargs)
        return
    # Spawn a single application-owned child; no hardware objects are inherited.
    process=multiprocessing.get_context('spawn').Process(target=run,args=(args.learning_state,roots),kwargs=kwargs)
    process.start()
    next_worker_restart=0.
    attention=camera=None
    try:
        from motion.controller import Deck
        from attention.manager import AttentionManager
        from stimulus.bus import StimulusBus
        from stimulus.keyboard import KeyboardStimulus
        from vision.camera import Camera
        from vision.detector import ColorDetector
        from vision.stimulus import VisionStimulus
        deck=Deck()
        bus=StimulusBus()
        attention=AttentionManager(bus)
        KeyboardStimulus(bus)
        camera=Camera()
        detector=ColorDetector(lower=[105,150,70],upper=[125,255,160])
        vision=VisionStimulus(camera,detector,bus)
        bus.emit('idle')
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
        if attention: attention.close()
        if camera: camera.close()
        if process.is_alive():
            process.terminate()  # SIGTERM lets bounded work persist/close normally.
        process.join(timeout=args.learning_budget+10)
        if process.is_alive():
            process.kill()
            process.join()


if __name__=='__main__':
    main()
