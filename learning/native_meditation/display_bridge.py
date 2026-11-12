"""Attach display-only RPC to the EXISTING serial owner, never open serial here."""
import json
import os
import socketserver
import threading
from .security import peer


class DisplayBridge:
    def __init__(self, controller):
        self.controller=controller
        self.cancel=threading.Event();controller.meditation_cancel=self.cancel

    def dispatch(self, uid, data):
        if uid!=0:raise PermissionError('only independent root scheduler may display a reservation')
        op=data.get('op')
        if op in ('safety','status','resume'):
            answer=self.controller._exchange('MOTION_STATUS','MOTION_STATUS ',timeout=.15)
            motion=json.loads(answer.split(' ',1)[1]) if answer else {}
            calibration=motion.get('calibration',{})
            if (motion.get('schema')!='charlie-motion-authority-v1'
                    or motion.get('session')!=self.controller.link_session
                    or any(motion.get(k) is not False for k in ('armed','moving','pwm_active'))
                    or motion.get('owner') is not None or calibration.get('automated') is not False
                    or calibration.get('state') not in ('IDLE','DISABLED','CLOSED','ABORTED')):
                raise PermissionError('unknown or active physical authority')
            if op=='resume':
                self.cancel.clear()
                return dict(clear=True,emergency=False)
            if op=='safety':return dict(clear=True,emergency=self.cancel.is_set())
            status=self.controller.meditation_notice_status()
            if status is None:raise PermissionError('physical display state unknown')
            return dict(status,emergency=self.cancel.is_set())
        if op!='notice':raise ValueError('display-only RPC')
        phase=data['phase']
        if phase!='CLEAR' and self.cancel.is_set():raise InterruptedError('STOP latch requires independent restart')
        result=self.controller.meditation_notice(data['slot'],data['sequence'],0 if phase=='CLEAR' else 2000,phase)
        if result is None:raise PermissionError('no matching display acknowledgement')
        return result

    def server(self, path):
        # Composition root supplies a separately installed protected socket path.
        # No RP2040Controller(), connect(), reset, heartbeat or competing lease here.
        bridge=self
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.request.settimeout(.5)
                try:
                    raw=self.rfile.readline(1025)
                    if len(raw)>1024 or not raw.endswith(b'\n'):raise ValueError('bounded display request')
                    result=bridge.dispatch(peer(self.request)[1],json.loads(raw))
                    reply=dict(ok=True,result=result)
                except Exception as exc:reply=dict(ok=False,error=type(exc).__name__)
                self.wfile.write(json.dumps(reply).encode()+b'\n')
        # Serial owner invokes server.serve_forever() on its existing bounded IO
        # thread; broker requests serialize through controller._exchange lock.
        old=os.umask(0o077)
        try:return socketserver.UnixStreamServer(str(path),Handler)
        finally:os.umask(old)
