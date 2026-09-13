"""
display.py

Charlie pico:ed attitude / status display.

Persistent state:
    IDLE
    SCAN
    TRACK
    HOME
    SLEEP
    ERROR

Transient feedback:
    THINK
    HAPPY
    ERROR

The Pi sends semantic intent.
The RP2040 decides how it appears.

Hardware:
    pico:ed 17x7 matrix
    I2C1
    SDA GP18
    SCL GP19
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
    NO_BRAIN = "NO_BRAIN"

    FRAME_MS = 100

    def __init__(self):

        self.state = self.IDLE

        self.feedback_state = None
        self.feedback_until = 0

        self.frame = 0
        self.last_frame = time.ticks_ms()

        self.message = None
        self.message_until = 0
        self.message_page = 0
        self.last_message_page = 0

        self.progress = None

        if DISPLAY_AVAILABLE:
            self.clear()

    def clear(self):

        if DISPLAY_AVAILABLE:
            matrix.fill(0)

    def _pixel(self, x, y, brightness=80):

        if not DISPLAY_AVAILABLE:
            return

        if not 0 <= x < self.WIDTH:
            return

        if not 0 <= y < self.HEIGHT:
            return

        # Charlie's matrix is extremely bright.
        # All requested values are reduced by half and
        # capped at half hardware brightness.
        brightness = max(
            0,
            min(127, int(brightness // 2))
        )

        matrix.pixel(
            x,
            y,
            brightness
        )

    # --------------------------------------------------
    # PERSISTENT STATE
    # --------------------------------------------------

    def status(self, state):

        self.state = str(state).upper()
        self.frame = 0

    # --------------------------------------------------
    # TRANSIENT FEEDBACK
    # --------------------------------------------------

    def feedback(self, state, duration_ms=1500):

        self.feedback_state = str(state).upper()

        self.feedback_until = time.ticks_add(
            time.ticks_ms(),
            int(duration_ms)
        )

        self.frame = 0

    def clear_feedback(self):

        self.feedback_state = None
        self.feedback_until = 0

    # --------------------------------------------------
    # TEXT
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

    def queue_text(self, text):
        self.show_text(text)

    def rx_activity(self):
        self.show_text("RX", 600)

    def tx_activity(self):
        self.show_text("TX", 600)

    def error(self, message):
        self.feedback(
            self.ERROR,
            2500
        )
        self.show_text(
            "ERR " + str(message),
            2500
        )

    # --------------------------------------------------
    # PROGRESS
    # --------------------------------------------------

    def set_progress(self, value):

        self.progress = max(
            0,
            min(100, int(value))
        )

    def clear_progress(self):
        self.progress = None

    # --------------------------------------------------
    # MESSAGE RENDERING
    # --------------------------------------------------

    def _draw_message(self):

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
            self.clear()

    # --------------------------------------------------
    # ANIMATIONS
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

    def _draw_scan(self):

        # Sweep back and forth across the 17 columns:
        #
        # 0 1 2 ... 15 16 15 ... 2 1 0 ...

        span = self.WIDTH - 1
        cycle = span * 2

        position = self.frame % cycle

        if position <= span:
            x = position
            previous = max(0, x - 1)
        else:
            x = cycle - position
            previous = min(
                self.WIDTH - 1,
                x + 1
            )

        for y in range(self.HEIGHT):

            # Dim trail behind the scanner.
            self._pixel(
                previous,
                y,
                25
            )

            # Main scanning line.
            self._pixel(
                x,
                y,
                110
            )
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

    def _draw_sleep(self):

        if self.frame % 16 == 0:
            self._pixel(
                8,
                3,
                15
            )

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

    def _draw_no_brain(self):

        """
        Brain-shaped warning with a diagonal slash.

        This is intentionally slow/static so the display
        never interferes with serial handling or recovery.
        """

        # Slow pulse so it is obviously alive,
        # but not visually frantic.
        pulse = (
            self.frame // 5
        ) % 2

        brain = 100 if pulse else 55
        slash = 140 if pulse else 90

        # Brain outline / lobes.

        brain_pixels = (
            (6, 1),
            (7, 1),
            (9, 1),
            (10, 1),

            (5, 2),
            (8, 2),
            (11, 2),

            (5, 3),
            (8, 3),
            (11, 3),

            (5, 4),
            (8, 4),
            (11, 4),

            (6, 5),
            (7, 5),
            (9, 5),
            (10, 5),
        )

        for x, y in brain_pixels:
            self._pixel(
                x,
                y,
                brain
            )

        # Slash through the brain.

        slash_pixels = (
            (4, 6),
            (5, 5),
            (6, 5),
            (7, 4),
            (8, 3),
            (9, 3),
            (10, 2),
            (11, 1),
            (12, 0),
        )

        for x, y in slash_pixels:
            self._pixel(
                x,
                y,
                slash
            )


    def _draw_named_state(self, state):

        if state == self.SCAN:
            self._draw_scan()

        elif state == self.TRACK:
            self._draw_track()

        elif state == self.HOME:
            self._draw_home()

        elif state == self.SLEEP:
            self._draw_sleep()

        elif state == self.ERROR:
            self._draw_error()

        elif state == self.THINK:
            self._draw_think()

        elif state == self.HAPPY:
            self._draw_happy()
        elif state == self.NO_BRAIN:
            self._draw_no_brain()

        else:
            self._draw_idle()

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
    # MAIN UPDATE
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

        # Temporary text has highest priority.

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

        # Temporary animated feedback comes next.

        if self.feedback_state:

            if time.ticks_diff(
                self.feedback_until,
                now
            ) > 0:

                self._draw_named_state(
                    self.feedback_state
                )

                self._draw_progress()
                return

            self.clear_feedback()

        # Persistent attitude.

        self._draw_named_state(
            self.state
        )

        # Optional process overlay.

        self._draw_progress()