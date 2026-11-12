"""Read-only saved-frame CPU benchmark. No camera/controller, identity or learning claims."""
import argparse
import json
from pathlib import Path
import time
from PIL import Image
from .gameplay_engine import CycleMetrics,AgencyScreen
from .eyes.taught_recognizer import TaughtRecognizer
from .eyes.sprites import regions
from .eyes.tracking import SpriteTracker
from .agency import AgencyTracker
from .robotron_screen_state import classify_screen_state
from .projectile_agency import candidates
from .forebrain import Forebrain
from .hindbrain import Hindbrain
from .models import Position,WorldState


def benchmark(paths,recognizer,*,repeats=2):
    metrics=CycleMetrics();tracker=SpriteTracker();agency=AgencyTracker();brain=Forebrain();hind=Hindbrain()
    screen=AgencyScreen(classify_screen_state,lambda:True);screen.active=True
    tick=0
    for _ in range(repeats):
        for path in paths:
            with metrics.measure('image_decode'):
                with Image.open(path) as im:frame=im.convert('RGB')
            with metrics.measure('full_terminal_classifier'):classify_screen_state(frame)
            # Explicit hypothetical supported-SELF context only measures scheduler
            # cost; these historical frames have no confirmed SELF identity.
            screen.reference=screen.signature(frame)
            with metrics.measure('hypothetical_supported_SELF_screen'):screen(frame)
            with metrics.measure('legacy_patch_classification'):
                for _,_,patch in regions(frame):recognizer.classify_patch(patch)
            with metrics.measure('batched_detection_and_classification'):pairs=recognizer.detect(frame)
            with metrics.measure('class_free_detection'):candidates(frame)
            with metrics.measure('tracking_and_belief'):
                assignments=tracker.update(tick,[d for d,_ in pairs],observed_at=float(tick+1))
                agency.observe({key:pairs[index][0].center for index,key in assignments.items()})
            world=WorldState(tick,Position(50,50),(),(),alive=True)
            with metrics.measure('hypothetical_existing_tactical_policy'):
                goal=brain.update(world);hind.decide(world,goal)
            tick+=1
    return dict(schema='agency-engine-replay-cost-v1',authentic_new_experience=False,native=False,
        caveat='CPU costs on archived pixels; hypothetical SELF/policy inputs are benchmark fixtures, not recovered identity',
        images=[str(p) for p in paths],repeats=repeats,
        stages={name:metrics.distribution(values) for name,values in metrics.stages.items()},
        unmeasured=['native camera delivery','perspective correction on full raw pixels',
                    'controller response','complete-game performance','sustained native gameplay update rate'],
        original_trajectory_gates_unchanged=True)


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--frames',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--repeats',type=int,default=2)
    ap.add_argument('--knowledge',type=Path,default=Path('config/robotron/sprite-knowledge.json'))
    args=ap.parse_args(argv)
    if not 1<=args.repeats<=10:ap.error('repeats must be 1..10')
    if args.output.resolve().is_relative_to(args.frames.resolve()):ap.error('output must be outside original frames')
    paths=sorted(args.frames.glob('raw-*.png'))[:60]
    if not paths:ap.error('no raw-*.png archived playfield frames')
    result=benchmark(paths,TaughtRecognizer.load(args.knowledge),repeats=args.repeats)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
