"""Stabilized observational display selection. No inference or motion authority."""
import math
import time
from rp2040.object_label import normalize_label


class ObjectLabels:
    def __init__(self,transport,*,clock=time.monotonic,min_confidence=.65,confirmations=3,
                 confirmation_seconds=.2,min_dwell=2.,max_age=1.,refresh_seconds=2.,ttl_ms=4500,step_ms=100):
        if (type(confirmations) is not int or confirmations<1 or not 0<=min_confidence<=1
                or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in
                       (min_dwell,max_age,refresh_seconds)) or not 0<=confirmation_seconds<=2):
            raise ValueError('invalid object display policy')
        from rp2040.object_label import label_request
        label_request('OBJECT',ttl_ms,step_ms)
        if refresh_seconds>=ttl_ms/1000:raise ValueError('refresh must precede firmware expiry')
        self.transport,self.clock=transport,clock
        self.min_confidence,self.confirmations=min_confidence,confirmations
        self.confirmation_seconds,self.min_dwell,self.max_age=confirmation_seconds,min_dwell,max_age
        self.refresh_seconds,self.ttl_ms,self.step_ms=refresh_seconds,ttl_ms,step_ms
        self.candidate=None;self.hits=0;self.candidate_since=None
        self.current=None;self.current_since=None;self.last_seen=None;self.last_tx=None
        self.pending=None;self.suppressed=False;self.times={};self.generation=getattr(transport,'link_session',None)
        self.last_attempt=None
        self.stats=dict(observations=0,shown=0,cleared=0,rejected=0)

    def observe(self,packet,attention=None):
        now=self.clock();source=packet.get('source');at=packet.get('at');fid=packet.get('frame_id')
        if (packet.get('schema')!='charlie.object-observation.v1' or packet.get('clock_domain')!='pi-monotonic'
                or not isinstance(source,str) or not source or not isinstance(fid,str) or not fid
                or type(at) not in (int,float) or not math.isfinite(at) or not 0<=now-at<=self.max_age):
            self.stats['rejected']+=1
            self.invalidate(source)
            return
        if source in self.times and (at<=self.times[source][0] or fid==self.times[source][1]):return
        if len(self.times)>=16 and source not in self.times:self.times.pop(next(iter(self.times)))
        self.times[source]=(at,fid);self.stats['observations']+=1
        attention=attention or packet.get('attention_target')
        if attention and attention.get('source')!=source:return
        rows=[]
        for row in packet.get('objects',[])[:128]:
            label=row.get('label');score=row.get('confidence');area=row.get('prominence',0)
            if (not isinstance(label,str) or not 1<=len(label)<=128 or type(score) not in (int,float)
                    or not math.isfinite(score) or not self.min_confidence<=score<=1
                    or type(area) not in (int,float) or not math.isfinite(area) or not 0<=area<=1):continue
            if attention and str(row.get('id'))!=str(attention.get('id')):continue
            rows.append(row)
        chosen=min(rows,key=lambda r:(-r['confidence'],-r.get('prominence',0),r['label'],str(r.get('id'))),default=None)
        if chosen is None:
            self.candidate=None;self.hits=0;self.pending=None
            return
        key=(source,normalize_label(chosen['label']))
        if key==self.current:self.last_seen=at
        if key!=self.candidate:
            self.candidate=key;self.hits=1;self.candidate_since=at;self.pending=None
        else:self.hits=min(self.confirmations,self.hits+1)
        if self.hits>=self.confirmations and at-self.candidate_since>=self.confirmation_seconds:
            self.pending=(key,at)

    def invalidate(self,source=None):
        if source is None or (self.candidate and source==self.candidate[0]):
            self.candidate=None;self.pending=None;self.hits=0
        if source is None or (self.current and source==self.current[0]):self.last_seen=None

    def tick(self):
        now=self.clock()
        generation=getattr(self.transport,'link_session',None)
        if generation!=self.generation:
            self.generation=generation;self.current=None;self.last_seen=None;self.last_tx=None
            self.candidate=None;self.pending=None;self.hits=0;self.last_attempt=None
        if self.current and (self.suppressed or self.last_seen is None or now-self.last_seen>self.max_age):
            if self.transport.clear_object_label():self.stats['cleared']+=1
            self.current=None;self.current_since=None;self.last_tx=None
        if self.suppressed:return
        if self.pending:
            key,seen=self.pending
            if not 0<=now-seen<=self.max_age:self.pending=None;return
            if self.current and key!=self.current and now-self.current_since<self.min_dwell:return
            if key!=self.current or self.last_tx is None or now-self.last_tx>=self.refresh_seconds:
                if self.last_attempt is not None and now-self.last_attempt<.5:return
                self.last_attempt=now
                if self.transport.show_object_label(key[1],self.ttl_ms,self.step_ms):
                    if key!=self.current:self.current_since=now
                    self.current=key;self.last_seen=seen;self.last_tx=now;self.stats['shown']+=1

    def close(self):
        if self.current:self.transport.clear_object_label()
        self.current=None;self.pending=None
