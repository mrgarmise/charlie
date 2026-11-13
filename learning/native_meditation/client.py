"""Unprivileged backend implementing PR #36's finite lease interface."""
from contextlib import contextmanager
from .security import SOCKET, rpc


class NativeBackend:
    def call(self, op, **fields):return rpc(SOCKET,dict(op=op,**fields),timeout=40 if op=='prepare' else 12)

    @contextmanager
    def exclusive(self, commission_id, seconds):
        result=self.call('reserve',commission=commission_id,seconds=seconds)
        lease=NativeLease(self,result['id'],result['ends_at'])
        try:yield lease
        finally:lease.finish(ends_at=lease.ends_at)

    def status(self):return self.call('status')
    def emergency(self):return self.call('cancel')
    def primary(self):return self.call('primary')
    def primary_done(self):return self.call('primary-done')


class NativeLease:
    def __init__(self, backend, identifier, ends_at):
        self.backend=backend;self.id=identifier;self.ends_at=ends_at;self.finished=False
    def inspect(self):return self.backend.call('inspect',slot=self.id)
    def reserve_budget(self, commission_id, max_daily, cooldown):
        return self.backend.call('budget',slot=self.id,commission=commission_id,daily=max_daily,cooldown=cooldown)
    def prepare(self, *, model, digest, ends_at):
        return self.backend.call('prepare',slot=self.id,model=model,digest=digest,ends_at=ends_at)
    def phase(self, phase):return self.backend.call('phase',slot=self.id,phase=phase)
    def finish(self, *, ends_at):
        if self.finished:return
        self.backend.call('finish',slot=self.id);self.finished=True


def main():
    import argparse,json
    p=argparse.ArgumentParser(description='Independent native status or urgent cancellation; never authorizes a slot')
    p.add_argument('action',choices=['status','cancel','primary','primary-done'])
    a=p.parse_args();print(json.dumps(NativeBackend().call(a.action),indent=2))

if __name__=='__main__':main()
