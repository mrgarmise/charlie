import time

from motion.controller import Deck
from attention.manager import AttentionManager

from stimulus.bus import StimulusBus
from stimulus.keyboard import KeyboardStimulus

from behaviors.idle import IdleBehavior

deck = Deck()

bus = StimulusBus()
attention = AttentionManager(bus)

KeyboardStimulus(bus)

# start idle explicitly
bus.emit("idle")

while True:
    attention.update(deck)
    time.sleep(0.02)