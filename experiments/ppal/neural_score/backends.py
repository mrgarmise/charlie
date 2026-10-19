"""Lazy CPU and actual HailoRT inference, with single shared resource admission."""
from contextlib import contextmanager
import importlib.metadata
import subprocess
import threading
import time
import numpy as np
from .contract import INPUT,OUTPUT,sha


class Busy(RuntimeError):
    """Score resource denial; do not shift contention onto CPU fallback."""


class Admission:
    """Cooperative process-local admission, not a second Hailo scheduler.

    All sprite/SELF and score users must share this instance. Scores never wait;
    urgent reservations prevent new score work. Existing in-flight work is bounded
    by Hailo stream timeout. Uncooperative external clients are not controlled.
    """
    def __init__(self):
        self.lock=threading.Lock();self.urgent=threading.Event();self.suspended=threading.Event();self.reason=None
    def suspend(self,reason):
        self.reason=str(reason);self.suspended.set()
    def resume(self):
        self.suspended.clear();self.reason=None
    @contextmanager
    def score(self):
        if self.suspended.is_set():raise Busy("score resource guard suspended: "+str(self.reason))
        if self.urgent.is_set() or not self.lock.acquire(blocking=False):raise Busy('Hailo busy; score dropped')
        try:
            if self.urgent.is_set() or self.suspended.is_set():raise Busy('SELF/perception reservation')
            yield
        finally:self.lock.release()

HAILO_ADMISSION=Admission()


class CPU:
    name='cpu-reference'
    def __init__(self,path,expected_sha):
        if sha(path)!=expected_sha:raise ValueError('ONNX hash mismatch')
        import onnxruntime as ort
        options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
        if self.session.get_inputs()[0].shape!=list(INPUT) or self.session.get_outputs()[0].shape!=list(OUTPUT):
            raise ValueError('CPU model shape mismatch')
    def infer(self,x):
        begin=time.perf_counter();submitted=time.monotonic();value=self.session.run(['logits'],{'images':x})[0]
        return value,dict(wall_seconds=time.perf_counter()-begin,device_seconds=None,inference_submitted_at=submitted,inference_returned_at=time.monotonic(),execution='actual CPU ONNX Runtime')


