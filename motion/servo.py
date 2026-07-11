import serial
import time

PORT = "/dev/ttyACM0"  # may change
BAUD = 115200

class ServoController:
    def __init__(self):
        self.ser = serial.Serial(PORT, BAUD, timeout=1)
        time.sleep(2)  # let RP2040 reset

    def send(self, msg):
        line = msg + "\n"
        self.ser.write(line.encode())

    def pan(self, angle):
        self.send(f"PAN {angle}")

    def tilt(self, angle):
        self.send(f"TILT {angle}")
