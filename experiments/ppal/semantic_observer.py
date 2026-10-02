"""Bounded optional learned semantic metadata over the single generic tracker."""
import queue
import threading
import time
from dataclasses import replace


class SemanticObserver:
    def __init__(self,model,activation,*,fps=2.,max_age=.75,max_crops=16):
        if not 0<fps<=5 or not 0<max_age<=1 or not 1<=max_crops<=32:raise ValueError('bounded semantic observer required')
        self.model=model;self.activation=activation;self.period=1/fps;self.max_age=max_age;self.max_crops=max_crops
        self.queue=queue.Queue(maxsize=1);self.latest={};self.last_submit=-float('inf')
        self.dropped=0;self.errors=0;self.applied=0;self.copy_seconds=[];self.processing_seconds=[]
        self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start()

    def submit(self,frame,pairs,assignments,tracks,*,self_id,timestamp):
        if timestamp-self.last_submit<self.period:return
        self.last_submit=timestamp;begin=time.perf_counter();crops=[]
        for index,identifier in assignments.items():
            track=tracks.get(identifier)
            if identifier==self_id or not track or track.identity_uncertain:continue
            detection=pairs[index][0]
            # Refine only UNKNOWN metadata, never replace existing taught evidence.
            if detection.kind!='unknown':continue
            if len(crops)>=self.max_crops:break
            crops.append((identifier,frame.crop(detection.box),tuple(detection.center)))
        if not crops:return
        try:self.queue.get_nowait();self.dropped+=1
        except queue.Empty:pass
        try:self.queue.put_nowait((timestamp,crops))
        except queue.Full:self.dropped+=1
        self.copy_seconds.append(time.perf_counter()-begin)
        self.copy_seconds=self.copy_seconds[-256:]

    def _run(self):
        while True:
            job=self.queue.get()
            if job is None:return
            timestamp,crops=job;results={};begin=time.perf_counter()
            for identifier,image,center in crops:
                try:results[identifier]=dict(self.model.infer(image),timestamp=timestamp,center=center,
                                            activation=self.activation['activation_key'])
                except Exception:self.errors+=1
            self.latest=results
            self.processing_seconds.append(time.perf_counter()-begin)
            self.processing_seconds=self.processing_seconds[-256:]

    def apply(self,pairs,assignments,tracks,*,self_id,timestamp):
        results=self.latest;output=list(pairs);evidence=[]
        for index,identifier in assignments.items():
            value=results.get(identifier);track=tracks.get(identifier);d,original=pairs[index]
            if not value or identifier==self_id or not track or track.identity_uncertain or d.kind!='unknown':continue
            age=timestamp-value['timestamp']
            if age<0 or age>self.max_age or value.get('label') not in ('human','threat'):continue
            metadata=dict(original,learned_semantics=dict(value,track_id=identifier,age_seconds=age,
                          identity_status='unchanged; semantic prediction only'))
            output[index]=(replace(d,kind=value['label']),metadata)
            evidence.append(metadata['learned_semantics']);self.applied+=1
        return output,evidence

    def report(self):
        return dict(activation=self.activation['activation_key'],candidate_id=self.activation['candidate_id'],
            applied=self.applied,dropped=self.dropped,errors=self.errors,
            copy_seconds=self.copy_seconds,processing_seconds=self.processing_seconds,
            inference='bounded worker; no camera or second association pass',rollback='reload next episode')

    def close(self):
        try:self.queue.get_nowait()
        except queue.Empty:pass
        try:self.queue.put_nowait(None)
        except queue.Full:pass
        self.thread.join(timeout=.2)
