from Pico_ed import *
import utime
import time
display.fill(0)

for x in range (10,17):
    for y in range (0,7):
        # displays box
#         if x == 10 or x == 16 or y == 0 or y==6: 
#             display.pixel(x,y,10)

# display circle ... ish
        print(x-10,y)
        for r in range (-3,3):
            if x-10 == round((abs(r-y)** .5)) or x-10 == round(abs((r+y))**.5):
                print("*")
                display.pixel(x,y,10)
#                 time.sleep(.01)
#                 display.fill(0)

