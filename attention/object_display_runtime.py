"""Normal-app display attachment and a no-device serialized event diagnostic."""
from collections import deque
import json
from pathlib import Path
import threading
from attention.object_labels import ObjectLabels
from rp2040.object_label import capabilities


class DryRunDisplay:
    """Exercise real host serialization with fake serial replies, never open USB."""
    def __init__(self):
        from hardware.rp2040_controller import RP2040Controller
        self.commands=deque((),256)
        parent=self
        class UART:
            timeout=.1
            def __init__(self):self.lines=[]
            def write(self,raw):
                line=raw.decode('ascii').rstrip('\n')
                parent.commands.append(line)
                if line=='DISPLAY_CAPS':answer='DISPLAY_CAPS '+json.dumps(capabilities())
                elif line.startswith('OBJECT_LABEL '):answer='OK OBJECT_LABEL'
                elif line=='OBJECT_CLEAR':answer='OK OBJECT_CLEAR'
                else:raise AssertionError('display diagnostic cannot issue other commands')
                self.lines=[(answer+'\n').encode()]
            def readline(self):return self.lines.pop(0) if self.lines else b''
            def close(self):pass
        self.host=RP2040Controller.__new__(RP2040Controller)
        self.host.connected=True;self.host.link_session='display-dry-run'
        self.host.serial=UART();self.host.lock=threading.Lock();self.host.running=False
        self.host.motion_owner=None;self.host.motion_epoch=None;self.host.last_tx=0

    @property
    def link_session(self):return self.host.link_session
    def show_object_label(self,*args):return self.host.show_object_label(*args)
    def clear_object_label(self):return self.host.clear_object_label()
    def close(self):self.host.close()


def attach(mode,*,clock,body=None,port='/dev/ttyACM0'):
    if mode=='off':return None,None
    owned=None
    if mode=='dry-run':body=owned=DryRunDisplay()
    elif mode=='rp2040':
        if body is None:
            # Explicit opt-in operator runtime only; never used in dry-run/tests.
            from hardware.rp2040_controller import RP2040Controller
            body=owned=RP2040Controller(port=port)
    else:raise ValueError('unknown display mode')
    return ObjectLabels(body,clock=clock),owned


def replay(path,*,publish=None):
    from attention.manager import AttentionManager
    from stimulus.bus import StimulusBus
    path=Path(path)
    if path.stat().st_size>2*1024*1024:raise ValueError('display replay exceeds 2MiB')
    rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not 1<=len(rows)<=10000:raise ValueError('bounded display replay required')
    now=[0.];link=DryRunDisplay();labels=ObjectLabels(link,clock=lambda:now[0])
    bus=StimulusBus();attention=AttentionManager(bus,mobile_enabled=False,object_labels=labels)
    trace=[];seen=0
    if publish is None:publish=lambda row:print(json.dumps(row),flush=True)
    try:
        for packet in rows:
            at=packet.get('at')
            if type(at) not in (int,float) or at<now[0]:raise ValueError('ordered local replay timestamp required')
            now[0]=at
            if packet.get('event')=='fault':bus.emit('object_observation_fault',packet.get('source'))
            else:bus.emit('object_observation',packet)
            attention.update(None)
            commands=list(link.commands)
            row=dict(at=at,selected=labels.current,outgoing=commands[seen:],mode='no-device dry-run')
            seen=len(commands);trace.append(row);publish(row)
        now[0]+=labels.max_age+.01;attention.update(None)
        publish(dict(outgoing=list(link.commands)[seen:],mode='no-device dry-run',expired=True))
        return trace,list(link.commands)
    finally:
        attention.close();link.close()
