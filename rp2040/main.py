from machine import Pin, PWM
import sys

pan = PWM(Pin(0))
tilt = PWM(Pin(1))

pan.freq(50)
tilt.freq(50)

def angle_to_duty(angle):
    return int(1000 + (angle / 180) * 8000)

while True:
    line = sys.stdin.readline().strip()

    if line.startswith("PAN"):
        angle = int(line.split()[1])
        pan.duty_u16(angle_to_duty(angle))

    if line.startswith("TILT"):
        angle = int(line.split()[1])
        tilt.duty_u16(angle_to_duty(angle))
