from hardware.elegoo_mobile import ElegooMobileBase


class MobileBase:
    """
    Charlie's independent ELEGOO-car interface.
    """

    def __init__(self):
        self.car = ElegooMobileBase()

    def connect(self):
        return self.car.connect()

    def close(self):
        return self.car.close()

    def stop(self):
        return self.car.stop()

    def pan(self, degrees):
        return self.car.pan(degrees)

    def yaw(self):
        return self.car.yaw()

    def pivot(self, direction, speed=None):
        return self.car.start_pivot(
            direction,
            speed=speed
        )

    def begin_attention_align(
        self,
        current_pan,
        max_rotation=None,
    ):
        return self.car.begin_attention_align(
            current_pan,
            max_rotation=max_rotation,
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
