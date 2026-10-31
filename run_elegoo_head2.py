#!/usr/bin/env python3
"""Compatibility entry point for the original ELEGOO head face tracker.

Uses the normal application's feeder, AttentionManager and actuator executor.
Hardware startup is explicit; registration by itself never grants motion.
"""
import time
from contextlib import ExitStack


def main(argv=None):
    from main import parser, application_camera_feeders, application_mobile_actuators
    from stimulus.bus import StimulusBus
    from stimulus.keyboard import KeyboardStimulus
    from attention.manager import AttentionManager
    from behaviors.mobile_face_runtime import MobileFaceRuntime
    from memory.gateway import MemoryGateway

    args=parser().parse_args(argv)
    if args.offline:
        raise ValueError('ELEGOO head entry point requires explicit --hardware')
    events=StimulusBus()
    with ExitStack() as lifecycle:
        frame_bus=lifecycle.enter_context(application_camera_feeders(args,selected=('elegoo',)))
        executor,telemetry=lifecycle.enter_context(application_mobile_actuators(frame_bus,
            state=args.learning_state,hardware_id=args.mobile_hardware_id,zone=args.mobile_zone,
            feed=args.actuator_safety_feed))
        attention=AttentionManager(events,mobile_enabled=False,emergency_stop=executor.emergency_stop)
        lifecycle.callback(attention.close)
        face=MobileFaceRuntime(frame_bus,events,executor,memory_gateway=MemoryGateway())
        lifecycle.callback(face.close)
        keyboard=KeyboardStimulus(events,emergency_only=True,on_emergency=executor.emergency_stop)
        lifecycle.callback(keyboard.close)
        print('Charlie ELEGOO Head 2: shared face tracking; motion requires independent qualification',flush=True)
        previous=None;last_telemetry=0.
        try:
            while True:
                if time.monotonic()-last_telemetry>=.1:
                    telemetry.poll();last_telemetry=time.monotonic()
                face.observe()
                attention.update(None)
                if face.last_status != previous:
                    print(face.last_status,flush=True)
                    previous=face.last_status
                time.sleep(.02)
        except KeyboardInterrupt:
            pass


if __name__=='__main__':
    main()
