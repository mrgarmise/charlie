"""Reuse existing Hailo NMS backend, with cross-process accelerator exclusion.

Depth contract is explicitly exported HWC relative depth, never metric clearance.
No model artifacts or native qualification are bundled.
"""
from contextlib import contextmanager
from pathlib import Path
import fcntl
import hashlib
import math
import os
import time


@contextmanager
def hailo_lease(path=None):
    path = Path(path or os.environ.get('CHARLIE_HAILO_LOCK', '/tmp/charlie-hailo.lock'))
    with path.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try: yield
        finally: fcntl.flock(handle, fcntl.LOCK_UN)


def runtime_version():
    import importlib.metadata
    try:return importlib.metadata.version('hailort')
    except importlib.metadata.PackageNotFoundError:
        import hailo_platform
        return getattr(hailo_platform,'__version__','unknown')


class HailoObjects:
    def __init__(self, path, *, sha256, classes, size=640, lock=None):
        from experiments.ppal.detector_bridge import HailoBackend
        # Explicit classes from artifact manifest; never silently assume an 80-class order.
        if not {'cat','dog','person'} <= set(classes): raise ValueError('pet/person classes required')
        self.backend = HailoBackend(path, sha256=sha256, classes=classes, size=size)
        self.lock = lock
        self.metadata = dict(backend='hailort-hef', sha256=sha256, path=str(path),
                             architecture='hailo8l', classes=classes, runtime=runtime_version(), qualification='unqualified')

    def infer(self, frame):
        from PIL import Image
        from experiments.ppal.detector_bridge import Frame
        rgb = Image.fromarray(frame.image[:,:,::-1])
        with hailo_lease(self.lock):
            rows = self.backend.infer(Frame(frame.id, rgb, frame.received_at, 'decode receipt', frame.metadata()))
        return [r for r in rows if r['label'] in ('cat','dog','person')]


class HailoRelativeDepth:
    """Lazy HailoRT depth adapter; reject layouts not matching the export manifest.

    Supports single RGB input resized to export size; single HWC/1-channel output.
    FastDepth/SCDepthV3 names alone do not establish that a HEF meets this contract.
    """
    def __init__(self, path, *, sha256, input_shape, output_shape, larger_is_nearer, lock=None):
        import subprocess
        import re
        self.path = str(path)
        if Path(path).suffix != '.hef' or hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha256:
            raise ValueError('HEF integrity mismatch')
        if (len(input_shape)!=3 or input_shape[-1]!=3 or len(output_shape)!=3 or output_shape[-1]!=1
                or any(type(v) is not int or v<=0 for v in (*input_shape,*output_shape))
                or type(larger_is_nearer) is not bool): raise ValueError('explicit HWC depth export required')
        report=subprocess.run(['hailortcli','parse-hef',str(path)],capture_output=True,text=True,timeout=5,check=True).stdout
        if not re.search(r'Architecture[^\n]*\bHAILO[-_ ]?8L\b',report,re.I): raise ValueError('requires hailo8l')
        self.input_shape,self.output_shape = tuple(input_shape),tuple(output_shape)
        self.nearer,self.lock = larger_is_nearer,lock
        self.metadata=dict(backend='hailort-hef', sha256=sha256, architecture='hailo8l',
                           input_shape=input_shape, output_shape=output_shape, kind='relative',
                           larger_is_nearer=larger_is_nearer, runtime=runtime_version(), qualification='unqualified')

    @staticmethod
    def summarize(array, shape, larger_is_nearer):
        import numpy as np
        a=np.asarray(array)
        if a.shape!=(1,*shape) or not np.isfinite(a).all() or a.size<4:
            raise ValueError('invalid depth tensor/layout')
        a=a[0,:,:,0]
        if float(np.ptp(a))<=1e-8: raise ValueError('degenerate relative depth')
        # Only summaries enter journals; relative values cannot certify free floor.
        return dict(kind='relative', median=float(np.median(a)), minimum=float(a.min()),
                    maximum=float(a.max()), larger_is_nearer=larger_is_nearer,
                    clearance_certified=False, qualification='unqualified')

    def infer(self, frame):
        import numpy as np
        from PIL import Image
        from hailo_platform import (HEF,VDevice,ConfigureParams,HailoStreamInterface,
            InputVStreamParams,OutputVStreamParams,FormatType,InferVStreams)
        with hailo_lease(self.lock):
            hef=HEF(self.path)
            ins,outs=hef.get_input_vstream_infos(),hef.get_output_vstream_infos()
            if len(ins)!=1 or len(outs)!=1 or tuple(ins[0].shape)!=self.input_shape or tuple(outs[0].shape)!=self.output_shape:
                raise ValueError('depth HEF differs from manifest')
            image=Image.fromarray(frame.image[:,:,::-1]).resize((self.input_shape[1],self.input_shape[0]))
            with VDevice() as device:
                groups=device.configure(hef,ConfigureParams.create_from_hef(hef,interface=HailoStreamInterface.PCIe))
                if len(groups)!=1: raise ValueError('one network group required')
                group=groups[0]
                inp=InputVStreamParams.make_from_network_group(group,quantized=False,format_type=FormatType.FLOAT32,timeout_ms=500)
                out=OutputVStreamParams.make_from_network_group(group,quantized=False,format_type=FormatType.FLOAT32,timeout_ms=500)
                with group.activate(group.create_params()):
                    with InferVStreams(group,inp,out) as pipeline:
                        result=pipeline.infer({ins[0].name:np.asarray(image,dtype=np.float32)[None]})
            return self.summarize(result[outs[0].name],self.output_shape,self.nearer)


class FixtureModel:
    """Explicit offline test input. Never a CPU model or Hailo qualification claim."""
    def __init__(self, result):
        self.result=result
        self.metadata=dict(backend='offline-fixture', qualification='fixture-only', sha256=None)
    def infer(self, frame):
        if frame.authentic: raise ValueError('fixture inference cannot label live frames')
        import copy
        return copy.deepcopy(self.result)
