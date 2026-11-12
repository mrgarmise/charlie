"""Root trust boundary. Never accept Executive-owned policy or approvals."""
import json
import os
from pathlib import Path
import socket
import stat
import struct

POLICY=Path('/etc/charlie-meditation/policy.json')
SOCKET=Path('/run/charlie-meditation/broker.sock')
APPROVALS=Path('/run/charlie-meditation/approvals')


def root_directory(path):
    path=Path(path)
    for item in (path,*path.parents):
        st=item.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022:
            raise PermissionError('protected root authority directory required')
    return path


def root_read(path, limit=65536):
    path=Path(path)
    for parent in (path.parent,*path.parent.parents):
        st=parent.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022:
            raise PermissionError('root-owned non-writable authority path required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        st=os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022:
            raise PermissionError('root-owned immutable authority file required')
        raw=f.read(limit+1)
    if len(raw)>limit:raise ValueError('authority file exceeds bound')
    return raw


def peer(sock):
    return struct.unpack('3i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))


def rpc(path, payload, *, expected_uid=0, timeout=2):
    raw=json.dumps(payload,allow_nan=False).encode()+b'\n'
    if len(raw)>16384:raise ValueError('bounded authority request required')
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
        s.settimeout(timeout);s.connect(str(path))
        if peer(s)[1]!=expected_uid:raise PermissionError('authority peer UID mismatch')
        s.sendall(raw);reply=b''
        while not reply.endswith(b'\n'):
            block=s.recv(min(4096,65537-len(reply)))
            if not block or len(reply)+len(block)>65536:raise ValueError('authority response refused')
            reply+=block
    result=json.loads(reply)
    if result.get('ok') is not True:raise PermissionError(result.get('error','authority refused'))
    return result['result']


def protected_source(path, client_uid, client_gid):
    path=Path(path)
    for item in (path,*path.parents):
        st=item.lstat()
        if (stat.S_ISLNK(st.st_mode) or st.st_uid==client_uid or st.st_mode&0o002
                or (st.st_gid==client_gid and st.st_mode&0o020)):
            raise PermissionError('Executive-writable source cannot establish original provenance')
    if not path.is_file():raise PermissionError('original source is not a regular journal')


def standing_bytes(path):
    path=Path(path)
    if path.parent!=APPROVALS or path.suffix!='.json' or len(path.stem)!=32 or any(c not in '0123456789abcdef' for c in path.stem):
        raise PermissionError('fixed root approval namespace required')
    return root_read(path,16384)


def validate_live(doc, raw):
    import hashlib
    policy=json.loads(root_read(POLICY))
    if policy.get('enabled') is not True or policy.get('client_uid')!=os.getuid():
        raise PermissionError('standing policy disabled or wrong client')
    return rpc(SOCKET,dict(op='validate',slot=doc['slot_id'],digest=hashlib.sha256(raw).hexdigest()))
