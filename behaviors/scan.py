from behaviors.base import Behavior


class ScanBehavior(Behavior):

    def enter(self, deck):
        self.deck = deck
        self.done = False

        print("ScanBehavior engaged")

        self.deck.scan()


    def update(self, deck):
        # RP2040 owns scanning now
        pass


    def is_finished(self):
        return self.done


    def exit(self, deck):
        self.deck.stop()
