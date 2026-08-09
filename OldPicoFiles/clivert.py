from Pico_ed import *
import time
import random

z = 5
delay = .01
display.fill(0)

while True:
    for c in range (0, 5, 1):
        for z in range (0, 50, 5):
            for x in range (1,17):
                for y in range (1,7):
#               	 if y == 4:
                    p = 2 * x
#               	else:
#               	     p=z
                    display.pixel(x,y,p)
                    print(x)
#                	display.fill(1)

    for z in range (50, 0. -10):
        for x in range (17,1):
            for y in range (7,1):
                p = 2 * x
                display.pixel(x,y,p)

#                display.pixel(x,y,z)
#                display.fill(0)
#   display.image('NO')
#   sleep(.05)
