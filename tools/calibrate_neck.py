"""Supervised CAL-1 console. No hardware opens without the explicit flag.

JSON operations are prepared/verified by the operator; GP10 is not an E-stop.
No firmware upload, profile activation, autofocus or gameplay is performed.
"""
import argparse
import json
import os
import select
import sys
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorize-supervised-calibration',action='store_true')
    parser.add_argument('--port',default='/dev/ttyACM0')
    parser.add_argument('--evidence',type=Path)
    parser.add_argument('--state-directory',type=Path,default=Path(os.environ.get(
        'CHARLIE_NECK_STATE',str(Path.home()/'.local/share/charlie/neck'))))
    parser.add_argument('--request-id')
    parser.add_argument('--list-requests',action='store_true',help='offline; never opens UART/camera')
    args=parser.parse_args()
    from hardware.calibration_service import CalibrationService
    if args.list_requests:
        from memory.evidence import EvidenceJournal
        from hardware.neck_calibration import ProfileRepository
        path=args.state_directory/'requests.sqlite3'
        if not path.exists():
            print('{}');return
        journal=EvidenceJournal(path,read_only=True)
        try:
            service=CalibrationService(None,ProfileRepository(args.state_directory/'profiles'),journal)
            print(json.dumps(service.requests(),indent=2))
        finally:journal.close()
        return
    if not args.authorize_supervised_calibration:
        parser.error('separate explicit physical authorization required; no hardware opened')
    if args.evidence is None:
        parser.error('new --evidence file required')
    from hardware.rp2040_controller import RP2040Controller
    from hardware.neck_calibration import CalibrationJournal
    service=CalibrationService.open(None,args.state_directory)
    service.refresh()
    request_id=args.request_id or service.request('uncertain',dict(reason='explicit supervisor request'))
    if request_id not in service.requests():
        service.close();parser.error('pending request ID required')
    # Reserve durable evidence BEFORE opening UART (opening can reboot Pico).
    evidence=None;controller=None
    try:
        evidence=CalibrationJournal(args.evidence,simulated=False,journal=service.journal)
        controller=RP2040Controller(args.port)
        service.controller=controller
        session=service.supervised_session(request_id,args.evidence,prepared_evidence=evidence)
        status=controller.motion_status()
        if not status or status.get('armed') or status.get('pwm_active'):
            raise RuntimeError('disarmed startup required')
        print('Enter one CAL JSON operation per line. Ctrl-D/C stops. Separate servo-power cutoff required.',flush=True)
        started=False
        # UART polling and SQLite evidence stay on one thread. The existing
        # controller heartbeat remains the sole communications worker.
        while True:
            state=session.poll()
            if started and state['state'] in ('ABORTED','CLOSED'):
                print(json.dumps(state));break
            if not select.select([sys.stdin],[],[],.1)[0]:continue
            line=sys.stdin.readline()
            if not line:break
            try: print(json.dumps(session.request(json.loads(line))))
            except (ValueError,PermissionError) as exc: print('REJECTED:',str(exc))
            else:started=True
    finally:
        try:
            service.close()
        finally:
            try:
                if controller is not None:
                    try:controller.stop()
                    finally:controller.close()
            finally:
                if evidence is not None:evidence.close()


if __name__=='__main__':main()
