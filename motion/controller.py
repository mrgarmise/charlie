from hardware.rp2040_controller import RP2040Controller


class Deck:

    def __init__(self):

        self.body = RP2040Controller()


    def center(self):

        self.body.home()


    def set_all(self, pl, tl, pr, tr):

        # Temporary compatibility function.
        # Eventually behaviors should use look()/track()
        self.body.look(pl, tl)


    def move_to(self, pl, tl, pr, tr, speed=60):

        self.body.look(pl, tl)


    def look_at(self, pan, tilt):

        self.body.look(pan, tilt)


    def track(self, pan, tilt):

        self.body.track(pan, tilt)


    def scan(self):

        self.body.scan()


    def stop(self):

        self.body.stop()
