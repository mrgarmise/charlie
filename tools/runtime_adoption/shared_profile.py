"""Shared stationary application composition, entered after controller admission."""
from contextlib import contextmanager
from pathlib import Path
import signal

from learning.recognition_transport import channel
from tools.runtime_adoption.stationary_boundary import install, install_stationary_stop

SESSION = Path('/home/five/charlie-ops/recognition-live')


@contextmanager
def session_channel(directory):
    # Only this invocation owns the new directory. An interrupted session requires
    # inspection under the runtime lock, never reuse another session's credentials.
    directory.mkdir(mode=0o700)
    try:
        yield channel(directory)
    finally:
        for name in ('recognize.token', 'display.token'):
            (directory / name).unlink(missing_ok=True)
        directory.rmdir()


def run(state, manifest, stream, *, display=False, summary=None):
    from main import parser, run_application
    from stimulus.keyboard import KeyboardStimulus

    arguments = ['--hardware', '--object-recognition', '--camera-source', 'elegoo',
                 '--executive-recognition', '--object-model-manifest', str(manifest),
                 '--elegoo-stream-url', stream, '--object-seconds', '90',
                 '--object-label-display', 'rp2040' if display else 'off',
                 '--learning-state', str(state), '--learning-require-thermal']
    args = parser().parse_args(arguments)
    args.recognition_summary = summary

    def deadline(*_):
        raise SystemExit('stationary wall deadline exceeded')

    with session_channel(SESSION) as admitted:
        install(stream, recognition_bind=admitted[0])
        restore = install_stationary_stop(KeyboardStimulus)
        previous = signal.signal(signal.SIGALRM, deadline)
        try:
            signal.alarm(150)
            run_application(args, arguments, admitted_channel=admitted)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
            restore()
