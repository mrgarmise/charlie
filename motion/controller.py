import serial
import time
import threading

class Deck:

    def __init__(self, port="/dev/ttyACM0"):
        self.ser = serial.Serial(port, 115200, timeout=1)
        time.sleep(2)

        # current state
        self.state = {
            "pan_l": 90,
            "tilt_l": 90,
            "pan_r": 90,
            "tilt_r": 90
        }

        # target state
        self.target = self.state.copy()

        self.speed = 90  # degrees per second

        self.running = True
        self.thread = threading.Thread(target=self._loop)
        self.thread.start()

    def center(self):
        self.move_to(90, 90, 90, 90, speed=60)

    def set_all(self, pl, tl, pr, tr):
        self.move_to(pl, tl, pr, tr, speed=60)

    def move_to(self, pl, tl, pr, tr, speed=60):

        # detect large jumps (quick glance behavior)
        big_move = (
            abs(pl - self.target["pan_l"]) > 25 or
            abs(tl - self.target["tilt_l"]) > 25
        )

        self.target["pan_l"] = pl
        self.target["tilt_l"] = tl
        self.target["pan_r"] = pr
        self.target["tilt_r"] = tr

        # fast or slow personality switch
        if big_move:
            self.speed = speed * 1.8   # fast saccade
        else:
            self.speed = speed


    def _send(self):
        cmd = f"SET {int(self.state['pan_l'])} {int(self.state['tilt_l'])} {int(self.state['pan_r'])} {int(self.state['tilt_r'])}\n"
        self.ser.write(cmd.encode())

    def _step(self, current, target, step):
        if abs(target - current) <= step:
            return target
        return current + step if target > current else current - step

    def _loop(self):
        while self.running:
            step = self.speed * 0.02  # loop runs ~50Hz

            for k in self.state:
                self.state[k] = self._step(self.state[k], self.target[k], step)

            self._send()
            time.sleep(0.02)
