"""Explicitly authorized physical preflight, never gameplay or deployment.

Use simulate_active_vision for hardware-free experiments. This entrypoint refuses
before constructing serial/camera objects unless head motion is authorized.
"""
import argparse
from pathlib import Path
import signal
from .active_vision import ActiveVision, discover, robotron_target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target', choices=('rectangle','robotron'), default='rectangle')
    parser.add_argument('--port', default='/dev/ttyACM0')
    parser.add_argument('--authorize-head-motion', action='store_true')
    args = parser.parse_args()
    if not args.authorize_head_motion:
        parser.error('explicit head-motion authorization is required; use simulate_active_vision instead')
    if args.output.exists():
        parser.error('output already exists; preserve evidence by choosing a new directory')
    from hardware.rp2040_controller import RP2040Controller
    from .sources import PiCameraSource
    from .passive import PassivePublisher
    controller = RP2040Controller(port=args.port)
    handlers = {}
    try:
        status = controller.viewpoint_status()
        if not status or not status['stop_hold']:
            raise RuntimeError('tested STOP_HOLD firmware required before Active Vision')
        optimizer = ActiveVision(PiCameraSource, controller, args.output,
            initial_pose=(status['pan'],status['tilt']), authorized=True,
            detector=robotron_target if args.target=='robotron' else discover,
            publisher_factory=PassivePublisher)
        def interrupt(signum, frame):
            optimizer.interrupt()
            raise InterruptedError(f'interrupted by signal {signum}')
        for number in (signal.SIGINT, signal.SIGTERM):
            handlers[number] = signal.signal(number, interrupt)
        result = optimizer.run()
        print(f"{result['state']}: validated configuration at {args.output/'view.json'}; camera released")
    finally:
        for number, handler in handlers.items():
            signal.signal(number, handler)
        try:controller.stop()
        finally:controller.close()


if __name__ == '__main__':
    main()
