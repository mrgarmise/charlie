from hardware.rp2040_controller import RP2040Controller
import time


body = RP2040Controller()


body.home()

time.sleep(2)


body.scan()

time.sleep(10)


body.look(90,45)

time.sleep(3)


body.display("THINK")
