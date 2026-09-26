"""Synthetic PPAL decisions routed through the PPAL-1 controller bridge."""

import argparse

from .forebrain import Forebrain
from .hands import RecordingSink, TCPCommandSink
from .hindbrain import Hindbrain
from .simulator import Simulator


def main() -> None:
    parser = argparse.ArgumentParser(description="PPAL-1 two-stick bridge demo")
    parser.add_argument("--tcp", action="store_true", help="send to an explicit JSON-line receiver")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--step-ms", type=int, default=100)
    parser.add_argument("--max-steps", type=int, default=20)
    args = parser.parse_args()
    if args.max_steps < 1:
        parser.error("max-steps must be positive")
    env, forebrain, hindbrain = Simulator(), Forebrain(), Hindbrain()
    sink = TCPCommandSink(args.host, args.port) if args.tcp else RecordingSink()
    print("World state is simulated. This is not camera-driven gameplay.")
    with sink:
        for _ in range(args.max_steps):
            before = env.observe()
            goal = forebrain.update(before)
            _, action = hindbrain.decide(before, goal)
            message = sink.execute(action, args.step_ms)
            result = env.step(action)
            print(f"{before.tick:02d} goal={goal.target_id or goal.kind} "
                  f"move={action.move} fire={action.fire} buttons={message['buttons']} "
                  f"events={','.join(result.events) or '-'}")
            if result.done:
                break
    print(f"Commands={sink.sequence} released=yes alive={env.alive} score={env.score}")


if __name__ == "__main__":
    main()
