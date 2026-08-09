from machine import Pin, PWM
import time

servo = PWM(Pin(15))
servo.freq(50)

def set_angle(angle):
    min_duty = 2000
    max_duty = 8000
    duty = int(min_duty + (angle / 180) * (max_duty - min_duty))
    servo.duty_u16(duty)

while True:
    set_angle(30)
    time.sleep(1)

    set_angle(90)
    time.sleep(1)

    set_angle(150)
    time.sleep(1)