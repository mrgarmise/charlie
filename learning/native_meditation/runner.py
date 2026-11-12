"""Root-launched finite model exec; independent guardian retains exclusion.

Never run directly during development. No model download or arbitrary command.
"""
import fcntl
import hashlib
import json
import os
import subprocess
import time
import re
from pathlib import Path
from .security import POLICY, root_read


def inherit_lock(path):
    fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BaseException:os.close(fd);raise
    os.set_inheritable(fd,True)
    return fd


def main():
    if os.geteuid()!=0:raise PermissionError('system launcher only')
    p=json.loads(root_read(POLICY))
    if p.get('enabled') is not True:raise PermissionError('policy disabled')
    binary=Path(p['ollama_binary']);raw=root_read(binary,256*1024*1024)
    if hashlib.sha256(raw).hexdigest()!=p['ollama_binary_sha256']:raise PermissionError('unreviewed model binary')
    lease=json.loads(root_read(Path(p['state_dir'])/'service-lease.json'))
    if (lease['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
            or lease['mono_end']-time.monotonic()<40):raise PermissionError('late or stale native launch')
    # RuntimeMaxSec is immutable after a service leaves UNIT_STUB on supported
    # systemd versions. Verify the preset bound; never pretend set-property works.
    unit='charlie-meditation-consultant.service'
    result=subprocess.run(['systemctl','show',unit,
        '--property=ActiveEnterTimestampMonotonic,RuntimeMaxUSec,TimeoutStopUSec'],
        check=True,capture_output=True,text=True,timeout=2)
    props=dict(x.split('=',1) for x in result.stdout.splitlines())
    def seconds(value):
        parts=re.findall(r'([0-9]+(?:\.[0-9]+)?)(min|ms|us|s)',value)
        if not parts or ''.join(a+b for a,b in parts)!=value.replace(' ',''):raise PermissionError('finite duration')
        units={'min':60,'s':1,'ms':.001,'us':.000001}
        return sum(float(a)*units[b] for a,b in parts)
    active=int(props['ActiveEnterTimestampMonotonic'])/1e6
    runtime=seconds(props['RuntimeMaxUSec']);stop=seconds(props['TimeoutStopUSec'])
    if (active<=0 or runtime!=lease['runtime_seconds'] or not 0<stop<=5
            or active+runtime+stop>lease['mono_end']-.25):
        raise PermissionError('late activation cannot fit absolute kernel cutoff')
    os.setgroups([]);os.setgid(p['model_gid']);os.setuid(p['model_uid'])
    os.execv(str(binary),[str(binary),'serve'])

if __name__=='__main__':main()
