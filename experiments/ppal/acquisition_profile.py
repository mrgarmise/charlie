"""Camera-only native timing profile. Never imports or opens a controller."""
import argparse
import json
from pathlib import Path
import time
from .projectile_agency import candidates, timing_summary


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native-camera',action='store_true',required=True)
    ap.add_argument('--seconds',type=float,default=5.)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(argv)
    if not 1<=args.seconds<=60:ap.error('seconds must be 1..60')
    from .eyes.sources import PiCameraSource
    source=PiCameraSource()
    rows=[]
    try:
        source.manual_focus(2.0)
        deadline=time.monotonic()+args.seconds
        while time.monotonic()<deadline:
            frame=source.read_fresh()
            capture=dict(source.last_capture)
            if (capture.get('lens_position') is None or abs(capture['lens_position']-2.)>.05
                    or capture.get('af_state')!=0):
                raise ValueError('manual focus 2.0 not verified; profile aborted')
            started=time.perf_counter()
            bodies,points=candidates(frame)
            rows.append(dict(capture=capture,capture_timestamp=capture['first_pixel_exposure_at'],
                acquisition_processing_seconds=time.perf_counter()-started,
                frame_size=frame.size,body_candidates=len(bodies),projectile_candidates=len(points)))
    finally:
        source.close()
    # No image encoding, journal writes or recognition in the capture loop.
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dict(schema='acquisition-camera-profile-v1',
        native=True,controller_opened=False,gameplay_evidence=False,focus=2.0,
        qualification='timing only; no SELF or policy qualification',
        summary=timing_summary(rows),observations=rows),indent=2)+'\n')


if __name__=='__main__':main()
