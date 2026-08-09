from Pico_ed import *
import utime
x=0
display.fill(0)


while True:
    i = j = k = 0
    x = utime.localtime()
    print(x[5]) #[5] = sec, [4] = min, [3] = hour
    print(bin(x[5])[2:]) #convert to binary & chop off the "0b" marker
    m = bin(x[5])[2:]
    print (m)
    n = "% 6s" % m #string formatter - makes it 6 spaces wide
    print (n)
    M = bin(x[4])[2:]
    N = "% 6s" % M
    mm = bin(x[3])[2:]
    nn = "% 6s" % mm
    for i, bit in enumerate(n): #for each bit, display if 1, turn off if not 1
        if bit != '1':
            display.pixel(i,5,0)
        else:
            display.pixel(i,5,10)
    for j, bit in enumerate(N):
        if bit != '1':
            display.pixel(j,3,0)
        else:
            display.pixel(j,3,10)
    for k, bit in enumerate(nn):
        if bit != '1':
            display.pixel(k,1,0)
        else:
            display.pixel(k,1,10)


