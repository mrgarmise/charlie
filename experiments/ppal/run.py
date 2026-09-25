"""Run with: python -m experiments.ppal.run [--log PATH]."""

import argparse
from pathlib import Path

from .controller import DryRunController
from .forebrain import Forebrain
from .hindbrain import Hindbrain
from .memory import Memory
from .vision import demo_frames


def main() -> None:
    parser = argparse.ArgumentParser(description="PPAL-0 synthetic rescue demonstration")
    parser.add_argument("--log", type=Path, default=Path("ppal_demo.jsonl"))
    args = parser.parse_args()
    frames = demo_frames()
    forebrain, hindbrain, controller, memory = Forebrain(), Hindbrain(), DryRunController(), Memory(args.log)
    print("Scripted observations; actions do not alter the next frame. No learning or hardware control.")
    for before, after in zip(frames, frames[1:]):
        goal = forebrain.update(before)
        intent, action = hindbrain.decide(before, goal)
        controller.execute(action)
        memory.record(before, goal, intent, action, after)
        print(f"{before.tick}: goal={goal.kind}:{goal.target_id or '-'} "
              f"intent={intent.kind}:{intent.target_id or '-'} "
              f"move={action.move} fire={action.fire} ({action.reason})")
    final_goal = forebrain.update(frames[-1])
    print(f"{frames[-1].tick}: goal={final_goal.kind} (rescue target no longer visible)")
    print(f"Recorded {len(frames) - 1} scripted transitions in {args.log}")


if __name__ == "__main__":
    main()
