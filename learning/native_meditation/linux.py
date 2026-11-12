"""Real Linux driver. Root policy, kernel locks/pidfds, systemd cutoff, sole-owner RPC.

Nothing in this module starts on import. Running/installing it is native work.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import time
import sys
import socket
import array
import math
from .security import POLICY, APPROVALS, root_read, rpc, root_directory
from learning.consultation import OllamaConfig, _http, consultation_resources
from learning.consultation_activation import service_identity, ready_model, SCHEMA
from learning.resources import temperature

UNIT='charlie-meditation-consultant.service'
FIELDS=('sensing','telemetry_deadline','watchdog_deadline','physical_task','gameplay','outstanding_lease','primary_pending','revoked','swap_used','throttled')


def run(*args, timeout=3):
    return subprocess.run(list(args),check=True,capture_output=True,text=True,timeout=timeout).stdout.strip()


def atomic(path, data, gid=None):
    path=Path(path);temp=path.with_suffix('.new')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o640)
    try:
        if gid is not None:os.fchown(fd,0,gid)
        with os.fdopen(fd,'wb',closefd=False) as f:
            f.write(data);f.flush();os.fsync(fd)
        os.rename(temp,path)
        d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(d)
        finally:os.close(d)
    finally:os.close(fd)


class LinuxDriver:
    def __init__(self):
        if os.geteuid()!=0:raise PermissionError('native issuer requires separate root identity')
        self.fd=None;self.pidfd=None;self.running=False;self.last_ack=None;self.pending=False;self.preparing=False
        self.slot=None;self.policy()

    def policy(self):
        p=json.loads(root_read(POLICY))
        if p.get('enabled') is not True:raise PermissionError('standing policy disabled')
        root_directory(p['state_dir']);root_directory(APPROVALS)
        if p.get('server_version')!='0.40.13':raise PermissionError('unqualified Ollama version')
        roles=[p.get(k) for k in ('client_uid','model_uid','display_uid','owner_uid')]
        if any(type(x) is not int or x<=0 for x in roles) or len(set(roles))!=4:
            raise PermissionError('distinct owner/Executive/model/display OS identities required')
        receipt=root_read(p['qualification_path'],1024*1024)
        if hashlib.sha256(receipt).hexdigest()!=p['qualification_sha256']:raise PermissionError('qualification receipt changed')
        qualification=json.loads(receipt)
        if (qualification.get('native_scheduler_display_accepted') is not True
                or qualification.get('code_revision')!=p['code_revision']
                or qualification.get('model_digest')!=p['model_digest']
                or qualification.get('inventory_sha256')!=hashlib.sha256(root_read(p['inventory_path'])).hexdigest()):
            raise PermissionError('separately accepted native inventory/display/issuer receipt required')
        stamp=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()
        if getattr(self,'_verified_policy',None)==stamp:self.p=p;return p
        # Python imports and runner are from this root-protected reviewed checkout.
        repo=Path(__file__).resolve().parents[2]
        if run('git','-C',str(repo),'rev-parse','HEAD')!=p['code_revision'] or run('git','-C',str(repo),'status','--porcelain'):
            raise PermissionError('exact clean native issuer source required')
        for path in repo.rglob('*.py'):root_read(path,1024*1024)
        self.p=p;self._verified_policy=stamp
        return p

    def inventory(self):
        inventory=json.loads(root_read(self.p['inventory_path']))
        until=inventory.get('valid_until');duties=inventory.get('scheduled_duties')
        if (type(until) not in (int,float) or not math.isfinite(until)
                or not isinstance(duties,list) or len(duties)>1024
                or any(not isinstance(d,dict) or type(d.get('at')) not in (int,float)
                       or not math.isfinite(d['at']) for d in duties)):
            raise PermissionError('unknown or nonfinite native deadlines')
        return inventory

    def _lock_path(self):
        path=Path(self.p['runtime_lock'])
        # The Executive is a separate UID, not the human account owning ~/charlie-ops.
        for parent in (path.parent,*path.parent.parents):
            st=parent.stat()
            if st.st_uid==self.p['client_uid'] or st.st_mode&2 or (st.st_gid==self.p['client_gid'] and st.st_mode&0o020):
                raise PermissionError('Executive may not replace runtime lock path')
        return path

    def acquire(self, requested_end):
        if self.fd is not None or self.running:raise PermissionError('driver already reserved')
        path=self._lock_path();self.fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW)
        try:
            fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.lock_inode=(os.fstat(self.fd).st_dev,os.fstat(self.fd).st_ino)
            inventory=self.inventory()
            deadlines=inventory['scheduled_duties']
            end=min([requested_end]+[float(x['at'])-5 for x in deadlines])
            self.reserved_end=end;self.reserved_mono=time.monotonic()+end-time.time()
            self.inspect(end)
            return end
        except BaseException:self.release();raise

    def watch_client(self, pid):
        status=dict(line.split(':',1) for line in Path('/proc',str(pid),'status').read_text().splitlines() if ':' in line)
        if (any(int(x)!=self.p['client_uid'] for x in status['Uid'].split())
                or any(int(x)!=self.p['client_gid'] for x in status['Gid'].split())
                or not set(map(int,status['Groups'].split()))<={self.p['client_gid']}
                or int(status['CapEff'].strip(),16)!=0 or int(status['CapPrm'].strip(),16)!=0
                or status.get('NoNewPrivs','').strip()!='1'):
            raise PermissionError('isolated nonprivileged Executive identity required')
        self.pidfd=os.pidfd_open(pid)
    def client_alive(self):return self.pidfd is not None and not select.select([self.pidfd],[],[],0)[0]

    def inspect(self, end):
        p=self.p;inventory=self.inventory()
        required={'camera','hailo','serial','telemetry','watchdog','motion','gameplay','human','primary'}
        if (set(inventory.get('owner_classes',[]))!=required or inventory.get('unknown_owners')!=[]
                or inventory.get('valid_until',0)<end or not inventory.get('units')):
            raise PermissionError('incomplete independent owner inventory')
        for unit in inventory['units']:
            if not isinstance(unit,str) or not unit.endswith('.service') or '/' in unit:raise ValueError('invalid primary unit')
            state=run('systemctl','show',unit,'--property=LoadState,ActiveState')
            props=dict(x.split('=',1) for x in state.splitlines())
            if props.get('LoadState')!='loaded' or props.get('ActiveState')!='inactive':raise InterruptedError('active/unknown primary owner')
        bridge=run('systemctl','show',p['display_unit'],'--property=MainPID,ActiveState')
        props=dict(x.split('=',1) for x in bridge.splitlines())
        bridge_pid=int(props.get('MainPID','0'))
        if props.get('ActiveState')!='active' or bridge_pid<=0:raise PermissionError('existing display owner unavailable')
        safety=rpc(p['display_socket'],dict(op='safety'),expected_uid=p['display_uid'])
        if safety.get('clear') is not True or (safety.get('emergency') is not False and not getattr(self,'_clearing_primary',False)):
            raise PermissionError('display owner has active/unknown physical duties')
        # Independently scan all live processes; inaccessible inventory is refusal.
        sensitive=('/dev/video','/dev/media','/dev/vchiq','/dev/hailo','/dev/ttyACM','/dev/ttyUSB','/dev/i2c','/dev/spidev','/dev/gpio','/dev/mem')
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():continue
            try:
                for fd in (proc/'fd').iterdir():
                    try:target=os.readlink(fd)
                    except FileNotFoundError:continue
                    if target.startswith(sensitive) and not (int(proc.name)==bridge_pid and target==p['serial_device']):
                        raise InterruptedError('unmanaged physical owner')
            except FileNotFoundError:continue
        if not self.running:
            for line in Path('/proc/net/tcp').read_text().splitlines()[1:]:
                fields=line.split()
                if fields[3]=='0A' and fields[1].endswith(':2CAA'):
                    raise PermissionError('pre-existing model server; manual path owns port')
        # Active non-loopback TCP clients may be camera/gameplay owners. Explicit
        # OS traffic exceptions are root-reviewed socket inode owners, never frames.
        for table in ('tcp','tcp6'):
            rows=(Path('/proc/net')/table).read_text().splitlines()[1:]
            for line in rows:
                fields=line.split()
                if fields[3]=='01' and fields[2].split(':')[0] not in ('0100007F','00000000000000000000000001000000'):
                    raise InterruptedError('non-loopback activity requires owner reconciliation')
        consultation_resources(lambda:None)
        heat=temperature()
        if heat is None:raise PermissionError('temperature unavailable')
        throttled=run('vcgencmd','get_throttled')!='throttled=0x0'
        st=self._lock_path().stat()
        if (st.st_dev,st.st_ino)!=self.lock_inode:raise PermissionError('runtime lock replaced')
        if self.running and hasattr(self,'identity'):
            identity=service_identity(system=True)
            if identity!=self.identity:raise PermissionError('model service restarted or bounds changed')
        if getattr(self,'guard_active',False):
            props=dict(x.split('=',1) for x in run('systemctl','show',self.guard_unit,'--property=MainPID,ActiveState').splitlines())
            if props.get('ActiveState')!='active':raise PermissionError('independent lock guardian unavailable')
            owned=False
            for f in Path('/proc',props['MainPID'],'fdinfo').iterdir():
                if 'FLOCK' in f.read_text():
                    st=Path('/proc',props['MainPID'],'fd',f.name).stat()
                    if (st.st_dev,st.st_ino)==self.lock_inode:owned=True
            if not owned:raise PermissionError('guardian does not hold runtime exclusion')
        values=dict.fromkeys(FIELDS,False)
        values.update(independent_inventory_complete=True,temperature_c=heat,available_gib=4,load=os.getloadavg()[0],
            reserved_until=end,primary_pending=self.pending,throttled=throttled)
        # consultation_resources already measures actual >=3GiB/no swap; report actual.
        mem={x.split(':')[0]:int(x.split()[1]) for x in Path('/proc/meminfo').read_text().splitlines() if len(x.split())>=3}
        values['available_gib']=mem['MemAvailable']/1024**2
        values['swap_used']=mem.get('SwapFree',0)<mem.get('SwapTotal',0)
        return values

    def notice(self, slot, sequence, phase):
        if phase=='PREPARING' and not getattr(self,'guard_active',False):self.start_guard(slot)
        reply=rpc(self.p['display_socket'],dict(op='notice',slot=slot,sequence=sequence,phase=phase),expected_uid=self.p['display_uid'])
        self.last_ack=reply;return reply

    def notice_valid(self, slot, seq):
        reply=rpc(self.p['display_socket'],dict(op='status'),expected_uid=self.p['display_uid'])
        return reply.get('visible') is True and reply.get('slot')==slot and reply.get('sequence')==seq and reply.get('emergency') is False

    def start_guard(self, slot):
        atomic(Path(self.p['state_dir'])/'service-lease.json',json.dumps(dict(slot=slot,
            mono_end=self.reserved_mono,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())).encode())
        self.guard_unit='charlie-meditation-guard-'+slot+'.service'
        self.guard_socket=Path('/run/charlie-meditation')/('guard-'+slot+'.sock')
        repo=Path(__file__).resolve().parents[2]
        run('systemd-run','--unit='+self.guard_unit,'--collect','--property=Type=exec',
            '--property=WorkingDirectory='+str(repo),'--property=Restart=no','--property=KillMode=control-group',
            '/usr/bin/python3','-m','learning.native_meditation.guard',slot)
        deadline=time.monotonic()+2
        while not self.guard_socket.exists():
            if time.monotonic()>=deadline:raise PermissionError('guardian startup unavailable')
            time.sleep(.02)
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as channel:
            channel.settimeout(2);channel.connect(str(self.guard_socket))
            from .security import peer
            if peer(channel)[1]!=0:raise PermissionError('guardian peer must be root')
            channel.sendmsg([slot.encode()],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[self.fd]))])
            if channel.recv(64)!=b'HELD\n':raise PermissionError('guardian did not confirm exclusion')
        self.guard_active=True

    def finish_guard(self):
        if not getattr(self,'guard_active',False):return
        if self.guard_socket.exists():
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as channel:
                channel.settimeout(10);channel.connect(str(self.guard_socket))
                from .security import peer
                if peer(channel)[1]!=0:raise PermissionError('guardian peer changed')
                channel.sendall(b'FINISH')
                if channel.recv(64)!=b'EMPTY\n':raise PermissionError('guardian cleanup unconfirmed')
        else:
            # A missing socket is not cleanup evidence. Independently verify model.
            from .guard import stop_model
            stop_model()
        self.guard_active=False

    def prepare(self, slot, model, digest):
        if hasattr(self,'identity'):del self.identity
        self.slot=slot;self.preparing=True
        if self.pending:raise InterruptedError('urgent primary pending')
        seconds=int(slot['ends_at']-time.time()-15)
        if seconds<35:raise PermissionError('startup/request/cutoff do not fit')
        atomic(Path(self.p['state_dir'])/'service-lease.json',json.dumps(dict(
            mono_end=slot['mono_end'],slot=slot['id'],runtime_seconds=seconds,
            boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())).encode())
        repo=Path(__file__).resolve().parents[2]
        args=['systemd-run','--unit='+UNIT,'--collect','--property=Type=exec',
              '--property=RuntimeMaxSec='+str(seconds),'--property=TimeoutStopSec=5',
              '--property=KillMode=control-group','--property=SendSIGKILL=yes','--property=Restart=no',
              '--property=MemoryMax=2500M','--property=MemorySwapMax=0','--property=CPUQuota=100%',
              '--property=PrivateNetwork=yes','--property=PrivateDevices=yes','--property=NoNewPrivileges=yes','--property=ProtectHome=tmpfs',
              '--property=ProtectSystem=strict','--property=BindPaths='+self.p['runtime_lock'],
              '--property=ReadWritePaths='+self.p['service_home'],
              '--property=IPAddressDeny=any','--property=IPAddressAllow=localhost',
              '--property=Environment=OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_MODELS='+self.p['models']+' HOME='+self.p['service_home'],
              '/usr/bin/python3','-m','learning.native_meditation.runner']
        # WorkingDirectory points at immutable root-owned code, never Executive cwd.
        args.insert(3,'--property=WorkingDirectory='+str(repo))
        run(*args);self.running=True
        deadline=time.monotonic()+min(25,max(0,slot['ends_at']-time.time()-40))
        while True:
            try:self.identity=service_identity(system=True);break
            except (OSError,ValueError,subprocess.SubprocessError):
                if time.monotonic()>=deadline:raise PermissionError('finite service did not become ready')
                time.sleep(.1)
        if self.identity['cutoff_monotonic']>slot['mono_end']-.1:raise PermissionError('kernel cutoff exceeds reservation')
        self.inspect(slot['ends_at'])
        if self.pending:raise InterruptedError('revoked before prewarm')
        config=OllamaConfig(wall_seconds=max(.1,min(25,slot['ends_at']-time.time()-35)))
        if self.http(None,'/api/version',timeout=config.wall_seconds).get('version')!=self.p['server_version']:raise PermissionError('Ollama version')
        # Empty, zero-output prewarm only. Questions exclusively use OperationalProvider.
        self.http(dict(model=model,prompt='',stream=False,keep_alive=max(35,int(slot['ends_at']-time.time()-1)),
             options=dict(num_ctx=2048,num_predict=0,num_thread=1)),'/api/generate',timeout=config.wall_seconds)
        ready_model(self.http(None,'/api/ps',timeout=2),dict(model_digest=digest),now=time.time())
        doc=dict(schema=SCHEMA,issuer='root-meditation-v1',slot_id=slot['id'],operator_consent=True,
            native_prerequisites_verified=True,safe_idle_no_sensing_deadlines=True,exclusive_service=True,
            model=model,model_digest=digest,server_version=self.p['server_version'],
            service_invocation_id=self.identity['invocation_id'],boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            code_revision=self.p['code_revision'],qualification_path=self.p['qualification_path'],
            qualification_sha256=self.p['qualification_sha256'],issued_at=time.time(),expires_at=slot['ends_at'])
        if doc['expires_at']-doc['issued_at']<35:raise PermissionError('prewarm consumed admission budget')
        path=APPROVALS/(slot['id']+'.json');raw=json.dumps(doc,sort_keys=True).encode()
        atomic(path,raw,self.p['client_gid'])
        return dict(path=str(path),digest=hashlib.sha256(raw).hexdigest())

    def http(self, payload, path, *, timeout):
        result=subprocess.run([sys.executable,'-m','learning.native_meditation.ns_http',
            str(self.identity['pid']),self.identity['start_ticks'],path],
            input=json.dumps(dict(payload=payload,timeout=timeout),allow_nan=False),
            capture_output=True,text=True,check=True,timeout=timeout+1)
        if len(result.stdout.encode())>32768:raise ValueError('bounded native response')
        return json.loads(result.stdout)

    def question(self, prompt):
        from learning.question_selection import discover,context_for
        def progress():
            if self.pending or time.monotonic()>=self.slot['mono_end']-5 or not self.client_alive():
                raise InterruptedError('question validation revoked')
        from .security import protected_source
        for source in self.p['question_sources']:protected_source(source,self.p['client_uid'],self.p['client_gid'])
        report=discover(self.p['question_sources'],check=progress)
        if report['errors'] or report['truncated']:raise PermissionError('source reconciliation incomplete')
        match=next((q for q in report['candidates'] if q['eligible'] and context_for(q)['text']==prompt),None)
        if match is None:raise PermissionError('prompt is not an eligible authentic source question')
        return match['id']

    def latch(self, slot):
        atomic(Path(self.p['state_dir'])/('unknown-'+slot+'.json'),json.dumps(dict(slot=slot)).encode())

    def unloaded(self, approval_digest):
        if self.http(None,'/api/ps',timeout=2).get('models')!=[]:raise PermissionError('unload unconfirmed')
        from memory.evidence import EvidenceJournal
        journal=EvidenceJournal(self.p['answer_journal'],read_only=True)
        try:
            if not any(r.data['payload'].get('state')=='answer-durable'
                       and r.data['payload'].get('trust')=='unverified_hypothesis'
                       and r.data['payload'].get('result',{}).get('identity',{}).get('approval_digest')==approval_digest
                       for r in journal.category_records('event','generalized_question')):
                raise PermissionError('independent durable answer receipt not found')
        finally:journal.close()
        # Preserve the independent unknown marker; audited ledger retention is not
        # authority to delete history or automatically clear an uncertain request.

    def emergency(self):
        self.pending=True
        if self.running or self.preparing:
            # Never waits on the engine/prewarm lock. Only this dedicated unit.
            subprocess.run(['systemctl','kill','--kill-whom=all','--signal=SIGKILL',UNIT],
                           capture_output=True,timeout=2)

    def quiesce(self, slot):
        if self.running or self.preparing:
            subprocess.run(['systemctl','stop',UNIT],capture_output=True,timeout=7)
            props=dict(x.split('=',1) for x in run('systemctl','show',UNIT,'--property=MainPID,ActiveState,ControlGroup').splitlines())
            if props.get('MainPID')!='0' or props.get('ActiveState') not in ('inactive','failed'):
                raise PermissionError('model unit not quiescent')
            group_name=getattr(self,'identity',{}).get('cgroup') or props.get('ControlGroup') or '/system.slice/'+UNIT
            group=Path('/sys/fs/cgroup')/group_name.lstrip('/')
            if group.exists() and any(p.read_text().strip() for p in group.rglob('cgroup.procs')):
                raise PermissionError('model cgroup not empty')
            self.running=False;self.preparing=False
        if self.fd is None:
            fd=os.open(self._lock_path(),os.O_RDWR|os.O_NOFOLLOW)
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BaseException:os.close(fd);raise
            self.fd=fd

    def expire_notice(self, slot):
        # Cosmetic clearing must never postpone emergency primary work after
        # proven model cutoff. Native receipt qualifies independent 2s device TTL;
        # log pending TTL honestly, rather than claim verified clearing.
        self.notice_expires_by=slot['last_notice']+2.1

    def complete(self, slot):
        path=Path(self.p['state_dir'])/('unknown-'+slot['id']+'.json')
        if path.exists():os.rename(path,path.with_name('completed-'+slot['id']+'.json'))

    def primary_done(self):
        if not self.model_empty():raise PermissionError('model still active')
        path=self._lock_path();fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW)
        old=self.pending
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.lock_inode=(os.fstat(fd).st_dev,os.fstat(fd).st_ino)
            # First probe still reports the STOP latch; reset is permitted only
            # after every independent physical/unit/deadline check succeeds.
            self.pending=False
            try:
                self._clearing_primary=True
                snapshot=self.inspect(time.time()+40)
                safety=rpc(self.p['display_socket'],dict(op='resume'),expected_uid=self.p['display_uid'])
                if safety.get('clear') is not True:raise PermissionError('display owner not quiescent')
            except BaseException:self.pending=old;raise
            finally:self._clearing_primary=False
            return snapshot
        finally:os.close(fd)

    def model_empty(self):
        result=run('systemctl','show',UNIT,'--property=MainPID,ActiveState,ControlGroup')
        props=dict(x.split('=',1) for x in result.splitlines())
        group=Path('/sys/fs/cgroup')/(props.get('ControlGroup') or '/system.slice/'+UNIT).lstrip('/')
        return (props.get('MainPID')=='0' and props.get('ActiveState') in ('inactive','failed')
                and (not group.exists() or not any(p.read_text().strip() for p in group.rglob('cgroup.procs'))))

    def release(self):
        self.finish_guard()
        if self.running:raise PermissionError('cannot release while model may be alive')
        if self.fd is not None:os.close(self.fd);self.fd=None
        if self.pidfd is not None:os.close(self.pidfd);self.pidfd=None
