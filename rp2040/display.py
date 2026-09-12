"""
display.py

Charlie pico:ed attitude / status display.

The Raspberry Pi communicates intent.
The RP2040 decides how that intent appears on the
pico:ed 17x7 LED matrix.

Hardware driver:
    /lib/Pico_ed.py

Pico:ed matrix:
    17 x 7 LEDs
    I2C1
    SDA = GP18
    SCL = GP19

Regular rendering is non-blocking. update() draws
one frame when needed and returns immediately.
"""

import time

try:
    from Pico_ed import display as matrix
    DISPLAY_AVAILABLE = True
except ImportError:
    matrix = None
    DISPLAY_AVAILABLE = False


class Display:

    WIDTH = 17
    HEIGHT = 7

    IDLE = "IDLE"
    SCAN = "SCAN"
    TRACK = "TRACK"
    HOME = "HOME"
    SLEEP = "SLEEP"
    ERROR = "ERROR"
    THINK = "THINK"
    HAPPY = "HAPPY"

    FRAME_MS = 100

    def __init__(self):

        self.state = self.IDLE
        self.frame = 0
        self.last_frame = time.ticks_ms()

        self.message = None
        self.message_until = 0
        self.message_page = 0
        self.last_message_page = 0

        self.progress = None

        if DISPLAY_AVAILABLE:
            self.clear()

    # --------------------------------------------------

    def clear(self):

        if not DISPLAY_AVAILABLE:
            return

        matrix.fill(0)

    # --------------------------------------------------

    def _pixel(self, x, y, brightness=80):

        if not DISPLAY_AVAILABLE:
            return

        if not 0 <= x < self.WIDTH:
            return

        if not 0 <= y < self.HEIGHT:
            return

        brightness = max(
            0,
            min(128, int(brightness // 2))
        )

        matrix.pixel(
            x,
            y,
            brightness
        )

    # --------------------------------------------------

    def status(self, state):

        self.state = str(state).upper()
        self.frame = 0

    # --------------------------------------------------

    def show_text(self, text, duration_ms=1800):

        self.message = str(text).upper()

        now = time.ticks_ms()

        self.message_until = time.ticks_add(
            now,
            duration_ms
        )

        self.message_page = 0
        self.last_message_page = now

    # --------------------------------------------------

    def queue_text(self, text):

        # Compatibility with the original interface.
        self.show_text(text)

    # --------------------------------------------------

    def rx_activity(self):

        self.show_text("RX", 600)

    # --------------------------------------------------

    def tx_activity(self):

        self.show_text("TX", 600)

    # --------------------------------------------------

    def error(self, message):

        self.state = self.ERROR

        self.show_text(
            "ERR " + str(message),
            2500
        )

    # --------------------------------------------------

    def set_progress(self, value):

        self.progress = max(
            0,
            min(100, int(value))
        )

    # --------------------------------------------------

    def clear_progress(self):

        self.progress = None

    # --------------------------------------------------
    # TEXT
    # --------------------------------------------------

    def _draw_message(self):

        """
        Pico_ed.Display.show() is safe for strings under
        four characters. Longer strings scroll internally
        and block, so Charlie pages messages three
        characters at a time instead.
        """

        if not self.message:
            return

        pages = []

        for start in range(
            0,
            len(self.message),
            3
        ):
            pages.append(
                self.message[start:start + 3]
            )

        if not pages:
            return

        page = pages[
            self.message_page % len(pages)
        ]

        try:
            matrix.show(page)
        except (KeyError, ValueError):
            # Unsupported character in the historical
            # font. Don't let display content crash Charlie.
            self.clear()

    # --------------------------------------------------
    # ATTITUDE ANIMATIONS
    # --------------------------------------------------

    def _draw_idle(self):

        levels = (
            12,
            20,
            35,
            55,
            90,
            55,
            35,
            20,
        )

        brightness = levels[
            self.frame % len(levels)
        ]

        cx = 8
        cy = 3

        self._pixel(
            cx,
            cy,
            brightness
        )

        if brightness >= 35:

            side = brightness // 3

            self._pixel(cx - 1, cy, side)
            self._pixel(cx + 1, cy, side)
            self._pixel(cx, cy - 1, side)
            self._pixel(cx, cy + 1, side)

    # --------------------------------------------------

    def _draw_scan(self):

        x = self.frame % self.WIDTH

        previous = (
            x - 1
        ) % self.WIDTH

        for y in range(self.HEIGHT):

            self._pixel(
                previous,
                y,
                25
            )

            self._pixel(
                x,
                y,
                110
            )

    # --------------------------------------------------

    def _draw_track(self):

        cx = 8
        cy = 3

        pulse = (
            self.frame // 3
        ) % 2

        edge = 110 if pulse else 40

        self._pixel(cx, cy, 150)

        self._pixel(cx - 2, cy, edge)
        self._pixel(cx + 2, cy, edge)
        self._pixel(cx, cy - 2, edge)
        self._pixel(cx, cy + 2, edge)

    # --------------------------------------------------

    def _draw_home(self):

        step = self.frame % 8

        left = min(step, 7)
        right = 16 - min(step, 7)

        self._pixel(
            left,
            3,
            100
        )

        self._pixel(
            right,
            3,
            100
        )

        self._pixel(
            8,
            3,
            25
        )

    # --------------------------------------------------

    def _draw_sleep(self):

        if self.frame % 16 == 0:

            self._pixel(
                8,
                3,
                15
            )

    # --------------------------------------------------

    def _draw_error(self):

        if (
            self.frame // 3
        ) % 2:

            return

        for i in range(7):

            x = 5 + i

            self._pixel(
                x,
                i,
                140
            )

            self._pixel(
                x,
                6 - i,
                140
            )

    # --------------------------------------------------

    def _draw_think(self):

        positions = (
            5,
            8,
            11,
        )

        phase = self.frame % 12

        for index, x in enumerate(
            positions
        ):

            distance = (
                phase - index * 3
            ) % 12

            if distance < 3:
                brightness = 130

            elif distance < 6:
                brightness = 50

            else:
                brightness = 15

            self._pixel(
                x,
                3,
                brightness
            )

    # --------------------------------------------------

    def _draw_happy(self):

        # Eyes

        self._pixel(
            6,
            1,
            130
        )

        self._pixel(
            10,
            1,
            130
        )

        # Smile

        self._pixel(
            5,
            4,
            70
        )

        self._pixel(
            6,
            5,
            100
        )

        self._pixel(
            7,
            5,
            120
        )

        self._pixel(
            8,
            5,
            140
        )

        self._pixel(
            9,
            5,
            120
        )

        self._pixel(
            10,
            5,
            100
        )

        self._pixel(
            11,
            4,
            70
        )

    # --------------------------------------------------

    def _draw_state(self):

        if self.state == self.SCAN:
            self._draw_scan()

        elif self.state == self.TRACK:
            self._draw_track()

        elif self.state == self.HOME:
            self._draw_home()

        elif self.state == self.SLEEP:
            self._draw_sleep()

        elif self.state == self.ERROR:
            self._draw_error()

        elif self.state == self.THINK:
            self._draw_think()

        elif self.state == self.HAPPY:
            self._draw_happy()

        else:
            self._draw_idle()

    # --------------------------------------------------

    def _draw_progress(self):

        if self.progress is None:
            return

        pixels = int(
            (
                self.progress
                * self.WIDTH
            )
            / 100
        )

        for x in range(pixels):

            self._pixel(
                x,
                6,
                75
            )

    # --------------------------------------------------

    def update(self):

        now = time.ticks_ms()

        if time.ticks_diff(
            now,
            self.last_frame
        ) < self.FRAME_MS:

            return

        self.last_frame = now
        self.frame += 1

        self.clear()

        # Temporary message overrides attitude.

        if self.message:

            if time.ticks_diff(
                self.message_until,
                now
            ) > 0:

                if time.ticks_diff(
                    now,
                    self.last_message_page
                ) >= 700:

                    self.message_page += 1
                    self.last_message_page = now

                self._draw_message()
                return

            self.message = None
            self.message_page = 0

        # Normal persistent attitude.

        self._draw_state()

        # Progress is an overlay.

        self._draw_progress()