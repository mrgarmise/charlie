"""Loopback-only HTTP application; CSRF/session/Host guards and bounded payloads."""
import argparse
import fcntl
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import secrets
import signal
from urllib.parse import urlsplit,parse_qs
from .store import Lab,canonical
from .jobs import Jobs,preflight
from .sources import add_source,hydrate
from .datasets import quality,freeze,export_zip,held_out

STATIC=Path(__file__).with_name('static')


def application(lab,jobs,token,port):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup();self.connection.settimeout(20)
        def log_message(self,*args):pass # Do not log source paths/tokens.
        def reply(self,status,value,mime='application/json'):
            raw=canonical(value).encode() if mime=='application/json' else (value.encode() if isinstance(value,str) else value)
            self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)))
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store')
            self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' blob:; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            if self.path=='/':self.send_header('Set-Cookie',f'visionlab={token}; HttpOnly; SameSite=Strict; Path=/')
            self.end_headers();self.wfile.write(raw)
        def file(self,path,mime):
            size=path.stat().st_size;self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(size));self.send_header('Content-Disposition','attachment; filename="'+path.name+'"');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
            with path.open('rb') as stream:
                for block in iter(lambda:stream.read(64*1024),b''):self.wfile.write(block)
        def guard(self,post=False):
            host=self.headers.get('Host','')
            allowed={f'localhost:{port}',f'127.0.0.1:{port}'}
            if host not in allowed:raise PermissionError('Loopback Host required')
            origin=self.headers.get('Origin')
            if origin and origin not in {f'http://{x}' for x in allowed}:raise PermissionError('Same origin required')
            if urlsplit(self.path).path in ('/','/app.js','/editor.js','/style.css'):return
            header=self.headers.get('X-Vision-Token','')
            cookies={part.strip() for part in self.headers.get('Cookie','').split(';')}
            if post and not secrets.compare_digest(header,token):raise PermissionError('CSRF token required')
            if not secrets.compare_digest(header,token) and f'visionlab={token}' not in cookies:raise PermissionError('Local session required')
        def do_GET(self):
            try:
                self.guard();u=urlsplit(self.path);q=parse_qs(u.query);path=u.path
                if path=='/':return self.reply(200,(STATIC/'index.html').read_text().replace('__TOKEN__',token),'text/html; charset=utf-8')
                if path in ('/app.js','/editor.js','/style.css'):
                    return self.reply(200,(STATIC/path[1:]).read_bytes(),'text/css' if path.endswith('css') else 'text/javascript')
                if path=='/api/state':
                    frames=lab.frames();counts={}
                    for f in frames:
                        f['annotation']=lab.annotation(f['id']);counts.setdefault(f.get('pixel_sha'),[]).append(f['id'])
                        f['held_out']=held_out(lab,f['pixel_sha']) if f.get('pixel_sha') else False
                    return self.reply(200,dict(classes=lab.get('settings','classes'),sources=lab.items('sources'),indexes=lab.items('indexes'),frames=frames,datasets=lab.items('datasets'),models=lab.items('models'),jobs=lab.items('jobs'),evaluations=lab.items('evaluations'),suggestions=lab.items('suggestions'),duplicates=[v for k,v in counts.items() if k and len(v)>1]))
                if path=='/api/preflight':return self.reply(200,preflight())
                if path=='/api/annotation':return self.reply(200,dict(current=lab.annotation(q['frame'][0]),history=lab.history(q['frame'][0])))
                if path in ('/image','/thumb'):
                    f=lab.frame(q['frame'][0]);thumb=lab.root/'thumbs'/(f['id']+'.jpg')
                    if path=='/thumb' and thumb.exists():return self.reply(200,thumb.read_bytes(),'image/jpeg')
                    f=hydrate(lab,q['frame'][0]);p=lab.root/'pixels'/(f['pixel_sha']+'.png') if path=='/image' else lab.root/'thumbs'/(f['id']+'.jpg')
                    return self.reply(200,p.read_bytes(),'image/png' if path=='/image' else 'image/jpeg')
                if path=='/api/log':
                    jid=q['job'][0];lab.get('jobs',jid);p=lab.root/'jobs'/jid/'log.txt'
                    if not p.exists():return self.reply(200,dict(text='Not started'))
                    with p.open('rb') as s:s.seek(max(0,p.stat().st_size-50000));text=s.read().decode(errors='replace')
                    return self.reply(200,dict(text=text))
                if path=='/download/dataset':return self.file(export_zip(lab,q['id'][0]),'application/zip')
                if path=='/download/model':
                    mid=q['id'][0];lab.get('models',mid);lab.get('exports',mid)
                    return self.file(lab.root/'models'/mid/'deployment.zip','application/zip')
                if path=='/evaluation-image':
                    eid=q['evaluation'][0];e=lab.get('evaluations',eid);fid=q['frame'][0]
                    if not any(r['frame_id']==fid for r in e['candidate']['error_examples']):raise KeyError('Not an evaluation error example')
                    return self.reply(200,(lab.root/'evaluations'/eid/(fid+'.jpg')).read_bytes(),'image/jpeg')
                raise KeyError('Unknown route')
            except (PermissionError,ValueError,KeyError,OSError) as e:self.reply(403 if isinstance(e,PermissionError) else 400,dict(error=str(e)))
        def do_POST(self):
            try:
                self.guard(post=True)
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=1_000_000:raise ValueError('Bounded JSON request required')
                d=json.loads(self.rfile.read(size));path=urlsplit(self.path).path
                if not isinstance(d,dict):raise ValueError('JSON object required')
                if path=='/api/sources':result=add_source(lab,d)
                elif path=='/api/classes':lab.set_classes(d['classes']);result=dict(saved=True)
                elif path=='/api/index':result=jobs.submit('index',dict(source_id=d['source_id']))
                elif path=='/api/annotation':result=lab.annotate(d['frame_id'],d)
                elif path=='/api/quality':result=quality(lab,d['frames'])
                elif path=='/api/datasets':result=freeze(lab,d['name'],d['frames'],d.get('assignments'),d.get('seed',7))
                elif path=='/api/jobs':result=jobs.submit(d['kind'],d['parameters'])
                elif path=='/api/cancel':result=jobs.cancel(d['job_id'])
                elif path=='/api/restart':result=jobs.restart(d['job_id'])
                else:raise KeyError('Unknown route')
                self.reply(200,result)
            except (PermissionError,ValueError,KeyError,OSError,TypeError) as e:self.reply(403 if isinstance(e,PermissionError) else 400,dict(error=str(e)))
    return Handler


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--state',type=Path,default=Path.home()/'.local/share/charlie/vision-lab');ap.add_argument('--port',type=int,default=8768)
    args=ap.parse_args(argv)
    if not 1024<=args.port<=65535:ap.error('Unprivileged port required')
    args.state=args.state.expanduser().resolve()
    if any((p/'learning-evidence.sqlite3').exists() for p in [args.state,*args.state.parents]):ap.error('Lab state must not be inside the original learning notebook')
    args.state.mkdir(parents=True,exist_ok=True)
    with (args.state/'application.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        lab=Lab(args.state);jobs=Jobs(lab);token=secrets.token_hex(32)
        server=ThreadingHTTPServer(('127.0.0.1',args.port),application(lab,jobs,token,args.port));server.daemon_threads=True
        def stop(*unused):raise KeyboardInterrupt()
        previous=signal.signal(signal.SIGTERM,stop)
        print(f'Charlie Vision Lab: http://127.0.0.1:{args.port} · state {lab.root} · no hardware/action authority',flush=True)
        try:server.serve_forever(poll_interval=.2)
        except KeyboardInterrupt:pass
        finally:jobs.close();server.server_close();signal.signal(signal.SIGTERM,previous)

if __name__=='__main__':main()
