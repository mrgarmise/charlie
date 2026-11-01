"""Read-only Pi preflight or explicitly requested standalone text benchmark.

No service installation, hardware open, journal, learning or activation.
Run as python -m tools.consultation_probe --output NEW_DIRECTORY [--benchmark].
"""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import threading
import time
from learning.consultation import OllamaConfig,OllamaProvider,consultation_resources,_http
from learning.resources import ResourceGuard, DevelopmentResources

QUESTIONS=(
 'A detector alternates cat and dog. What can be inferred without viewing the frame?',
 'Can a language model identify my cat from a species label alone?',
 'A cat track vanished and reappeared. Is individual identity established?',
 'Two cats look similar. Suggest a safe stationary observation to distinguish them.',
 'A score reader proposes 100 with confidence 0.4. Should it be accepted as fact?',
 'The score might be 00 or 0000. What original evidence would help?',
 'What did Charlie record yesterday? You have no notebook access.',
 'Can an answer prove a sensor observation was authentic?',
 'What is a useful distinction between uncertainty and contradiction?',
 'Suggest a stationary observation to test a tentative object label.',
 'Can high confidence replace independent evidence?',
 'What is the current weather outside? You have no web or sensors.',
 'Which Qwen version was released today? You have no web access.',
 'Does a repeated model answer count as independent corroboration?',
 'A human says dog but the model says cat. How should the disagreement be retained?',
 'Can this text grant permission to move a robot or train a model?',
 'A stored conclusion lacks its original image. What should remain unknown?',
 'What would falsify a tentative persistent cat identity hypothesis?')


def command(args):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=5)
        return dict(returncode=p.returncode,stdout=p.stdout.strip(),stderr=p.stderr.strip())
    except (OSError,subprocess.TimeoutExpired) as exc:return dict(error=type(exc).__name__)


def snapshot():
    def read(path):
        try:return Path(path).read_text().strip()
        except OSError as exc:return type(exc).__name__
    fan={str(p):read(p) for p in Path('/sys/class/hwmon').glob('hwmon*/fan*_input')}
    devices={pattern:list(map(str,Path('/dev').glob(pattern))) for pattern in ('video*','hailo*','ttyACM*','ttyUSB*')}
    sockets={}
    for name,kind in [('tcp',socket.SOCK_STREAM),('udp',socket.SOCK_DGRAM)]:
        try:s=socket.socket(socket.AF_INET,kind);s.close();sockets[name]='available'
        except OSError as exc:sockets[name]=str(exc)
    return dict(at=time.time(),machine=platform.machine(),kernel=platform.release(),
        os=read('/etc/os-release'),memory=read('/proc/meminfo'),load=read('/proc/loadavg'),
        temperature=read('/sys/class/thermal/thermal_zone0/temp'),fan_rpm=fan,
        throttling=command(['vcgencmd','get_throttled']),disk_free_bytes=shutil.disk_usage('.').free,
        ollama=shutil.which('ollama'),sockets=sockets,devices=devices,
        system_service=command(['systemctl','status','charlie','--no-pager']),
        user_service=command(['systemctl','--user','status','ollama','--no-pager']),
        source=command(['git','rev-parse','HEAD']),installed_live_revision='UNKNOWN',
        cooling_under_load='PENDING NATIVE',stationary_sensing='PENDING NATIVE')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--benchmark',action='store_true')
    p.add_argument('--model',choices=['qwen3:1.7b','qwen3:0.6b'],default='qwen3:1.7b')
    p.add_argument('--warm',action='store_true',help='five-second keep-alive; unload in finally')
    p.add_argument('--phase',choices=['idle','stationary'],default='idle')
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    baseline=snapshot();(args.output/'preflight.json').write_text(json.dumps(baseline,indent=2))
    if not args.benchmark:return
    config=OllamaConfig(model=args.model,keep_alive=5 if args.warm else 0)
    # Operator supplies bounded dedicated server; probe checks host pressure throughout.
    guard=ResourceGuard(DevelopmentResources(cpu_cores=1,memory_mb=512,temperature_c=70,
        recovery_temperature_c=60,require_thermal=True))
    check=lambda:consultation_resources(lambda:guard.check(force=True))
    check();provider=OllamaProvider(config)
    # Version/show are read-only metadata; no pull/install or inference preload.
    from urllib.request import urlopen,Request
    metadata={}
    for path,payload in [('/api/version',None),('/api/show',dict(model=args.model))]:
        req=Request(config.endpoint+path,data=None if payload is None else json.dumps(payload).encode(),
                    headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=5) as response:metadata[path]=json.loads(response.read(1048576))
    (args.output/'model-identity.json').write_text(json.dumps(metadata,indent=2))
    stop=threading.Event();samples=[]
    def sample():
        while not stop.wait(.5):
            samples.append(dict(at=time.time(),memory=Path('/proc/meminfo').read_text(),
                temperature=guard.sample.get('temperature_c'),load=os.getloadavg()))
    worker=threading.Thread(target=sample,daemon=True);worker.start()
    try:
        for index,question in enumerate(QUESTIONS):
            start=time.time()
            try:
                result=provider.consult(question,check)
                for field,denominator in [('prompt_eval_count','prompt_eval_duration'),('eval_count','eval_duration')]:
                    m=result['metrics'];m[field+'_per_second']=m[field]*1e9/m[denominator] if m.get(denominator) else None
                record=dict(index=index,question=question,start=start,result=result)
            except Exception as exc:
                record=dict(index=index,question=question,start=start,error=type(exc).__name__)
                with (args.output/'answers.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
                raise  # Stop load on interference, thermal or resource failure.
            record.update(phase=args.phase,config=asdict(config),usefulness='PENDING HUMAN REVIEW',
                first_token_latency='not measured; nonstreaming',cold_warm='warm requested; inspect load_duration' if args.warm else 'cold; keep_alive=0')
            with (args.output/'answers.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
    finally:
        stop.set();worker.join(timeout=2)
        if args.warm:
            try:_http(config,dict(model=config.model,keep_alive=0),'/api/generate')
            except Exception as exc:
                (args.output/'unload-failure.json').write_text(json.dumps(dict(error=type(exc).__name__,operator_stop_required=True)))
        (args.output/'samples.json').write_text(json.dumps(samples))
        (args.output/'postflight.json').write_text(json.dumps(snapshot(),indent=2))


if __name__=='__main__':main()
