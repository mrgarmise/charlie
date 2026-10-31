"""Opt-in HTTP adapter inside Charlie; never a second robot-control process.

Loopback + SSH forwarding by default. Exact Origin/Host, bearer authentication,
boot-scoped single-use challenges, bounded bodies and a fixed capability dispatch.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit
from learning.capabilities import default_registry
from learning.demonstration import ABILITY

DEFAULT_ORIGIN = 'https://charlie-project-dashboard.garmiseprojects.chatgpt.site'


def start_dashboard(service, token, *, port=8768, origin=DEFAULT_ORIGIN, mobile=None, drive_token=None):
    if not isinstance(token,str) or len(token)<32 or any(c.isspace() for c in token):
        raise ValueError('dashboard token must have at least 32 non-whitespace characters')
    if drive_token is not None and (len(drive_token)<32 or any(c.isspace() for c in drive_token) or drive_token==token):
        raise ValueError('separate strong drive credential required')
    parsed=urlsplit(origin)
    if parsed.scheme!='https' or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('exact HTTPS dashboard origin required')
    registry=default_registry()
    class Server(ThreadingHTTPServer):
        daemon_threads=True
        slots=threading.BoundedSemaphore(16)
        def process_request(self, request, address):
            if not self.slots.acquire(blocking=False):
                self.shutdown_request(request);return
            try:super().process_request(request,address)
            except BaseException:
                self.slots.release();raise
        def process_request_thread(self, request, address):
            try:super().process_request_thread(request,address)
            finally:self.slots.release()
        def get_request(self):
            sock, addr=super().get_request()
            sock.settimeout(2)
            return sock, addr
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def permitted(self):
            host=self.headers.get('Host')
            return host in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}') and self.headers.get('Origin') in (
                None,origin,f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}')
        def reply(self,code,body):
            raw=json.dumps(body,allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            if self.headers.get('Origin')==origin:
                self.send_header('Access-Control-Allow-Origin',origin)
                self.send_header('Vary','Origin')
            self.end_headers();self.wfile.write(raw)
        def authorized(self, drive=False):
            if not self.permitted():self.reply(403,{'error':'origin or host denied'});return False
            supplied=self.headers.get('Authorization','')
            allowed = [drive_token] if drive else [token, drive_token]
            if not any(value and hmac.compare_digest(supplied.encode(),('Bearer '+value).encode()) for value in allowed):
                self.reply(401,{'error':'operator authentication required'});return False
            return True
        def do_OPTIONS(self):
            if not self.permitted():self.reply(403,{'error':'origin or host denied'});return
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin',self.headers.get('Origin',origin))
            self.send_header('Access-Control-Allow-Methods','GET, POST')
            self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type')
            self.send_header('Access-Control-Allow-Private-Network','true')
            self.send_header('Vary','Origin')
            self.end_headers()
        def do_GET(self):
            if self.path in ('/','/abilities.js','/mobile','/mobile.js','/mobile.css') and self.permitted():
                name={'/':'abilities.html','/abilities.js':'abilities.js','/mobile':'mobile.html','/mobile.js':'mobile.js','/mobile.css':'mobile.css'}[self.path]
                raw=Path(__file__).with_name(name).read_bytes()
                self.send_response(200)
                self.send_header('Content-Type','text/html; charset=utf-8' if self.path in ('/','/mobile') else 'text/css' if self.path.endswith('.css') else 'text/javascript; charset=utf-8')
                self.send_header('Content-Length',str(len(raw)))
                self.send_header('Cache-Control','no-store')
                self.send_header('Referrer-Policy','no-referrer')
                self.send_header('X-Frame-Options','DENY')
                self.end_headers();self.wfile.write(raw);return
            if not self.authorized():return
            if mobile is not None and self.path=='/api/mobile':
                self.reply(200,mobile.status());return
            if mobile is not None and self.path=='/api/mobile/frame':
                try:
                    raw,metadata=mobile.image()
                    self.send_response(200)
                    self.send_header('Content-Type','image/png')
                    self.send_header('Content-Length',str(len(raw)))
                    self.send_header('Cache-Control','no-store')
                    self.send_header('X-Content-Type-Options','nosniff')
                    self.send_header('X-Charlie-Frame',json.dumps(metadata,allow_nan=False))
                    if self.headers.get('Origin')==origin:
                        self.send_header('Access-Control-Allow-Origin',origin)
                        self.send_header('Access-Control-Expose-Headers','X-Charlie-Frame')
                        self.send_header('Vary','Origin')
                    self.end_headers();self.wfile.write(raw)
                except TimeoutError as exc:self.reply(503,{'error':str(exc)})
                return
            if self.path!='/api/abilities' or service is None:self.reply(404,{'error':'not found'});return
            self.reply(200,service.status())
        def do_POST(self):
            is_mobile=self.path=='/api/mobile' and mobile is not None
            if not self.authorized(drive=is_mobile):return
            if not is_mobile and (self.path!='/api/abilities' or service is None):self.reply(404,{'error':'not found'});return
            if self.headers.get('Content-Type')!='application/json' or self.headers.get('Transfer-Encoding'):
                self.reply(400,{'error':'bounded JSON body required'});return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=4096:raise ValueError('request exceeds bound')
                raw=self.rfile.read(size)
                if len(raw)!=size:raise ValueError('incomplete body')
                request=json.loads(raw)
                if not isinstance(request,dict):raise ValueError('JSON object required')
                if is_mobile:
                    if request.get('action')=='acquire':
                        if request.get('boot')!=mobile.boot:raise ValueError('current service boot required')
                        result=mobile.acquire()
                    else:result=mobile.control(request)
                    self.reply(200,result);return
                result=registry.invoke(ABILITY,resources={'operator-request','pi-primary','object-model','object-label-display'},
                    authorized={ABILITY},service=service,request=request)
                self.reply(202,result)
            except PermissionError as exc:self.reply(403,{'error':str(exc)[:256]})
            except (TimeoutError,OSError) as exc:self.reply(503,{'error':str(exc)[:256]})
            except (ValueError,TypeError,KeyError,OverflowError) as exc:self.reply(400,{'error':str(exc)[:256]})
    server=Server(('127.0.0.1',port),Handler)
    if mobile is not None:mobile.start()
    worker=threading.Thread(target=server.serve_forever,name='charlie-dashboard-http',daemon=True)
    worker.start()
    class Handle:
        address=server.server_address
        def close(self):
            try:
                if mobile is not None:mobile.close()
            finally:server.shutdown();server.server_close();worker.join(timeout=3)
    return Handle()


def attach_dashboard(args, resources, frame_bus, attention, lifecycle, *, factory=None):
    if not args.abilities_dashboard:return None
    import os
    from learning.demonstration import Demonstration, recognition_factory
    service=Demonstration(attention,factory or recognition_factory(args,resources,frame_bus,attention),args.learning_state)
    lifecycle.callback(service.close)
    mobile=attach_mobile(args,frame_bus,lifecycle,start_http=False)
    server=start_dashboard(service,os.environ.get('CHARLIE_OPERATOR_TOKEN',''),
                           port=args.abilities_port,origin=args.abilities_origin,mobile=mobile,drive_token=os.environ.get('CHARLIE_DRIVE_TOKEN'))
    lifecycle.callback(server.close)
    print(f'Abilities listening on http://127.0.0.1:{server.address[1]} (authenticated, motion not requested)',flush=True)
    return service


def attach_mobile(args, frame_bus, lifecycle, *, executor=None, start_http=True):
    if not getattr(args,'mobile_dashboard',False):return None
    import os
    from ui.mobile import MobileConsole
    if executor is None:
        from motion.elegoo_executor import application_executor
        try:executor=application_executor()
        except RuntimeError:pass
    mobile=MobileConsole(frame_bus,executor)
    lifecycle.callback(mobile.close)
    if start_http:
        server=start_dashboard(None,os.environ.get('CHARLIE_MONITOR_TOKEN',''),
            port=args.abilities_port,origin=args.abilities_origin,mobile=mobile,
            drive_token=os.environ.get('CHARLIE_DRIVE_TOKEN'))
        lifecycle.callback(server.close)
        print(f'Mobile Body: http://127.0.0.1:{server.address[1]}/mobile (per-command qualification required)',flush=True)
    return mobile
