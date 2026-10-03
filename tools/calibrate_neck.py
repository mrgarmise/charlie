"""Supervised CAL-1 console. No hardware opens without the explicit flag.

JSON operations are prepared/verified by the operator; GP10 is not an E-stop.
No firmware upload, profile activation, autofocus or gameplay is performed.
"""
import argparse
import json
import threading
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorize-supervised-calibration',action='store_true')
    parser.add_argument('--port',default='/dev/ttyACM0')
    parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args()
    if not args.authorize_supervised_calibration:
        parser.error('separate explicit physical authorization required; no hardware opened')
    from hardware.rp2040_controller import RP2040Controller
    from hardware.neck_calibration import CalibrationJournal,SupervisedCalibration
    # Reserve durable evidence BEFORE opening UART (opening can reboot Pico).
    evidence=CalibrationJournal(args.evidence,simulated=False)
    controller=None;session=None;done=threading.Event();poller=None
    try:
        controller=RP2040Controller(args.port)
        session=SupervisedCalibration(controller,evidence)
        status=controller.motion_status()
        if not status or status.get('armed') or status.get('pwm_active'):
            raise RuntimeError('disarmed startup required')
        def poll():
            while not done.wait(.1):
                try:
                    state=session.poll()
                    if state['state'] in ('ABORTED','CLOSED'):
                        print(json.dumps(state))
                        done.set()
                except Exception as exc:
                    done.set();controller.stop()
                    print('CAL STOPPED:',str(exc))
        poller=threading.Thread(target=poll,daemon=True);poller.start()
        print('Enter one CAL JSON operation per line. Ctrl-D/C stops. Separate servo-power cutoff required.')
        while not done.is_set():
            try: line=input('CAL> ')
            except EOFError: break
            if done.is_set():break
            try: print(json.dumps(session.request(json.loads(line))))
            except (ValueError,PermissionError) as exc: print('REJECTED:',str(exc))
    finally:
        done.set()
        if poller is not None:poller.join(timeout=2)
        try:
            if session is not None:session.close()
        finally:
            try:
                if controller is not None:controller.close()
            finally:evidence.close()


if __name__=='__main__':main()
