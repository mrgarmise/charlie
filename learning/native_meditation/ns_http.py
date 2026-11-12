"""Root-invoked bounded HTTP in the model's PRIVATE network namespace.

No client-controlled PID, executable, endpoint, model or filesystem path. Root
broker supplies the inspected PID/start identity; privileges drop before HTTP.
"""
import json
import os
from pathlib import Path
import sys
from .security import POLICY,root_read
from learning.consultation import OllamaConfig,_http


def main():
    if os.geteuid()!=0:raise PermissionError('independent namespace broker only')
    if len(sys.argv)!=4 or sys.argv[3] not in ('/api/chat','/api/ps','/api/version','/api/generate'):
        raise ValueError('bounded native API')
    pid=int(sys.argv[1]);expected=sys.argv[2]
    p=json.loads(root_read(POLICY))
    raw=sys.stdin.buffer.read(16385)
    if len(raw)>16384:raise ValueError('bounded request')
    data=json.loads(raw)
    fd=os.open('/proc/%d/ns/net'%pid,os.O_RDONLY)
    try:
        ticks=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19]
        if ticks!=expected:raise PermissionError('model process changed')
        os.setns(fd,os.CLONE_NEWNET)
    finally:os.close(fd)
    os.setgroups([]);os.setgid(p['model_gid']);os.setuid(p['model_uid'])
    result=_http(OllamaConfig(wall_seconds=min(30,max(.1,float(data['timeout'])))),data['payload'],sys.argv[3])
    sys.stdout.write(json.dumps(result,ensure_ascii=False,allow_nan=False))

if __name__=='__main__':main()
