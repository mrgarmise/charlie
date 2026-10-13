"""One bounded local worker at a time; durable queue, cancellation and resume."""
import fcntl
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from .store import identifier,file_hash


def own_worker(job,root):
    pid=job.get('worker_pid')
    if not pid:return False
    try:
        proc=Path('/proc')/str(pid);state=(proc/'stat').read_text().rsplit(')',1)[1].split()
        args=(proc/'cmdline').read_bytes().split(b'\0')
        return proc.stat().st_uid==os.getuid() and state[0]!='Z' and state[19]==job.get('worker_start_ticks') and b'vision_lab.worker' in args and str(root).encode() in args and job['id'].encode() in args and os.getpgid(pid)==pid
    except (OSError,IndexError):return False


def stop_retained(job,root):
    if not own_worker(job,root):return
    os.killpg(job['worker_pid'],signal.SIGTERM);end=time.monotonic()+5
    while own_worker(job,root) and time.monotonic()<end:time.sleep(.1)
    if own_worker(job,root):
        os.killpg(job['worker_pid'],signal.SIGKILL);end=time.monotonic()+2
        while own_worker(job,root) and time.monotonic()<end:time.sleep(.1)
    if own_worker(job,root):raise RuntimeError('Retained worker could not be stopped; refusing another scheduler')


