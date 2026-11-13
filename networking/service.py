"""Existing-dashboard service layer for locally prepared, one-shot operations.

Secrets enter through local private enrollment/operator code, never a dashboard
response. Dashboard may execute only an already authorized intent. No startup,
watcher or browser monitoring credential can authorize adapter switching.
"""
import secrets
import threading

from networking.provisioning import Authorization, NetworkCredentials


class NetworkService:
    def __init__(self, manager):
        self.manager = manager
        self.lock = threading.Lock()
        self.pending = None
        self.worker = None

    def arm(self, credentials, authorization):
        if not isinstance(credentials, NetworkCredentials) or not isinstance(authorization, Authorization):
            raise ValueError('local credentials and authorization required')
        with self.lock:
            if self.worker and self.worker.is_alive(): raise RuntimeError('network operation active')
            if self.pending is not None: raise RuntimeError('intent already armed')
            handle = secrets.token_urlsafe(32)
            self.pending = (handle, credentials, authorization)
            return handle

    def status(self):
        # Pending data, Wi-Fi SSIDs, tokens, certificates and exceptions stay private.
        return self.manager.status()

    def execute(self, request):
        with self.lock:
            if set(request) != {'operation'} or not isinstance(request['operation'], str):
                raise ValueError('one operation handle required')
            if self.pending is None or not secrets.compare_digest(request['operation'], self.pending[0]):
                raise PermissionError('locally authorized operation required')
            _, credentials, authorization = self.pending
            self.pending = None
            if self.manager.clock() >= authorization.expires:
                raise PermissionError('operation expired')
            def run():
                try: self.manager.provision(credentials, authorization)
                except Exception: pass  # Sanitized manager state is authoritative; no secret logging.
            self.worker = threading.Thread(target=run, name='elegoo-provision', daemon=True)
            self.worker.start()
            return {'accepted': True}
