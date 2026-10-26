import threading
import sys

class KeyboardStimulus:

    def __init__(self, bus, *, object_mode=False):
        self.object_mode = object_mode
        self.bus = bus
        self.running = True

        t = threading.Thread(target=self.loop, daemon=True)
        t.start()

    def loop(self):

        if self.object_mode:
            print('Object Recognition: 1 = Pi camera, 2 = ELEGOO camera, q = quit (stationary)')
        else:
            self.tracking_help()
        while self.running:
            key = sys.stdin.read(1)
            if not key:
                return
            if self.object_mode:
                event = {'1': ('camera_source', 'pi'), '2': ('camera_source', 'elegoo'),
                         'q': ('object_recognition_stop', None)}.get(key)
                if event:
                    self.bus.emit(*event)
                continue
            self.tracking_key(key)

    def close(self):
        self.running = False

    def tracking_help(self):
        print("Keyboard controls:")
        print("  s = scan")
        print("  i = idle")
        print("  t = track")
        print("  c = request supervised neck calibration")
        print("  v = confirm the displayed reviewed starting pose")

    def tracking_key(self, key):
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

