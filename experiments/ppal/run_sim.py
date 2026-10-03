"""Run from the Charlie repo root: python3 -m experiments.ppal.run_sim"""

import argparse
from pathlib import Path

from .forebrain import Forebrain
from .hindbrain import Hindbrain
from .memory import Memory
from .simulator import Simulator


def main() -> None:
    parser = argparse.ArgumentParser(description="PPAL-0.5 causal simulator")
    parser.add_argument("--log", type=Path, default=Path("ppal_sim.jsonl"))
    parser.add_argument("--max-steps", type=int, default=30)
    args = parser.parse_args()
    if args.max_steps < 1:
        parser.error("--max-steps must be positive")

    env, forebrain, hindbrain, memory = Simulator(), Forebrain(), Hindbrain(), Memory(args.log)
    print("Simulator only: actions change the world; no camera, RetroArch, or learning.")
    for _ in range(args.max_steps):
        before = env.observe()
        goal = forebrain.update(before)
        intent, action = hindbrain.decide(before, goal)
        result = env.step(action)
        memory.record(before, goal, intent, action, result.world,
                      reward=result.reward, source="simulator", events=result.events)
        print(f"{before.tick:02d} goal={goal.kind}:{goal.target_id or '-'} "
              f"intent={intent.kind}:{intent.target_id or '-'} "
              f"move={action.move} fire={action.fire} "
              f"player=({result.world.player.x:.1f},{result.world.player.y:.1f}) "
              f"reward={result.reward:+d} events={','.join(result.events) or '-'}")
        if result.done:
            break
    print(f"Finished={env.done} alive={env.alive} score={env.score} "
          f"steps={env.tick} log={args.log}")


if __name__ == "__main__":
    main()
