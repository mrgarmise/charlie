import serial
import time
import threading


class RP2040Controller:
    """
    Communication layer between Raspberry Pi and RP2040.

    The Pi sends high-level commands.
    The RP2040 handles servo timing and hardware.
    """

    def __init__(self, port="/dev/ttyACM0", baud=115200):

        self.port = port
        self.baud = baud

        self.serial = None
        self.lock = threading.Lock()

        self.connected = False

        self.connect()


    def connect(self):

        try:
            self.serial = serial.Serial(
                self.port,
                self.baud,
                timeout=1
            )

            time.sleep(2)

            self.connected = True
            print("RP2040 connected")

        except Exception as e:
            print(f"RP2040 connection failed: {e}")
            self.connected = False


    def send(self, command):

        if not self.connected:
            return False

        try:
            with self.lock:
                self.serial.write(
                    (command + "\n").encode()
                )

            return True

        except Exception as e:
            print(f"RP2040 send error: {e}")
            return False


    def ping(self):

        return self.send("PING")


    def home(self):

        return self.send("HOME")


    def scan(self):

        return self.send("SCAN")


    def stop(self):

        return self.send("STOP")


    def look(self, pan, tilt):

        return self.send(
            f"LOOK {pan} {tilt}"
        )


    def track(self, pan, tilt):

        return self.send(
            f"TRACK {pan} {tilt}"
        )


    def display(self, state):

        return self.send(state)
