"""Shared read-only ELEGOO acquisition, using the application's motor transport.

No caller can supply a guessed protocol. Independent installed-source verification
must enable each read; unknown physical properties stay unknown in publication.
"""
import math
import time
from uuid import uuid4
from stimulus.bus import Observation


class ElegooTelemetry:
    def __init__(self, executor, *, clock=time.monotonic):
        self.executor, self.bus, self.clock = executor, executor.bus, clock
        self.generation, self.sequence = uuid4().hex, 0
        self.sources = ('elegoo-ultrasonic', 'elegoo-pose')
        for source in self.sources:
            self.bus.claim_observations(source, self, metadata={
                'body': 'ELEGOO', 'modality': 'range' if source.endswith('ultrasonic') else 'pose',
                'clock': 'host-monotonic receipt; device capture unknown',
                'physical_accuracy': 'unknown until native measurement',
                'acquisition': 'installed-source verification required'})

    def poll(self):
        # Share executor scheduling; never queue telemetry ahead of a movement
        # renewal/STOP and never open a second connection for a subscriber.
        if not self.executor._request_lock.acquire(blocking=False):
            return False
        try:
            authority = self.executor.authority
            if authority is None or not hasattr(authority, 'telemetry_protocol'):
                raise PermissionError('installed telemetry protocol unverified')
            protocol = authority.telemetry_protocol(boot_id=self.executor.boot_id)
            if not self.executor._connected:
                # Telemetry activation is separately authorized, no motion grant.
                if protocol.get('read_only_connection_authorized') is not True:
                    raise PermissionError('read-only connection not authorized')
                self.executor.base.connect()
                self.executor._connected = True
            self.sequence += 1
            for source in self.sources:
                try:
                    started = self.clock()
                    if source == 'elegoo-ultrasonic':
                        reading = self.executor.base.read_ultrasonic(protocol=protocol, clock=self.clock)
                        values = dict(reading, clearance=None, target_association=False,
                                      field_of_view_verified=False)
                    else:
                        if protocol.get('yaw_read_only') is not True or protocol.get('yaw') != {'N': 24}:
                            raise PermissionError('installed yaw read unverified')
                        yaw = self.executor.base.yaw()
                        if not math.isfinite(yaw):
                            raise ValueError('nonfinite yaw')
                        values = dict(yaw_degrees=yaw, yaw_valid=True,
                                      pan_degrees=None, chassis_position=None)
                    self.bus.publish_observation(source, self, Observation(source,
                        self.sequence, self.clock(), values,
                        dict(query_started_at=started, firmware_identity=protocol.get('firmware_identity'),
                             exposure_time=None, accuracy=None, qualification=protocol.get('evidence_id')),
                        self.generation))
                except Exception as exc:
                    self.bus.observation_fault(source, self, str(exc))
            return True
        except Exception as exc:
            for source in self.sources:
                self.bus.observation_fault(source, self, str(exc))
            return False
        finally:
            self.executor._request_lock.release()

    def close(self):
        for source in self.sources:
            self.bus.release_observations(source, self)
