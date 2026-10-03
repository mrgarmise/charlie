"""Live actuator/camera adapter for Charlie Arcade's existing TCP protocol.

Acknowledgments are transport acceptance only. Game observations come from
camera pixels; this module never reads emulator memory or screenshots.
"""
import math
import socket
import time

from experiments.ppal.models import Action

DIRECTIONS = {'STAY': 'CENTER', 'NONE': 'CENTER', 'N': 'UP', 'NE': 'UP_RIGHT',
              'E': 'RIGHT', 'SE': 'DOWN_RIGHT', 'S': 'DOWN', 'SW': 'DOWN_LEFT',
              'W': 'LEFT', 'NW': 'UP_LEFT'}


class ArcadeController:
    def __init__(self, host, port=8765, timeout=1.0):
        self.host, self.port, self.timeout = host, port, timeout
        self.socket = None
        self.reader = None

    def open(self):
        if self.socket is not None:
            return
        self.socket = socket.create_connection((self.host, self.port), self.timeout)
        self.reader = self.socket.makefile('rb')
        try:
            self.command('NEUTRAL')
        except BaseException:
            self.close()
            raise

    def command(self, command):
        if command not in {'NEUTRAL', 'START', 'BACK'} and command not in {
            prefix + value for prefix in ('LS_', 'RS_') for value in DIRECTIONS.values()
        }:
            raise ValueError('Unsupported controller command')
        if self.socket is None:
            raise RuntimeError('Controller is not connected')
        try:
            self.socket.sendall((command + '\n').encode('ascii'))
            response = self.reader.readline(64)
            if response != b'OK\n':
                raise OSError('Controller rejected command or disconnected')
        except BaseException:
            # A broken stream cannot be reused: a late OK could match the next command.
            self._disconnect()
            raise

    def execute(self, action: Action):
        if action.move not in DIRECTIONS or action.fire not in DIRECTIONS:
            raise ValueError('Unsupported PPAL direction')
        self.command('LS_' + DIRECTIONS[action.move])
        self.command('RS_' + DIRECTIONS[action.fire])

    def _disconnect(self):
        if self.socket is not None:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if self.reader is not None:
            self.reader.close()
            self.reader = None
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def close(self):
        try:
            if self.socket is not None:
                self.command('NEUTRAL')
        finally:
            self._disconnect()


class RobotronSession:
    """PPAL actions in, physical-camera frames out. No invented game metrics."""
    def __init__(self, controller, camera):
        self.controller, self.camera = controller, camera

    def __enter__(self):
        try:
            self.camera.open()
            self.camera.read(timeout=2, require_new=True)
            self.controller.open()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def step(self, action: Action, duration=0.1):
        if not math.isfinite(duration) or not 0 < duration <= 2:
            raise ValueError('Action duration must be within (0, 2] seconds')
        try:
            self.controller.execute(action)
            time.sleep(duration)
            self.controller.command('NEUTRAL')
            # Discard previously buffered frames, then request a new observation.
            frame = self.camera.discard_until_new(frame_count=2, timeout=2)
            return {'received_at': time.monotonic(), 'frame': frame,
                    'action': action, 'duration': duration}
        except BaseException:
            self.controller.close()
            raise

    def reset(self, seed):
        raise NotImplementedError('Paired experiments require a verified reset adapter; camera similarity cannot certify identical game state')

    def __exit__(self, *args):
        try:
            self.controller.close()
        finally:
            self.camera.close()
