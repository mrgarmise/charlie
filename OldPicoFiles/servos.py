from machine import Pin, PWM
import time

servo = PWM(Pin(2))
servo.freq(1000)

def set_angle(a):
    duty = int(2000 + (a/180)*6000)
    servo.duty_u16(duty)

set_angle(90)
time.sleep(2)
set_angle(150)
time.sleep(2)