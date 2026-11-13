"""Reusable HailoRT session, not a scheduler. Cooperating clients share one lease."""
from contextlib import ExitStack, contextmanager
from pathlib import Path
import fcntl
import hashlib
import os
import threading


@contextmanager
def accelerator_lease(path=None):
    with Path(path or os.environ.get('CHARLIE_HAILO_LOCK','/tmp/charlie-hailo.lock')).open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)


class HailoSession:
    """Keep configure/activation/vstreams open across frames; fail/close on error.

    Lease belongs to this session's lifetime. Caller closes/yields on primary-task,
    thermal suspension, cancellation and bounded-watcher exit. No background loop.
    """
    def __init__(self,path,*,sha256,input_shape,output_shape=None,timeout=.5,lock=None):
        if not 0<timeout<=5:raise ValueError('bounded Hailo timeout required')
        self.path,self.sha256,self.input_shape=str(path),sha256,tuple(input_shape)
        self.output_shape,self.timeout,self.lock=output_shape,timeout,lock
        self.stack=None;self.pipeline=None;self.configurations=0;self.owner=None

    def open(self):
        if self.stack is not None:return
        stack=ExitStack()
        try:
            stack.enter_context(accelerator_lease(self.lock))
            if hashlib.sha256(Path(self.path).read_bytes()).hexdigest()!=self.sha256:raise ValueError('HEF changed before session open')
            from hailo_platform import (HEF,VDevice,ConfigureParams,HailoStreamInterface,
                InputVStreamParams,OutputVStreamParams,FormatType,InferVStreams)
            hef=HEF(self.path);inputs=hef.get_input_vstream_infos();outputs=hef.get_output_vstream_infos()
            if len(inputs)!=1 or len(outputs)!=1 or tuple(inputs[0].shape)!=self.input_shape:
                raise ValueError('session HEF contract mismatch')
            if self.output_shape is not None and tuple(outputs[0].shape)!=tuple(self.output_shape):raise ValueError('depth HEF output mismatch')
            device=stack.enter_context(VDevice())
            groups=device.configure(hef,ConfigureParams.create_from_hef(hef,interface=HailoStreamInterface.PCIe))
            if len(groups)!=1:raise ValueError('one Hailo network group required')
            group=groups[0]
            inp=InputVStreamParams.make_from_network_group(group,quantized=False,format_type=FormatType.FLOAT32,timeout_ms=round(self.timeout*1000))
            out=OutputVStreamParams.make_from_network_group(group,quantized=False,format_type=FormatType.FLOAT32,timeout_ms=round(self.timeout*1000))
            stack.enter_context(group.activate(group.create_params()))
            self.pipeline=stack.enter_context(InferVStreams(group,inp,out))
            self.input_name=inputs[0].name;self.output_name=outputs[0].name
            self.stack=stack;self.owner=threading.get_ident();self.configurations+=1
        except BaseException:
            stack.close();self.pipeline=None
            raise

    def infer(self,tensor):
        try:
            self.open()
            if self.owner!=threading.get_ident():raise RuntimeError('Hailo session may not cross worker threads')
            return self.pipeline.infer({self.input_name:tensor})
        except BaseException:
            self.close();raise

    def close(self):
        stack,self.stack=self.stack,None
        self.pipeline=None;self.owner=None
        if stack is not None:stack.close()

    def __enter__(self):self.open();return self
    def __exit__(self,*exc):self.close()
