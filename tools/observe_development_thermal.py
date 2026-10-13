"""Read-only native telemetry collector. Never runs an Executive or heats a Pi.

Use beside an explicitly approved offline validation on a copied notebook.
Snapshots are operational observations, never new learning evidence.
"""
import argparse
import datetime
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from learning.resources import temperature


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=330.)
    parser.add_argument('--interval',type=float,default=1.)
    args=parser.parse_args()
    if not 0<args.seconds<=86400 or not .1<=args.interval<=10:
        raise ValueError('bounded observation duration/cadence required')
    start=time.monotonic()
    with args.output.open('x') as stream: # Never overwrite previous observations.
        while time.monotonic()-start<args.seconds:
            row=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                elapsed_seconds=time.monotonic()-start,physical_authorization=False)
            try:row['independent_sensor_temperature_c']=temperature()
            except (OSError,ValueError):row['sensor_error']='unavailable or invalid'
            try:row['operational']=json.loads((args.state/'development-operational-status.json').read_text())
            except (OSError,ValueError):row['status_error']='unavailable or incomplete'
            stream.write(json.dumps(row,allow_nan=False)+'\n');stream.flush()
            time.sleep(min(args.interval,max(0,args.seconds-(time.monotonic()-start))))


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:pass
