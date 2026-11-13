"""Overlap ordinary frame preparation with one existing bounded controller pulse.

Only transport runs on this worker. Main-thread preparation must not journal or
mutate observation/agency state. Causal experiments use their pinned path.
"""
import socket
import threading


def execute_with_lookahead(controller,action,duration,stream,after,prepare,*,deadline=None):
    cancel=threading.Event();done=threading.Event();errors=[];prepared=None
    def execute():
        try:controller.execute(action,duration,cancel_event=cancel,deadline=deadline)
        except BaseException as exc:errors.append(exc)
        finally:done.set()
    worker=threading.Thread(target=execute,name='charlie-bounded-controller',daemon=False)
    worker.start()
    try:
        while not done.is_set():
            if stream.failed.is_set():raise RuntimeError('camera failed during controller pulse')
            try:packet=stream.latest(after=after,timeout=.02)
            except TimeoutError:continue
            after=packet.sequence
            prepared=prepare(packet)
        if errors:raise errors[0]
        return prepared
    except BaseException:
        cancel.set()
        raise
    finally:
        worker.join(2.5)
        if worker.is_alive():
            cancel.set()
            # Interrupt a blocked wire read; do not let another control worker
            # start while the old one still owns the stream.
            connection=getattr(controller,'connection',None)
            if connection is not None:
                try:connection.shutdown(socket.SHUT_RDWR)
                except OSError:pass
            worker.join(.5)
        if worker.is_alive():raise RuntimeError('controller worker did not stop; session invalid')
        if cancel.is_set() or errors:controller.close()
