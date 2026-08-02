from hardware.rp2040_controller import RP2040Controller


class Deck:

    def __init__(self):

        self.body = RP2040Controller()


    def look_at(self, pan, tilt):

        self.body.look(
            pan,
            tilt
        )


    def track(self, pan, tilt):

        self.body.track(
            pan,
            tilt
        )


    def scan(self):

        self.body.scan()


    def home(self):

        self.body.home()


    def stop(self):

        self.body.stop()


    def display(self, state):

        self.body.display(state)
