from Pico_ed import *
import math
import time
from servo import Servo


while True:
    try:
        my_servo = Servo(pin_id=0)
        my_servo.write(30)

    except KeyboardInterrupt:
        display.fill(10)
        time.sleep(2.0)
        display.fill(0)
        break
