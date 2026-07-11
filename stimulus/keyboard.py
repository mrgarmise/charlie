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

        while self.running:
            key = sys.stdin.read(1)

            if key == "s":
                self.bus.emit("scan")

            if key == "i":
                self.bus.emit("idle")
                
            if key == "t":
                self.bus.emit("track", (110,90))
                