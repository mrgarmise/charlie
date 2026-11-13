"""Protected, owner-installed root broker. No installation/autostart on import."""
import argparse
import json
import os
from pathlib import Path
import signal
import socketserver
import threading
import time
from .security import POLICY, SOCKET, root_read, peer
from .engine import Scheduler
from .linux import LinuxDriver


class Broker:
    def __init__(self, engine):self.engine=engine;self.lock=threading.RLock()

    def handle(self, uid, pid, request):
        p=self.engine.driver.p
        op=request.get('op')
        if uid!=p['client_uid'] and not (op in ('cancel','primary','primary-done') and uid in (0,p.get('owner_uid',-1))):
            raise PermissionError('wrong Executive identity')
        if op in ('cancel','primary'):
            # Outside the engine lock: STOP/revocation cannot wait for prewarm HTTP.
            self.engine.driver.emergency()
            with self.lock:self.engine.finish('urgent primary/STOP')
            return dict(available=self.engine.active is None)
        if op=='http':
            with self.lock:
                e=self.engine;a=e.active
                if not a or request.get('slot')!=a['id']:raise PermissionError('unknown reservation')
                e.validate(request['digest'])
                path=request['path'];payload=request.get('payload')
                if path in ('/api/version','/api/ps') and payload is None:pass
                elif path=='/api/chat':
                    if not a['submitted'] or a.get('proxied'):raise PermissionError('one actual query per slot')
                    from learning.consultation import request_payload,OllamaConfig
                    prompt=payload['messages'][1]['content']
                    if payload!=request_payload(OllamaConfig(),prompt):raise PermissionError('fixed provider envelope required')
                    a['proxied']=True  # durable submitted-unknown already exists
                else:raise PermissionError('no model administration or arbitrary API')
            # Long model HTTP never holds the engine lock: validation and urgent
            # cancellation remain responsive in independent handler threads.
            if path=='/api/chat':
                question=e.driver.question(prompt)
                with self.lock:
                    e.validate(request['digest'])
                    if e.db.execute("SELECT 1 FROM events WHERE op='question-admitted' AND json_extract(data,'$.question_id')=?",(question,)).fetchone():
                        raise PermissionError('question already consulted; no automatic resend')
                    e.event(a['id'],'question-admitted',question_id=question)
            return e.driver.http(payload,path,timeout=30 if path=='/api/chat' else 2)
        with self.lock:
            e=self.engine
            if op=='primary-done':
                if e.active:raise PermissionError('reservation still active')
                result=e.driver.primary_done()
                e.event('primary-control','available',independently_quiet=True)
                return result
            if op=='status':return dict(available=e.active is None and e.driver.model_empty(),recovery_blocked=e.recovery_blocked)
            if op=='configuration':
                p=e.policy()
                return {k:p[k] for k in ('question_sources','answer_journal','max_seconds','daily_limit','cooldown')}
            if op=='reserve':return e.reserve(request.get('commission'),request.get('seconds'),pid)
            a=e.active
            if op=='finish' and a is None:
                row=e.db.execute('SELECT op FROM events WHERE slot=? ORDER BY n DESC LIMIT 1',(request.get('slot'),)).fetchone()
                if row and row[0] in ('available','uncertain-completion'):return True
            if not a or request.get('slot')!=a['id']:raise PermissionError('unknown reservation')
            if op=='inspect':return e.check()
            if op=='phase':
                if request['phase'] not in ('MEDITATING','THINKING'):raise ValueError('caller cannot clear reserved notice')
                e.notice(request['phase']);return e.check()
            if op=='budget':e.budget(request['commission'],request['daily'],request['cooldown']);return True
            if op=='prepare':return e.prepare(request['model'],request['digest'],request['ends_at'])
            if op=='validate':return e.validate(request['digest'])
            if op=='submit':e.mark_submission(request['digest']);return True
            if op=='retained':e.retained(request['digest']);return True
            if op=='finish':e.finish();return True
            raise ValueError('unknown scheduler operation')

    def monitor(self, stop):
        while not stop.wait(.1):
            a=self.engine.active
            if not a or a.get('closing') or a.get('initializing'):continue
            try:
                # Independent of the prewarm/dispatch lock. Device TTL refresh
                # and owner/resource revocation continue through long startup.
                self.engine.check()
                if self.engine.active is a and not a.get('closing') and self.engine.mono()-a['last_notice']>=.75:
                    self.engine.notice(a['phase'])
            except Exception:
                if self.engine.active is not a or a.get('closing'):continue
                try:self.engine.driver.emergency()
                except Exception:pass  # absolute kernel cutoff still holds flock
                if self.lock.acquire(blocking=False):
                    try:self.engine.finish('independent guard revoked')
                    except Exception:pass
                    finally:self.lock.release()


def serve():
    if os.geteuid()!=0:raise PermissionError('separate root-owned native issuer required')
    p=json.loads(root_read(POLICY));driver=LinuxDriver()
    engine=Scheduler(driver,Path(p['state_dir'])/'scheduler.sqlite3');broker=Broker(engine)
    # Parent directories are installed root-owned, never made by an Executive.
    st=SOCKET.parent.stat()
    if st.st_uid!=0 or st.st_mode&0o022:raise PermissionError('protected broker directory required')
    if SOCKET.exists():raise PermissionError('stale socket requires independent recovery')
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.request.settimeout(2)
            try:
                pid,uid,gid=peer(self.request)
                raw=self.rfile.readline(16385)
                if not raw.endswith(b'\n') or len(raw)>16384:raise ValueError('bounded request required')
                result=broker.handle(uid,pid,json.loads(raw))
                reply=dict(ok=True,result=result)
            except Exception as exc:reply=dict(ok=False,error=type(exc).__name__)
            self.wfile.write(json.dumps(reply,allow_nan=False,ensure_ascii=False).encode()+b'\n')
    class Server(socketserver.ThreadingUnixStreamServer):
        daemon_threads=True
        def process_request(self, request, address):
            if not self.slots.acquire(blocking=False):request.close();return
            super().process_request(request,address)
        def process_request_thread(self,request,address):
            try:super().process_request_thread(request,address)
            finally:self.slots.release()
    old=os.umask(0o007)
    try:server=Server(str(SOCKET),Handler)
    finally:os.umask(old)
    server.slots=threading.BoundedSemaphore(8)
    os.chown(SOCKET,0,p['client_gid']);os.chmod(SOCKET,0o660)
    stop=threading.Event();thread=threading.Thread(target=broker.monitor,args=(stop,),daemon=True);thread.start()
    def shutdown(*args):
        driver.emergency();stop.set()
        threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,shutdown);signal.signal(signal.SIGINT,shutdown)
    try:server.serve_forever(poll_interval=.1)
    finally:
        stop.set();driver.emergency()
        with broker.lock:engine.finish('issuer shutdown')
        server.server_close();SOCKET.unlink(missing_ok=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['check-config','serve'])
    a=p.parse_args()
    if a.action=='check-config':LinuxDriver().policy();print('protected native policy verified; no service started')
    else:serve()

if __name__=='__main__':main()
