"""Independent root unit holds the SAME flock until model cgroup is empty.

Broker-to-guard SCM_RIGHTS preserves continuous exclusion. Neither broker death
nor model MainPID death drops the last lock while model children survive.
"""
import array
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import time
from .security import POLICY,root_read,peer

UNIT='charlie-meditation-consultant.service'


def stop_model():
    subprocess.run(['systemctl','stop',UNIT],capture_output=True,timeout=7)
    result=subprocess.run(['systemctl','show',UNIT,'--property=MainPID,ActiveState,ControlGroup'],
                          capture_output=True,text=True,check=True,timeout=2)
    props=dict(x.split('=',1) for x in result.stdout.splitlines())
    if props.get('MainPID')!='0' or props.get('ActiveState') not in ('inactive','failed'):
        raise PermissionError('model unit still active')
    group=Path('/sys/fs/cgroup')/(props.get('ControlGroup') or '/system.slice/'+UNIT).lstrip('/')
    if group.exists() and any(p.read_text().strip() for p in group.rglob('cgroup.procs')):
        raise PermissionError('model descendants remain')


def main():
    if os.geteuid()!=0:raise PermissionError('root guardian only')
    slot=sys.argv[1]
    if len(slot)!=32 or any(c not in '0123456789abcdef' for c in slot):raise ValueError('slot')
    p=json.loads(root_read(POLICY));lease=json.loads(root_read(Path(p['state_dir'])/'service-lease.json'))
    if lease['slot']!=slot or lease['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        raise PermissionError('stale guardian')
    path=Path('/run/charlie-meditation')/('guard-'+slot+'.sock')
    fd=pidfd=None
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
        server.bind(str(path));os.chmod(path,0o600);server.listen(2);server.settimeout(2)
        try:
            connection,_=server.accept()
            with connection:
                pid,uid,_=peer(connection)
                if uid!=0:raise PermissionError('only root issuer transfers exclusion')
                message,ancillary,flags,_=connection.recvmsg(64,socket.CMSG_SPACE(array.array('i').itemsize),socket.MSG_CMSG_CLOEXEC)
                descriptors=array.array('i')
                for level,kind,data in ancillary:
                    if level==socket.SOL_SOCKET and kind==socket.SCM_RIGHTS:descriptors.frombytes(data[:len(data)//descriptors.itemsize*descriptors.itemsize])
                if message!=slot.encode() or len(descriptors)!=1:raise PermissionError('one exact slot lock required')
                fd=descriptors[0]
                actual=os.fstat(fd);expected=Path(p['runtime_lock']).stat()
                if (actual.st_dev,actual.st_ino)!=(expected.st_dev,expected.st_ino):raise PermissionError('wrong lock inode')
                pidfd=os.pidfd_open(pid);connection.sendall(b'HELD\n')
            finish_connection=None
            while time.monotonic()<lease['mono_end']-5 and not select.select([pidfd],[],[],0)[0]:
                ready=select.select([server],[],[],.1)[0]
                if ready:
                    candidate,_=server.accept();candidate.settimeout(1)
                    if peer(candidate)[1]==0 and candidate.recv(64)==b'FINISH':finish_connection=candidate;break
                    candidate.close()
            # Never release based on a requested stop or elapsed clock alone.
            # A failure intentionally retains the FD until independently repaired.
            while True:
                try:stop_model();break
                except Exception:time.sleep(.2)
            if finish_connection:
                with finish_connection:finish_connection.sendall(b'EMPTY\n')
        finally:
            # Even an unexpected socket/peer exception after FD receipt must
            # retain exclusion until independent descendant cleanup succeeds.
            if fd is not None:
                while True:
                    try:stop_model();break
                    except Exception:time.sleep(.2)
                os.close(fd)
            if pidfd is not None:os.close(pidfd)
            path.unlink(missing_ok=True)

if __name__=='__main__':main()