def preflight():
    versions={}
    for name in ('Pillow','paramiko','ultralytics','torch','torchvision','onnx','onnxruntime'):
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    cuda=False;devices=[]
    if versions['torch']:
        try:
            import torch
            cuda=torch.cuda.is_available();devices=[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
        except (ImportError,OSError):pass
    memory=None
    try:memory=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
    except (OSError,StopIteration,ValueError):pass
    import shutil,platform
    return dict(platform=platform.platform(),python=sys.version,cpu_count=os.cpu_count(),available_memory_bytes=memory,cuda_available=cuda,gpu_devices=devices,versions=versions,
        training_available=all(versions[x] for x in ('torch','torchvision','ultralytics')),
        onnx_available=bool(versions['onnx']),hailomz=shutil.which('hailomz'),hailo_compiler=shutil.which('hailo'),
        hailo_target='hailo8l; 13 TOPS',native_hardware_validated=False)


class Jobs:
    def __init__(self,lab):
        self.lab=lab;self.closed=False;self.children={};self.mutex=threading.Lock()
        # Completed jobs remain immutable in meaning; unfinished prior processes need explicit restart.
        for row in lab.items('jobs'):
            if row['data']['status']=='running' or (row['data']['status']=='queued' and row['data'].get('worker_pid')):
                stop_retained(row['data'],lab.root)
                d=row['data'];d.update(status='interrupted',error='Application restarted; inspect last checkpoint and explicitly restart');lab.put('jobs',row['id'],d)
        # If process identity cannot be established, never run beside an orphan.
        with (lab.root/'worker.lock').open('a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError as e:raise RuntimeError('Existing lab worker still owns resources; refuse a second scheduler') from e
        self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()

    def submit(self,kind,parameters):
        if kind not in ('index','train','evaluate','suggest','export'):raise ValueError('Unknown job type')
        if not isinstance(parameters,dict):raise ValueError('Job parameters required')
        deadline=parameters.get('deadline_seconds',86400)
        if type(deadline) is not int or not 30<=deadline<=86400:raise ValueError('Job deadline must be 30..86400 seconds')
        parameters['deadline_seconds']=deadline
        if kind=='train':
            if not preflight()['training_available']:raise ValueError('Install optional local training dependencies first')
            for name,default,low,high in [('epochs',10,1,1000),('imgsz',640,64,640),('batch',4,1,64),('threads',2,1,8),('seed',7,0,1000000)]:
                value=parameters.get(name,default)
                if type(value) is not int or not low<=value<=high:raise ValueError('Invalid '+name)
                parameters[name]=value
            if parameters['imgsz']%32:raise ValueError('Input size must be a multiple of 32')
            device=parameters.get('device','cpu')
            if device!='cpu' and (not isinstance(device,str) or not device.isdigit() or not preflight()['cuda_available']):raise ValueError('Available CUDA index or cpu required')
            parameters['device']=device
            from .datasets import verify_manifest
            m=verify_manifest(self.lab,parameters['dataset_id'])
            with self.lab.connect() as c:
                for row in m['frames']:
                    if row['role']=='test' and c.execute('SELECT 1 FROM consulted_tests WHERE pixel_sha=?',(row['pixel_sha'],)).fetchone():
                        raise ValueError('Test outcome already exposed; new training/selection requires fresh unconsulted test sessions')
            parameters['dataset_digest']=m['digest']
            baseline=parameters.get('baseline_id')
            if baseline:
                model=self.lab.get('models',baseline);parameters['baseline_sha256']=model['checkpoint_sha256']
        job=dict(id=identifier(),kind=kind,parameters=parameters,status='queued',created_at=time.time(),physical_authorization=False)
        self.lab.put('jobs',job['id'],job,immutable=True)
        return job

    def cancel(self,job_id):
        job=self.lab.get('jobs',job_id)
        if job['status'] not in ('running','queued'):return job
        (self.lab.root/'jobs'/job_id).mkdir(exist_ok=True)
        (self.lab.root/'jobs'/job_id/'cancel').touch()
        if job['status']=='queued':job.update(status='cancelled');self.lab.put('jobs',job_id,job)
        return job

    def restart(self,job_id):
        job=self.lab.get('jobs',job_id)
        if job['status'] not in ('failed','interrupted','cancelled'):raise ValueError('Only stopped/failed jobs can restart')
        p=dict(job['parameters']);last=self.lab.root/'jobs'/job_id/'run'/'weights'/'last.pt'
        if job['kind']=='train' and last.is_file():p['resume_job_id']=job_id;p['resume_sha256']=file_hash(last)
        return self.submit(job['kind'],p)

    def loop(self):
        while not self.closed:
            queued=next((r['data'] for r in self.lab.items('jobs') if r['data']['status']=='queued'),None)
            if not queued:time.sleep(.1);continue
            folder=self.lab.root/'jobs'/queued['id'];folder.mkdir(exist_ok=True)
            with (folder/'log.txt').open('ab') as log:
                env=dict(os.environ,YOLO_OFFLINE='true',YOLO_AUTOINSTALL='false',OMP_NUM_THREADS=str(queued['parameters'].get('threads',2)),OPENBLAS_NUM_THREADS='2',YOLO_CONFIG_DIR=str(self.lab.root/'dependency-config'))
                try:child=subprocess.Popen([sys.executable,'-m','vision_lab.worker','--state',str(self.lab.root),'--job',queued['id']],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
                except OSError as e:
                    queued.update(status='failed',error='Cannot launch local worker: '+str(e));self.lab.put('jobs',queued['id'],queued);continue
                self.children[queued['id']]=child
                timeout_at=time.monotonic()+queued['parameters'].get('deadline_seconds',86400)
                cancelled_at=None
                while child.poll() is None:
                    if self.closed or (folder/'cancel').exists() or time.monotonic()>timeout_at:
                        if cancelled_at is None:
                            cancelled_at=time.monotonic()
                            try:os.killpg(child.pid,signal.SIGTERM)
                            except ProcessLookupError:pass
                        elif time.monotonic()-cancelled_at>5:
                            try:os.killpg(child.pid,signal.SIGKILL)
                            except ProcessLookupError:pass
                    time.sleep(.1)
                child.wait();self.children.pop(queued['id'],None)
                state=self.lab.get('jobs',queued['id'])
                if cancelled_at is not None:state.update(status='cancelled',error='Cancelled; completed epoch checkpoints retained for explicit resume')
                elif child.returncode or state['status'] not in ('completed','failed'):state.update(status='failed',error=state.get('error') or 'Worker exited without completion; inspect logs')
                state['returncode']=child.returncode;state['finished_at']=time.time();self.lab.put('jobs',queued['id'],state)

    def close(self):
        self.closed=True;self.thread.join(timeout=8)
