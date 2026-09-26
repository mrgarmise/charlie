"""Record a real camera/control calibration clip, with neutral controls by default."""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import time

from experiments.ppal.models import Action
from .live import ArcadeController, DIRECTIONS, RobotronSession


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True, help='Pi Zero arcade address')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--camera-url', default='http://192.168.4.1:81/stream')
    parser.add_argument('--output', type=Path, required=True, help='new recording directory')
    parser.add_argument('--seconds', type=float, default=15)
    parser.add_argument('--move', choices=DIRECTIONS, default='STAY')
    parser.add_argument('--fire', choices=DIRECTIONS, default='NONE')
    parser.add_argument('--pulse', type=float, default=.1,
                        help='one initial controller test pulse, then neutral recording')
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 120 or not math.isfinite(args.pulse) or not 0 < args.pulse <= 2:
        parser.error('Recording must be 0–120 seconds; pulse must be 0–2 seconds')
    import cv2
    from hardware.elegoo_camera import ElegooCamera
    args.output.mkdir(parents=True, exist_ok=False)
    action = Action(args.move, args.fire, 'live calibration')
    camera = ElegooCamera(args.camera_url, timeout=2)
    controller = ArcadeController(args.host, args.port)
    summary = {'source': 'physical-camera', 'metrics_verified': False, 'frames': 0}
    try:
        with RobotronSession(controller, camera) as session:
            observation = session.step(action, args.pulse)
            (args.output / 'action.json').write_text(json.dumps(asdict(action)))
            deadline = time.monotonic() + args.seconds
            with (args.output / 'frames.jsonl').open('w') as log:
                while True:
                    filename = f"frame-{summary['frames']:05d}.jpg"
                    if not cv2.imwrite(str(args.output / filename), observation['frame']):
                        raise OSError('Could not save camera frame')
                    log.write(json.dumps({'file': filename, 'received_at': observation['received_at']}) + '\n')
                    summary['frames'] += 1
                    if time.monotonic() >= deadline:
                        break
                    frame = camera.read(timeout=2, require_new=True)
                    observation = {'frame': frame, 'received_at': time.monotonic()}
    finally:
        (args.output / 'capture.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
