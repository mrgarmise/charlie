from hardware.elegoo_mobile import ElegooMobileBase


class MobileBase:
    """
    Charlie's independent ELEGOO-car interface.

    This is a separate subsystem from the RP2040-controlled head/body.

    RP2040 / Deck owns:
      - existing pan/tilt servos
      - pico display
      - scan / track behavior

    MobileBase owns:
      - ELEGOO camera pan servo
      - chassis motors
      - MPU6050 yaw
      - mobile attention alignment
      - later navigation sensors / mapping
    """

    def __init__(self):
        self.car = ElegooMobileBase()

    # --------------------------------------------------
    # CONNECTION / SAFETY
    # --------------------------------------------------

    def connect(self):
        return self.car.connect()

    def close(self):
        return self.car.close()

    def stop(self):
        return self.car.stop()

    # --------------------------------------------------
    # MOBILE HEAD
    # --------------------------------------------------

    def pan(self, degrees):
        return self.car.pan(degrees)

    # --------------------------------------------------
    # MOBILE BODY / SENSORS
    # --------------------------------------------------

    def yaw(self):
        return self.car.yaw()

    def pivot(self, direction, speed=None):
        return self.car.start_pivot(
            direction,
            speed=speed
        )

    # --------------------------------------------------
    # COORDINATED MOBILE ATTENTION
    # --------------------------------------------------

    def begin_attention_align(self, current_pan):
        return self.car.begin_attention_align(
            current_pan
        )

    def update_attention_align(
        self,
        face_visible=True
    ):
        return self.car.update_attention_align(
            face_visible=face_visible
        )

    def cancel_attention_align(
        self,
        reason="cancelled"
    ):
        return self.car.cancel_attention_align(
            reason
        )
