from Pico_ed import *
import math
import random
import time
from servo import Servo

bank=0



while True:
    try:
        a=random.randint(0,9)
        b=random.randint(0,9)
        c=random.randint(0,9)
        d=a*100+b*10+c        
        display.show(d)
        if ButtonA.is_pressed():
            display.show(d)
            break
        if ButtonB.is_pressed():
            display.fill(0)
            break        

    except KeyboardInterrupt:
        display.fill(0)
        break
    

