import threading
import sys

class KeyboardStimulus:

    def __init__(self, bus):
        self.bus = bus
        self.running = True

        t = threading.Thread(target=self.loop, daemon=True)
        t.start()

    def loop(self):

        print("Keyboard controls:")
        print("  s = scan")
        print("  i = idle")
        print("  t = track")
        print("  c = request supervised neck calibration")
        print("  v = confirm the displayed reviewed starting pose")

        while self.running:
            key = sys.stdin.read(1)
            if not key:
                return
            if key == 'c':
                self.bus.emit('calibrate_neck')
            if key == 'v':
                self.bus.emit('confirm_neck_start')

            if key == "s":
                self.bus.emit("scan")

            if key == "i":
                self.bus.emit("idle")

            if key == "t":
                self.bus.emit("track", (110,90))

