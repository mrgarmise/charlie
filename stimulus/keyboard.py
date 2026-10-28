import threading
import sys

class KeyboardStimulus:

    def __init__(self, bus, *, object_mode=False, emergency_only=False, on_emergency=None):
        self.object_mode = object_mode
        self.emergency_only = emergency_only
        self.on_emergency = on_emergency
        self.bus = bus
        self.running = True

        t = threading.Thread(target=self.loop, daemon=True)
        t.start()

    def loop(self):

        if self.emergency_only:
            print('Keyboard: x = emergency STOP')
        elif self.object_mode:
            print('Object Recognition: 1 = Pi camera, 2 = ELEGOO camera, x = emergency STOP, q = quit')
        else:
            self.tracking_help()
        while self.running:
            key = sys.stdin.read(1)
            if not key:
                return
            if self.emergency_only:
                if key == 'x':self.emergency_stop()
                continue
            if self.object_mode:
                event = {'1': ('camera_source', 'pi'), '2': ('camera_source', 'elegoo'),
                         'x': ('emergency_stop', None), 'q': ('object_recognition_stop', None)}.get(key)
                if event:
                    if event[0] == 'emergency_stop':self.emergency_stop()
                    else:self.bus.emit(*event)
                continue
            self.tracking_key(key)

    def close(self):
        self.running = False

    def emergency_stop(self):
        # Physical STOP is attempted from the input thread, even if the
        # attention loop is waiting on a bounded movement request.
        try:
            if self.on_emergency is not None:self.on_emergency()
        except Exception as exc:
            print(f'Emergency STOP delivery uncertain: {type(exc).__name__}',flush=True)
        finally:
            self.bus.emit('emergency_stop')

    def tracking_help(self):
        print("Keyboard controls:")
        print("  s = scan")
        print("  i = idle")
        print("  t = track")
        print("  c = request supervised neck calibration")
        print("  v = confirm the displayed reviewed starting pose")
        print("  x = emergency STOP")

    def tracking_key(self, key):
        if key == 'x':
            self.emergency_stop()
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