class Hailo:
    name='hailo-required'
    def __init__(self,path,contract,*,admission=HAILO_ADMISSION,timeout_ms=250):
        if contract.get('architecture')!='hailo8l' or contract.get('normalization')!='host /255; no embedded normalization':raise ValueError('Hailo contract/normalization mismatch')
        for key,expected in (('input_shape',list(INPUT)),('output_shape',list(OUTPUT)),
                             ('vstream_output_shape',[1,1,64,11]),
                             ('hef_input_dimensions',[32,256,3]),('hef_output_dimensions',[1,64,11])):
            if key in contract and contract[key]!=expected:raise ValueError('Hailo contract shape mismatch')
        if contract.get('vstream_dtype','float32')!='float32':raise ValueError('Hailo virtual stream dtype mismatch')
        if not 1<=timeout_ms<=1000 or sha(path)!=contract['hef_sha256']:raise ValueError('HEF integrity/timeout mismatch')
        report=subprocess.run(['hailortcli','parse-hef',str(path)],capture_output=True,text=True,timeout=5,check=True).stdout
        import re
        if not re.search(r'Architecture[^\n]*\bHAILO[-_ ]?8L\b',report,re.I):raise ValueError('HEF is not hailo8l')
        import hailo_platform
        self.runtime_version=getattr(hailo_platform,"__version__",None)
        from hailo_platform import HEF,Device
        self.hef=HEF(str(path));inputs=self.hef.get_input_vstream_infos();outputs=self.hef.get_output_vstream_infos()
        if not Device.scan():raise RuntimeError('no Hailo device')
        if len(inputs)!=1 or tuple(inputs[0].shape)!=(32,256,3) or len(outputs)!=1 or tuple(outputs[0].shape)!=(1,64,11):raise ValueError('HEF tensor dimensions mismatch')
        # Enum stringification is FormatOrder.FCR on HailoRT 4.23.0.
        # FCR describes HEF metadata, NOT a request to reorder the returned
        # Python FLOAT32 virtual-stream array. Only this fixed contract is known.
        input_order=str(inputs[0].format.order).rsplit('.',1)[-1]
        output_order=str(outputs[0].format.order).rsplit('.',1)[-1]
        if input_order!='NHWC' or output_order not in ('NHWC','FCR'):raise ValueError('unsupported tensor order')
        self.input_name,self.output_name=inputs[0].name,outputs[0].name
        if (self.input_name,self.output_name)!=('charlie_score/input_layer1','charlie_score/conv4'):
            raise ValueError('HEF score network names mismatch')
        for key,actual in (('input_name',self.input_name),('output_name',self.output_name),
                           ('hef_input_order',input_order),('hef_output_order',output_order)):
            if key in contract and contract[key]!=actual:raise ValueError('HEF metadata/manifest mismatch')
        self.output_order=output_order
        self.admission,self.timeout=admission,timeout_ms

    def infer(self,x):
        if x.shape!=INPUT or x.dtype!=np.float32 or not np.isfinite(x).all() or np.any(x<0) or np.any(x>1):
            raise ValueError('Hailo input shape/dtype/range mismatch')
        from hailo_platform import (VDevice,ConfigureParams,HailoStreamInterface,
            InputVStreamParams,OutputVStreamParams,FormatType,InferVStreams)
        begin=time.perf_counter()
        with self.admission.score():
            with VDevice() as device:
                groups=device.configure(self.hef,ConfigureParams.create_from_hef(self.hef,interface=HailoStreamInterface.PCIe))
                if len(groups)!=1:raise ValueError('one HEF network group required')
                group=groups[0]
                inp=InputVStreamParams.make_from_network_group(group,quantized=False,format_type=FormatType.FLOAT32,timeout_ms=self.timeout,queue_size=1)
                out=OutputVStreamParams.make_from_network_group(group,quantized=False,format_type=FormatType.FLOAT32,timeout_ms=self.timeout,queue_size=1)
                with InferVStreams(group,inp,out) as pipeline:
                    with group.activate(group.create_params()):
                        submitted=time.monotonic()
                        value=pipeline.infer({self.input_name:np.ascontiguousarray(x.transpose(0,2,3,1))})[self.output_name]
                        returned=time.monotonic()
        if value.shape!=(1,1,64,11) or value.dtype!=np.float32 or not np.isfinite(value).all():raise ValueError('Hailo output layout/dtype/nonfinite mismatch')
        return value.transpose(0,3,1,2),dict(wall_seconds=time.perf_counter()-begin,device_seconds=None,vstream_submitted_at=submitted,vstream_returned_at=returned,
            execution='actual HailoRT FLOAT32 streams; driver performs HEF quantization/dequantization',hailort_version=self.runtime_version,
            hef_output_order=self.output_order,vstream_output_shape=list(value.shape))


class Backend:
    def __init__(self,mode,cpu_factory,hailo_factory=None):
        if mode not in ('cpu-reference','hailo-required','hailo-preferred'):raise ValueError('explicit backend mode required')
        self.mode=mode;self.cpu_factory=cpu_factory;self.hailo_factory=hailo_factory
        self.cpu=None;self.hailo=None
    def infer(self,x):
        event=None
        if self.mode!='cpu-reference':
            try:
                if self.hailo is None:
                    if self.hailo_factory is None:raise RuntimeError('HEF/runtime unavailable')
                    self.hailo=self.hailo_factory()
                value,timing=self.hailo.infer(x)
                return value,dict(timing,backend='hailo-required',health_event=None)
            except (Busy,MemoryError):
                raise
            except Exception as exc:
                event=dict(error=type(exc).__name__,message=str(exc))
                self.hailo=None
                if self.mode=='hailo-required':raise
        if self.cpu is None:self.cpu=self.cpu_factory()
        value,timing=self.cpu.infer(x)
        return value,dict(timing,backend='cpu-reference',health_event=event)
