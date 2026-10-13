"""One bounded PPAL action, previewed by default; real send requires --connect."""

import argparse

from .arcade_transport import ArcadeController, controls_for, positions_for
from .models import Action


def main() -> None:
    parser = argparse.ArgumentParser(description="PPAL to charlie-arcade protocol probe")
    parser.add_argument("--move", default="STAY")
    parser.add_argument("--fire", default="NONE")
    parser.add_argument("--duration-ms", type=int, default=100)
    parser.add_argument("--connect", action="store_true", help="send one action to the arcade")
    parser.add_argument("--host", help="arcade host/IP, required with --connect")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--protocol", choices=("positions", "legacy"), default="positions")
    args = parser.parse_args()
    action = Action(args.move.upper(), args.fire.upper())
    controls = sorted(controls_for(action))
    if not 30 <= args.duration_ms <= 500:
        parser.error("duration-ms must be 30..500")
    if args.connect and not args.host:
        parser.error("--host is required with --connect")
    print("Send:", ", ".join(positions_for(action)) if args.protocol == "positions" else
          ", ".join(control + "_DOWN" for control in controls) or "(none)")
    print(f"Hold for {args.duration_ms} ms; then NEUTRAL")
    if not args.connect:
        print("Preview only; nothing sent.")
        return
    with ArcadeController(args.host, args.port, protocol=args.protocol) as controller:
        controller.execute(action, args.duration_ms)
    print("Arcade replied OK and controls were released.")


if __name__ == "__main__":
    main()
