from hardware.elegoo_mobile import ElegooMobileBase


class LegacyMotionUnavailable(RuntimeError):
    """A legacy motion path has no independently qualified executor yet."""


def _deny_legacy_motion():
    raise LegacyMotionUnavailable(
        'Legacy ELEGOO pan/chassis motion is unavailable: a qualified actuator '
        'executor and independent device-specific authorization are required.'
    )


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
        return _deny_legacy_motion()

    def yaw(self):
        return self.car.yaw()

    def pivot(self, direction, speed=None):
        return _deny_legacy_motion()

    def begin_attention_align(self, current_pan, max_rotation=None):
        return _deny_legacy_motion()

    def update_attention_align(self, face_visible=True):
        return _deny_legacy_motion()

    def cancel_attention_align(
        self,
        reason="cancelled"
    ):
        return self.car.cancel_attention_align(
            reason
        )

    def pulse(self, direction, **kwargs):
        from motion.elegoo_executor import _application_executor
        authority = kwargs.pop('_executor', None)
        if _application_executor is not None and authority is not _application_executor:
            raise PermissionError('motion requests require the application executor')
        if authority is not None:
            kwargs['_executor'] = authority
        return self.car.pulse(direction, **kwargs)

    def stop_verified(self):
        return self.car.stop_verified()

    def read_ultrasonic(self, **kwargs):
        return self.car.read_ultrasonic(**kwargs)
