"""Explicitly authorized physical preflight, never gameplay or deployment.

Use simulate_active_vision for hardware-free experiments. This entrypoint refuses
before constructing serial/camera objects unless scoped control is requested.
That request cannot physically arm the RP2040 or override its calibration/gate.
"""
import argparse
from pathlib import Path
import signal
import time
import os
from .active_vision import ActiveVision, Config, discover, robotron_target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target', choices=('rectangle','robotron'), default='rectangle')
    parser.add_argument('--port', default='/dev/ttyACM0')
    parser.add_argument('--neck-state-directory', type=Path,
        default=Path(os.environ.get('CHARLIE_NECK_STATE', str(Path.home()/'.local/share/charlie/neck'))))
    parser.add_argument('--authorize-head-motion', action='store_true')
    for name in ('pan-min', 'pan-max', 'tilt-min', 'tilt-max'):
        parser.add_argument('--' + name, type=float)
    parser.add_argument('--wait-for-local-arm', type=float, default=0)
    args = parser.parse_args()
    if not 0 <= args.wait_for_local_arm <= 60:
        parser.error('local arming wait must be 0..60 seconds')
    if not args.authorize_head_motion:
        parser.error('explicit head-motion authorization is required; use simulate_active_vision instead')
    if any(getattr(args, name) is None for name in
           ('pan_min', 'pan_max', 'tilt_min', 'tilt_max')):
        parser.error('all four physical movement boundaries are required')
    try:
        cfg = Config(
            pan_min=args.pan_min, pan_max=args.pan_max,
            tilt_min=args.tilt_min, tilt_max=args.tilt_max,
            step=2, rate=5, acquisition_moves=8, experiments=8,
        )
        # Physical travel limits must be deliberately narrow.
        if cfg.pan_max - cfg.pan_min > 20:
            parser.error('physical pan envelope exceeds 20 degrees')
        if cfg.tilt_max - cfg.tilt_min > 20:
            parser.error('physical tilt envelope exceeds 20 degrees')
    except ValueError as exc:
        parser.error(str(exc))
    if args.output.exists():
        parser.error('output already exists; preserve evidence by choosing a new directory')
    from hardware.rp2040_controller import RP2040Controller
    from .sources import PiCameraSource
    from .passive import PassivePublisher
    controller = RP2040Controller(port=args.port)
    neck = None
    handlers = {}
    try:
        from hardware.calibration_service import CalibrationService
        neck = CalibrationService.open(controller, args.neck_state_directory)
        deadline=time.monotonic()+args.wait_for_local_arm
        while True:
            status=controller.motion_status()
            if not status or not status.get('envelope') or not status.get('electrical_gate_cleared'):
                raise RuntimeError('RP2040 assembled calibration/electrical gate is blocked')
            if status.get('armed'):break
            if time.monotonic()>=deadline:
                raise RuntimeError('RP2040 is DISARMED; Pi authorization cannot physically arm it')
            time.sleep(.1)
        optimizer = ActiveVision(lambda:PiCameraSource(role='active_vision'), controller, args.output,
            initial_pose=(status['pan'],status['tilt']), authorized=True,
            detector=robotron_target if args.target=='robotron' else discover,
            publisher_factory=PassivePublisher, config=cfg,
            journal=neck.journal, calibration_service=neck)
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
        try:
            if neck is not None:neck.close()
        finally:
            try:controller.stop()
            finally:controller.close()


if __name__ == '__main__':
    main()
