"""Witness an admitted foreground session via existing local clients, never open devices."""
import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_adoption.shared_profile import SESSION


def sample():
    from tools.runtime_adoption.inventory import resources
    result = dict(at=time.monotonic(), host=resources())
    for key, argv in [('hailo', ['fuser', '/dev/hailo0']), ('pico', ['fuser', '/dev/ttyACM0']),
                      ('tcp', ['ss', '-Hntp', 'state', 'established']),
                      ('throttling', ['vcgencmd', 'get_throttled'])]:
        try:
            run = subprocess.run(argv, capture_output=True, text=True, timeout=1)
            output = run.stdout
            if key == 'tcp':
                from urllib.parse import urlsplit
                config = json.loads(Path('/home/five/charlie-mobile-models/mobile-models.json').read_text())
                url = urlsplit(config.get('stream_url') or 'http://192.168.4.1:81/stream')
                peer = f'{url.hostname}:{url.port or 80}'
                output = '\n'.join(line for line in output.splitlines() if peer in line.split())
            result[key] = dict(exit=run.returncode, output=output.strip()[:2048],
                               diagnostic=run.stderr.strip()[:256])
        except (OSError, subprocess.TimeoutExpired) as exc:
            result[key] = dict(error=type(exc).__name__)
    return result


def witness(path, display):
    from experiments.ppal.eyes.passive import PublishedFrameSubscription
    from learning.recognition_transport import display_label
    deadline = time.monotonic() + 120
    with path.open('x') as output, ExitStack() as children:
        def record(event, value):
            output.write(json.dumps(dict(at=time.monotonic(), event=event, value=value)) + '\n')
            output.flush()
        record('initial', sample())
        while not (SESSION / 'recognition.sock').is_socket():
            if time.monotonic() >= deadline:
                raise TimeoutError('no admitted owner')
            time.sleep(.05)
        deadline = time.monotonic() + 155
        reader = PublishedFrameSubscription('elegoo-v4', max_age=2)
        children.callback(reader.close)
        peers = []
        for _ in range(2):
            proc = subprocess.Popen([sys.executable, '-IB', __file__, '--peer'],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            children.enter_context(proc)
            children.callback(lambda p=proc: p.kill() if p.poll() is None else None)
            peers.append(proc)
        record('under-load', sample())
        seen = []
        end = time.monotonic() + 6
        while time.monotonic() < end:
            try:
                frame = reader.read()
                if frame:
                    seen.append(dict(frame=frame.id, generation=frame.stream_generation))
            except TimeoutError:
                pass
            if seen and all(p.poll() is not None for p in peers):
                break
            time.sleep(.05)
        record('passive-frames', seen)
        for p in peers:
            out, err = p.communicate(timeout=2)
            record('recognition-peer', dict(pid=p.pid, exit=p.returncode,
                                           results=[json.loads(line) for line in out.splitlines()],
                                           error=err[-512:]))
        if display:
            token = (SESSION / 'display.token').read_text().strip()
            for label in ('CHAIR', 'CAT', None):
                record('display', dict(intent=label, acknowledged=display_label(
                    str(SESSION / 'recognition.sock'), token, label)))
                time.sleep(.7)
        record('post-demand', sample())
        while SESSION.exists() and time.monotonic() < deadline:
            time.sleep(2)
            if SESSION.exists():
                record('running', sample())
        record('socket-released', not SESSION.exists())
        record('final', sample())
    print(hashlib.sha256(path.read_bytes()).hexdigest(), path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--receipt', type=Path)
    group.add_argument('--peer', action='store_true')
    parser.add_argument('--display', action='store_true')
    args = parser.parse_args()
    if socket.gethostname() != 'charlie':
        parser.error('run on Charlie alongside an admitted qualification')
    if args.peer:
        from learning.recognition_transport import recognize
        token = (SESSION / 'recognize.token').read_text().strip()
        started = time.monotonic()
        for r in recognize(str(SESSION / 'recognition.sock'), token, frames=2, timeout=8):
            print(json.dumps(dict(elapsed=time.monotonic()-started, **{
                key:r[key] for key in ('source', 'generation', 'frame_id', 'model_sha256')})), flush=True)
    else:
        witness(args.receipt, args.display)


if __name__ == '__main__':
    main()
