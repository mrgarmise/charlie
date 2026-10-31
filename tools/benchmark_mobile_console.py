#!/usr/bin/env python3
"""Measure lossless console encoding of SYNTHETIC shared frames; no devices.

This is a CPU/transport-preparation baseline, never live camera FPS or latency.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import platform
import statistics
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from stimulus.bus import StimulusBus
from vision.camera_source import CameraFrame
from ui.mobile import MobileConsole


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frames',type=int,default=20)
    p.add_argument('--width',type=int,default=640);p.add_argument('--height',type=int,default=480)
    args=p.parse_args(argv)
    if not 1<=args.frames<=100 or not 1<=args.width<=1920 or not 1<=args.height<=1080:
        raise ValueError('bounded synthetic workload required')
    bus=StimulusBus();owner=object();bus.claim_frames('elegoo-v4',owner)
    console=MobileConsole(bus);rng=np.random.default_rng(31)
    times=[];sizes=[];started=time.perf_counter()
    try:
        for seq in range(args.frames):
            pixels=rng.integers(0,256,(args.height,args.width,3),dtype=np.uint8);pixels.flags.writeable=False
            frame=CameraFrame('synthetic:'+str(seq),pixels,time.monotonic(),source='elegoo-v4',sequence=seq,stream_generation='synthetic')
            bus.publish_frame('elegoo-v4',owner,frame)
            begin=time.perf_counter();raw,metadata=console.image();times.append(time.perf_counter()-begin);sizes.append(len(raw))
        elapsed=time.perf_counter()-started
        print(json.dumps(dict(kind='SYNTHETIC encoding only; no live camera or HTTP transport',
            machine=platform.machine(),python=platform.python_version(),frames=args.frames,geometry=[args.width,args.height],
            format='lossless PNG baseline; random incompressible BGR fixture',
            encoding_seconds=dict(p50=float(np.percentile(times,50)),p95=float(np.percentile(times,95)),max=max(times)),
            mean_encoded_bytes=statistics.mean(sizes),elapsed_seconds=elapsed,
            synthetic_encode_throughput_fps=args.frames/sum(times),live_camera_fps=None,
            exposure_latency_seconds=None,transport_latency_seconds=None),indent=2))
    finally:console.close()


if __name__=='__main__':main()
